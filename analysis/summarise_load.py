"""Summarise the JMeter load-test runs into the tables and charts Slide 9 needs.

Owner: Yeo Kai Yuan (technical core). Feeds Slide 9 ("Load and Stress Test
Results") and the load-test playbook in ``docs/playbooks/``.

The script walks a directory of run directories (the layout in the build
contract, ``results/runs/<stamp>_<model>_<plan>_<rate>_run<k>/``), and writes:

* ``load_per_run``        -- one row per run, headline metrics over every sample;
* ``load_per_run_by_label`` -- one row per (run, JMeter sampler label), which is
  how a ``mixed_load`` run has to be read because POST /tickets and GET /search
  latencies must not be pooled;
* ``load_per_config``     -- one row per (model, plan, rate, metric): the mean
  and the spread across the repeat runs of that configuration;
* ``load_summary.md``     -- those tables plus the definitions below and any
  warnings, in one file a marker can read end to end;
* ``latency_vs_rate_<model>.png`` -- one chart per candidate model.

Nothing here runs a model and nothing here invents a value: every figure is
derived from a ``.jtl`` written by JMeter or a line written by the service.

Metric definitions (these are the definitions a marker should check against)
---------------------------------------------------------------------------
**Latency.** The headline latency is JMeter's ``elapsed`` column: the
client-observed time from the moment the sampler sent the request to the moment
the last byte of the response arrived, in milliseconds. That is the quantity a
response-time requirement is about -- the intake system waits for the whole
round trip, not for the service's internal stopwatch. Alongside it we report the
service's own ``total_latency_ms`` (the request handler's wall clock) from the
service log, so the two can be compared: the gap is network plus framework
overhead, and ``analysis/reconcile.py`` gates on it. Percentiles are computed
with linear interpolation (:func:`analysis.common.percentile`); p95 computed
with a different interpolation rule differs on small samples, so the rule is
stated rather than assumed.

**Achieved throughput.** Completed samples divided by the wall-clock span of the
measured samples, where the span runs from the start of the earliest measured
sample (JMeter's ``timeStamp``, which is a start time) to the completion of the
latest measured sample (``timeStamp + elapsed``). A "completed" sample is one
JMeter recorded a response for, successful or not. Reported in requests per
second and, because the brief's throughput requirement is stated per hour, also
multiplied by 3600. ``ok_throughput`` is the same figure counting only
successful samples -- that is the rate of tickets actually classified, and it is
the one to compare against a "tickets per hour" requirement when the run had
errors. Note this is the *achieved* rate, not the offered rate: the offered rate
is the arrival rate configured in the plan (the ``<rate>`` in the directory
name), and the two diverging is itself a finding.

**Error rate.** Samples whose JMeter ``success`` flag is false, divided by total
samples, reported as a percentage. JMeter sets that flag from the plan's
Response Assertion (HTTP 200), so a 502 from a model timeout counts as an error.

**Warm-up.** Warm-up samples are excluded. The first request after a model
switch pays the model-load cost and would otherwise dominate p99. The run script
flags the warm-up request (``X-Warmup``) and writes its log line to
``warmup.jsonl``; this script additionally drops any ``.jtl`` sample whose
``request_id`` appears in ``warmup.jsonl`` or in ``metadata.json``'s
``warmup_request_id``, and applies :func:`analysis.common.exclude_warmup` to the
service log as a belt-and-braces guard.

**Repeats.** The brief requires three runs per configuration and states that a
single run is not a measurement. Spread across runs is reported as min, max and
sample standard deviation (ddof=1, so n=1 gives NaN rather than a falsely
precise 0). Any configuration with fewer than three runs is called out in the
markdown and on stderr.

Exit status
-----------
Non-zero when no run directories were found (including when the ``--model`` or
``--plan`` filter matches nothing) and when a run directory has no
``metadata.json`` -- a result without its model pin, prompt hash and freeze
commit is not evidence, so summarising it would be worse than failing.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# ``python analysis/summarise_load.py`` puts ``analysis/`` on sys.path, not the
# repository root, so make the root importable before touching our own packages.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis import common  # noqa: E402  (after the sys.path bootstrap)

#: Kept deliberately in step with the "Metric definitions" section of the module
#: docstring. The docstring is for whoever reads the code; this block is for the
#: marker reading the generated report, who will not read the code.
DEFINITIONS_MD = """\
## Definitions used in this report

| Quantity | Definition |
|---|---|
| Latency (headline) | JMeter `elapsed`: client-observed round trip in ms, from request sent to last response byte received. This is what a response-time requirement is about. |
| Latency (server) | The service log's `total_latency_ms`: the request handler's own wall clock. Reported alongside the client figure so the two can be compared. |
| Percentiles | Linear interpolation (`analysis/common.py::percentile`). Stated because p95 under a different interpolation rule differs on small samples. |
| Achieved throughput | Completed samples / wall-clock span of the measured samples, where the span is from the earliest sample's start (`timeStamp`) to the latest sample's completion (`timeStamp + elapsed`). Given per second and per hour (the brief's requirement is per hour). |
| `ok_throughput` | As above but counting only successful samples: the rate of tickets actually classified. |
| Offered rate | The arrival rate configured in the JMeter plan (the `<rate>` in the run directory name). Achieved throughput below the offered rate is a finding, not a rounding error. |
| Error rate | Samples with JMeter `success == false`, over total samples, as a percentage. |
| Warm-up | Excluded: the warm-up `request_id` from `warmup.jsonl` / `metadata.json` is dropped from the `.jtl`, and `exclude_warmup()` is applied to the service log. |
| Spread across runs | min, max and sample standard deviation (ddof=1) of the per-run figures of one configuration. n=1 gives SD = n/a, never 0. |
"""

#: Per-run metrics whose spread across repeat runs is reported per configuration.
#: Long format (one row per metric) rather than 4 columns per metric, so the
#: markdown table stays readable on a slide-sized page.
CONFIG_METRICS: tuple[str, ...] = (
    "client_p50_ms",
    "client_p95_ms",
    "client_p99_ms",
    "server_p95_ms",
    "throughput_rps",
    "throughput_per_hour",
    "ok_throughput_per_hour",
    "error_rate_pct",
    "samples",
)

#: The brief: "Three runs per configuration... A single run is not a measurement."
MIN_RUNS_PER_CONFIG = 3


# ---------------------------------------------------------------------------
# Per-run measurement
# ---------------------------------------------------------------------------

def warmup_request_ids(run_dir: Path, metadata: dict) -> set[str]:
    """Every ``request_id`` that belongs to the warm-up, not to the measurement.

    Three sources, because each on its own can be absent: the warm-up log lines
    the run script split out into ``warmup.jsonl``, any warm-up-flagged line
    left in ``service.jsonl``, and ``metadata.json``'s ``warmup_request_id``.
    """
    ids: set[str] = set()
    warm_id = metadata.get("warmup_request_id")
    if isinstance(warm_id, str) and warm_id:
        ids.add(warm_id)

    warm_log = run_dir / "warmup.jsonl"
    if warm_log.is_file():
        frame = common.read_service_log(warm_log)
        ids.update(str(value) for value in frame["request_id"].dropna())

    service_log = run_dir / "service.jsonl"
    if service_log.is_file():
        frame = common.read_service_log(service_log)
        flagged = frame.loc[frame["warmup"].astype(bool), "request_id"].dropna()
        ids.update(str(value) for value in flagged)
    return ids


def measured_samples(jtl: pd.DataFrame, warm_ids: set[str]) -> tuple[pd.DataFrame, int]:
    """Drop warm-up samples from a ``.jtl`` frame; return the frame and how many went."""
    if "request_id" not in jtl.columns or not warm_ids:
        return jtl.copy(), 0
    is_warm = jtl["request_id"].astype("string").isin(warm_ids)
    return jtl.loc[~is_warm].copy(), int(is_warm.sum())


def client_metrics(samples: pd.DataFrame) -> dict[str, float]:
    """Latency percentiles, throughput and error rate over a set of ``.jtl`` samples.

    The span is measured from the first sample's start to the last sample's
    completion, so a single sample still has a positive span (its own elapsed
    time) and the throughput of a one-sample run is defined rather than dividing
    by zero.
    """
    if samples.empty:
        raise common.AnalysisError(
            "No measured samples left after excluding warm-up. Either the run "
            "produced nothing or every sample was flagged as warm-up."
        )
    elapsed = pd.to_numeric(samples["elapsed"], errors="coerce")
    percentiles = common.latency_percentiles(elapsed)

    started = samples["ts"].min()
    finished = (samples["ts"] + pd.to_timedelta(elapsed, unit="ms")).max()
    span_s = float((finished - started).total_seconds())

    total = int(len(samples))
    ok = int(samples["ok"].astype(bool).sum())
    errors = total - ok
    # A span can only be zero if every sample reported elapsed == 0, which would
    # itself be a broken .jtl; guard rather than raise ZeroDivisionError.
    throughput_rps = total / span_s if span_s > 0 else float("nan")
    ok_throughput_rps = ok / span_s if span_s > 0 else float("nan")
    return {
        "samples": float(total),
        "errors": float(errors),
        "error_rate_pct": 100.0 * errors / total,
        "client_p50_ms": percentiles["p50"],
        "client_p95_ms": percentiles["p95"],
        "client_p99_ms": percentiles["p99"],
        "client_mean_ms": percentiles["mean"],
        "client_min_ms": percentiles["min"],
        "client_max_ms": percentiles["max"],
        "span_s": span_s,
        "throughput_rps": throughput_rps,
        "throughput_per_hour": throughput_rps * 3600.0,
        "ok_throughput_rps": ok_throughput_rps,
        "ok_throughput_per_hour": ok_throughput_rps * 3600.0,
    }


def server_metrics(log: pd.DataFrame) -> dict[str, float]:
    """The service's own ``total_latency_ms`` percentiles, for comparison.

    Computed over every measured log line of the run, which matches the headline
    client figure: that pools every sample too. For a mixed run, where the log
    holds ``/tickets`` and ``/search`` lines, read the per-label table instead of
    either pooled figure.
    """
    percentiles = common.latency_percentiles(
        pd.to_numeric(log["total_latency_ms"], errors="coerce")
    )
    return {
        "server_p50_ms": percentiles["p50"],
        "server_p95_ms": percentiles["p95"],
        "server_p99_ms": percentiles["p99"],
        "server_mean_ms": percentiles["mean"],
        "service_log_lines": float(len(log)),
    }


@dataclass(frozen=True)
class RunSummary:
    """Everything we report about one run directory."""

    info: common.RunDirInfo
    metadata: dict
    metrics: dict[str, float]
    by_label: dict[str, dict[str, float]] = field(default_factory=dict)

    @property
    def model_tag(self) -> str:
        """The pinned Ollama tag from the metadata, which is the honest name."""
        return str(self.metadata.get("model_tag") or self.info.model)

    @property
    def mode(self) -> str:
        """``real`` or ``dev``. A dev-mode run is never evidence."""
        return str(self.metadata.get("mode") or "unknown")

    @property
    def config_key(self) -> tuple[str, str, str]:
        """(model tag, plan, rate) -- shared by the repeat runs of a configuration."""
        return (self.model_tag, self.info.plan, self.info.rate)

    @property
    def rate_per_min(self) -> float | None:
        """Offered arrival rate in requests/min, or ``None`` for the ramp plan."""
        return parse_rate(self.info.rate)

    def row(self) -> dict[str, object]:
        """The flat per-run table row, in the order the report shows it."""
        return {
            "run_id": self.info.path.name,
            "model_tag": self.model_tag,
            "plan": self.info.plan,
            "rate": self.info.rate,
            "rate_per_min": self.rate_per_min,
            "run_index": self.info.run_index,
            "mode": self.mode,
            "samples": int(self.metrics["samples"]),
            "errors": int(self.metrics["errors"]),
            "error_rate_pct": self.metrics["error_rate_pct"],
            "client_p50_ms": self.metrics["client_p50_ms"],
            "client_p95_ms": self.metrics["client_p95_ms"],
            "client_p99_ms": self.metrics["client_p99_ms"],
            "client_mean_ms": self.metrics["client_mean_ms"],
            "client_min_ms": self.metrics["client_min_ms"],
            "client_max_ms": self.metrics["client_max_ms"],
            "server_p50_ms": self.metrics["server_p50_ms"],
            "server_p95_ms": self.metrics["server_p95_ms"],
            "server_p99_ms": self.metrics["server_p99_ms"],
            "server_mean_ms": self.metrics["server_mean_ms"],
            "span_s": self.metrics["span_s"],
            "throughput_rps": self.metrics["throughput_rps"],
            "throughput_per_hour": self.metrics["throughput_per_hour"],
            "ok_throughput_rps": self.metrics["ok_throughput_rps"],
            "ok_throughput_per_hour": self.metrics["ok_throughput_per_hour"],
            "warmup_samples_excluded": int(self.metrics["warmup_samples_excluded"]),
            "service_log_lines": int(self.metrics["service_log_lines"]),
            "labels": ";".join(sorted(self.by_label)),
        }


def parse_rate(rate: str) -> float | None:
    """``"60pm"`` -> ``60.0``; ``"ramp"`` -> ``None`` (no single arrival rate)."""
    if rate.endswith("pm"):
        try:
            return float(rate.removesuffix("pm"))
        except ValueError:
            return None
    return None


def summarise_run(info: common.RunDirInfo) -> RunSummary:
    """Read one run directory and compute its metrics.

    Raises :class:`analysis.common.AnalysisError` (via the readers) if the run is
    not complete enough to be evidence -- missing ``metadata.json``, missing or
    empty ``results.jtl``, unparseable service log.
    """
    metadata = common.load_metadata(info.path)
    jtl = common.read_jtl(info.path / "results.jtl")
    warm_ids = warmup_request_ids(info.path, metadata)
    samples, dropped = measured_samples(jtl, warm_ids)

    log = common.exclude_warmup(common.read_service_log(info.path / "service.jsonl"))

    metrics = client_metrics(samples)
    metrics.update(server_metrics(log))
    metrics["warmup_samples_excluded"] = float(dropped)

    # Per JMeter sampler label as well: a mixed_load run holds POST /tickets and
    # GET /search samples in one file, and pooling their latencies would be a
    # meaningless average of two different operations.
    by_label: dict[str, dict[str, float]] = {}
    if "label" in samples.columns:
        for label, group in samples.groupby(samples["label"].astype(str), sort=True):
            by_label[str(label)] = client_metrics(group)
    return RunSummary(info=info, metadata=metadata, metrics=metrics, by_label=by_label)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

def per_run_frame(summaries: list[RunSummary]) -> pd.DataFrame:
    """One row per run, sorted by model, plan, offered rate then run index."""
    frame = pd.DataFrame.from_records([s.row() for s in summaries])
    return frame.sort_values(
        by=["model_tag", "plan", "rate_per_min", "rate", "run_index"],
        na_position="last",
        kind="stable",
    ).reset_index(drop=True)


def per_label_frame(summaries: list[RunSummary]) -> pd.DataFrame:
    """One row per (run, JMeter sampler label): client-side metrics only.

    Server-side percentiles are deliberately absent here: the service log's
    ``endpoint`` is not the JMeter label, and guessing a mapping between them
    would be inventing a join that the data does not support.
    """
    rows: list[dict[str, object]] = []
    for summary in summaries:
        for label, metrics in sorted(summary.by_label.items()):
            rows.append(
                {
                    "run_id": summary.info.path.name,
                    "model_tag": summary.model_tag,
                    "plan": summary.info.plan,
                    "rate": summary.info.rate,
                    "run_index": summary.info.run_index,
                    "label": label,
                    "samples": int(metrics["samples"]),
                    "errors": int(metrics["errors"]),
                    "error_rate_pct": metrics["error_rate_pct"],
                    "client_p50_ms": metrics["client_p50_ms"],
                    "client_p95_ms": metrics["client_p95_ms"],
                    "client_p99_ms": metrics["client_p99_ms"],
                    "span_s": metrics["span_s"],
                    "throughput_rps": metrics["throughput_rps"],
                    "throughput_per_hour": metrics["throughput_per_hour"],
                }
            )
    return pd.DataFrame.from_records(rows)


def per_config_frame(summaries: list[RunSummary]) -> tuple[pd.DataFrame, list[str]]:
    """Mean and spread of each metric across the repeat runs of a configuration.

    Returns the long-format table and the list of loud warnings (configurations
    with fewer than :data:`MIN_RUNS_PER_CONFIG` runs), which the caller prints to
    stderr as well as writing into the markdown.
    """
    grouped: dict[tuple[str, str, str], list[RunSummary]] = {}
    for summary in summaries:
        grouped.setdefault(summary.config_key, []).append(summary)

    rows: list[dict[str, object]] = []
    warnings: list[str] = []
    for key in sorted(grouped, key=lambda k: (k[0], k[1], parse_rate(k[2]) or 1e9, k[2])):
        model_tag, plan, rate = key
        runs = sorted(grouped[key], key=lambda s: s.info.run_index)
        n_runs = len(runs)
        note = ""
        if n_runs < MIN_RUNS_PER_CONFIG:
            note = f"FEWER THAN {MIN_RUNS_PER_CONFIG} RUNS (n={n_runs}) - NOT A MEASUREMENT"
            warnings.append(
                f"{model_tag} {plan} {rate}: only {n_runs} run(s) found. The brief "
                f"requires {MIN_RUNS_PER_CONFIG} runs per configuration and states "
                f"that a single run is not a measurement. Do not report this "
                f"configuration until the missing runs exist."
            )
        for metric in CONFIG_METRICS:
            stats = common.spread([s.metrics[metric] for s in runs])
            rows.append(
                {
                    "model_tag": model_tag,
                    "plan": plan,
                    "rate": rate,
                    "rate_per_min": parse_rate(rate),
                    "metric": metric,
                    "runs": n_runs,
                    "mean": stats["mean"],
                    "min": stats["min"],
                    "max": stats["max"],
                    "sd": stats["sd"],
                    "run_indexes": ";".join(str(s.info.run_index) for s in runs),
                    "warning": note,
                }
            )
    return pd.DataFrame.from_records(rows), warnings


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

#: (metric, legend label, marker, line style, grey level). Greyscale-legible by
#: construction: the three series differ by marker AND dash pattern, not colour,
#: because these charts are printed in slides that may be greyscale.
_CHART_SERIES: tuple[tuple[str, str, str, str, str], ...] = (
    ("client_p50_ms", "p50", "o", "-", "0.0"),
    ("client_p95_ms", "p95", "s", "--", "0.30"),
    ("client_p99_ms", "p99", "^", ":", "0.45"),
)


def chart_latency_vs_rate(summaries: list[RunSummary], out_dir: Path) -> list[Path]:
    """One ``latency_vs_rate_<model>.png`` per model; return the paths written.

    x is the offered arrival rate, y is client-observed latency, one line per
    percentile, and the error bars show the observed min-max range across the
    repeat runs of that configuration (not a confidence interval -- with three
    runs the honest thing to draw is the range we actually saw).

    Runs whose rate is not a per-minute number (the ``ramp`` plan) are skipped:
    a stepped ramp has no single arrival rate, and ``analysis/stress_summary.py``
    is the script that reads it. One subplot per plan, because POST-only and
    mixed traffic are different workloads and must not share an axis.
    """
    plt = common.use_headless_matplotlib()
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    by_model: dict[str, list[RunSummary]] = {}
    for summary in summaries:
        if summary.rate_per_min is None:
            continue
        by_model.setdefault(summary.model_tag, []).append(summary)

    for model_tag in sorted(by_model):
        model_runs = by_model[model_tag]
        plans = sorted({s.info.plan for s in model_runs})
        figure, axes = plt.subplots(
            1, len(plans), figsize=(5.6 * len(plans), 4.0), sharey=True, squeeze=False
        )
        footnotes: list[str] = []

        for axis, plan in zip(axes[0], plans):
            plan_runs = [s for s in model_runs if s.info.plan == plan]
            # Group the repeat runs of each rate so the error bars are the
            # spread across runs, which is what the brief asks to be reported.
            by_rate: dict[float, list[RunSummary]] = {}
            for summary in plan_runs:
                by_rate.setdefault(float(summary.rate_per_min), []).append(summary)
            rates = sorted(by_rate)

            for metric, legend, marker, style, grey in _CHART_SERIES:
                means: list[float] = []
                lower: list[float] = []
                upper: list[float] = []
                for rate in rates:
                    stats = common.spread([s.metrics[metric] for s in by_rate[rate]])
                    means.append(stats["mean"])
                    lower.append(stats["mean"] - stats["min"])
                    upper.append(stats["max"] - stats["mean"])
                axis.errorbar(
                    rates,
                    means,
                    yerr=[lower, upper],
                    label=legend,
                    color=grey,
                    marker=marker,
                    markersize=6,
                    markerfacecolor="white",
                    markeredgewidth=1.2,
                    linestyle=style,
                    linewidth=1.8,
                    capsize=4,
                )

            axis.set_title(plan, fontsize=10)
            axis.set_xlabel("Offered arrival rate (requests/min)")
            axis.set_xticks(rates)
            axis.grid(True, which="major", linewidth=0.4, color="0.85")
            axis.set_axisbelow(True)

            thin = [r for r in rates if len(by_rate[r]) < MIN_RUNS_PER_CONFIG]
            if thin:
                footnotes.append(
                    f"{plan}: fewer than {MIN_RUNS_PER_CONFIG} runs at "
                    + ", ".join(f"{r:g}/min (n={len(by_rate[r])})" for r in thin)
                )
            multi_label = {label for s in plan_runs for label in s.by_label}
            if len(multi_label) > 1:
                footnotes.append(
                    f"{plan}: samples span {len(multi_label)} sampler labels; see "
                    f"load_per_run_by_label.csv for the per-label figures."
                )

        axes[0][0].set_ylabel("POST latency, client-observed (ms)")
        axes[0][0].legend(title="percentile", fontsize=9, loc="best")
        figure.suptitle(
            f"{model_tag}: latency vs offered arrival rate\n"
            f"error bars = min-max across repeat runs",
            fontsize=11,
        )
        if footnotes:
            figure.text(0.01, 0.005, "Note: " + " | ".join(footnotes), fontsize=7)
        figure.tight_layout(rect=(0, 0.04 if footnotes else 0.0, 1, 0.90))

        path = out_dir / f"latency_vs_rate_{common.sanitise_model_tag(model_tag)}.png"
        # metadata Software=None keeps the PNG bytes deterministic, so re-running
        # the analysis does not produce a spurious diff in a committed chart.
        figure.savefig(path, dpi=150, metadata={"Software": None})
        plt.close(figure)
        written.append(path)
    return written


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def build_report(
    runs_root: Path,
    per_run: pd.DataFrame,
    per_label: pd.DataFrame,
    per_config: pd.DataFrame,
    charts: list[Path],
    warnings: list[str],
) -> str:
    """Stitch the tables, the definitions and the warnings into one markdown page."""
    n_configs = (
        0
        if per_config.empty
        else len(per_config[["model_tag", "plan", "rate"]].drop_duplicates())
    )
    parts: list[str] = [
        "# Load-test summary",
        "",
        f"Source: `{runs_root}` -- {len(per_run)} run(s), {n_configs} configuration(s).",
        "",
        "Generated by `analysis/summarise_load.py`. Every figure here comes from a "
        "JMeter `.jtl` or a service log line in the run directories named below; "
        "nothing is entered by hand.",
        "",
        DEFINITIONS_MD,
    ]

    if warnings:
        parts += [
            "## Warnings -- read before quoting any of these numbers",
            "",
            *(f"* **{line}**" for line in warnings),
            "",
        ]

    parts += [
        "## Per configuration (mean and spread across repeat runs)",
        "",
        common.to_markdown_table(per_config, float_format="{:.2f}"),
        "",
        "## Per run",
        "",
        common.to_markdown_table(per_run, float_format="{:.2f}"),
        "",
    ]

    if not per_label.empty:
        parts += [
            "## Per run and JMeter sampler label",
            "",
            "Read this table, not the headline one, for a mixed-load run: POST "
            "/tickets and GET /search latencies must not be pooled.",
            "",
            common.to_markdown_table(per_label, float_format="{:.2f}"),
            "",
        ]

    if charts:
        parts += ["## Charts", ""]
        parts += [f"* `{path.name}`" for path in charts]
        parts += [""]
    else:
        parts += [
            "## Charts",
            "",
            "None. A latency-versus-arrival-rate chart needs runs whose rate is a "
            "per-minute number; every run here is a stepped ramp, which "
            "`analysis/stress_summary.py` reads instead.",
            "",
        ]
    parts += [
        "## Reconciliation",
        "",
        "These tables are counts of samples, not proof that the samples match the "
        "service's own log. Run `analysis/reconcile.py --run-dir <run>` for each "
        "run before quoting a number from it.",
        "",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    """The command line described in the build contract's CLI section."""
    parser = argparse.ArgumentParser(
        prog="analysis/summarise_load.py",
        description=(
            "Summarise JMeter load-test runs: p50/p95/p99 latency, achieved "
            "throughput, error rate and sample count per run; mean and spread "
            "across the repeat runs of each configuration; one "
            "latency-versus-arrival-rate chart per model."
        ),
        epilog=(
            "Exits non-zero if no runs were found or a run directory has no "
            "metadata.json. Never point this at a directory of results you have "
            "not also reconciled with analysis/reconcile.py."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--runs",
        type=Path,
        default=Path("results/runs"),
        help="directory containing <stamp>_<model>_<plan>_<rate>_run<k> directories",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="only summarise runs of this model (Ollama tag or its sanitised form)",
    )
    parser.add_argument(
        "--plan",
        default=None,
        help="only summarise runs of this plan, e.g. load_post_tickets",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("analysis/output/load"),
        help="where the CSV, markdown and PNG outputs are written",
    )
    return parser


def select_runs(
    runs_root: Path, model: str | None, plan: str | None
) -> list[common.RunDirInfo]:
    """Run directories under ``runs_root`` that pass the ``--model``/``--plan`` filters."""
    found = common.iter_run_dirs(runs_root)
    selected = found
    if model is not None:
        wanted = {model, common.sanitise_model_tag(model)}
        selected = [info for info in selected if info.model in wanted]
    if plan is not None:
        selected = [info for info in selected if info.plan == plan]
    if not selected:
        raise common.AnalysisError(
            f"No runs in {runs_root} match model={model!r} plan={plan!r}. "
            f"Found {len(found)} run(s): "
            + ", ".join(sorted(info.path.name for info in found))
        )
    return selected


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the process exit status."""
    args = build_arg_parser().parse_args(argv)
    try:
        selected = select_runs(args.runs, args.model, args.plan)
        summaries = [summarise_run(info) for info in selected]
    except common.AnalysisError as exc:
        print(f"summarise_load: FAILED: {exc}", file=sys.stderr)
        return 1

    per_run = per_run_frame(summaries)
    per_label = per_label_frame(summaries)
    per_config, warnings = per_config_frame(summaries)

    # A dev-mode run is synthetic-ticket traffic. It is useful for checking the
    # pipeline and is never evidence, so it must not slip into a slide unnoticed.
    dev_runs = [s.info.path.name for s in summaries if s.mode == "dev"]
    if dev_runs:
        warnings.insert(
            0,
            "DEV MODE runs included ("
            + ", ".join(sorted(dev_runs))
            + "). Dev-mode results are synthetic-ticket traffic and are NOT evidence.",
        )

    out_dir: Path = args.out_dir
    common.write_table(per_run, out_dir, "load_per_run", float_format="{:.2f}")
    common.write_table(per_config, out_dir, "load_per_config", float_format="{:.2f}")
    if not per_label.empty:
        common.write_table(
            per_label, out_dir, "load_per_run_by_label", float_format="{:.2f}"
        )
    charts = chart_latency_vs_rate(summaries, out_dir)

    report = build_report(args.runs, per_run, per_label, per_config, charts, warnings)
    report_path = out_dir / "load_summary.md"
    report_path.write_text(report, encoding="utf-8")

    print(f"summarise_load: {len(summaries)} run(s) from {args.runs}")
    print(f"summarise_load: wrote {report_path}")
    for path in charts:
        print(f"summarise_load: wrote {path}")
    # Flush before writing to stderr so the two streams read in order when the
    # operator is watching a terminal rather than a redirected log.
    sys.stdout.flush()
    for line in warnings:
        # stderr as well as the markdown: a warning only a file knows about is a
        # warning nobody read.
        print(f"summarise_load: WARNING: {line}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
