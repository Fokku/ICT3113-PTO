"""Summarise the Assignment 2 speed-test runs into the tables Slide 5 needs.

Owner: Yeo Kai Yuan (Part 1). ``TODO_A2.md`` §1.4. Feeds Slide 5 ("Speed
results") and the Step 5 recommendation, which applies the "fastest" rule fixed
in ``predictions/prediction_record_a2.md`` §4 to the per-configuration table.

What it reads
-------------
Only Assignment 2 speed runs: ``results/runs/<stamp>_<config>_speed_a2_<rate>_run<k>/``
(``common.A2_SPEED_PLAN``), as written by ``scripts/run_load_test_a2.sh``. An
Assignment 1 run directory in the same folder is never opened, and nothing is
read from ``analysis/output/load/`` -- the brief forbids reusing an Assignment 1
speed figure for any configuration (``TODO_A2.md`` guardrail 10). Output goes to
``analysis/output/speed_a2/`` and the script refuses to write into the
Assignment 1 load directory.

Optionally, ``--accuracy-root`` (``results/accuracy_a2/``) supplies the
accuracy-test escalation fraction per cascade setting, and
``--accuracy-verdicts`` (Part 3's pass/fail table) labels configurations that do
not pass the accuracy limits.

What it writes (under ``--out-dir``)
------------------------------------
``per_run.csv``/``.md`` (one row per run, **every** run, nothing dropped),
``per_config.csv``/``.md`` (one row per configuration and rate) and
``report.md`` (both tables, the definitions, the thresholds in force, every
flag, and the note on what is not reported).

Definitions (kept in step with :data:`DEFINITIONS_MD`, which goes in the report)
------------------------------------------------------------------------------
* **Measured samples.** ``.jtl`` samples minus the warm-up: any sample whose
  ``request_id`` is in ``warmup.jsonl``, in a warm-up-flagged service-log line,
  or in ``metadata.json``'s ``warmup_request_id`` / ``warmup_request_ids``.
  The same ids are removed from the service log.
* **sent / completed / errored / unfinished.** ``sent`` is the number of
  measured samples. A sample is *completed* when its ``responseCode`` is the
  number 200, *errored* when it is any other number (e.g. 502), and *unfinished*
  when it is not a number at all -- JMeter writes ``Non HTTP response code: ...``
  for a request that timed out or was cut off. Unfinished requests are counted
  and reported; the run is kept (brief: "reported as such, not thrown away").
  A request JMeter abandoned without writing any sample shows up only as a
  service-log line with no sample (``log_lines_without_sample``), and
  ``reconcile.py`` fails the run for it.
* **stats_delta.** ``stats_total_after - stats_total_before`` (``GET /stats``,
  from ``metadata.json`` or ``stats_before/after.json``). Consistent when it
  equals ``completed``, or exceeds it by no more than the unfinished and
  unrecorded requests (the service may finish and store a request after JMeter
  gave up on it). Missing or otherwise inconsistent makes the run invalid.
* **p50.** Median of ``elapsed`` over the completed samples, linear
  interpolation (``common.percentile``).
* **Halves split (no-queue check).** By **time**: the run's midpoint is halfway
  between the start (``timeStamp``) of its first and last measured sample, i.e.
  the middle of the arrival window. Completed samples that started before it
  form the first half, the rest the second. ``halves_change_pct = 100 *
  (p50_second - p50_first) / p50_first``. Chosen over an equal-count split
  because the question is whether latency grew over the run's duration (the
  brief: a longer run gives a bigger number when a queue builds); with random
  arrivals the halves hold about the same number of requests, and both counts
  are reported.
* **Queue wait.** Median over measured ``POST /tickets`` log lines of
  ``analysis/bottleneck_hints.py``'s ``ollama_other_ms``: ``total_duration/1e6
  - (load_duration + prompt_eval_duration + eval_duration)/1e6``. This is the
  "median ``ollama_other_ms`` (queue wait)" of ``TODO_A2.md`` §1.4 and
  ``prediction_record_a2.md`` §4, and it is where Assignment 1 measured Ollama's
  queueing: waiting for the single parallel slot is inside Ollama's
  ``total_duration`` but in none of its three components
  (``predictions/outcomes.md`` §2.4: ``ollama_other_ms`` rose 10 -> 858 ms with
  load while ``queue_residual_ms`` stayed 10-13 ms). ``bottleneck_hints.py``'s
  other residual, ``queue_residual_ms = model_latency_ms - total_duration/1e6``
  (HTTP, container network, connection setup), is reported alongside as
  ``queue_residual_median_ms`` for information and is not part of the check.
  On an escalated cascade line both models' timings are summed by the service
  (``service/log_schema.py``), so the figure is the sum of both calls' waits.
* **Queued.** Flagged when ``halves_change_pct`` exceeds ``+tolerance`` (the
  second half's p50 more than 20% *above* the first's -- one-sided, exactly as
  the frozen ``prediction_record_a2.md`` §4 states it; a faster second half is
  no sign of a queue) or the queue-wait median reaches the threshold. A queued run is reported, flagged,
  and not compared on p50 (``prediction_record_a2.md`` §4).
* **Throughput.** ``completed / span_s``, where ``span_s`` is
  ``summarise_load.client_metrics``'s span: first measured sample's start to the
  last measured sample's end (``timeStamp + elapsed``), over every measured
  sample. **Error rate** is ``100 * (sent - completed) / sent``: errored and
  unfinished together, the same as Assignment 1's JMeter-``success`` figure.
* **Escalation fraction** (cascade only). ``escalated == true`` lines over all
  measured ``POST /tickets`` service-log lines. The accuracy-test fraction is the
  same quantity over the newest test-set accuracy run of the same setting; the
  gap is in percentage points, speed minus accuracy.
* **Reload.** Any measured line whose ``load_duration`` exceeds
  ``--reload-threshold-ms`` means a model was (re)loaded mid-run: "not a
  cascade result; it is a loading result" (brief). Applied to every run.
* **Repeats.** ``sent`` above ``--max-tickets`` or any ``source_row`` sampled
  twice: a ticket repeated within the run and its latency is suspect (prompt
  cache).
* **Valid.** ``mode == real``, ``gate.json`` ok, environment check ok, every
  expected model resident before the run, at least three warm-up requests,
  ``stats_delta`` consistent, no-queue check passed, no reload, no repeats, and
  ``reconcile.py`` passes. Residency *after* the run is reported but not
  required: the trailing pause outlasts ``OLLAMA_KEEP_ALIVE``, so Ollama may
  unload an idle model before the after-snapshot; a mid-run unload is caught by
  ``load_duration`` instead.
* **Per configuration.** p50 mean/min/max/sample SD (``common.spread``), pooled
  p95 (every completed sample of the counted runs, with its count), mean
  throughput, mean error rate and the pooled escalation fraction are computed
  over the **valid** runs only; every run is still listed. "Faster than
  ``qwen2.5:7b``" means this configuration's per-run p50 range [min, max] lies
  entirely below the reference's; overlapping ranges are "not distinguishable"
  (``prediction_record_a2.md`` §4).

No p99 is computed or written anywhere: the brief, Step 4, "Do not report p99;
the sample is too small". ``common.latency_percentiles`` (which emits one) is
never used for an Assignment 2 figure.

Exit status
-----------
0 when the tables were written. 1 when no speed_a2 run exists under ``--runs``,
when a run's core evidence (``metadata.json``, ``results.jtl``,
``service.jsonl``) cannot be read, when a verdicts file is malformed, or when
``--out-dir`` points into the Assignment 1 load output. Never an empty table.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# ``python analysis/summarise_load_a2.py`` puts ``analysis/`` on sys.path, not the
# repository root, so make the root importable before touching our own packages.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis import common, reconcile  # noqa: E402  (after the sys.path bootstrap)
from analysis.summarise_load import (  # noqa: E402
    client_metrics,
    measured_samples,
    parse_rate,
    warmup_request_ids,
)

PROG = "summarise_load_a2"
DEFAULT_RUNS = Path("results/runs")
DEFAULT_OUT_DIR = Path("analysis/output/speed_a2")
DEFAULT_ACCURACY_ROOT = Path("results/accuracy_a2")
#: Assignment 1's load-test output. No Assignment 2 figure may ever land there.
A1_LOAD_OUT_DIR = REPO_ROOT / "analysis" / "output" / "load"
#: The top Assignment 1 model; every other configuration is compared with it.
REFERENCE_CONFIG = "qwen2.5:7b"
#: The brief: three runs per configuration.
MIN_RUNS_PER_CONFIG = 3
#: The brief, "Each run": three fixed warm-up tickets.
EXPECTED_WARMUPS = 3
NS_PER_MS = 1_000_000.0
_STAMP_RE = re.compile(r"(\d{8}T\d{6}Z)$")
_TRUE_WORDS = {"true", "yes", "1", "pass", "passes"}
_FALSE_WORDS = {"false", "no", "0", "fail", "fails"}


@dataclass(frozen=True)
class Thresholds:
    """The analysis thresholds; defaults from ``prediction_record_a2.md`` §4."""

    halves_tolerance: float = 0.20
    queue_wait_ms: float = 100.0
    gap_threshold_pp: float = 15.0
    reload_threshold_ms: float = 1000.0
    max_tickets: int = 100


DEFINITIONS_MD = """\
## Definitions used in this report

| Quantity | Definition |
|---|---|
| Measured samples | `.jtl` samples minus the warm-up (ids from `warmup.jsonl`, warm-up-flagged log lines, `metadata.json` `warmup_request_id` / `warmup_request_ids`). The same ids are removed from the service log. |
| sent | Number of measured `.jtl` samples. |
| completed | Measured samples with `responseCode` 200. |
| errored | Measured samples with any other numeric `responseCode` (e.g. 502). |
| unfinished | Measured samples whose `responseCode` is not a number (`Non HTTP response code: ...`: timed out or cut off). Counted and reported; the run is kept, never thrown away. |
| log_lines_without_sample | Measured `POST /tickets` service-log lines with no `.jtl` sample: requests JMeter abandoned without recording. `reconcile.py` fails a run for these. |
| stats_delta | `GET /stats` total after minus before. Consistent when it equals `completed`, or exceeds it by at most unfinished + unrecorded requests (the service can store a request after JMeter gave up on it). |
| p50 | Median of `elapsed` (client-observed ms) over completed samples, linear interpolation (`analysis/common.py::percentile`). |
| First/second-half p50 | Split by time at the midpoint of the arrival window: halfway between the start (`timeStamp`) of the first and the last measured sample. Completed samples that started before it are the first half. `halves_change_pct = 100 * (second - first) / first`. |
| Queue wait | Median over measured `POST /tickets` log lines of `ollama_other_ms` as `analysis/bottleneck_hints.py` defines it: `total_duration/1e6 - (load_duration + prompt_eval_duration + eval_duration)/1e6`. This is where Assignment 1 measured Ollama's queueing (waiting for its single slot; `predictions/outcomes.md` 2.4). Summed over both calls on an escalated cascade line. `queue_residual_median_ms` (`model_latency_ms - total_duration/1e6`, HTTP and network) is shown for information only. |
| Queued | Halves differ by more than the tolerance, or the queue-wait median reaches the threshold. Reported, flagged, and not compared on p50. |
| Throughput | completed / span, where span runs from the first measured sample's start to the last measured sample's end (`timeStamp + elapsed`), as in Assignment 1's `client_metrics`. Requests per second. |
| Error rate | `100 * (sent - completed) / sent`: errored and unfinished together. |
| Escalation fraction | Cascade only: `escalated == true` lines over all measured `POST /tickets` service-log lines. Accuracy-test fraction: the same over the newest test-set accuracy run of that setting. Gap = speed minus accuracy, in percentage points. |
| Reload | A measured log line whose `load_duration` exceeds the reload threshold: a model was loaded mid-run. A loading result, not a speed result. |
| Repeats | sent above the ticket-list size, or a `source_row` sampled twice: a ticket repeated within the run (prompt cache). |
| Valid | mode real, `gate.json` ok, environment check ok, all expected models resident before the run, at least three warm-up requests, stats delta consistent, no-queue check passed, no reload, no repeats, `reconcile.py` passes. Residency after the run is shown but not required: the trailing pause outlasts `OLLAMA_KEEP_ALIVE`, and a mid-run unload is caught by the reload check. |
| Per-configuration figures | p50 mean/min/max/sample SD (ddof=1), pooled p95 with its sample count, mean throughput, mean error rate and pooled escalation fraction, all over the **valid** runs only. Every run is listed in `p50_per_run_ms` and in the per-run table. |
| faster_than_reference | This configuration's per-run p50 range [min, max] (valid runs) lies entirely below the reference's: "yes". Overlapping: "not distinguishable". Entirely above: "slower" (`predictions/prediction_record_a2.md` section 4). |
"""

#: Per-run columns, in report order.
RUN_COLUMNS: tuple[str, ...] = (
    "run_id", "config", "cascade_setting", "rate", "rate_per_min", "run_index", "mode",
    "s_seconds", "duration_s",
    "gate_ok", "env_check_ok", "all_expected_resident_before",
    "all_expected_resident_after", "warmup_requests",
    "sent", "completed", "errored", "unfinished", "log_lines_without_sample",
    "stats_total_before", "stats_total_after", "stats_delta",
    "stats_delta_equals_completed", "stats_consistent",
    "p50_ms", "n_latency",
    "p50_first_half_ms", "n_first_half", "p50_second_half_ms", "n_second_half",
    "halves_change_pct",
    "queue_wait_median_ms", "n_queue_wait", "queue_residual_median_ms",
    "no_queue_check", "queued",
    "span_s", "throughput_rps", "error_rate_pct",
    "escalated_count", "escalation_total", "escalation_fraction",
    "accuracy_escalation_fraction", "escalation_gap_pp", "escalation_gap_flag",
    "max_load_duration_ms", "reload_requests", "reload",
    "distinct_source_rows", "repeats",
    "reconcile_ok", "valid", "reasons", "notes",
)

#: Per-configuration columns, in report order.
CONFIG_COLUMNS: tuple[str, ...] = (
    "config", "cascade_setting", "rate", "n_runs", "n_valid_runs", "runs_counted",
    "p50_per_run_ms", "p50_mean_ms", "p50_min_ms", "p50_max_ms", "p50_sd_ms",
    "pooled_p95_ms", "pooled_n", "throughput_mean_rps", "error_rate_mean_pct",
    "sent_total", "completed_total", "errored_total", "unfinished_total",
    "escalated_count", "escalation_total", "escalation_fraction",
    "accuracy_run_id", "accuracy_escalated_count", "accuracy_escalation_total",
    "accuracy_escalation_fraction", "escalation_gap_pp", "escalation_gap_flag",
    "passes_accuracy", "label", "faster_than_reference", "warning",
)

#: Count columns, written as integers (blank when not applicable), never 6.00.
INTEGER_COLUMNS: frozenset[str] = frozenset({
    "run_index", "warmup_requests", "sent", "completed", "errored", "unfinished",
    "log_lines_without_sample", "stats_total_before", "stats_total_after", "stats_delta",
    "n_latency", "n_first_half", "n_second_half", "n_queue_wait", "escalated_count",
    "escalation_total", "reload_requests", "distinct_source_rows", "n_runs",
    "n_valid_runs", "pooled_n", "sent_total", "completed_total", "errored_total",
    "unfinished_total", "accuracy_escalated_count", "accuracy_escalation_total",
})

#: The two narrower per-run views the report shows (the CSV has every column).
REPORT_RUN_FIGURES: tuple[str, ...] = (
    "run_id", "config", "run_index", "valid", "no_queue_check", "sent", "completed",
    "errored", "unfinished", "stats_delta", "p50_ms", "n_latency", "p50_first_half_ms",
    "p50_second_half_ms", "halves_change_pct", "queue_wait_median_ms",
    "throughput_rps", "error_rate_pct", "escalated_count", "escalation_total",
    "escalation_fraction", "escalation_gap_pp", "max_load_duration_ms",
)
REPORT_RUN_CHECKS: tuple[str, ...] = (
    "run_id", "mode", "gate_ok", "env_check_ok", "all_expected_resident_before",
    "all_expected_resident_after", "warmup_requests", "stats_consistent", "reload",
    "repeats", "reconcile_ok", "valid", "reasons", "notes",
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _bool_or_none(value: object) -> bool | None:
    """A metadata flag as a boolean: ``True``/``False``, ``"true"``/``"false"``, else ``None``."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        word = value.strip().lower()
        if word in _TRUE_WORDS:
            return True
        if word in _FALSE_WORDS:
            return False
    return None


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def _read_json(path: Path) -> object | None:
    """A JSON file's content, ``None`` if it is missing; unreadable JSON is ``None`` too."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def tidy_frame(records: list[dict[str, object]], columns: tuple[str, ...]) -> pd.DataFrame:
    """A table whose not-applicable cells stay blank and whose counts stay integers.

    ``DataFrame.from_records`` turns a ``None`` into NaN and an integer column
    with a ``None`` in it into floats; neither is what the reader should see. A
    count is shown as ``6``, a not-applicable cell (a cascade column on a single
    model) as blank, and only a figure that could not be computed as ``n/a``.
    """
    def as_int(value: object) -> int | None:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return None
        return int(value)  # type: ignore[call-overload]

    data: dict[str, pd.Series] = {}
    for name in columns:
        values = [record.get(name) for record in records]
        if name in INTEGER_COLUMNS:
            values = [as_int(value) for value in values]
        # dtype=object keeps None as None and 6 as 6; pandas would otherwise
        # infer float64 and print 6.00 and n/a.
        data[name] = pd.Series(values, dtype="object")
    return pd.DataFrame(data)


def config_key(config: str) -> str:
    """Comparable form of a configuration name: ``qwen2.5:7b`` == ``qwen2.5-7b``, any case."""
    return common.sanitise_model_tag(str(config).strip()).lower()


def is_cascade_metadata(metadata: dict) -> bool:
    """The same rule ``reconcile.py`` uses: service_mode cascade, or config ``cascade-*``."""
    return reconcile.run_service_mode(metadata) == reconcile.SERVICE_MODE_CASCADE


def run_config(info: common.RunDirInfo, metadata: dict) -> str:
    """The configuration a run measured: metadata ``config``, else the model or setting."""
    config = str(metadata.get("config") or "").strip()
    if config:
        return config
    if is_cascade_metadata(metadata):
        setting = reconcile.expected_cascade_setting(metadata)
        return f"cascade-{setting}" if setting else info.model
    return str(metadata.get("model_tag") or info.model)


def classify_outcomes(samples: pd.DataFrame) -> pd.Series:
    """``completed`` (HTTP 200), ``errored`` (other number) or ``unfinished`` (not a number)."""
    text = samples["responseCode"].astype("string").fillna("").str.strip()
    # float64, not the nullable Int64 to_numeric returns for a string column: an
    # <NA> in a mask condition would be taken as true and turn an unfinished
    # sample into a completed one.
    numeric = pd.to_numeric(text, errors="coerce").astype("float64")
    outcome = pd.Series("unfinished", index=samples.index, dtype="object")
    outcome = outcome.mask(numeric.notna(), "errored")
    return outcome.mask(numeric == 200, "completed")


def split_halves(samples: pd.DataFrame, completed: pd.Series) -> dict[str, float]:
    """First- and second-half p50 of the completed samples, split at the arrival midpoint."""
    nan = float("nan")
    if samples.empty:
        return {"p50_first_half_ms": nan, "n_first_half": 0, "p50_second_half_ms": nan,
                "n_second_half": 0, "halves_change_pct": nan}
    starts = samples["ts"]
    midpoint = starts.min() + (starts.max() - starts.min()) / 2
    elapsed = pd.to_numeric(samples["elapsed"], errors="coerce")
    first = elapsed[completed & (starts < midpoint)].dropna()
    second = elapsed[completed & (starts >= midpoint)].dropna()
    p_first = common.percentile(first, 0.50)
    p_second = common.percentile(second, 0.50)
    change = (
        100.0 * (p_second - p_first) / p_first
        if _finite(p_first) and _finite(p_second) and p_first > 0
        else nan
    )
    return {"p50_first_half_ms": p_first, "n_first_half": int(len(first)),
            "p50_second_half_ms": p_second, "n_second_half": int(len(second)),
            "halves_change_pct": change}


def queue_wait(tickets: pd.DataFrame) -> dict[str, float]:
    """Median ``ollama_other_ms`` (the queue wait) and median ``queue_residual_ms``."""
    def num(column: str) -> pd.Series:
        return pd.to_numeric(tickets[column], errors="coerce")

    total, load = num("total_duration"), num("load_duration")
    prompt, gen = num("prompt_eval_duration"), num("eval_duration")
    other_ms = ((total - (load + prompt + gen)) / NS_PER_MS).dropna()
    residual_ms = (num("model_latency_ms") - total / NS_PER_MS).dropna()
    return {
        "queue_wait_median_ms": common.percentile(other_ms, 0.50),
        "n_queue_wait": int(len(other_ms)),
        "queue_residual_median_ms": common.percentile(residual_ms, 0.50),
    }


def escalation_counts(tickets: pd.DataFrame) -> tuple[int, int]:
    """(escalated == true lines, all measured POST /tickets lines)."""
    escalated = tickets["escalated"].map(reconcile.as_bool)
    return int((escalated == True).sum()), int(len(tickets))  # noqa: E712


def ticket_lines(log: pd.DataFrame, warm_ids: set[str]) -> pd.DataFrame:
    """Measured ``POST /tickets`` lines of a service log: no warm-up, no other endpoint."""
    log = common.exclude_warmup(log)
    log = log.loc[~reconcile.id_strings(log["request_id"]).isin(warm_ids)]
    return log.loc[(log["endpoint"] == "/tickets") & (log["method"] == "POST")].copy()


def stats_totals(run_dir: Path, metadata: dict) -> tuple[int | None, int | None]:
    """``GET /stats`` totals before and after: metadata first, then the saved bodies."""
    totals: list[int | None] = []
    for key, filename in (("stats_total_before", "stats_before.json"),
                          ("stats_total_after", "stats_after.json")):
        value = _int_or_none(metadata.get(key))
        if value is None:
            body = _read_json(run_dir / filename)
            if isinstance(body, dict):
                value = _int_or_none(body.get("total"))
        totals.append(value)
    return totals[0], totals[1]


def json_ok(path: Path) -> bool | None:
    """``True`` when the file says ``"ok": true``, ``False`` otherwise, ``None`` if missing."""
    if not path.is_file():
        return None
    body = _read_json(path)
    return isinstance(body, dict) and body.get("ok") is True


# ---------------------------------------------------------------------------
# One run
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    """One run's per-run row plus what the per-configuration figures need."""

    info: common.RunDirInfo
    metadata: dict
    row: dict[str, object]
    latencies: pd.Series  # elapsed of the completed samples, for the pooled p95

    @property
    def config(self) -> str:
        return str(self.row["config"])

    @property
    def is_cascade(self) -> bool:
        return is_cascade_metadata(self.metadata)

    @property
    def valid(self) -> bool:
        return bool(self.row["valid"])


def unmeasured_run(info: common.RunDirInfo, metadata: dict) -> RunResult:
    """The row for a run the load-test script deliberately did not measure.

    Every figure is blank (nothing was sent), ``valid`` is false, and the reason
    is the script's own note, so the per-run table still shows that the run was
    attempted and why it does not count. It never contributes to a
    per-configuration figure, because those use valid runs only.
    """
    cascade = is_cascade_metadata(metadata)
    row: dict[str, object] = {name: None for name in RUN_COLUMNS}
    row.update(
        {
            "run_id": info.path.name,
            "config": run_config(info, metadata),
            "cascade_setting": (reconcile.expected_cascade_setting(metadata) or None)
            if cascade else None,
            "rate": info.rate,
            "rate_per_min": parse_rate(info.rate),
            "run_index": info.run_index,
            "mode": metadata.get("mode"),
            "s_seconds": metadata.get("s_seconds"),
            "duration_s": metadata.get("duration_s"),
            "gate_ok": json_ok(info.path / "gate.json") is True,
            "env_check_ok": metadata.get("env_check_ok"),
            "all_expected_resident_before": metadata.get("all_expected_resident_before"),
            "all_expected_resident_after": metadata.get("all_expected_resident_after"),
            "sent": 0,
            "completed": 0,
            "errored": 0,
            "unfinished": 0,
            "valid": False,
            "reasons": "not measured by scripts/run_load_test_a2.sh (metadata measured=false): "
            + str(metadata.get("notes") or "no reason recorded"),
            "notes": "",
        }
    )
    return RunResult(info=info, metadata=metadata, row=row, latencies=pd.Series(dtype="float64"))


def summarise_run(info: common.RunDirInfo, thresholds: Thresholds) -> RunResult:
    """Read one speed_a2 run directory and compute its per-run row.

    Raises :class:`analysis.common.AnalysisError` when the core evidence cannot be
    read. Everything else -- a failed gate, unfinished requests, a queue -- is
    recorded in the row, never a reason to leave the run out.
    """
    run_dir = info.path
    metadata = common.load_metadata(run_dir)
    if metadata.get("measured") is False:
        # scripts/run_load_test_a2.sh keeps the directory of a run it refused to
        # measure (e.g. not every expected model resident -- brief: "Do not start
        # the run until they are"). Playbook section 6: an invalid run is kept and
        # reported, never dropped, so it gets a row of its own with no figures.
        return unmeasured_run(info, metadata)
    jtl = common.read_jtl(run_dir / "results.jtl")
    warm_ids = warmup_request_ids(run_dir, metadata) | reconcile.metadata_warmup_ids(metadata)
    samples, _ = measured_samples(jtl, warm_ids)
    tickets = ticket_lines(common.read_service_log(run_dir / "service.jsonl"), warm_ids)

    cascade = is_cascade_metadata(metadata)
    reasons: list[str] = []
    notes: list[str] = []

    # --- counts -------------------------------------------------------------
    outcome = classify_outcomes(samples)
    completed_mask = outcome == "completed"
    sent = int(len(samples))
    completed = int(completed_mask.sum())
    errored = int((outcome == "errored").sum())
    unfinished = int((outcome == "unfinished").sum())
    sample_ids = (set(reconcile.id_strings(samples["request_id"]))
                  if "request_id" in samples.columns else set())
    log_ids = reconcile.id_strings(tickets["request_id"])
    log_without_sample = int((~log_ids.isin(sample_ids)).sum())
    if sent == 0:
        reasons.append("no measured samples in results.jtl")
    if unfinished:
        notes.append(f"{unfinished} unfinished request(s) (non-HTTP response code): "
                     f"reported, not discarded")
    if "success" in samples.columns:
        flag_mismatch = int((samples["ok"].astype(bool) != completed_mask).sum())
        if flag_mismatch:
            notes.append(f"{flag_mismatch} sample(s) where JMeter's success flag "
                         f"disagrees with HTTP 200")

    # --- GET /stats delta -----------------------------------------------------
    before, after = stats_totals(run_dir, metadata)
    delta = after - before if before is not None and after is not None else None
    equals = None if delta is None else delta == completed
    if delta is None:
        consistent = False
        reasons.append("GET /stats total before/after not recorded")
    elif completed <= delta <= completed + unfinished + log_without_sample:
        consistent = True
        if delta != completed:
            notes.append(f"stats delta {delta} exceeds completed {completed} by "
                         f"{delta - completed}: stored by the service after JMeter gave "
                         f"up on them (unfinished/unrecorded)")
    else:
        consistent = False
        reasons.append(f"stats delta {delta} inconsistent with completed {completed} "
                       f"(unfinished {unfinished})")

    # --- latency ------------------------------------------------------------
    elapsed = pd.to_numeric(samples["elapsed"], errors="coerce")
    latencies = elapsed[completed_mask].dropna()
    p50 = common.percentile(latencies, 0.50)
    halves = split_halves(samples, completed_mask)
    waits = queue_wait(tickets)

    failures: list[str] = []
    change = halves["halves_change_pct"]
    if _finite(change) and change > 100.0 * thresholds.halves_tolerance:
        failures.append(f"second-half p50 {change:+.1f}% vs first half "
                        f"(limit +{100.0 * thresholds.halves_tolerance:g}%)")
    wait = waits["queue_wait_median_ms"]
    if _finite(wait) and wait >= thresholds.queue_wait_ms:
        failures.append(f"median queue wait {wait:.1f} ms "
                        f"(limit < {thresholds.queue_wait_ms:g} ms)")
    if failures:
        no_queue = "queued"
        reasons.append("flagged as queued, not compared on p50: " + "; ".join(failures))
    elif not (_finite(change) and _finite(wait)):
        no_queue = "not computable"
        reasons.append("no-queue check not computable (a half has no completed "
                       "samples, or no line has Ollama timings)")
    else:
        no_queue = "pass"

    span_s = float(client_metrics(samples)["span_s"]) if sent else float("nan")
    throughput = completed / span_s if _finite(span_s) and span_s > 0 else float("nan")
    error_rate = 100.0 * (sent - completed) / sent if sent else float("nan")

    # --- escalation (cascade only) -------------------------------------------
    if cascade:
        n_escalated, n_lines = escalation_counts(tickets)
        fraction = n_escalated / n_lines if n_lines else float("nan")
    else:
        n_escalated = n_lines = None
        fraction = None

    # --- reload, repeats ------------------------------------------------------
    load_ms = (pd.to_numeric(tickets["load_duration"], errors="coerce") / NS_PER_MS).dropna()
    max_load = float(load_ms.max()) if not load_ms.empty else float("nan")
    n_reload = int((load_ms > thresholds.reload_threshold_ms).sum())
    reload_flag = n_reload > 0
    if reload_flag:
        reasons.append(f"loading result: {n_reload} measured request(s) with "
                       f"load_duration > {thresholds.reload_threshold_ms:g} ms "
                       f"(max {max_load:.1f} ms), a model was loaded mid-run")

    rows = (reconcile.id_strings(samples["source_row"])
            if "source_row" in samples.columns else pd.Series(dtype="string"))
    rows = rows[rows != ""]
    repeated_rows = int(rows.duplicated().sum())
    repeats = sent > thresholds.max_tickets or repeated_rows > 0
    if sent > thresholds.max_tickets:
        reasons.append(f"sent {sent} > {thresholds.max_tickets} tickets in the list: "
                       f"tickets repeated within the run (prompt cache)")
    if repeated_rows:
        reasons.append(f"{repeated_rows} sample(s) repeat a source_row already sent "
                       f"in this run (prompt cache)")

    # --- run-level checks -----------------------------------------------------
    mode = str(metadata.get("mode") or "unknown")
    if mode != "real":
        reasons.append(f"mode={mode}: not evidence")
    gate_ok = json_ok(run_dir / "gate.json")
    if gate_ok is None:
        reasons.append("gate.json missing")
    elif not gate_ok:
        reasons.append("gate.json does not show ok: true")
    env_ok = _bool_or_none(metadata.get("env_check_ok"))
    if env_ok is None:
        env_ok = json_ok(run_dir / "env_check.json")
    if env_ok is None:
        reasons.append("environment check not recorded")
    elif not env_ok:
        reasons.append("environment check failed (versions/digests/Ollama settings)")
    resident_before = _bool_or_none(metadata.get("all_expected_resident_before"))
    resident_after = _bool_or_none(metadata.get("all_expected_resident_after"))
    if resident_before is None:
        reasons.append("model residency before the run not recorded")
    elif not resident_before:
        reasons.append("not every expected model was resident before the run "
                       "(ollama ps)")
    if resident_after is False:
        notes.append("not every expected model resident after the run (the pause "
                     "outlasts OLLAMA_KEEP_ALIVE; mid-run reloads are checked by "
                     "load_duration)")
    n_warm = len(warm_ids)
    if n_warm < EXPECTED_WARMUPS:
        reasons.append(f"{n_warm} warm-up request(s) found, {EXPECTED_WARMUPS} required")

    parser = reconcile.build_arg_parser()
    try:
        recon = reconcile.reconcile_run(
            run_dir,
            latency_threshold_ms=parser.get_default("latency_threshold_ms"),
            max_unmatched=parser.get_default("max_unmatched"),
        )
        reconcile_ok = recon.ok
        if not reconcile_ok:
            reasons.append(f"reconcile.py: {len(recon.blockers)} blocker(s); run "
                           f"analysis/reconcile.py --run-dir on this run")
    except common.AnalysisError as exc:
        reconcile_ok = False
        reasons.append(f"reconcile.py could not read the evidence: {exc}")

    valid = not reasons
    row: dict[str, object] = {
        "run_id": run_dir.name,
        "config": run_config(info, metadata),
        "cascade_setting": (reconcile.expected_cascade_setting(metadata) or None)
        if cascade else None,
        "rate": info.rate,
        "rate_per_min": parse_rate(info.rate),
        "run_index": info.run_index,
        "mode": mode,
        "s_seconds": metadata.get("s_seconds"),
        "duration_s": metadata.get("duration_s"),
        "gate_ok": bool(gate_ok),
        "env_check_ok": env_ok,
        "all_expected_resident_before": resident_before,
        "all_expected_resident_after": resident_after,
        "warmup_requests": n_warm,
        "sent": sent,
        "completed": completed,
        "errored": errored,
        "unfinished": unfinished,
        "log_lines_without_sample": log_without_sample,
        "stats_total_before": before,
        "stats_total_after": after,
        "stats_delta": delta,
        "stats_delta_equals_completed": equals,
        "stats_consistent": consistent,
        "p50_ms": p50,
        "n_latency": int(len(latencies)),
        **halves,
        **waits,
        "no_queue_check": no_queue,
        "queued": no_queue == "queued",
        "span_s": span_s,
        "throughput_rps": throughput,
        "error_rate_pct": error_rate,
        "escalated_count": n_escalated,
        "escalation_total": n_lines,
        "escalation_fraction": fraction,
        "accuracy_escalation_fraction": None,
        "escalation_gap_pp": None,
        "escalation_gap_flag": None,
        "max_load_duration_ms": max_load,
        "reload_requests": n_reload,
        "reload": reload_flag,
        "distinct_source_rows": int(rows.nunique()),
        "repeats": repeats,
        "reconcile_ok": reconcile_ok,
        "valid": valid,
        "reasons": "; ".join(reasons),
        "notes": "; ".join(notes),
    }
    return RunResult(info=info, metadata=metadata, row=row, latencies=latencies)


# ---------------------------------------------------------------------------
# Accuracy-test escalation and verdicts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AccuracyEscalation:
    """The escalation fraction of one test-set accuracy run of a cascade setting."""

    run_id: str
    setting: str
    escalated: int
    total: int

    @property
    def fraction(self) -> float:
        return self.escalated / self.total if self.total else float("nan")


def accuracy_setting(metadata: dict) -> str:
    """The cascade setting an accuracy run measured, or ``""`` for a single model."""
    setting = str(metadata.get("cascade_setting") or "").strip().upper()
    if setting:
        return setting
    config = str(metadata.get("config") or "").strip()
    if config.lower().startswith("cascade-"):
        return config[len("cascade-"):].upper()
    return ""


def find_accuracy_escalations(
    root: Path, settings: set[str]
) -> tuple[dict[str, AccuracyEscalation], list[str]]:
    """For each wanted setting, the newest test-set accuracy run's escalation fraction.

    Returns the matches and notes for the report (what was skipped and why). A
    missing root is not an error -- the accuracy test may not have run yet -- but
    a chosen run whose service log cannot be read is.
    """
    notes: list[str] = []
    if not settings:
        return {}, notes
    if not root.is_dir():
        notes.append(f"No accuracy-test directory at `{root}`: the accuracy-test "
                     f"escalation fraction and the gap are not computed.")
        return {}, notes

    candidates: dict[str, list[tuple[str, str, Path, dict]]] = {}
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        metadata_path = child / "metadata.json"
        if not metadata_path.is_file():
            notes.append(f"Skipped `{child.name}`: no metadata.json.")
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise common.AnalysisError(f"{metadata_path} is not valid JSON: {exc}") from exc
        setting = accuracy_setting(metadata)
        if setting not in settings:
            continue
        if metadata.get("rows_set") != "test":
            notes.append(f"Skipped `{child.name}`: rows_set={metadata.get('rows_set')!r}; "
                         f"only test-set accuracy runs are compared.")
            continue
        if metadata.get("mode") == "dev":
            notes.append(f"Skipped `{child.name}`: a dev-mode run is not evidence.")
            continue
        match = _STAMP_RE.search(child.name)
        stamp = match.group(1) if match else str(metadata.get("started_at_utc") or "")
        candidates.setdefault(setting, []).append((stamp, child.name, child, metadata))

    chosen: dict[str, AccuracyEscalation] = {}
    for setting, items in sorted(candidates.items()):
        items.sort(key=lambda item: (item[0], item[1]))
        _, name, path, metadata = items[-1]
        warm_ids = warmup_request_ids(path, metadata) | reconcile.metadata_warmup_ids(metadata)
        tickets = ticket_lines(common.read_service_log(path / "service.jsonl"), warm_ids)
        escalated, total = escalation_counts(tickets)
        chosen[setting] = AccuracyEscalation(name, setting, escalated, total)
        notes.append(f"Setting {setting}: accuracy-test escalation from `{name}` "
                     f"({escalated}/{total} measured POST /tickets lines).")
        if len(items) > 1:
            older = ", ".join(f"`{item[1]}`" for item in items[:-1])
            notes.append(f"Setting {setting}: older test-set accuracy run(s) not used: {older}.")
        recorded_n = _int_or_none(metadata.get("escalated_count"))
        recorded_d = _int_or_none(metadata.get("escalation_denominator"))
        if recorded_n is not None and recorded_d is not None and (
            recorded_n, recorded_d) != (escalated, total):
            notes.append(f"Setting {setting}: `{name}` metadata records "
                         f"{recorded_n}/{recorded_d} escalated (lines with a known "
                         f"escalated value); this report uses {escalated}/{total} from "
                         f"service.jsonl. Check why they differ.")
    for setting in sorted(settings - set(chosen)):
        notes.append(f"Setting {setting}: no test-set accuracy run found under `{root}`; "
                     f"the gap is not computed.")
    return chosen, notes


def load_verdicts(path: Path) -> dict[str, bool]:
    """Part 3's pass/fail table: ``config,passes_accuracy`` with true/false values."""
    if not path.is_file():
        raise common.AnalysisError(f"No such accuracy verdicts file: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = {name.strip() for name in (reader.fieldnames or [])}
        if not {"config", "passes_accuracy"} <= columns:
            raise common.AnalysisError(
                f"{path} must have columns config,passes_accuracy; found "
                f"{sorted(columns)}"
            )
        verdicts: dict[str, bool] = {}
        for lineno, raw in enumerate(reader, 2):
            row = {key.strip(): (value or "").strip() for key, value in raw.items() if key}
            if not row.get("config"):
                continue
            verdict = _bool_or_none(row.get("passes_accuracy", ""))
            if verdict is None:
                raise common.AnalysisError(
                    f"{path}:{lineno}: passes_accuracy must be true or false, got "
                    f"{row.get('passes_accuracy')!r}"
                )
            verdicts[config_key(row["config"])] = verdict
    return verdicts


def attach_accuracy(results: list[RunResult], accuracy: dict[str, AccuracyEscalation],
                    thresholds: Thresholds) -> None:
    """Fill each cascade run's accuracy-test fraction, gap and gap flag."""
    for result in results:
        if not result.is_cascade:
            continue
        acc = accuracy.get(str(result.row["cascade_setting"] or ""))
        fraction = result.row["escalation_fraction"]
        if acc is None or not _finite(acc.fraction):
            continue
        result.row["accuracy_escalation_fraction"] = acc.fraction
        if _finite(fraction):
            gap = 100.0 * (float(fraction) - acc.fraction)
            flag = abs(gap) > thresholds.gap_threshold_pp
            result.row["escalation_gap_pp"] = gap
            result.row["escalation_gap_flag"] = flag
            if flag:
                note = (f"escalation gap {gap:+.1f} pp vs the accuracy test exceeds "
                        f"{thresholds.gap_threshold_pp:g} pp: explain it (brief)")
                result.row["notes"] = "; ".join(
                    part for part in (str(result.row["notes"]), note) if part)


# ---------------------------------------------------------------------------
# Per configuration
# ---------------------------------------------------------------------------

def _config_order(config: str, reference: str) -> tuple[int, str]:
    if config_key(config) == config_key(reference):
        return (0, config)
    return (2 if config.lower().startswith("cascade-") else 1, config_key(config))


def _run_label(result: RunResult, duplicate_index: bool) -> str:
    label = f"run{result.info.run_index}"
    return f"{label}@{result.info.stamp}" if duplicate_index else label


def per_config(
    results: list[RunResult],
    accuracy: dict[str, AccuracyEscalation],
    verdicts: dict[str, bool] | None,
    thresholds: Thresholds,
    reference: str,
) -> tuple[list[dict[str, object]], list[str]]:
    """One row per (configuration, rate), and the loud warnings that go with them."""
    groups: dict[tuple[str, str], list[RunResult]] = {}
    for result in results:
        groups.setdefault((result.config, result.info.rate), []).append(result)

    rows: list[dict[str, object]] = []
    warnings: list[str] = []
    ranges: dict[tuple[str, str], tuple[float, float] | None] = {}
    for key in sorted(groups, key=lambda k: (_config_order(k[0], reference),
                                             parse_rate(k[1]) or 0.0, k[1])):
        config, rate = key
        runs = sorted(groups[key], key=lambda r: (r.info.run_index, r.info.stamp))
        indexes = [r.info.run_index for r in runs]
        counted = [r for r in runs if r.valid]
        cascade = any(r.is_cascade for r in runs)

        listing = []
        for r in runs:
            p50 = r.row["p50_ms"]
            value = f"{p50:.1f}" if _finite(p50) else "n/a"
            status = "" if r.valid else (" [queued]" if r.row["queued"] else " [invalid]")
            listing.append(f"{_run_label(r, indexes.count(r.info.run_index) > 1)}={value}{status}")

        p50s = [float(r.row["p50_ms"]) for r in counted if _finite(r.row["p50_ms"])]
        spread = common.spread(p50s)
        ranges[key] = (spread["min"], spread["max"]) if p50s else None
        pooled = (pd.concat([r.latencies for r in counted], ignore_index=True)
                  if counted else pd.Series(dtype="float64"))
        throughput = common.spread([r.row["throughput_rps"] for r in counted])["mean"]
        error_rate = common.spread([r.row["error_rate_pct"] for r in counted])["mean"]

        warning: list[str] = []
        if len(runs) < MIN_RUNS_PER_CONFIG:
            warning.append(f"FEWER THAN {MIN_RUNS_PER_CONFIG} RUNS (n={len(runs)})")
            warnings.append(
                f"{config} at {rate}: only {len(runs)} run(s) found. The brief requires "
                f"{MIN_RUNS_PER_CONFIG} runs per configuration; do not report this "
                f"configuration until the missing runs exist."
            )
        if len(counted) < MIN_RUNS_PER_CONFIG:
            warning.append(f"ONLY {len(counted)} VALID RUN(S)")
            warnings.append(
                f"{config} at {rate}: {len(counted)} of {len(runs)} run(s) valid. The "
                f"per-configuration figures use valid runs only; a configuration is done "
                f"with {MIN_RUNS_PER_CONFIG} valid runs (docs/playbooks/cascade-test.md "
                f"section 7). Re-run only for a reason in section 6, and keep the invalid run."
            )

        setting = next((str(r.row["cascade_setting"]) for r in runs
                        if r.row["cascade_setting"]), None) if cascade else None
        esc_count = esc_total = None
        esc_fraction = gap = gap_flag = None
        acc = accuracy.get(setting or "") if cascade else None
        if cascade:
            esc_count = sum(int(r.row["escalated_count"] or 0) for r in counted)
            esc_total = sum(int(r.row["escalation_total"] or 0) for r in counted)
            esc_fraction = esc_count / esc_total if esc_total else float("nan")
            if acc is not None and _finite(acc.fraction) and _finite(esc_fraction):
                gap = 100.0 * (esc_fraction - acc.fraction)
                gap_flag = abs(gap) > thresholds.gap_threshold_pp
                if gap_flag:
                    warnings.append(
                        f"{config}: escalation under load {100 * esc_fraction:.1f}% vs "
                        f"{100 * acc.fraction:.1f}% in the accuracy test, a gap of "
                        f"{gap:+.1f} pp (> {thresholds.gap_threshold_pp:g} pp). The brief: "
                        f"explain any large gap."
                    )

        verdict = None if verdicts is None else verdicts.get(config_key(config))
        passes = "unknown" if verdict is None else ("true" if verdict else "false")
        label = {"true": "", "false": "not passing accuracy",
                 "unknown": "accuracy verdict unknown"}[passes]
        if passes == "false":
            warnings.append(f"{config}: NOT PASSING ACCURACY. Its speed is reported, marked "
                            f"as such (brief, Step 4), and it cannot be recommended.")

        rows.append({
            "config": config,
            "cascade_setting": setting,
            "rate": rate,
            "n_runs": len(runs),
            "n_valid_runs": len(counted),
            "runs_counted": ";".join(_run_label(r, indexes.count(r.info.run_index) > 1)
                                     for r in counted),
            "p50_per_run_ms": "; ".join(listing),
            "p50_mean_ms": spread["mean"],
            "p50_min_ms": spread["min"],
            "p50_max_ms": spread["max"],
            "p50_sd_ms": spread["sd"],
            "pooled_p95_ms": common.percentile(pooled, 0.95),
            "pooled_n": int(len(pooled)),
            "throughput_mean_rps": throughput,
            "error_rate_mean_pct": error_rate,
            "sent_total": sum(int(r.row["sent"] or 0) for r in runs),
            "completed_total": sum(int(r.row["completed"] or 0) for r in runs),
            "errored_total": sum(int(r.row["errored"] or 0) for r in runs),
            "unfinished_total": sum(int(r.row["unfinished"] or 0) for r in runs),
            "escalated_count": esc_count,
            "escalation_total": esc_total,
            "escalation_fraction": esc_fraction,
            "accuracy_run_id": acc.run_id if acc else None,
            "accuracy_escalated_count": acc.escalated if acc else None,
            "accuracy_escalation_total": acc.total if acc else None,
            "accuracy_escalation_fraction": acc.fraction if acc else None,
            "escalation_gap_pp": gap,
            "escalation_gap_flag": gap_flag,
            "passes_accuracy": passes,
            "label": label,
            "faster_than_reference": "",
            "warning": "; ".join(warning),
        })

    # The "fastest" rule, against the reference at the same rate.
    reference_keys = {k for k in groups if config_key(k[0]) == config_key(reference)}
    if not reference_keys:
        warnings.append(f"No {reference} runs found: no configuration can be shown to be "
                        f"faster than the reference (prediction_record_a2.md section 4).")
    for row in rows:
        key = (str(row["config"]), str(row["rate"]))
        ref_key = next((k for k in reference_keys if k[1] == key[1]), None)
        if key in reference_keys:
            verdict_text = "reference"
        elif ref_key is None or ranges.get(ref_key) is None:
            verdict_text = f"not comparable: no valid {reference} runs at this rate"
        elif ranges.get(key) is None:
            verdict_text = "not comparable: no valid runs"
        else:
            low, high = ranges[key]  # type: ignore[misc]
            ref_low, ref_high = ranges[ref_key]  # type: ignore[misc]
            if high < ref_low:
                verdict_text = "yes: distinguishably faster"
            elif low > ref_high:
                verdict_text = "no: slower"
            else:
                verdict_text = "no: not distinguishable (p50 ranges overlap)"
        row["faster_than_reference"] = verdict_text
    return rows, warnings


def consistency_warnings(results: list[RunResult]) -> list[str]:
    """Rate, run length, S and ticket list must be the same for every run (brief, Set-up)."""
    warnings: list[str] = []
    checks = {
        "rate": lambda r: r.info.rate,
        "s_seconds": lambda r: r.metadata.get("s_seconds"),
        "duration_s": lambda r: r.metadata.get("duration_s"),
        "response_timeout_ms": lambda r: r.metadata.get("response_timeout_ms"),
        "ticket_list": lambda r: r.metadata.get("ticket_list"),
    }
    for name, getter in checks.items():
        values = {json.dumps(getter(r), sort_keys=True) for r in results
                  if getter(r) is not None}
        if len(values) > 1:
            warnings.append(
                f"Runs differ in {name} ({', '.join(sorted(values))}). The brief: use the "
                f"same rate, run length and ticket list for every configuration."
            )
    return warnings


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def thresholds_md(thresholds: Thresholds, reference: str) -> str:
    tol = 100.0 * thresholds.halves_tolerance
    return "\n".join([
        "## Thresholds in force",
        "",
        "| Threshold | Value | Source |",
        "|---|---|---|",
        f"| No-queue check: second-half p50 vs first half | at most +{tol:g}% | "
        "`predictions/prediction_record_a2.md` section 4 |",
        f"| No-queue check: median queue wait (`ollama_other_ms`) | under "
        f"{thresholds.queue_wait_ms:g} ms | `predictions/prediction_record_a2.md` section 4 |",
        f"| Large escalation gap (speed vs accuracy test) | more than "
        f"{thresholds.gap_threshold_pp:g} pp | `predictions/prediction_record_a2.md` section 4 |",
        f"| Reload (loading result) | any measured `load_duration` above "
        f"{thresholds.reload_threshold_ms:g} ms | `TODO_A2.md` 1.1, "
        "`docs/playbooks/cascade-test.md` section 5 |",
        f"| Ticket list size (repeats) | at most {thresholds.max_tickets} sent | "
        "`workload/speed_test_rows_a2.txt`, `docs/playbooks/cascade-test.md` section 5 |",
        f"| Runs per configuration | {MIN_RUNS_PER_CONFIG} valid | brief, Step 4 |",
        f"| Warm-up requests per run | at least {EXPECTED_WARMUPS} | brief, Step 4 \"Each run\" |",
        "| Reconciliation | `analysis/reconcile.py` defaults | `docs/playbooks/cascade-test.md` section 7 |",
        f"| Reference configuration | `{reference}` | brief, The Task; `prediction_record_a2.md` section 4 |",
        "",
    ])


def build_report(
    runs_root: Path,
    per_run: pd.DataFrame,
    per_cfg: pd.DataFrame,
    flags: list[str],
    warnings: list[str],
    accuracy_notes: list[str],
    thresholds: Thresholds,
    reference: str,
    verdicts_path: Path | None,
) -> str:
    """The tables, definitions, thresholds and every flag, in one page."""
    parts: list[str] = [
        "# Assignment 2 speed-test summary",
        "",
        f"Source: `{runs_root}` -- {len(per_run)} speed_a2 run(s), "
        f"{len(per_cfg)} configuration(s). Generated by `analysis/summarise_load_a2.py`. "
        "Every figure comes from a `.jtl` or a service-log line in the run directories "
        "named below; nothing is entered by hand.",
        "",
        "No Assignment 1 speed figure is used. Only `*_speed_a2_*` run directories are "
        "read; the Assignment 1 load tables in `analysis/output/load/` are not.",
        "",
        "**Not reported:** no 99th-percentile figure appears anywhere in this output. "
        "The brief, Step 4: the sample is too small for it. The tail is described by the "
        "p95 pooled over a configuration's valid runs, stated with the number of samples "
        "it is based on (`pooled_n`).",
        "",
        "Accuracy verdicts: "
        + (f"`{verdicts_path}`." if verdicts_path else
           "none supplied (`--accuracy-verdicts`); every configuration is "
           "\"accuracy verdict unknown\" until Part 3's pass/fail table is passed in."),
        "",
    ]
    if warnings:
        parts += ["## Warnings -- read before quoting any of these numbers", "",
                  *(f"* **{line}**" for line in warnings), ""]
    parts += ["## Run flags", ""]
    parts += [*(f"* {line}" for line in flags)] if flags else [
        "None: every run passed every check."]
    parts += [
        "",
        "## Per configuration",
        "",
        "Figures over the valid runs only; `p50_per_run_ms` lists every run. A queued "
        "run is listed `[queued]` and is not compared on p50.",
        "",
        common.to_markdown_table(per_cfg, float_format="{:.2f}"),
        "",
        "## Per run: counts and latency",
        "",
        "Every run is here, including runs with unfinished requests and invalid runs.",
        "",
        common.to_markdown_table(per_run[list(REPORT_RUN_FIGURES)], float_format="{:.2f}"),
        "",
        "## Per run: validity checks",
        "",
        common.to_markdown_table(per_run[list(REPORT_RUN_CHECKS)], float_format="{:.2f}"),
        "",
        "`per_run.csv` holds every per-run column, including the halves' sample counts, "
        "the `GET /stats` totals and `queue_residual_median_ms`.",
        "",
        "## Accuracy-test escalation source",
        "",
        *([f"* {line}" for line in accuracy_notes] or ["* No cascade runs."]),
        "",
        DEFINITIONS_MD,
        thresholds_md(thresholds, reference),
        "## Reconciliation",
        "",
        "`reconcile_ok` is `analysis/reconcile.py` run on each run with its default "
        "thresholds, including the Assignment 2 \"which model answered\" checks. Run "
        "`python analysis/reconcile.py --run-dir <run>` for its full report.",
        "",
    ]
    return "\n".join(parts)


def run_flags(results: list[RunResult]) -> list[str]:
    """One line per run that is not clean: what is wrong, and what is merely noted."""
    lines: list[str] = []
    for result in results:
        row = result.row
        status = "VALID" if row["valid"] else ("QUEUED" if row["queued"] else "INVALID")
        if row["reasons"] or row["notes"]:
            text = f"`{row['run_id']}` ({row['config']}): {status}"
            if row["reasons"]:
                text += f" -- {row['reasons']}"
            if row["notes"]:
                text += f" (notes: {row['notes']})"
            lines.append(text)
    return lines


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    defaults = Thresholds()
    parser = argparse.ArgumentParser(
        prog="analysis/summarise_load_a2.py",
        description=(
            "Summarise the Assignment 2 speed-test runs (plan speed_a2): per run, "
            "sent/completed/errored/unfinished, p50, first/second-half p50 and queue "
            "wait (no-queue check), throughput, error rate, escalation fraction, "
            "reload and repeat flags; per configuration, p50 mean and spread, pooled "
            "p95 with its count, and whether it is distinguishably faster than "
            "qwen2.5:7b. No 99th percentile is reported."
        ),
        epilog=(
            "Exits non-zero if no speed_a2 run exists, if a run's metadata.json, "
            "results.jtl or service.jsonl cannot be read, or if --out-dir is the "
            "Assignment 1 load output."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS,
                        help="directory holding the run directories; only speed_a2 ones are read")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                        help="where per_run, per_config and report.md are written")
    parser.add_argument("--accuracy-root", type=Path, default=DEFAULT_ACCURACY_ROOT,
                        help="Assignment 2 accuracy runs, for the accuracy-test escalation "
                             "fraction (optional: skipped if absent)")
    parser.add_argument("--accuracy-verdicts", type=Path, default=None,
                        help="CSV with columns config,passes_accuracy (true/false), from Part 3")
    parser.add_argument("--reference-config", default=REFERENCE_CONFIG,
                        help="the configuration every other one must beat")
    parser.add_argument("--halves-tolerance", type=float, default=defaults.halves_tolerance,
                        help="no-queue check: max |second-half p50 / first-half p50 - 1|")
    parser.add_argument("--queue-wait-ms", type=float, default=defaults.queue_wait_ms,
                        help="no-queue check: median queue wait must be under this")
    parser.add_argument("--gap-threshold-pp", type=float, default=defaults.gap_threshold_pp,
                        help="flag speed vs accuracy-test escalation gaps above this (pp)")
    parser.add_argument("--reload-threshold-ms", type=float,
                        default=defaults.reload_threshold_ms,
                        help="a measured load_duration above this means a mid-run model load")
    parser.add_argument("--max-tickets", type=int, default=defaults.max_tickets,
                        help="size of the fixed ticket list; more samples than this repeat tickets")
    return parser


def select_speed_runs(runs_root: Path) -> list[common.RunDirInfo]:
    """Every speed_a2 run directory under ``runs_root``; raises if there are none."""
    found = common.iter_run_dirs(runs_root)
    selected = [info for info in found if info.plan == common.A2_SPEED_PLAN]
    if not selected:
        raise common.AnalysisError(
            f"No {common.A2_SPEED_PLAN} run directories in {runs_root} "
            f"(<stamp>_<config>_{common.A2_SPEED_PLAN}_<rate>_run<k>). Found "
            f"{len(found)} other run(s), which are Assignment 1 and are never used here."
        )
    return selected


def check_out_dir(out_dir: Path) -> None:
    """Refuse the Assignment 1 load directory (TODO_A2.md guardrail 10)."""
    resolved = out_dir.resolve()
    forbidden = A1_LOAD_OUT_DIR.resolve()
    if resolved == forbidden or forbidden in resolved.parents:
        raise common.AnalysisError(
            f"--out-dir {out_dir} is the Assignment 1 load output. Assignment 2 speed "
            f"figures go to {DEFAULT_OUT_DIR} so they can never be mixed with A1's."
        )


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the process exit status."""
    args = build_arg_parser().parse_args(argv)
    thresholds = Thresholds(
        halves_tolerance=args.halves_tolerance,
        queue_wait_ms=args.queue_wait_ms,
        gap_threshold_pp=args.gap_threshold_pp,
        reload_threshold_ms=args.reload_threshold_ms,
        max_tickets=args.max_tickets,
    )
    try:
        check_out_dir(args.out_dir)
        selected = select_speed_runs(args.runs)
        results = [summarise_run(info, thresholds) for info in selected]
        settings = {str(r.row["cascade_setting"]) for r in results
                    if r.is_cascade and r.row["cascade_setting"]}
        accuracy, accuracy_notes = find_accuracy_escalations(args.accuracy_root, settings)
        verdicts = (load_verdicts(args.accuracy_verdicts)
                    if args.accuracy_verdicts is not None else None)
    except common.AnalysisError as exc:
        print(f"{PROG}: FAILED: {exc}", file=sys.stderr)
        return 1

    attach_accuracy(results, accuracy, thresholds)
    results.sort(key=lambda r: (_config_order(r.config, args.reference_config),
                                parse_rate(r.info.rate) or 0.0, r.info.rate,
                                r.info.run_index, r.info.stamp))
    config_rows, warnings = per_config(results, accuracy, verdicts, thresholds,
                                       args.reference_config)
    warnings = consistency_warnings(results) + warnings
    dev_runs = sorted(r.info.path.name for r in results if r.row["mode"] != "real")
    if dev_runs:
        warnings.insert(0, "Runs not in real mode (" + ", ".join(dev_runs) + ") are NOT "
                        "evidence and are never counted as valid.")

    per_run = tidy_frame([r.row for r in results], RUN_COLUMNS)
    per_cfg = tidy_frame(config_rows, CONFIG_COLUMNS)
    if per_run.empty or per_cfg.empty:  # cannot happen after select_speed_runs; be loud anyway
        print(f"{PROG}: FAILED: no rows to write", file=sys.stderr)
        return 1

    out_dir: Path = args.out_dir
    common.write_table(per_run, out_dir, "per_run", float_format="{:.2f}")
    common.write_table(per_cfg, out_dir, "per_config", float_format="{:.2f}")
    report = build_report(args.runs, per_run, per_cfg, run_flags(results), warnings,
                          accuracy_notes, thresholds, args.reference_config,
                          args.accuracy_verdicts)
    report_path = out_dir / "report.md"
    report_path.write_text(report, encoding="utf-8")

    n_valid = int(per_run["valid"].astype(bool).sum())
    print(f"{PROG}: {len(results)} speed_a2 run(s) from {args.runs}, {n_valid} valid, "
          f"{len(per_cfg)} configuration(s)")
    print(f"{PROG}: wrote {out_dir / 'per_run.csv'}, {out_dir / 'per_config.csv'}, "
          f"{report_path}")
    sys.stdout.flush()
    for line in warnings:
        print(f"{PROG}: WARNING: {line}", file=sys.stderr)
    for result in results:
        if not result.valid:
            print(f"{PROG}: FLAG: {result.row['run_id']}: {result.row['reasons']}",
                  file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
