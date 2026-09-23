"""Stress-test analysis: cut the ramp into its steps and find the system's limit.

Owner: Yeo Kai Yuan (Part 5 measurement tooling). Feeds **Slide 9 — Load and
Stress Test Results** (the stress test and the limit it found).

What it reads
-------------
One stress run directory (``--run-dir``) produced by ``scripts/run_load_test.sh
--plan stress_ramp``:

* ``results.jtl`` -- the JMeter CSV. Latency, achieved arrival rate and error
  rate all come from here, because the load generator's view is the client's
  view: it includes every millisecond the service and Ollama made the caller
  wait. ``service.jsonl`` is the right evidence for *where* the time went (see
  ``bottleneck_hints.py``), not for *what the caller experienced*.
* ``metadata.json`` -- the model tag and the plan, for labelling the output.

Steps
-----
``stress_ramp.jmx`` is a stepped open-model ramp: the arrival rate is held
constant for ``ramp_step_duration_s`` seconds, then raised. JMeter's ``.jtl``
does not record which step a sample belongs to, so the boundaries have to be
supplied:

* ``--step-seconds`` (default 120, matching the plan's default) cuts the
  measured window into equal steps from the first measured sample onwards; or
* ``--step-boundaries`` takes explicit offsets in seconds from the first
  measured sample. ``K`` values define ``K - 1`` steps, so the final value is
  the end of the last step. Samples outside the first and last boundary are
  excluded and counted in the report; this is how a warm-up window is trimmed.

Samples are assigned to a step by their **start** time (JMeter's ``timeStamp``),
because it is the arrival that the schedule controls. A final step covered by
less than ``--min-step-fraction`` of its nominal duration is dropped: an
achieved rate and a p95 computed from a three-second sliver of a step are noise,
and would be reported as if they were a measurement.

The **offered** rate cannot be recovered from the ``.jtl`` either -- only the
achieved rate can. Supply it with ``--offered-rates`` (one value per step, taken
from the playbook) or with ``--ramp-start-per-min`` plus ``--ramp-step-per-min``
for the arithmetic ramp the plan generates. With neither, the offered column is
reported as ``n/a``, the offered-versus-achieved signal is not assessed, and the
report says so instead of quietly filling the gap.

The limit
---------
The limit is the **first** step at which either criterion is crossed:

* ``p95 > --p95-limit-ms`` (only assessed when the requirement is supplied; the
  comparison is strictly greater, so a p95 exactly at the limit still meets it);
* ``error rate > --error-rate-limit`` (default 0.01).

The report names which criterion tripped, and names both when they trip in the
same step.

Threshold-free saturation signals
---------------------------------
A limit expressed against our own requirement only tells us where *our*
requirement broke. Two further signals say whether the system itself was
saturating, and neither depends on a chosen threshold:

1. **p95 rises monotonically across the last N steps** (``--monotonic-steps``,
   default 3). Under an open-loop arrival process, a stable system's latency
   distribution settles at each rate; a queue that is growing without bound
   makes each step worse than the last. Reported with the factor by which p95
   rose across those steps, so a monotone but trivial rise is visible as such.
2. **The achieved rate stops tracking the offered rate.** In an open-loop test
   the generator does not wait for responses, so while the system keeps up, the
   achieved rate follows the offered rate. When it stops following -- the
   offered rate rises and the achieved rate does not -- requests are queueing or
   failing faster than they are being served. That divergence is the classic
   open-loop saturation signature, and it is visible before any latency
   requirement is breached. ``--tracking-tolerance`` (default 0.05) is an
   allowance for the jitter of a ``random_arrivals`` schedule, not a
   service-level threshold.

Either signal is enough to call the ramp a stress test that found something.

Exit codes
----------
* ``0`` -- a limit was found, or a saturation signal was present.
* ``1`` -- the evidence could not be read, or no limit was found within the ramp
  and no saturation signal was present, which means the stress test did not
  stress the system and must be re-run at higher rates. The tables and the chart
  are written first either way.

Development-time rule
---------------------
This script must not be run against real model output before the freeze. Its
tests run on fabricated JMeter files, and no example here contains a measured
value.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:  # so `python analysis/stress_summary.py` works
    sys.path.insert(0, str(_REPO_ROOT))

from analysis.common import (  # noqa: E402
    REPO_ROOT,
    AnalysisError,
    latency_percentiles,
    load_metadata,
    read_jtl,
    to_markdown_table,
    use_headless_matplotlib,
    write_table,
)

DEFAULT_OUT_DIR = REPO_ROOT / "analysis" / "output" / "stress"

#: The exact wording the run must fail with when the ramp proved nothing. Kept
#: as a constant so the message on stderr, in the report and in the test are one
#: string and cannot drift apart.
NO_STRESS_MESSAGE = (
    "No limit was found within the ramp and no saturation signal was present: "
    "the stress test did not stress the system and must be re-run at higher rates."
)

STEP_COLUMNS: tuple[str, ...] = (
    "step",
    "start_s",
    "end_s",
    "duration_s",
    "offered_per_min",
    "samples",
    "achieved_per_min",
    "tracking_ratio",
    "errors",
    "error_rate",
    "error_rate_pct",
    "p50_ms",
    "p95_ms",
    "p99_ms",
    "max_ms",
)


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def parse_float_list(raw: str, what: str) -> list[float]:
    """Parse a comma-separated list of numbers from the command line."""
    values: list[float] = []
    for piece in raw.replace(" ", "").split(","):
        if not piece:
            continue
        try:
            values.append(float(piece))
        except ValueError as exc:
            raise AnalysisError(f"{what}: {piece!r} is not a number ({exc}).") from exc
    if not values:
        raise AnalysisError(f"{what}: no values given.")
    return values


def build_step_windows(
    span_s: float,
    *,
    step_seconds: float | None,
    boundaries: list[float] | None,
) -> list[tuple[float, float]]:
    """The ``[start, end)`` offsets, in seconds, of each ramp step.

    ``span_s`` is the offset of the last measured sample. With explicit
    ``boundaries``, ``K`` values give ``K - 1`` windows and the caller's
    boundaries are honoured exactly (including a first boundary above zero,
    which trims a warm-up window). Otherwise equal windows of ``step_seconds``
    are laid down from zero until the data runs out.
    """
    if boundaries is not None:
        if len(boundaries) < 2:
            raise AnalysisError(
                "--step-boundaries needs at least two values: K values define "
                "K-1 steps, so the last value is the end of the last step."
            )
        ordered = sorted(boundaries)
        if ordered != boundaries:
            raise AnalysisError(
                f"--step-boundaries must be ascending; got {boundaries}."
            )
        return [(ordered[i], ordered[i + 1]) for i in range(len(ordered) - 1)]

    if step_seconds is None or step_seconds <= 0:
        raise AnalysisError("--step-seconds must be a positive number of seconds.")
    if span_s <= 0:
        raise AnalysisError(
            "All samples share one timestamp, so the ramp cannot be cut into "
            "steps. Is this really a stress run?"
        )
    n_steps = max(1, math.ceil(span_s / step_seconds))
    return [(index * step_seconds, (index + 1) * step_seconds) for index in range(n_steps)]


def resolve_offered_rates(
    n_steps: int,
    *,
    offered_rates: list[float] | None,
    ramp_start_per_min: float | None,
    ramp_step_per_min: float | None,
    warnings: list[str],
) -> list[float]:
    """One offered arrival rate (per minute) per step, or NaN where unknown.

    The offered rate is a property of the JMeter schedule, not of the results
    file, so it has to be told to us. Guessing it would put a number in the
    report that traces to nothing.
    """
    if offered_rates is not None:
        if ramp_start_per_min is not None or ramp_step_per_min is not None:
            warnings.append(
                "--offered-rates was given as well as --ramp-start-per-min/"
                "--ramp-step-per-min; the explicit --offered-rates list wins."
            )
        if len(offered_rates) < n_steps:
            raise AnalysisError(
                f"--offered-rates has {len(offered_rates)} value(s) but the data "
                f"covers {n_steps} step(s). Give one offered rate per step, from "
                f"docs/playbooks/stress-test.md."
            )
        if len(offered_rates) > n_steps:
            warnings.append(
                f"--offered-rates has {len(offered_rates)} value(s) but only "
                f"{n_steps} step(s) were measured; the extra value(s) are "
                f"ignored. Did the run stop before the ramp finished?"
            )
        return offered_rates[:n_steps]

    if ramp_start_per_min is not None and ramp_step_per_min is not None:
        return [ramp_start_per_min + index * ramp_step_per_min for index in range(n_steps)]
    if ramp_start_per_min is not None or ramp_step_per_min is not None:
        raise AnalysisError(
            "--ramp-start-per-min and --ramp-step-per-min must be given "
            "together (or use --offered-rates)."
        )
    warnings.append(
        "No offered rate was supplied (--offered-rates, or "
        "--ramp-start-per-min with --ramp-step-per-min), so the offered column "
        "is n/a and the offered-versus-achieved saturation signal cannot be "
        "assessed. The step boundaries and rates are in "
        "docs/playbooks/stress-test.md."
    )
    return [float("nan")] * n_steps


def build_step_table(
    samples: pd.DataFrame,
    windows: list[tuple[float, float]],
    offered: list[float],
    *,
    min_step_fraction: float,
    warnings: list[str],
) -> pd.DataFrame:
    """Per-step arrival rates, latency percentiles, error rate and sample count.

    ``achieved_per_min`` uses the step's **nominal** duration, not the span
    between its first and last sample: the schedule offered traffic for the
    whole window, so a window that happens to end a few seconds after its last
    arrival must not be credited with a higher rate than it ran at.
    """
    offsets = samples["offset_s"]
    records: list[dict[str, object]] = []
    dropped_partial = 0
    span_s = float(offsets.max())
    for index, ((start, end), offered_rate) in enumerate(zip(windows, offered), start=1):
        nominal = end - start
        covered = max(0.0, min(span_s, end) - start)
        if nominal > 0 and covered < min_step_fraction * nominal:
            dropped_partial += 1
            warnings.append(
                f"Step {index} ({start:.0f}-{end:.0f} s) is only covered to "
                f"{covered:.0f} s of its {nominal:.0f} s, which is below "
                f"--min-step-fraction={min_step_fraction}. It is dropped: a "
                f"percentile and an arrival rate from a fragment of a step are "
                f"not a measurement."
            )
            continue
        in_step = samples.loc[(offsets >= start) & (offsets < end)]
        n_samples = int(len(in_step))
        n_errors = int((~in_step["ok"]).sum()) if n_samples else 0
        stats = latency_percentiles(in_step["elapsed"]) if n_samples else {
            "p50": float("nan"), "p95": float("nan"), "p99": float("nan"),
            "max": float("nan"),
        }
        achieved = (n_samples / nominal * 60.0) if nominal > 0 else float("nan")
        error_rate = (n_errors / n_samples) if n_samples else float("nan")
        records.append(
            {
                "step": index,
                "start_s": start,
                "end_s": end,
                "duration_s": nominal,
                "offered_per_min": offered_rate,
                "samples": n_samples,
                "achieved_per_min": achieved,
                "tracking_ratio": (
                    achieved / offered_rate
                    if offered_rate and not math.isnan(offered_rate)
                    else float("nan")
                ),
                "errors": n_errors,
                "error_rate": error_rate,
                "error_rate_pct": error_rate * 100.0 if not math.isnan(error_rate) else float("nan"),
                "p50_ms": stats["p50"],
                "p95_ms": stats["p95"],
                "p99_ms": stats["p99"],
                "max_ms": stats["max"],
            }
        )
    table = pd.DataFrame(records, columns=list(STEP_COLUMNS))
    empty = table.loc[table["samples"] == 0, "step"].tolist()
    if empty:
        warnings.append(
            f"Step(s) {empty} contain no samples at all. Either the boundaries "
            f"do not match the schedule in docs/playbooks/stress-test.md, or the "
            f"generator stopped sending."
        )
    if dropped_partial:
        warnings.append(f"{dropped_partial} partial step(s) were dropped.")
    if table.empty:
        raise AnalysisError(
            "No usable steps: every window was empty or partial. Check "
            "--step-seconds / --step-boundaries against the run's schedule."
        )
    return table


def as_display_frame(table: pd.DataFrame, integer_columns: tuple[str, ...]) -> pd.DataFrame:
    """Return a copy whose whole-number columns stay whole numbers on the page.

    ``to_markdown_table`` formats every float with the float format, and pandas
    upcasts a row of an all-numeric frame to float64 -- so a step number and a
    sample count would both be rendered as "1.00". Casting the counting columns
    to ``object`` keeps them as integers in the Markdown table and in the CSV,
    where "60 samples" is what a reader expects to see.
    """
    display = table.copy()
    for column in integer_columns:
        if column in display.columns:
            display[column] = display[column].astype("int64").astype(object)
    return display


# ---------------------------------------------------------------------------
# Limit and saturation signals
# ---------------------------------------------------------------------------

def _ratio_or_na(value: float) -> str:
    """A ratio for prose, or ``n/a`` when it could not be computed."""
    return "n/a" if math.isnan(value) else f"{value:.3f}"


def _rate_or_na(value: float) -> str:
    """An arrival rate for prose, or ``n/a`` when it was never supplied."""
    return "n/a" if math.isnan(value) else f"{value:.0f}/min"


@dataclass(frozen=True)
class Limit:
    """The first step at which a criterion was crossed."""

    step: int
    offered_per_min: float
    achieved_per_min: float
    p95_ms: float
    error_rate: float
    criterion: str

    def describe(self) -> str:
        """One sentence naming the limit and what tripped it."""
        return (
            f"step {self.step} (offered {_rate_or_na(self.offered_per_min)}, achieved "
            f"{self.achieved_per_min:.1f}/min): {self.criterion}"
        )


def find_limit(
    table: pd.DataFrame, *, p95_limit_ms: float | None, error_rate_limit: float
) -> Limit | None:
    """The first step whose p95 or error rate crosses its limit.

    Both criteria are checked on every step, in step order, so the step reported
    is the earliest failure and the criterion names what actually failed there
    (both, when both fail in the same step).
    """
    for _, row in table.iterrows():
        tripped: list[str] = []
        p95 = float(row["p95_ms"])
        error_rate = float(row["error_rate"])
        if p95_limit_ms is not None and not math.isnan(p95) and p95 > p95_limit_ms:
            tripped.append(f"p95 {p95:.1f} ms > limit {p95_limit_ms:.1f} ms")
        if not math.isnan(error_rate) and error_rate > error_rate_limit:
            tripped.append(
                f"error rate {error_rate:.4f} > limit {error_rate_limit:.4f}"
            )
        if tripped:
            return Limit(
                step=int(row["step"]),
                offered_per_min=float(row["offered_per_min"]),
                achieved_per_min=float(row["achieved_per_min"]),
                p95_ms=p95,
                error_rate=error_rate,
                criterion=" and ".join(tripped),
            )
    return None


@dataclass
class SaturationSignals:
    """The two threshold-free growth signals. See the module docstring."""

    monotonic_steps: int
    p95_monotonic_rise: bool
    p95_rise_factor: float
    achieved_plateau: bool
    plateau_detail: str
    tracking_ratio_first: float
    tracking_ratio_last: float
    offered_known: bool

    @property
    def any_signal(self) -> bool:
        """True when either signal fired."""
        return bool(self.p95_monotonic_rise or self.achieved_plateau)

    def as_frame(self) -> pd.DataFrame:
        """One-row table for ``stress_signals.csv``."""
        return pd.DataFrame(
            [
                {
                    "monotonic_steps": self.monotonic_steps,
                    "p95_monotonic_rise": self.p95_monotonic_rise,
                    "p95_rise_factor": self.p95_rise_factor,
                    "achieved_plateau": self.achieved_plateau,
                    "plateau_detail": self.plateau_detail,
                    "tracking_ratio_first": self.tracking_ratio_first,
                    "tracking_ratio_last": self.tracking_ratio_last,
                    "offered_known": self.offered_known,
                    "saturation_signal": self.any_signal,
                }
            ]
        )


def detect_saturation(
    table: pd.DataFrame, *, monotonic_steps: int, tracking_tolerance: float
) -> SaturationSignals:
    """Assess the two saturation signals over the last ``monotonic_steps`` steps."""
    tail = table.tail(monotonic_steps)
    p95 = [float(v) for v in tail["p95_ms"]]
    usable_p95 = [v for v in p95 if not math.isnan(v)]
    monotonic = (
        len(tail) >= monotonic_steps
        and len(usable_p95) == len(p95)
        and len(p95) >= 2
        and all(later > earlier for earlier, later in zip(p95, p95[1:]))
    )
    rise_factor = (
        p95[-1] / p95[0] if len(p95) >= 2 and p95[0] and not math.isnan(p95[0]) else float("nan")
    )

    offered = [float(v) for v in tail["offered_per_min"]]
    achieved = [float(v) for v in tail["achieved_per_min"]]
    offered_known = not any(math.isnan(v) for v in offered)
    plateau = False
    detail = "not assessed: the offered rate was not supplied"
    if offered_known and len(tail) >= 2:
        reasons: list[str] = []
        for index in range(1, len(tail)):
            offered_rose = offered[index] > offered[index - 1]
            achieved_rose = achieved[index] > achieved[index - 1] * (1.0 + tracking_tolerance)
            if offered_rose and not achieved_rose:
                reasons.append(
                    f"offered {offered[index - 1]:.0f}->{offered[index]:.0f}/min but "
                    f"achieved {achieved[index - 1]:.1f}->{achieved[index]:.1f}/min"
                )
        plateau = bool(reasons)
        detail = "; ".join(reasons) if reasons else (
            "the achieved rate kept tracking the offered rate"
        )

    ratios = [float(v) for v in table["tracking_ratio"]]
    return SaturationSignals(
        monotonic_steps=monotonic_steps,
        p95_monotonic_rise=bool(monotonic),
        p95_rise_factor=rise_factor,
        achieved_plateau=plateau,
        plateau_detail=detail,
        tracking_ratio_first=ratios[0] if ratios else float("nan"),
        tracking_ratio_last=ratios[-1] if ratios else float("nan"),
        offered_known=offered_known,
    )


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------

def write_ramp_png(
    table: pd.DataFrame, limit: Limit | None, out_path: Path, title: str
) -> Path:
    """Plot p95 and the achieved rate against the offered rate.

    Line styles and markers differ as well as the greys, so the chart survives
    being printed in black and white. Where the offered rate is unknown the x
    axis falls back to the step number and says so, rather than plotting against
    an invented rate.
    """
    plt = use_headless_matplotlib()
    offered = [float(v) for v in table["offered_per_min"]]
    offered_known = not any(math.isnan(v) for v in offered)
    x_values = offered if offered_known else [float(v) for v in table["step"]]
    x_label = (
        "Offered arrival rate (requests/min)"
        if offered_known
        else "Ramp step (offered rate not supplied)"
    )

    fig, ax_latency = plt.subplots(figsize=(8.0, 4.8))
    ax_latency.plot(
        x_values, [float(v) for v in table["p95_ms"]],
        color="black", marker="o", linestyle="-", label="p95 latency (ms)",
    )
    ax_latency.set_xlabel(x_label)
    ax_latency.set_ylabel("p95 latency (ms)")
    ax_latency.grid(True, linestyle=":", linewidth=0.6, color="0.8")

    ax_rate = ax_latency.twinx()
    ax_rate.plot(
        x_values, [float(v) for v in table["achieved_per_min"]],
        color="0.35", marker="s", linestyle="--", label="achieved rate (/min)",
    )
    if offered_known:
        ax_rate.plot(
            x_values, offered,
            color="0.55", marker="^", linestyle=":", label="offered rate (/min)",
        )
    ax_rate.set_ylabel("Arrival rate (requests/min)")

    if limit is not None:
        x_limit = (
            limit.offered_per_min if offered_known and not math.isnan(limit.offered_per_min)
            else float(limit.step)
        )
        ax_latency.axvline(x_limit, color="black", linestyle="-.", linewidth=1.2)
        # Label on whichever side of the rule has room, so a limit found in the
        # last step does not have its label clipped off the figure.
        left, right = ax_latency.get_xlim()
        on_the_right = x_limit > (left + right) / 2
        ax_latency.annotate(
            f"limit: step {limit.step}",
            xy=(x_limit, ax_latency.get_ylim()[0]),
            xytext=(-6 if on_the_right else 6, 10),
            textcoords="offset points",
            ha="right" if on_the_right else "left",
            fontsize=8,
        )

    handles = ax_latency.get_legend_handles_labels()[0] + ax_rate.get_legend_handles_labels()[0]
    labels = ax_latency.get_legend_handles_labels()[1] + ax_rate.get_legend_handles_labels()[1]
    ax_latency.legend(handles, labels, loc="upper left", fontsize=8)
    ax_latency.set_title(title, fontsize=10)
    fig.tight_layout()
    # Date=None keeps the PNG byte-identical between runs on identical input.
    fig.savefig(out_path, dpi=150, metadata={"Date": None})
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

@dataclass
class StressReport:
    """Everything one stress run produced."""

    run_dir: Path
    model_tag: str
    plan: str
    mode: str
    table: pd.DataFrame
    limit: Limit | None
    signals: SaturationSignals
    p95_limit_ms: float | None
    error_rate_limit: float
    n_samples_used: int
    n_samples_excluded: int
    warnings: list[str] = field(default_factory=list)

    @property
    def stressed(self) -> bool:
        """True when the ramp found a limit or showed a saturation signal."""
        return self.limit is not None or self.signals.any_signal


def render_report(report: StressReport) -> str:
    """The human-readable ``stress_report.md``."""
    signals = report.signals
    lines = [
        f"# Stress test — {report.model_tag}",
        "",
        f"* Run directory: `{report.run_dir}`",
        f"* Plan: `{report.plan}`; run mode: `{report.mode}`",
        f"* Samples analysed: {report.n_samples_used} "
        f"(excluded by the step boundaries: {report.n_samples_excluded})",
        f"* p95 requirement supplied: "
        f"{'none' if report.p95_limit_ms is None else f'{report.p95_limit_ms:.1f} ms'}",
        f"* Error-rate limit: {report.error_rate_limit:.4f}",
        "",
    ]
    if report.mode == "dev":
        lines += [
            "> *** DEV MODE — synthetic tickets only. Results are NOT evidence. ***",
            "",
        ]
    lines += ["## The limit", ""]
    if report.limit is None:
        lines += [
            "No step crossed either criterion within this ramp.",
            "",
        ]
        if report.p95_limit_ms is None:
            lines += [
                "The latency criterion was not assessed, because no p95 "
                "requirement was supplied.",
                "",
                "TODO(Part 4 — Teammate X): pass the agreed p95 response-time "
                "requirement as --p95-limit-ms so the limit is measured against "
                "the requirement we published, not against a number chosen "
                "after the fact.",
                "",
            ]
    else:
        lines += [
            f"First step to cross a criterion: {report.limit.describe()}.",
            "",
            f"* Step: {report.limit.step}",
            f"* Offered rate: {_rate_or_na(report.limit.offered_per_min)}",
            f"* Achieved rate: {report.limit.achieved_per_min:.1f}/min",
            f"* p95 at that step: {report.limit.p95_ms:.1f} ms",
            f"* Error rate at that step: {report.limit.error_rate:.4f}",
            f"* Criterion that tripped: {report.limit.criterion}",
            "",
        ]
    lines += [
        "## Saturation signals (threshold-free)",
        "",
        f"* p95 rises monotonically across the last {signals.monotonic_steps} "
        f"steps: **{signals.p95_monotonic_rise}**"
        + (
            ""
            if math.isnan(signals.p95_rise_factor)
            else f" (p95 rose by a factor of {signals.p95_rise_factor:.2f} across them)"
        ),
        f"* Achieved rate stopped tracking the offered rate: "
        f"**{signals.achieved_plateau}** — {signals.plateau_detail}",
        f"* Achieved/offered ratio: first step "
        f"{_ratio_or_na(signals.tracking_ratio_first)}, "
        f"last step {_ratio_or_na(signals.tracking_ratio_last)}",
        "",
        "A rising p95 across consecutive steps, or an achieved rate that no "
        "longer follows the offered rate, is evidence of an unbounded queue. In "
        "an open-loop test the generator does not slow down when the server "
        "does, so the divergence is the system's own saturation showing through.",
        "",
        "## Per-step table",
        "",
        to_markdown_table(report.table, float_format="{:.2f}"),
        "`achieved_per_min` uses each step's nominal duration. `error_rate` is "
        "the fraction compared against --error-rate-limit; `error_rate_pct` is "
        "the same number as a percentage, for the slide.",
        "",
        "See `stress_ramp.png` for p95 and the achieved rate against the "
        "offered rate.",
        "",
    ]
    if report.warnings:
        lines += ["## Warnings raised by this run", ""]
        lines += [f"* {warning}" for warning in report.warnings]
        lines += [""]
    if not report.stressed:
        lines += ["## Check that failed", "", NO_STRESS_MESSAGE, ""]
    lines += [
        "## Interpretation still owed",
        "",
        "TODO(Part 5 — Teammate X): state the limit this run found in one "
        "sentence for Slide 9, and say which component the limit is attributed "
        "to. Use `analysis/bottleneck_hints.py` on the same run directory for "
        "the request-time breakdown that supports the attribution.",
        "",
        "TODO(Part 5 — Teammate X): if no limit was found, say whether the ramp "
        "is to be re-run at higher rates or the requirement is to be defended "
        "as met across the whole ramp.",
        "",
        'TODO(Yeo Kai Yuan): replace "Teammate X" above with the teammate who '
        "owns the Slide 9 write-up.",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyse(args: argparse.Namespace) -> StressReport:
    """Read the run, cut it into steps, find the limit and write every output."""
    run_dir: Path = args.run_dir
    if not run_dir.is_dir():
        raise AnalysisError(f"No such run directory: {run_dir}")
    metadata = load_metadata(run_dir)
    warnings: list[str] = []
    plan = str(metadata.get("plan") or "unknown")
    if plan != "stress_ramp":
        warnings.append(
            f"metadata.json says plan={plan!r}, not 'stress_ramp'. Analysing it "
            f"anyway, but the step boundaries only mean something for a stepped "
            f"ramp."
        )

    samples = read_jtl(run_dir / "results.jtl")
    if args.label:
        selected = samples.loc[samples["label"].astype(str) == args.label]
        if selected.empty:
            raise AnalysisError(
                f"No samples with label {args.label!r} in {run_dir / 'results.jtl'}. "
                f"Labels present: {sorted(set(samples['label'].astype(str)))}."
            )
        samples = selected.copy()
    labels = sorted(set(samples["label"].astype(str)))
    if len(labels) > 1:
        warnings.append(
            f"The .jtl mixes {len(labels)} sampler labels ({labels}); their "
            f"latencies are pooled. Use --label to analyse one sampler, because "
            f"a p95 over two different endpoints describes neither."
        )

    samples = samples.sort_values("ts", kind="stable").copy()
    start = samples["ts"].min()
    samples["offset_s"] = (samples["ts"] - start).dt.total_seconds()
    span_s = float(samples["offset_s"].max())

    boundaries = (
        parse_float_list(args.step_boundaries, "--step-boundaries")
        if args.step_boundaries
        else None
    )
    windows = build_step_windows(
        span_s, step_seconds=args.step_seconds, boundaries=boundaries
    )
    offered = resolve_offered_rates(
        len(windows),
        offered_rates=(
            parse_float_list(args.offered_rates, "--offered-rates")
            if args.offered_rates
            else None
        ),
        ramp_start_per_min=args.ramp_start_per_min,
        ramp_step_per_min=args.ramp_step_per_min,
        warnings=warnings,
    )

    window_start, window_end = windows[0][0], windows[-1][1]
    inside = samples.loc[
        (samples["offset_s"] >= window_start) & (samples["offset_s"] < window_end)
    ]
    n_excluded = int(len(samples) - len(inside))
    if n_excluded:
        warnings.append(
            f"{n_excluded} sample(s) fall outside the step boundaries "
            f"[{window_start:.0f}, {window_end:.0f}) s and are excluded."
        )

    table = build_step_table(
        samples,
        windows,
        offered,
        min_step_fraction=args.min_step_fraction,
        warnings=warnings,
    )
    if len(table) < args.monotonic_steps:
        warnings.append(
            f"Only {len(table)} usable step(s), fewer than "
            f"--monotonic-steps={args.monotonic_steps}, so the p95 monotonicity "
            f"signal cannot be assessed. A ramp needs at least that many steps "
            f"before a trend means anything."
        )
    limit = find_limit(
        table, p95_limit_ms=args.p95_limit_ms, error_rate_limit=args.error_rate_limit
    )
    signals = detect_saturation(
        table,
        monotonic_steps=args.monotonic_steps,
        tracking_tolerance=args.tracking_tolerance,
    )

    # The counting columns are rendered as integers from here on; every
    # derivation above has already been made from the numeric table.
    display_table = as_display_frame(table, ("step", "samples", "errors"))

    report = StressReport(
        run_dir=run_dir,
        model_tag=str(metadata.get("model_tag") or "unknown"),
        plan=plan,
        mode=str(metadata.get("mode") or "unknown"),
        table=display_table,
        limit=limit,
        signals=signals,
        p95_limit_ms=args.p95_limit_ms,
        error_rate_limit=args.error_rate_limit,
        n_samples_used=int(table["samples"].sum()),
        n_samples_excluded=n_excluded,
        warnings=warnings,
    )

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    write_table(display_table, out_dir, "stress_steps", float_format="{:.2f}")
    write_table(signals.as_frame(), out_dir, "stress_signals", float_format="{:.3f}")
    if not args.no_charts:
        write_ramp_png(
            display_table,
            limit,
            out_dir / "stress_ramp.png",
            f"Stress ramp — {report.model_tag}\n{run_dir.name}",
        )
    (out_dir / "stress_report.md").write_text(render_report(report), encoding="utf-8")
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line. See the module docstring for the semantics."""
    parser = argparse.ArgumentParser(
        prog="analysis/stress_summary.py",
        description=(
            "Cut a stepped open-loop stress ramp into its steps, report per-step "
            "arrival rates, latency percentiles and error rate, and identify the "
            "first step at which the system breaches a limit or shows an "
            "unbounded-growth signal."
        ),
        epilog=(
            "Exit codes: 0 a limit was found or a saturation signal was present; "
            "1 the evidence could not be read, or the ramp neither found a limit "
            "nor saturated (the stress test did not stress the system and must "
            "be re-run at higher rates). Tables and the chart are written first "
            "either way."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="one stress run directory under results/runs/ (must contain "
        "results.jtl and metadata.json)",
    )
    parser.add_argument(
        "--p95-limit-ms",
        type=float,
        default=None,
        help="the p95 response-time requirement, in milliseconds. Omit and only "
        "the error-rate criterion is assessed",
    )
    parser.add_argument(
        "--error-rate-limit",
        type=float,
        default=0.01,
        help="error-rate criterion as a fraction of samples (default: %(default)s)",
    )
    parser.add_argument(
        "--step-seconds",
        type=float,
        default=120.0,
        help="nominal duration of each ramp step, in seconds; matches the plan's "
        "ramp_step_duration_s (default: %(default)s)",
    )
    parser.add_argument(
        "--step-boundaries",
        default=None,
        help="explicit step boundaries as comma-separated offsets in seconds "
        "from the first measured sample; K values define K-1 steps. Overrides "
        "--step-seconds",
    )
    parser.add_argument(
        "--offered-rates",
        default=None,
        help="comma-separated offered arrival rate per step, in requests per "
        "minute, taken from docs/playbooks/stress-test.md",
    )
    parser.add_argument(
        "--ramp-start-per-min",
        type=float,
        default=None,
        help="offered rate of the first step, for an arithmetic ramp (use with "
        "--ramp-step-per-min instead of --offered-rates)",
    )
    parser.add_argument(
        "--ramp-step-per-min",
        type=float,
        default=None,
        help="increment in offered rate per step, for an arithmetic ramp",
    )
    parser.add_argument(
        "--monotonic-steps",
        type=int,
        default=3,
        help="how many trailing steps the p95 monotonicity signal looks at "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--tracking-tolerance",
        type=float,
        default=0.05,
        help="relative allowance for arrival jitter when deciding whether the "
        "achieved rate still follows the offered rate; not a service-level "
        "threshold (default: %(default)s)",
    )
    parser.add_argument(
        "--min-step-fraction",
        type=float,
        default=0.5,
        help="a step covered by less than this fraction of its nominal duration "
        "is dropped as a fragment (default: %(default)s)",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="analyse only samples with this JMeter sampler label",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="where tables, the chart and the report are written "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--no-charts",
        action="store_true",
        help="write tables only; skip the PNG",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the stress analysis; return the process exit code."""
    args = parse_args(argv)
    try:
        report = analyse(args)
    except AnalysisError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    for warning in report.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    if report.mode == "dev":
        print(
            "*** DEV MODE — synthetic tickets only. Results are NOT evidence. ***",
            file=sys.stderr,
        )
    print(f"Steps analysed: {len(report.table)}; samples: {report.n_samples_used}")
    if report.limit is None:
        print("Limit: none found within this ramp")
    else:
        print(f"Limit: {report.limit.describe()}")
    print(
        f"Saturation signals: p95 monotonic rise="
        f"{report.signals.p95_monotonic_rise}, achieved-rate plateau="
        f"{report.signals.achieved_plateau}"
    )
    print(f"Wrote {args.out_dir / 'stress_steps.csv'}")

    if not report.stressed:
        print("", file=sys.stderr)
        print(f"ERROR: {NO_STRESS_MESSAGE}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
