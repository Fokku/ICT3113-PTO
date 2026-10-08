"""Where a request's time went: a breakdown from the service log's Ollama timings.

Owner: Yeo Kai Yuan (Part 5 measurement tooling). Feeds **Slide 9 — Load and
Stress Test Results** (the "short interpretation, including the diagnosed
bottleneck" line) and the prediction post-mortem on Slide 11.

What it reads
-------------
One run directory (``--run-dir``) and nothing but its ``service.jsonl`` and
``metadata.json``. This script deliberately does not look at the ``.jtl``: the
question here is not "what did the caller experience" (that is
``summarise_load.py`` and ``stress_summary.py``) but "inside one request, which
stage consumed the time", and only the service log carries the timings that can
answer it.

Only measured ``POST /tickets`` lines are used. ``/search`` and ``/stats`` lines
have no model timings by design and are counted separately, not reported as
Ollama failures.

The breakdown
-------------
Two clocks are involved and the arithmetic has to respect both. The service
measures ``total_latency_ms`` around its whole handler and ``model_latency_ms``
around the Ollama HTTP call. Ollama reports, in nanoseconds, its own
``total_duration`` and the components ``load_duration``,
``prompt_eval_duration`` and ``eval_duration``. From those:

===========================  ============================================================
component                    definition
===========================  ============================================================
``service_overhead_ms``      ``total_latency_ms - model_latency_ms``: request parsing,
                             prompt construction, category normalisation, the SQLite
                             insert and the log write.
``queue_residual_ms``        ``model_latency_ms - total_duration/1e6``: the part of our
                             own HTTP call that Ollama does not account for. **A
                             RESIDUAL, not a measured quantity** (see below).
``load_ms``                  ``load_duration/1e6``: Ollama loading the model. Large on
                             the first request after a model switch, which is exactly
                             why the warm-up request exists and is excluded.
``prompt_eval_ms``           ``prompt_eval_duration/1e6``: evaluating the prompt tokens
                             (the "prefill"). Scales with the ticket length.
``eval_ms``                  ``eval_duration/1e6``: generating the reply tokens. On CPU
                             this is usually the largest term.
``ollama_other_ms``          ``total_duration/1e6`` minus the three components above.
                             Ollama's own total is not exactly their sum; the remainder
                             is reported rather than silently distributed.
===========================  ============================================================

By construction these six sum to ``total_latency_ms`` for every request, so the
stacked chart is a genuine decomposition of the mean request.

What the queue residual is and is not
-------------------------------------
``queue_residual_ms`` is **derived by subtraction**, not measured. It is the time
our HTTP call spent that Ollama's own instrumentation does not explain, and
Ollama-side queueing is the thing we expect to find there: the service imposes no
concurrency limit, so under load the in-flight model calls are bounded only by
``OLLAMA_NUM_PARALLEL`` and Ollama's internal queue, and a request waiting in that
queue is not yet being evaluated and so is not yet in ``total_duration``.

It is not *only* queueing. Anything else between our ``perf_counter`` calls and
Ollama's own accounting inflates it: HTTP request and response serialisation,
container networking and the Docker bridge, JSON encoding of the prompt and
decoding of the reply, TCP connection setup (we create a fresh ``AsyncClient``
per request on purpose, so every request pays a new connection), and any time the
service's own event loop or thread pool made the coroutine wait. A large residual
is therefore a *hint* to investigate Ollama queueing, not proof of it. The
honest next step is to correlate it with concurrency, which is what the load and
stress runs give us.

Tokens per second, and num_ctx truncation
-----------------------------------------
``prompt_eval_count / prompt_eval_duration`` and ``eval_count / eval_duration``
give prompt-evaluation and generation throughput in tokens per second. Both are
reported per request (distribution) and in aggregate (total tokens over total
time), because the aggregate is what a capacity estimate needs and the
distribution is what shows whether it is stable.

``prompt_eval_count`` also lets us check for silent truncation. Ollama truncates
the prompt to ``num_ctx`` without telling the caller, so a prompt-token count
sitting at (or just under) the configured ``num_ctx`` is the signature of a
ticket that was cut off before the model ever saw the end of it. Any request
whose ``prompt_eval_count`` reaches ``--ctx-warn-fraction`` of its logged
``num_ctx`` is flagged in ``ctx_truncation_suspects.csv``. This is the reason
``NUM_CTX`` is set explicitly and logged on every request.

A note on percentiles
---------------------
Only the **mean** decomposes additively: the component means sum to the mean
total latency, which is why the stacked chart plots means. Percentiles of the
components do not sum to the percentile of the total (the slowest request for one
component need not be the slowest overall), so the percentile columns are there
to show each component's own spread and must not be added up.

Outputs (under ``--out-dir``)
----------------------------
``bottleneck_breakdown.csv`` / ``.md`` (one row per component, with mean and
percentiles and its share of the mean total), ``bottleneck_per_request.csv``
(the derived values for every usable request, so any figure can be traced back
to a log line), ``bottleneck_tokens.csv`` / ``.md``,
``ctx_truncation_suspects.csv``, ``bottleneck_stacked.png`` and
``bottleneck_report.md``, which names the largest component.

Exit codes
----------
* ``0`` -- a breakdown was produced.
* ``1`` -- the evidence could not be read, or no request in the run had a
  complete set of Ollama timings, so there is nothing to break down.

Development-time rule
---------------------
This script must not be run against real model output before the freeze. Its
tests run on fabricated log lines, and no example here contains a measured value.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:  # so `python analysis/bottleneck_hints.py` works
    sys.path.insert(0, str(_REPO_ROOT))

from analysis.common import (  # noqa: E402
    REPO_ROOT,
    AnalysisError,
    exclude_warmup,
    load_metadata,
    percentile,
    read_service_log,
    to_markdown_table,
    use_headless_matplotlib,
    write_table,
)

DEFAULT_OUT_DIR = REPO_ROOT / "analysis" / "output" / "bottleneck"

#: Nanoseconds per millisecond: Ollama reports ns, we report ms.
NS_PER_MS = 1_000_000.0
#: Nanoseconds per second, for the tokens-per-second arithmetic.
NS_PER_S = 1_000_000_000.0

#: The six components of ``total_latency_ms``, in the order a request passes
#: through them. The chart stacks them in this order.
COMPONENTS: tuple[str, ...] = (
    "service_overhead_ms",
    "queue_residual_ms",
    "load_ms",
    "prompt_eval_ms",
    "eval_ms",
    "ollama_other_ms",
)

#: What each component is, for the report. Kept next to the code that computes
#: them so the two cannot drift apart.
COMPONENT_NOTES: dict[str, str] = {
    "service_overhead_ms": (
        "our own handler outside the model call: request parsing, prompt "
        "construction, category normalisation, the SQLite insert, the log write"
    ),
    "queue_residual_ms": (
        "RESIDUAL: our HTTP call minus Ollama's own total_duration. Where "
        "Ollama-side queueing shows up, but also HTTP and container-network "
        "overhead and per-request connection setup"
    ),
    "load_ms": "Ollama loading the model (load_duration)",
    "prompt_eval_ms": "evaluating the prompt tokens, the prefill (prompt_eval_duration)",
    "eval_ms": "generating the reply tokens (eval_duration)",
    "ollama_other_ms": (
        "RESIDUAL: Ollama's total_duration minus load + prompt eval + generation"
    ),
}

#: What the largest component means, so the generated verdict says something
#: useful about the mechanism. The judgement about what to DO stays with the
#: teammate who writes the slide.
COMPONENT_VERDICTS: dict[str, str] = {
    "service_overhead_ms": (
        "the time is in our own service, not in the model. Look at the "
        "per-request SQLite connection, the full-table LIKE scan if /search is "
        "in the mix, and the open-write-close log call on every request."
    ),
    "queue_residual_ms": (
        "the time is in neither our handler nor Ollama's own accounting, which "
        "is where Ollama-side queueing appears. Correlate it with concurrency "
        "before concluding queueing: HTTP and container networking and the "
        "per-request connection also live in this term."
    ),
    "load_ms": (
        "model loading dominates, which should not happen in a measured window. "
        "Check that the warm-up request ran, that it is excluded, and that "
        "Ollama is not evicting the model between requests "
        "(OLLAMA_MAX_LOADED_MODELS, keep_alive)."
    ),
    "prompt_eval_ms": (
        "prefill dominates: the cost is in reading the ticket, so it scales with "
        "ticket length and prompt size rather than with the length of the reply."
    ),
    "eval_ms": (
        "token generation dominates, which is the expected shape for CPU-only "
        "inference: the cost is the model's per-token compute, so it scales with "
        "the number of tokens the model chooses to emit and with model size."
    ),
    "ollama_other_ms": (
        "most of Ollama's own total_duration is in none of its three reported "
        "components. Check the Ollama version's accounting before drawing a "
        "conclusion from it."
    ),
}

#: Columns of the per-request evidence file.
PER_REQUEST_COLUMNS: tuple[str, ...] = (
    "ts",
    "request_id",
    "source_row",
    "total_latency_ms",
    "model_latency_ms",
    "ollama_total_ms",
    *COMPONENTS,
    "prompt_eval_count",
    "eval_count",
    "prompt_eval_tps",
    "eval_tps",
    "num_ctx",
    "ctx_ratio",
    "ctx_truncation_suspect",
)


# ---------------------------------------------------------------------------
# Derivation
# ---------------------------------------------------------------------------

#: Every field that must be present for a request to be decomposable.
REQUIRED_TIMING_FIELDS: tuple[str, ...] = (
    "total_latency_ms",
    "model_latency_ms",
    "total_duration",
    "load_duration",
    "prompt_eval_duration",
    "eval_duration",
)


@dataclass
class Derived:
    """The per-request breakdown plus the counts of what had to be dropped."""

    frame: pd.DataFrame
    n_ticket_lines: int
    n_other_endpoints: int
    n_missing_timings: int
    missing_reasons: pd.DataFrame
    warnings: list[str] = field(default_factory=list)


def derive_components(run_dir: Path, *, ctx_warn_fraction: float) -> Derived:
    """Read one run's service log and derive the per-request time breakdown.

    Requests where Ollama returned no timings -- the error path, where the
    service returns 502 and stores nothing -- cannot be decomposed and are
    excluded. They are counted, and their error slugs are reported, because a run
    whose timings are missing from a third of its requests is not a run whose
    breakdown should be quoted.
    """
    warnings: list[str] = []
    frame = exclude_warmup(read_service_log(run_dir / "service.jsonl"))
    n_all = int(len(frame))
    tickets = frame.loc[
        (frame["endpoint"] == "/tickets") & (frame["method"] == "POST")
    ].copy()
    n_ticket_lines = int(len(tickets))
    n_other_endpoints = n_all - n_ticket_lines
    if n_ticket_lines == 0:
        raise AnalysisError(
            f"{run_dir / 'service.jsonl'} holds no measured POST /tickets lines, "
            f"so there is no model call to break down."
        )

    for column in REQUIRED_TIMING_FIELDS + ("prompt_eval_count", "eval_count", "num_ctx"):
        tickets[column] = pd.to_numeric(tickets[column], errors="coerce")

    complete = tickets[list(REQUIRED_TIMING_FIELDS)].notna().all(axis=1)
    incomplete = tickets.loc[~complete]
    n_missing = int(len(incomplete))
    missing_reasons = (
        incomplete.assign(error=incomplete["error"].fillna("no error slug logged"))
        .groupby(["status", "error"], dropna=False)
        .size()
        .reset_index(name="requests")
        if n_missing
        else pd.DataFrame(columns=["status", "error", "requests"])
    )
    if n_missing:
        warnings.append(
            f"{n_missing} of {n_ticket_lines} POST /tickets request(s) returned no "
            f"Ollama timings and are excluded from the breakdown. That is the "
            f"error path (the service returns 502 and stores nothing), so their "
            f"time cannot be attributed to a stage."
        )
    usable = tickets.loc[complete].copy()
    if usable.empty:
        raise AnalysisError(
            f"No request in {run_dir / 'service.jsonl'} has a complete set of "
            f"Ollama timings ({n_missing} request(s) had none), so no breakdown "
            f"can be produced. Did every model call fail?"
        )

    usable["ollama_total_ms"] = usable["total_duration"] / NS_PER_MS
    usable["service_overhead_ms"] = usable["total_latency_ms"] - usable["model_latency_ms"]
    usable["queue_residual_ms"] = usable["model_latency_ms"] - usable["ollama_total_ms"]
    usable["load_ms"] = usable["load_duration"] / NS_PER_MS
    usable["prompt_eval_ms"] = usable["prompt_eval_duration"] / NS_PER_MS
    usable["eval_ms"] = usable["eval_duration"] / NS_PER_MS
    usable["ollama_other_ms"] = usable["ollama_total_ms"] - (
        usable["load_ms"] + usable["prompt_eval_ms"] + usable["eval_ms"]
    )

    # Tokens per second. A zero duration would be a division by zero rather than
    # an infinitely fast model, so it becomes NaN and is excluded from the stats.
    usable["prompt_eval_tps"] = usable["prompt_eval_count"] / (
        usable["prompt_eval_duration"].where(usable["prompt_eval_duration"] > 0) / NS_PER_S
    )
    usable["eval_tps"] = usable["eval_count"] / (
        usable["eval_duration"].where(usable["eval_duration"] > 0) / NS_PER_S
    )

    usable["ctx_ratio"] = usable["prompt_eval_count"] / usable["num_ctx"].where(
        usable["num_ctx"] > 0
    )
    usable["ctx_truncation_suspect"] = usable["ctx_ratio"] >= ctx_warn_fraction

    for component in ("service_overhead_ms", "queue_residual_ms", "ollama_other_ms"):
        negative = usable.loc[usable[component] < 0, component]
        if not negative.empty:
            warnings.append(
                f"{len(negative)} request(s) have a negative {component} "
                f"(minimum {float(negative.min()):.1f} ms). A residual computed "
                f"by subtracting two clocks can go slightly negative through "
                f"rounding; a large negative value means the two clocks "
                f"disagree and the breakdown should not be quoted. The values "
                f"are reported as measured and only the chart clamps them at "
                f"zero, so the distortion stays visible."
            )
    n_suspects = int(usable["ctx_truncation_suspect"].sum())
    if n_suspects:
        warnings.append(
            f"{n_suspects} request(s) have prompt_eval_count at or above "
            f"{ctx_warn_fraction:.2f} of the logged num_ctx, which is the "
            f"signature of Ollama silently truncating the prompt. See "
            f"ctx_truncation_suspects.csv; those classifications were made "
            f"without the end of the ticket."
        )

    return Derived(
        frame=usable,
        n_ticket_lines=n_ticket_lines,
        n_other_endpoints=n_other_endpoints,
        n_missing_timings=n_missing,
        missing_reasons=missing_reasons,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

def build_breakdown(frame: pd.DataFrame) -> pd.DataFrame:
    """Mean, percentiles and share of the mean total, one row per component.

    ``share_of_mean_total_pct`` is computed against the mean ``total_latency_ms``
    and the shares therefore add to 100 per cent. The percentile columns do not
    add up and must not be added up -- see the module docstring.
    """
    mean_total = float(frame["total_latency_ms"].mean())
    records: list[dict[str, object]] = []
    for component in COMPONENTS:
        values = frame[component].astype(float)
        mean = float(values.mean())
        records.append(
            {
                "component": component,
                "note": COMPONENT_NOTES[component],
                "mean_ms": mean,
                "share_of_mean_total_pct": (
                    mean / mean_total * 100.0 if mean_total else float("nan")
                ),
                "p50_ms": percentile(values, 0.50),
                "p95_ms": percentile(values, 0.95),
                "p99_ms": percentile(values, 0.99),
                "min_ms": float(values.min()),
                "max_ms": float(values.max()),
            }
        )
    records.append(
        {
            "component": "total_latency_ms",
            "note": "the whole request handler, as measured by the service",
            "mean_ms": mean_total,
            "share_of_mean_total_pct": 100.0 if mean_total else float("nan"),
            "p50_ms": percentile(frame["total_latency_ms"], 0.50),
            "p95_ms": percentile(frame["total_latency_ms"], 0.95),
            "p99_ms": percentile(frame["total_latency_ms"], 0.99),
            "min_ms": float(frame["total_latency_ms"].min()),
            "max_ms": float(frame["total_latency_ms"].max()),
        }
    )
    return pd.DataFrame(
        records,
        columns=[
            "component",
            "note",
            "mean_ms",
            "share_of_mean_total_pct",
            "p50_ms",
            "p95_ms",
            "p99_ms",
            "min_ms",
            "max_ms",
        ],
    )


def build_token_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Prompt-evaluation and generation throughput, per request and in aggregate.

    The aggregate row divides total tokens by total time, which is the figure a
    capacity estimate needs; the per-request mean and percentiles show whether
    that aggregate is stable or an average of two different behaviours.
    """
    records: list[dict[str, object]] = []
    for name, count_field, duration_field, rate_field in (
        ("prompt evaluation", "prompt_eval_count", "prompt_eval_duration", "prompt_eval_tps"),
        ("generation", "eval_count", "eval_duration", "eval_tps"),
    ):
        rates = frame[rate_field].astype(float)
        # Token counts are integers; carrying them as floats would print a
        # token total with a decimal point in the report.
        total_tokens = int(frame[count_field].sum())
        total_seconds = float(frame[duration_field].sum()) / NS_PER_S
        records.append(
            {
                "stage": name,
                "requests": int(rates.notna().sum()),
                "total_tokens": total_tokens,
                "total_seconds": total_seconds,
                "aggregate_tokens_per_s": (
                    total_tokens / total_seconds if total_seconds else float("nan")
                ),  # total tokens over total time: the figure a capacity estimate needs
                "mean_tokens_per_s": float(rates.mean()),
                "p50_tokens_per_s": percentile(rates, 0.50),
                "p95_tokens_per_s": percentile(rates, 0.95),
                "mean_tokens_per_request": float(frame[count_field].astype(float).mean()),
            }
        )
    return pd.DataFrame(
        records,
        columns=[
            "stage",
            "requests",
            "total_tokens",
            "total_seconds",
            "aggregate_tokens_per_s",
            "mean_tokens_per_s",
            "p50_tokens_per_s",
            "p95_tokens_per_s",
            "mean_tokens_per_request",
        ],
    )


def build_ctx_suspects(frame: pd.DataFrame) -> pd.DataFrame:
    """The requests whose prompt-token count sits at the ``num_ctx`` limit."""
    columns = [
        "ts",
        "request_id",
        "source_row",
        "prompt_eval_count",
        "num_ctx",
        "ctx_ratio",
        "ticket_chars",
    ]
    suspects = frame.loc[frame["ctx_truncation_suspect"]]
    if suspects.empty:
        return pd.DataFrame(columns=columns)
    built = suspects[["request_id", "source_row", "prompt_eval_count", "num_ctx",
                      "ctx_ratio", "ticket_chars"]].copy()
    built.insert(0, "ts", [_format_ts(v) for v in suspects["ts"]])
    return built[columns].reset_index(drop=True)


def build_per_request(frame: pd.DataFrame) -> pd.DataFrame:
    """The derived values for every usable request, for the evidence trail."""
    built = frame.copy()
    built["ts"] = [_format_ts(v) for v in frame["ts"]]
    return built[list(PER_REQUEST_COLUMNS)].reset_index(drop=True)


def _format_ts(value: object) -> str:
    """Render a parsed log timestamp back in the service's format (ISO ms, Z)."""
    if value is None or value is pd.NA:
        return ""
    moment = pd.Timestamp(value)
    if pd.isna(moment):
        return ""
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------

def write_stacked_png(
    breakdown: pd.DataFrame, out_path: Path, title: str
) -> Path:
    """One stacked bar: the mean request, decomposed into its six components.

    Hatching as well as greys, because the deck may be printed in black and
    white and six shades of grey are not six distinguishable shades of grey.
    Negative residuals are clamped at zero here (and only here) so the stack
    remains a stack; the table reports them as measured.
    """
    plt = use_headless_matplotlib()
    rows = breakdown.loc[breakdown["component"].isin(COMPONENTS)]
    means = {str(row["component"]): float(row["mean_ms"]) for _, row in rows.iterrows()}
    greys = ["0.15", "0.35", "0.50", "0.65", "0.80", "0.92"]
    hatches = ["", "//", "xx", "..", "\\\\", "++"]

    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    bottom = 0.0
    clamped: list[str] = []
    for component, grey, hatch in zip(COMPONENTS, greys, hatches):
        value = means.get(component, float("nan"))
        if math.isnan(value):
            continue
        if value < 0:
            clamped.append(component)
            value = 0.0
        ax.bar(
            [0], [value], bottom=[bottom], width=0.5,
            color=grey, edgecolor="black", hatch=hatch,
            label=f"{component} ({value:.1f} ms)",
        )
        bottom += value
    ax.set_xticks([0], labels=["mean request"])
    # One bar on its own would otherwise be stretched across the whole axis.
    ax.set_xlim(-0.75, 0.75)
    ax.set_ylabel("Time (ms)")
    # Two lines at a smaller size: a run directory name is long enough to be
    # clipped off the figure when it shares one line with the model tag.
    ax.set_title(title, fontsize=10)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), fontsize=8, frameon=False)
    if clamped:
        ax.annotate(
            "clamped at zero for the chart: " + ", ".join(clamped),
            xy=(0.02, 0.98), xycoords="axes fraction", va="top", fontsize=7,
        )
    fig.tight_layout()
    # Date=None keeps the PNG byte-identical between runs on identical input.
    fig.savefig(out_path, dpi=150, metadata={"Date": None})
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

@dataclass
class BottleneckReport:
    """Everything one run's breakdown produced."""

    run_dir: Path
    model_tag: str
    mode: str
    num_ctx_values: list[int]
    derived: Derived
    breakdown: pd.DataFrame
    tokens: pd.DataFrame
    suspects: pd.DataFrame
    largest_component: str
    largest_mean_ms: float
    largest_share_pct: float


def largest_component(breakdown: pd.DataFrame) -> tuple[str, float, float]:
    """The component with the largest mean, with its mean and its share."""
    rows = breakdown.loc[breakdown["component"].isin(COMPONENTS)].copy()
    rows = rows.sort_values(["mean_ms", "component"], ascending=[False, True], kind="stable")
    top = rows.iloc[0]
    return str(top["component"]), float(top["mean_ms"]), float(top["share_of_mean_total_pct"])


def render_report(report: BottleneckReport) -> str:
    """The human-readable ``bottleneck_report.md``, including the verdict."""
    derived = report.derived
    lines = [
        f"# Request time breakdown — {report.model_tag}",
        "",
        f"* Run directory: `{report.run_dir}`",
        f"* Run mode: `{report.mode}`",
        f"* Measured POST /tickets requests: {derived.n_ticket_lines}",
        f"* Requests excluded because Ollama returned no timings: "
        f"{derived.n_missing_timings}",
        f"* Non-/tickets log lines skipped (no model call to break down): "
        f"{derived.n_other_endpoints}",
        f"* Requests in the breakdown: {len(derived.frame)}",
        f"* num_ctx logged on these requests: {report.num_ctx_values}",
        "",
    ]
    if report.mode == "dev":
        lines += [
            "> *** DEV MODE — synthetic tickets only. Results are NOT evidence. ***",
            "",
        ]
    lines += [
        "## Verdict",
        "",
        f"The largest component of the mean request is **{report.largest_component}** "
        f"({report.largest_mean_ms:.1f} ms, {report.largest_share_pct:.1f} per cent "
        f"of the mean total latency).",
        "",
        f"What that means: {COMPONENT_VERDICTS[report.largest_component]}",
        "",
        "## Breakdown",
        "",
        to_markdown_table(report.breakdown, float_format="{:.1f}"),
        "The component means sum to the mean total latency. The percentile "
        "columns describe each component's own spread and do not sum to the "
        "percentile of the total.",
        "",
        "`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's "
        "own `total_duration` from the wall clock around our HTTP call. "
        "Ollama-side queueing appears there, and so do HTTP and container "
        "networking, JSON encoding, and the TCP connection we deliberately "
        "create per request. `ollama_other_ms` is the part of Ollama's own total "
        "that its three reported components do not explain.",
        "",
        "See `bottleneck_stacked.png` for the mean breakdown and "
        "`bottleneck_per_request.csv` for the per-request values behind it.",
        "",
        "## Token throughput",
        "",
        to_markdown_table(report.tokens, float_format="{:.2f}"),
        "",
        "## num_ctx truncation check",
        "",
        f"Requests whose `prompt_eval_count` sits at or above the warning "
        f"fraction of their logged `num_ctx`: **{len(report.suspects)}**.",
        "",
        "Ollama truncates a prompt longer than `num_ctx` silently, so a "
        "prompt-token count pinned at the limit means the model classified a "
        "ticket it had not fully read. Suspects are listed in "
        "`ctx_truncation_suspects.csv`.",
        "",
    ]
    if not derived.missing_reasons.empty:
        lines += [
            "## Requests with no timings",
            "",
            to_markdown_table(derived.missing_reasons, float_format="{:.0f}"),
            "",
        ]
    if derived.warnings:
        lines += ["## Warnings raised by this run", ""]
        lines += [f"* {warning}" for warning in derived.warnings]
        lines += [""]
    lines += [
        "## Interpretation",
        "",
        "The one-line bottleneck diagnosis is on Slide 9, and its comparison "
        "with the bottleneck named in `predictions/prediction_record.md` is on "
        "Slide 11. Both rest on this breakdown and on how its components move "
        "with the offered rate across runs. This file reports; it does not "
        "interpret.",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyse(args: argparse.Namespace) -> BottleneckReport:
    """Derive the breakdown for one run and write every output file."""
    run_dir: Path = args.run_dir
    if not run_dir.is_dir():
        raise AnalysisError(f"No such run directory: {run_dir}")
    metadata = load_metadata(run_dir)
    derived = derive_components(run_dir, ctx_warn_fraction=args.ctx_warn_fraction)

    breakdown = build_breakdown(derived.frame)
    tokens = build_token_table(derived.frame)
    suspects = build_ctx_suspects(derived.frame)
    per_request = build_per_request(derived.frame)
    component, mean_ms, share_pct = largest_component(breakdown)

    report = BottleneckReport(
        run_dir=run_dir,
        model_tag=str(metadata.get("model_tag") or "unknown"),
        mode=str(metadata.get("mode") or "unknown"),
        num_ctx_values=sorted(
            int(v) for v in derived.frame["num_ctx"].dropna().unique()
        ),
        derived=derived,
        breakdown=breakdown,
        tokens=tokens,
        suspects=suspects,
        largest_component=component,
        largest_mean_ms=mean_ms,
        largest_share_pct=share_pct,
    )

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    write_table(breakdown, out_dir, "bottleneck_breakdown", float_format="{:.1f}")
    write_table(tokens, out_dir, "bottleneck_tokens", float_format="{:.2f}")
    per_request.to_csv(out_dir / "bottleneck_per_request.csv", index=False)
    suspects.to_csv(out_dir / "ctx_truncation_suspects.csv", index=False)
    if not args.no_charts:
        write_stacked_png(
            breakdown,
            out_dir / "bottleneck_stacked.png",
            f"Mean request breakdown — {report.model_tag}\n{run_dir.name}",
        )
    (out_dir / "bottleneck_report.md").write_text(render_report(report), encoding="utf-8")
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line. See the module docstring for the semantics."""
    parser = argparse.ArgumentParser(
        prog="analysis/bottleneck_hints.py",
        description=(
            "Break a request's time down using only the service log's own "
            "timings and Ollama's reported durations: service overhead, the "
            "queue/transport residual, model load, prompt evaluation and "
            "generation, plus token throughput and a num_ctx truncation check."
        ),
        epilog=(
            "Exit codes: 0 a breakdown was produced; 1 the evidence could not be "
            "read, or no request had a complete set of Ollama timings. "
            "The queue term is a RESIDUAL, not a measured quantity: see the "
            "module docstring before quoting it."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="one run directory under results/runs/ (must contain service.jsonl "
        "and metadata.json)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="where tables, the chart and the report are written "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--ctx-warn-fraction",
        type=float,
        default=0.98,
        help="flag a request whose prompt_eval_count reaches this fraction of "
        "its logged num_ctx as a possible silent truncation (default: %(default)s)",
    )
    parser.add_argument(
        "--no-charts",
        action="store_true",
        help="write tables only; skip the PNG",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the breakdown; return the process exit code."""
    args = parse_args(argv)
    try:
        report = analyse(args)
    except AnalysisError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    for warning in report.derived.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    if report.mode == "dev":
        print(
            "*** DEV MODE — synthetic tickets only. Results are NOT evidence. ***",
            file=sys.stderr,
        )
    print(
        f"Requests in the breakdown: {len(report.derived.frame)} "
        f"(excluded for missing Ollama timings: {report.derived.n_missing_timings})"
    )
    print(
        f"Largest mean component: {report.largest_component} "
        f"({report.largest_mean_ms:.1f} ms, {report.largest_share_pct:.1f}%)"
    )
    print(f"Wrote {args.out_dir / 'bottleneck_breakdown.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
