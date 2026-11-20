"""Reconcile one run's JMeter ``.jtl`` against the service's own request log.

Owner: Yeo Kai Yuan (technical core). Feeds the instrumentation claim on Slide 9
and the "every number reconciles with the logs" requirement in the brief.

The brief is blunt about this: *"a number that cannot be traced to a log entry is
treated as unsupported, and you may be asked to produce and explain your logs"*,
and fabricated or irreconcilable numbers are treated as an academic integrity
matter rather than a marking deduction. So before any figure from a run is
quoted, that run has to pass here.

How the join works
------------------
Each JMeter sampler generates a per-iteration ``request_id`` (a ``__UUID()`` in a
User Parameters pre-processor), sends it as ``X-Request-ID``, and the run script
passes ``-Jsample_variables=request_id,source_row`` so JMeter writes both values
as extra columns in the CSV ``.jtl``. The service logs the same
``request_id``/``source_row`` on the line it writes for that request. The join is
therefore an inner join on ``request_id``: one ``.jtl`` sample, one log line.

What is checked, and why each failure means the run cannot be reported
---------------------------------------------------------------------
* **``.jtl`` samples with no log line.** A sample that the service never logged
  is a latency number in our slides with nothing behind it. If we are asked to
  produce the log entry for it, there is none. Blocker when the count exceeds
  ``--max-unmatched`` (default 0).
* **Log lines with no ``.jtl`` sample.** The service handled traffic that the
  load generator did not record: either something other than our test was
  talking to the service, or the log slice does not cover the run window. Either
  way the denominators (error rate, throughput) are wrong. Blocker on the same
  threshold.
* **Duplicate ``request_id`` on either side.** The join is then ambiguous, so
  "the log line behind this sample" is not a well-defined phrase any more. Under
  our plan configuration a duplicate means ``__UUID()`` was not re-evaluated per
  iteration, which also means the join is not trustworthy anywhere else in the
  run. Blocker.
* **Rows with no ``request_id`` at all.** Nothing can be joined to them, and the
  sample variables must therefore not have been captured on that side. Blocker,
  counted separately from the duplicates so the report says which defect it is.
* **Response code disagreement.** The client says 200 and the service logged 502
  (or the reverse). One of the two instruments is wrong about what happened, so
  neither the error rate nor the success-only throughput can be defended.
  Blocker, with no tolerance: this is not a statistical quantity.
* **``source_row`` disagreement.** The load generator says it posted the
  narrative from row X and the service logged row Y. The traffic we measured is
  then not the traffic we think we measured, and the accuracy and length
  distributions no longer line up with the workload model. Blocker when both
  sides carry a value and the values differ (a missing value on one side is
  reported as a warning instead, since a plan may legitimately omit the header).
* **Client-minus-server latency difference.** ``elapsed`` (client-observed) minus
  ``total_latency_ms`` (the handler's own wall clock) is network plus framework
  overhead and should be small and stable. A large p99 means either the load
  generator is saturated -- in which case the latency we are reporting is partly
  our own test rig, which the brief explicitly rejects -- or the two clocks
  disagree, in which case the join is still sound but the numbers are not
  comparable. Blocker when the p99 of the **absolute** difference exceeds
  ``--latency-threshold-ms`` (default 250). The absolute value is used for the
  gate because a *negative* difference, the server claiming to have taken longer
  than the client observed, is physically impossible beyond clock granularity and
  is even stronger evidence of a clock problem; the signed percentiles are
  reported alongside so the direction is visible.

Warm-up requests are not part of the measured set and are excluded here too: the
warm-up ``request_id`` comes from ``warmup.jsonl`` and from ``metadata.json``
(``warmup_request_id``, and for an Assignment 2 run the ``warmup_request_ids``
list), and ``exclude_warmup()`` is applied to the service log as a
belt-and-braces guard. Counting the warm-up as an unmatched log line would be a
false alarm, because JMeter never sampled it.

Assignment 2: which model answered (cascade and single-model speed runs)
------------------------------------------------------------------------
An Assignment 2 run's ``metadata.json`` carries ``service_mode`` (and
``config``). The join is still on ``request_id``; what is added is a check, on
every measured ``POST /tickets`` log line, that the line's "which model answered"
fields agree with the configuration the run says it measured. Without this the
escalation fraction on Slide 5 would be asserted rather than derived.

For a **cascade** run (``service_mode == "cascade"`` or ``config`` starting
``cascade-``):

* ``cascade_escalated_logged`` -- every line written by the ``POST /tickets``
  handler (HTTP 200 or 502) has ``escalated`` true or false, never null. Blocker:
  a null there means a single-model service answered, or the line cannot be
  counted. A null on a 422/500 line is a warning only: those lines come from the
  validation and unhandled-error handlers, which never reach a model and log every
  model field as null by design.
* ``cascade_setting_matches_metadata`` / ``cascade_small_model_matches_metadata``
  -- the line's ``cascade_setting`` and ``small_model_tag`` equal the metadata's
  ``cascade_setting`` and ``cascade_small_model_tag``. Blocker: the run measured
  a different cascade from the one it is labelled as.
* ``cascade_answering_model_consistent`` -- on every HTTP 200 line, ``model_tag``
  is the large model (``cascade_large_model_tag``) exactly when ``escalated`` is
  true, and the small model exactly when it is false. Blocker: the log
  contradicts itself about which model produced the answer.
* ``cascade_small_category_logged`` -- ``small_model_category`` is null only
  when the ticket was escalated (the length rule skips the small call) or the
  request failed. Warning otherwise: an accepted answer whose small-model
  category is missing cannot be traced.
* ``cascade_escalation_fraction`` -- informational: escalated-true lines over
  measured ``POST /tickets`` lines.

For **every** Assignment 2 run, a matched sample JMeter recorded with no HTTP
status (``Non HTTP response code: ...``: the client timed out or was cut off
while the service went on to finish and log the request) is an **unfinished
request**. The brief says a run with unfinished requests "is reported as such,
not thrown away", and the playbook does not treat them as a validity failure, so
such a sample is listed as ``unfinished_request`` and counted by the
``unfinished_requests`` check (a warning) instead of as a status disagreement,
and it is left out of the client-minus-server gap, since the client never waited
for the response. A sample with no log line at all is still a blocker.

For a **single-model** Assignment 2 run (``service_mode == "single"``):
``single_mode_cascade_fields_null`` (all six cascade fields null on every line)
and ``single_mode_model_tag_matches_metadata`` (``model_tag`` equals the
metadata's ``model_tag`` on every 200/502 line). Both blockers.

An Assignment 1 run has no ``service_mode`` key, so none of these checks is
added and its report is exactly what it was before Assignment 2.

Exit status
-----------
0 when the run reconciles (warnings may still be printed), 1 when any blocker
above fires or the evidence cannot be read at all. Silence is not an option: the
whole point of the script is to refuse to bless a run quietly.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# ``python analysis/reconcile.py`` puts ``analysis/`` on sys.path, not the
# repository root, so make the root importable before touching our own packages.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis import common  # noqa: E402  (after the sys.path bootstrap)
from analysis.summarise_load import warmup_request_ids  # noqa: E402

#: How many offending rows are listed in the markdown before it says "and N more".
#: The CSV always carries every row; the markdown is for reading.
MAX_LISTED_ROWS = 50

_BLOCKER = "BLOCKER"
_WARN = "WARN"
_PASS = "pass"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def status_strings(values: pd.Series) -> pd.Series:
    """Render HTTP status codes as comparable strings.

    JMeter writes ``responseCode`` as text and pandas may read it as an integer,
    while the service log's ``status`` is always an integer, so ``"200"``, ``200``
    and ``200.0`` must all compare equal. JMeter also writes non-numeric codes
    such as ``"Non HTTP response code: java.net.SocketTimeoutException"`` when
    the request never reached the service; those are passed through unchanged so
    they show up as the mismatch they are.
    """
    text = values.astype("string").fillna("").str.strip()
    numeric = pd.to_numeric(text, errors="coerce")
    return numeric.astype("Int64").astype("string").fillna(text)


def id_strings(values: pd.Series) -> pd.Series:
    """Normalise an identifier column to stripped strings, ``<NA>`` becoming ``""``."""
    return values.astype("string").fillna("").str.strip()


def _verdict_for_unmatched(count: int, max_unmatched: int) -> str:
    """Blocker above the tolerance, warning inside it, pass at zero.

    An unmatched sample that ``--max-unmatched`` forgives is still an unmatched
    sample: it is reported as a warning rather than disappearing, so that a team
    that raised the tolerance has to say out loud that it did.
    """
    if count > max_unmatched:
        return _BLOCKER
    return _WARN if count else _PASS


def duplicate_counts(ids: pd.Series) -> dict[str, int]:
    """``{request_id: occurrences}`` for every identifier appearing more than once."""
    counts = ids.value_counts()
    return {str(key): int(value) for key, value in counts.items() if value > 1}


# ---------------------------------------------------------------------------
# Assignment 2: service mode and "which model answered"
# ---------------------------------------------------------------------------

SERVICE_MODE_CASCADE = "cascade"
SERVICE_MODE_SINGLE = "single"

#: The statuses the ``POST /tickets`` handler itself writes: a classified ticket
#: (200) or a failed model call (502). The 422 and 500 handlers never reach a
#: model and log every model field, the cascade fields included, as null.
_TICKET_HANDLER_STATUSES = (200, 502)

#: Columns of the Assignment 2 per-line problem table.
MODE_PROBLEM_COLUMNS = ["problem", "request_id", "status", "expected", "logged", "note"]


def run_service_mode(metadata: dict) -> str | None:
    """``"cascade"``, ``"single"``, or ``None`` for an Assignment 1 run.

    A run is a cascade run when ``metadata.json`` says ``service_mode ==
    "cascade"`` or its ``config`` starts with ``cascade-``; a single-model
    Assignment 2 run when ``service_mode == "single"``. Assignment 1 metadata has
    neither key, which is what keeps its reconciliation unchanged.
    """
    mode = metadata.get("service_mode")
    config = str(metadata.get("config") or "")
    if mode == SERVICE_MODE_CASCADE or config.lower().startswith("cascade-"):
        return SERVICE_MODE_CASCADE
    if mode == SERVICE_MODE_SINGLE:
        return SERVICE_MODE_SINGLE
    return None


def metadata_warmup_ids(metadata: dict) -> set[str]:
    """The Assignment 2 ``warmup_request_ids`` list (empty for Assignment 1 metadata)."""
    listed = metadata.get("warmup_request_ids")
    if not isinstance(listed, list):
        return set()
    return {str(value) for value in listed if isinstance(value, str) and value}


def as_bool(value: object) -> bool | None:
    """A log line's ``escalated`` as a real boolean, or ``None`` when absent.

    JSON ``true``/``false`` arrive as ``bool`` (or ``numpy.bool_`` in an all-bool
    column). Anything else that is not null is not a value the schema allows, and
    is treated as absent so that it is counted rather than guessed at.
    """
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None
    if isinstance(value, bool):
        return value
    if type(value).__name__ == "bool_":  # numpy.bool_, without importing numpy
        return bool(value)
    return None


def _text(value: object) -> str:
    """A log or metadata value as stripped text, null becoming ``""``."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def expected_cascade_setting(metadata: dict) -> str:
    """The setting a cascade run measured: ``cascade_setting``, else ``config``'s suffix."""
    setting = _text(metadata.get("cascade_setting"))
    if setting:
        return setting
    config = _text(metadata.get("config"))
    if config.lower().startswith("cascade-"):
        return config[len("cascade-"):].upper()
    return ""


def _mode_problem(problem: str, row: pd.Series, expected: str, logged: str,
                  note: str) -> dict[str, object]:
    status = pd.to_numeric(pd.Series([row.get("status")]), errors="coerce").iloc[0]
    return {
        "problem": problem,
        "request_id": _text(row.get("request_id")),
        "status": "" if pd.isna(status) else str(int(status)),
        "expected": expected,
        "logged": logged,
        "note": note,
    }


def cascade_checks(
    tickets: pd.DataFrame, metadata: dict
) -> tuple[list[Check], list[dict[str, object]]]:
    """The "which model answered" checks for a cascade run's measured POST /tickets lines."""
    setting = expected_cascade_setting(metadata)
    small = _text(metadata.get("cascade_small_model_tag"))
    large = _text(metadata.get("cascade_large_model_tag"))
    if not large:
        # In cascade mode MODEL_TAG is the large model, but a run script may
        # label a cascade's model_tag with its configuration ("cascade-A"),
        # which is not a model and must not be taken for one.
        fallback = _text(metadata.get("model_tag"))
        large = "" if fallback.lower().startswith("cascade") else fallback

    status = pd.to_numeric(tickets["status"], errors="coerce")
    escalated = tickets["escalated"].map(as_bool)
    from_handler = status.isin(_TICKET_HANDLER_STATUSES)
    total = int(len(tickets))
    rows: list[dict[str, object]] = []

    # 1. escalated is logged on every line the handler wrote.
    missing_handler = from_handler & escalated.isna()
    missing_other = (~from_handler) & escalated.isna()
    for _, row in tickets.loc[missing_handler].iterrows():
        rows.append(_mode_problem(
            "escalated_not_logged", row, "true|false", "null",
            "a POST /tickets line from a cascade run must say whether it escalated"))
    for _, row in tickets.loc[missing_other].iterrows():
        rows.append(_mode_problem(
            "escalated_not_logged_error_handler", row, "true|false", "null",
            "written by the 422/500 handler, which never reaches a model"))
    n_handler_missing = int(missing_handler.sum())
    n_other_missing = int(missing_other.sum())
    checks = [
        Check(
            name="cascade_escalated_logged",
            value=f"null on {n_handler_missing} of {int(from_handler.sum())} 200/502 "
                  f"line(s); {n_other_missing} 422/500 line(s)",
            limit="0 null on 200/502 lines",
            verdict=(_BLOCKER if n_handler_missing
                     else _WARN if n_other_missing else _PASS),
            detail=(
                "a line with no escalated value cannot be counted towards the "
                "escalation fraction, or was not written by a cascade service"
                if n_handler_missing
                else "only error-handler lines (422/500, no model call) lack escalated"
                if n_other_missing
                else "every measured POST /tickets line records whether it escalated"
            ),
        )
    ]

    # 2. cascade_setting and 3. small_model_tag agree with the metadata.
    for name, field_name, expected, problem, what in (
        ("cascade_setting_matches_metadata", "cascade_setting", setting,
         "cascade_setting_disagreement", "cascade_setting"),
        ("cascade_small_model_matches_metadata", "small_model_tag", small,
         "small_model_tag_disagreement", "cascade_small_model_tag"),
    ):
        handler_lines = tickets.loc[from_handler]
        logged = handler_lines[field_name].map(_text)
        bad = logged != expected if expected else pd.Series(True, index=logged.index)
        for (_, row), value in zip(handler_lines.loc[bad].iterrows(), logged.loc[bad]):
            rows.append(_mode_problem(
                problem, row, expected or "(not in metadata.json)", value or "null",
                f"the line's {field_name} is not the run's {what}"))
        n_bad = int(bad.sum())
        checks.append(
            Check(
                name=name,
                value=str(n_bad),
                limit="0",
                verdict=_BLOCKER if (n_bad or not expected) else _PASS,
                detail=(
                    f"metadata.json records no {what}, so the lines cannot be checked"
                    if not expected
                    else f"{n_bad} line(s) measured a different cascade from the one "
                         f"this run is labelled as ({what} = {expected})"
                    if n_bad
                    else f"every 200/502 line has {field_name} = {expected}"
                ),
            )
        )

    # 4. The answering model agrees with escalated, on every classified ticket.
    answered = (status == 200) & escalated.notna()
    n_answer_bad = 0
    for (_, row), was_escalated in zip(tickets.loc[answered].iterrows(),
                                       escalated.loc[answered]):
        want = large if was_escalated else small
        got = _text(row.get("model_tag"))
        if not want or got != want:
            n_answer_bad += 1
            rows.append(_mode_problem(
                "answering_model_disagreement", row,
                want or "(not in metadata.json)", got or "null",
                "escalated=true must be answered by the large model, "
                "escalated=false by the small model"
                if was_escalated is not None else ""))
    tags_known = bool(small and large)
    checks.append(
        Check(
            name="cascade_answering_model_consistent",
            value=str(n_answer_bad),
            limit="0",
            verdict=_BLOCKER if (n_answer_bad or not tags_known) else _PASS,
            detail=(
                "metadata.json does not name both cascade models "
                "(cascade_small_model_tag, cascade_large_model_tag)"
                if not tags_known
                else "the log contradicts itself about which model produced the answer"
                if n_answer_bad
                else f"every HTTP 200 line names {large} when escalated and {small} "
                     f"when not"
            ),
        )
    )

    # 5. small_model_category is missing only where it legitimately can be.
    small_category_missing = tickets["small_model_category"].map(_text) == ""
    unexplained = small_category_missing & (status == 200) & (escalated == False)  # noqa: E712
    for _, row in tickets.loc[unexplained].iterrows():
        rows.append(_mode_problem(
            "small_model_category_missing", row, "the small model's category", "null",
            "an accepted (not escalated) answer must record what the small model said"))
    n_unexplained = int(unexplained.sum())
    checks.append(
        Check(
            name="cascade_small_category_logged",
            value=str(n_unexplained),
            limit="0",
            verdict=_WARN if n_unexplained else _PASS,
            detail=(
                "accepted answers with no small_model_category cannot be traced "
                "to the small model's own reply"
                if n_unexplained
                else "small_model_category is null only on escalated (length rule) "
                     "or failed requests"
            ),
        )
    )

    # 6. The escalation fraction, from the log, for the record.
    n_escalated = int((escalated == True).sum())  # noqa: E712
    skipped_small = int(((escalated == True) & small_category_missing  # noqa: E712
                         & (status == 200)).sum())
    fraction = f"{100.0 * n_escalated / total:.1f}%" if total else "n/a"
    checks.append(
        Check(
            name="cascade_escalation_fraction",
            value=f"{n_escalated}/{total} ({fraction})",
            limit="informational",
            verdict=_PASS,
            detail=(
                "escalated=true lines over measured POST /tickets lines; "
                f"{skipped_small} escalated HTTP 200 line(s) had no small-model "
                f"category (sent straight to the large model by a length rule)"
            ),
        )
    )
    return checks, rows


def single_mode_checks(
    tickets: pd.DataFrame, metadata: dict
) -> tuple[list[Check], list[dict[str, object]]]:
    """The checks for a single-model Assignment 2 run's measured POST /tickets lines."""
    expected_tag = _text(metadata.get("model_tag"))
    status = pd.to_numeric(tickets["status"], errors="coerce")
    from_handler = status.isin(_TICKET_HANDLER_STATUSES)
    rows: list[dict[str, object]] = []

    set_fields = tickets[list(common.CASCADE_LOG_FIELDS)].map(_text) != ""
    has_cascade = set_fields.any(axis=1)
    for index, row in tickets.loc[has_cascade].iterrows():
        names = [name for name in common.CASCADE_LOG_FIELDS if set_fields.at[index, name]]
        rows.append(_mode_problem(
            "cascade_field_on_single_line", row, "all six cascade fields null",
            ";".join(names), "a single-model service must not log cascade fields"))
    n_cascade = int(has_cascade.sum())

    logged_tag = tickets.loc[from_handler, "model_tag"].map(_text)
    bad_tag = logged_tag != expected_tag if expected_tag else pd.Series(
        True, index=logged_tag.index)
    for (_, row), value in zip(tickets.loc[from_handler].loc[bad_tag].iterrows(),
                               logged_tag.loc[bad_tag]):
        rows.append(_mode_problem(
            "model_tag_disagreement", row, expected_tag or "(not in metadata.json)",
            value or "null", "the line names a different model from the run's model_tag"))
    n_bad_tag = int(bad_tag.sum())

    checks = [
        Check(
            name="single_mode_cascade_fields_null",
            value=str(n_cascade),
            limit="0",
            verdict=_BLOCKER if n_cascade else _PASS,
            detail=(
                "a single-model run's log carries cascade fields, so it was not "
                "written by the single-model service the run is labelled as"
                if n_cascade
                else "all six cascade fields are null on every measured line"
            ),
        ),
        Check(
            name="single_mode_model_tag_matches_metadata",
            value=str(n_bad_tag),
            limit="0",
            verdict=_BLOCKER if (n_bad_tag or not expected_tag) else _PASS,
            detail=(
                "metadata.json records no model_tag, so the lines cannot be checked"
                if not expected_tag
                else "the log names a different model from the one this run measured"
                if n_bad_tag
                else f"every 200/502 line has model_tag = {expected_tag}"
            ),
        ),
    ]
    return checks, rows


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Check:
    """One line of the verdict table."""

    name: str
    value: str
    limit: str
    verdict: str
    detail: str


@dataclass
class ReconcileReport:
    """Everything the reconciliation found for one run directory."""

    run_id: str
    run_dir: Path
    metadata: dict
    jtl_samples: int
    log_lines: int
    matched: int
    checks: list[Check] = field(default_factory=list)
    problems: pd.DataFrame = field(default_factory=pd.DataFrame)
    mismatches: pd.DataFrame = field(default_factory=pd.DataFrame)
    latency_diff: pd.DataFrame = field(default_factory=pd.DataFrame)
    #: Assignment 2 only: ``"cascade"`` / ``"single"``; ``None`` for Assignment 1.
    service_mode: str | None = None
    #: Assignment 2 only: per-line "which model answered" problems.
    mode_problems: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def blockers(self) -> list[Check]:
        """The checks that make this run unreportable."""
        return [c for c in self.checks if c.verdict == _BLOCKER]

    @property
    def warnings(self) -> list[Check]:
        """The checks worth reading but not fatal."""
        return [c for c in self.checks if c.verdict == _WARN]

    @property
    def ok(self) -> bool:
        """True when nothing blocks the run from being reported."""
        return not self.blockers

    def checks_frame(self) -> pd.DataFrame:
        """The verdict table, for CSV and markdown."""
        return pd.DataFrame.from_records(
            [
                {
                    "check": c.name,
                    "value": c.value,
                    "limit": c.limit,
                    "verdict": c.verdict,
                    "detail": c.detail,
                }
                for c in self.checks
            ]
        )


def reconcile_run(
    run_dir: Path, *, latency_threshold_ms: float, max_unmatched: int
) -> ReconcileReport:
    """Join one run's ``.jtl`` to its service log and run every check.

    Raises :class:`analysis.common.AnalysisError` when the evidence cannot be
    read at all (no ``metadata.json``, no ``results.jtl``, a service log that
    does not match ``service/log_schema.py``, or a ``.jtl`` without the
    ``request_id`` column). That is a different failure from "the run does not
    reconcile" and the caller reports it differently.
    """
    metadata = common.load_metadata(run_dir)
    jtl = common.read_jtl(run_dir / "results.jtl")
    if "request_id" not in jtl.columns:
        raise common.AnalysisError(
            f"{run_dir / 'results.jtl'} has no request_id column, so it cannot be "
            f"joined to the service log. The run script must pass "
            f"-Jsample_variables=request_id,source_row to JMeter."
        )
    log = common.exclude_warmup(common.read_service_log(run_dir / "service.jsonl"))

    # The warm-up is not part of the measured set on either side. An Assignment 2
    # run lists its three warm-up ids in metadata.json too; Assignment 1 metadata
    # has no such key, so this union changes nothing for an Assignment 1 run.
    warm_ids = warmup_request_ids(run_dir, metadata) | metadata_warmup_ids(metadata)
    jtl = jtl.loc[~id_strings(jtl["request_id"]).isin(warm_ids)].copy()
    log = log.loc[~id_strings(log["request_id"]).isin(warm_ids)].copy()

    jtl["request_id"] = id_strings(jtl["request_id"])
    log["request_id"] = id_strings(log["request_id"])
    jtl_measured = int(len(jtl))
    log_measured = int(len(log))
    # Every measured POST /tickets line, before any join, for the Assignment 2
    # "which model answered" checks: those are about the log itself.
    measured_tickets = log.loc[
        (log["endpoint"] == "/tickets") & (log["method"] == "POST")
    ].copy()

    # A row with no request_id cannot be joined to anything, and would otherwise
    # masquerade as one big duplicate of the empty string. Count those rows on
    # their own and take them out, so "unmatched" and "duplicate" below describe
    # only rows that could in principle have been joined.
    jtl_blank = int((jtl["request_id"] == "").sum())
    log_blank = int((log["request_id"] == "").sum())
    jtl = jtl.loc[jtl["request_id"] != ""].copy()
    log = log.loc[log["request_id"] != ""].copy()

    jtl_dups = duplicate_counts(jtl["request_id"])
    log_dups = duplicate_counts(log["request_id"])

    jtl_ids = set(jtl["request_id"])
    log_ids = set(log["request_id"])
    jtl_only = sorted(jtl_ids - log_ids)
    log_only = sorted(log_ids - jtl_ids)

    problem_rows: list[dict[str, object]] = []
    problem_rows += [
        {
            "problem": "jtl_sample_without_log_line",
            "side": "jtl",
            "request_id": rid,
            "count": 1,
            "note": "a measured sample with no service log line behind it",
        }
        for rid in jtl_only
    ]
    problem_rows += [
        {
            "problem": "log_line_without_jtl_sample",
            "side": "service_log",
            "request_id": rid,
            "count": 1,
            "note": "the service handled a request the load generator did not record",
        }
        for rid in log_only
    ]
    problem_rows += [
        {
            "problem": "duplicate_request_id",
            "side": "jtl",
            "request_id": rid,
            "count": count,
            "note": "ambiguous join: the same request_id appears more than once",
        }
        for rid, count in sorted(jtl_dups.items())
    ]
    problem_rows += [
        {
            "problem": "duplicate_request_id",
            "side": "service_log",
            "request_id": rid,
            "count": count,
            "note": "ambiguous join: the same request_id appears more than once",
        }
        for rid, count in sorted(log_dups.items())
    ]
    problem_rows += [
        {
            "problem": "blank_request_id",
            "side": side,
            "request_id": "",
            "count": blanks,
            "note": "rows carrying no request_id at all, which cannot be joined",
        }
        for side, blanks in (("jtl", jtl_blank), ("service_log", log_blank))
        if blanks
    ]
    problems = pd.DataFrame.from_records(
        problem_rows,
        columns=["problem", "side", "request_id", "count", "note"],
    )

    # Duplicates are a blocker in their own right; de-duplicate before the join so
    # that a fan-out cannot silently multiply the row counts of every other check.
    joined = jtl.drop_duplicates(subset="request_id", keep="first").merge(
        log.drop_duplicates(subset="request_id", keep="first"),
        on="request_id",
        how="inner",
        suffixes=("_jtl", "_log"),
    )

    mismatch_rows: list[dict[str, object]] = []
    source_row_unset = 0
    # Assignment 2 only: a sample JMeter recorded with no HTTP status at all
    # ("Non HTTP response code: ...") is an unfinished request -- the client timed
    # out or was cut off, and the service logged the request when it finished.
    # The brief says such a run "is reported as such, not thrown away", so for an
    # A2 run these are counted as unfinished rather than as status disagreements,
    # and kept out of the client-minus-server gap (the client never waited for the
    # response). An Assignment 1 run is reconciled exactly as before.
    is_a2_run = run_service_mode(metadata) is not None
    unfinished_ids: set[str] = set()
    if not joined.empty:
        client_code = status_strings(joined["responseCode"])
        server_code = status_strings(joined["status"])
        for rid, client, server in zip(
            joined["request_id"], client_code, server_code, strict=True
        ):
            if is_a2_run and not str(client).isdigit():
                unfinished_ids.add(str(rid))
                mismatch_rows.append(
                    {
                        "problem": "unfinished_request",
                        "request_id": rid,
                        "jtl_value": str(client),
                        "log_value": str(server),
                        "note": "JMeter got no HTTP response (timed out or cut off); "
                                "the service logged the request",
                    }
                )
                continue
            if str(client) != str(server):
                mismatch_rows.append(
                    {
                        "problem": "status_disagreement",
                        "request_id": rid,
                        "jtl_value": str(client),
                        "log_value": str(server),
                        "note": "client and service disagree about the HTTP status",
                    }
                )

        client_row = id_strings(joined["source_row_jtl"])
        server_row = id_strings(joined["source_row_log"])
        for rid, client, server in zip(
            joined["request_id"], client_row, server_row, strict=True
        ):
            if not client or not server:
                source_row_unset += 1
                continue
            if str(client) != str(server):
                mismatch_rows.append(
                    {
                        "problem": "source_row_disagreement",
                        "request_id": rid,
                        "jtl_value": str(client),
                        "log_value": str(server),
                        "note": "the sample and the log line name different course rows",
                    }
                )
    mismatches = pd.DataFrame.from_records(
        mismatch_rows,
        columns=["problem", "request_id", "jtl_value", "log_value", "note"],
    )

    # Client-observed minus server-observed latency, in milliseconds.
    if joined.empty:
        diff = pd.Series(dtype="float64")
    else:
        compared = joined
        if unfinished_ids:
            compared = joined.loc[~joined["request_id"].astype(str).isin(unfinished_ids)]
        diff = pd.to_numeric(compared["elapsed"], errors="coerce") - pd.to_numeric(
            compared["total_latency_ms"], errors="coerce"
        )
    diff = diff.dropna()
    signed = common.latency_percentiles(diff)
    absolute = common.latency_percentiles(diff.abs())
    latency_diff = pd.DataFrame.from_records(
        [
            {
                "statistic": "rows_compared",
                "signed_ms": float(len(diff)),
                "absolute_ms": float(len(diff)),
            },
            *(
                {
                    "statistic": key,
                    "signed_ms": signed[key],
                    "absolute_ms": absolute[key],
                }
                for key in ("p50", "p95", "p99", "min", "max", "mean")
            ),
        ]
    )

    status_mismatches = int((mismatches["problem"] == "status_disagreement").sum())
    row_mismatches = int((mismatches["problem"] == "source_row_disagreement").sum())

    checks: list[Check] = [
        Check(
            name="jtl_samples_without_log_line",
            value=str(len(jtl_only)),
            limit=f"<= {max_unmatched}",
            verdict=_verdict_for_unmatched(len(jtl_only), max_unmatched),
            detail=(
                "a measured sample with no log line is a number with nothing behind it"
                if jtl_only
                else "every measured sample has a service log line"
            ),
        ),
        Check(
            name="log_lines_without_jtl_sample",
            value=str(len(log_only)),
            limit=f"<= {max_unmatched}",
            verdict=_verdict_for_unmatched(len(log_only), max_unmatched),
            detail=(
                "the service handled traffic the load generator did not record, so "
                "the error-rate and throughput denominators are wrong"
                if log_only
                else "every log line in the run window has a matching sample"
            ),
        ),
        Check(
            name="blank_request_ids",
            value=f"jtl={jtl_blank} log={log_blank}",
            limit="0",
            verdict=_BLOCKER if (jtl_blank or log_blank) else _PASS,
            detail=(
                "a row with no request_id cannot be joined to anything, so the "
                "sample variables were not captured on that side"
                if (jtl_blank or log_blank)
                else "every row carries a request_id"
            ),
        ),
        Check(
            name="duplicate_request_ids",
            value=f"jtl={len(jtl_dups)} log={len(log_dups)}",
            limit="0",
            verdict=_BLOCKER if (jtl_dups or log_dups) else _PASS,
            detail=(
                "a duplicate request_id makes the join ambiguous"
                if (jtl_dups or log_dups)
                else "request_ids are unique on both sides"
            ),
        ),
        Check(
            name="status_disagreements",
            value=str(status_mismatches),
            limit="0",
            verdict=_BLOCKER if status_mismatches else _PASS,
            detail=(
                "client and service disagree about what happened, so the error rate "
                "cannot be defended"
                if status_mismatches
                else "every matched sample agrees with its log line on HTTP status"
            ),
        ),
        Check(
            name="source_row_disagreements",
            value=str(row_mismatches),
            limit="0",
            verdict=_BLOCKER if row_mismatches else _PASS,
            detail=(
                "the traffic measured is not the traffic we think we measured"
                if row_mismatches
                else "every matched sample agrees with its log line on source_row"
            ),
        ),
        Check(
            name="client_minus_server_latency_p99_ms",
            value=f"{absolute['p99']:.1f}" if len(diff) else "n/a",
            limit=f"<= {latency_threshold_ms:g}",
            verdict=(
                _BLOCKER
                if len(diff) and absolute["p99"] > latency_threshold_ms
                else _PASS
            ),
            detail=(
                "p99 of abs(elapsed minus total_latency_ms); a large value means the "
                "load generator or the clocks, not the service, are shaping the numbers"
            ),
        ),
    ]

    if source_row_unset:
        checks.append(
            Check(
                name="source_row_unset",
                value=str(source_row_unset),
                limit="informational",
                verdict=_WARN,
                detail=(
                    "matched rows where one side carried no source_row; the join "
                    "still holds but those samples cannot be traced to a course row"
                ),
            )
        )
    if not len(diff):
        checks.append(
            Check(
                name="latency_difference_measurable",
                value="0 rows",
                limit="informational",
                verdict=_WARN,
                detail="no matched row carried both elapsed and total_latency_ms",
            )
        )

    # Assignment 2 only, appended after every Assignment 1 check so that an
    # Assignment 1 run's checks table is unchanged in content and in order.
    service_mode = run_service_mode(metadata)
    mode_rows: list[dict[str, object]] = []
    if is_a2_run:
        checks.append(
            Check(
                name="unfinished_requests",
                value=str(len(unfinished_ids)),
                limit="informational",
                verdict=_WARN if unfinished_ids else _PASS,
                detail=(
                    "samples with no HTTP response (timed out or cut off) whose request "
                    "the service did log: reported as unfinished, not thrown away, and "
                    "left out of the status and client-minus-server checks"
                    if unfinished_ids
                    else "every matched sample received an HTTP response"
                ),
            )
        )
    if service_mode == SERVICE_MODE_CASCADE:
        extra, mode_rows = cascade_checks(measured_tickets, metadata)
        checks += extra
    elif service_mode == SERVICE_MODE_SINGLE:
        extra, mode_rows = single_mode_checks(measured_tickets, metadata)
        checks += extra
    mode_problems = pd.DataFrame.from_records(mode_rows, columns=MODE_PROBLEM_COLUMNS)

    return ReconcileReport(
        run_id=run_dir.name,
        run_dir=run_dir,
        metadata=metadata,
        jtl_samples=jtl_measured,
        log_lines=log_measured,
        matched=int(len(joined)),
        checks=checks,
        problems=problems,
        mismatches=mismatches,
        latency_diff=latency_diff,
        service_mode=service_mode,
        mode_problems=mode_problems,
    )


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _listing(frame: pd.DataFrame) -> str:
    """Markdown for a possibly long offenders table, truncated for readability."""
    if frame.empty:
        return "_(none)_\n"
    shown = frame.head(MAX_LISTED_ROWS)
    text = common.to_markdown_table(shown, float_format="{:.1f}")
    if len(frame) > MAX_LISTED_ROWS:
        text += f"\n_and {len(frame) - MAX_LISTED_ROWS} more row(s); see the CSV._\n"
    return text


def build_report_markdown(
    report: ReconcileReport, *, latency_threshold_ms: float, max_unmatched: int
) -> str:
    """The human-readable reconciliation report for one run."""
    verdict = "PASS" if report.ok else "FAIL"
    parts: list[str] = [
        f"# Reconciliation report: `{report.run_id}`",
        "",
        f"**Verdict: {verdict}**",
        "",
        f"* Run directory: `{report.run_dir}`",
        f"* Model pin: `{report.metadata.get('model_tag')}` "
        f"(`{report.metadata.get('model_digest')}`)",
        f"* Mode: `{report.metadata.get('mode')}`, "
        f"freeze commit: `{report.metadata.get('freeze_commit')}`",
        f"* Prompt hash: `{report.metadata.get('prompt_hash')}`, "
        f"num_ctx: `{report.metadata.get('num_ctx')}`, seed: `{report.metadata.get('seed')}`",
    ]
    if report.service_mode is not None:
        # Assignment 2 only: an Assignment 1 report keeps exactly its old header.
        meta = report.metadata
        parts += [
            f"* Assignment 2 configuration: `{meta.get('config')}`, service mode "
            f"`{meta.get('service_mode')}`, gate commit `{meta.get('gate_commit')}` "
            f"(`{meta.get('gate_tag')}`)",
        ]
        if report.service_mode == SERVICE_MODE_CASCADE:
            parts += [
                f"* Cascade: setting `{expected_cascade_setting(meta)}`, small "
                f"`{meta.get('cascade_small_model_tag')}` "
                f"(`{meta.get('cascade_small_model_digest')}`), large "
                f"`{meta.get('cascade_large_model_tag')}`",
            ]
    parts += [
        "",
        f"Measured `.jtl` samples: {report.jtl_samples}. "
        f"Measured service log lines: {report.log_lines}. "
        f"Joined on `request_id`: {report.matched}.",
        "",
        "Thresholds in force: "
        f"`--max-unmatched {max_unmatched}`, "
        f"`--latency-threshold-ms {latency_threshold_ms:g}`.",
        "",
        "## Checks",
        "",
        common.to_markdown_table(report.checks_frame(), float_format="{:.1f}"),
        "",
        "## Unmatched and duplicated request_ids",
        "",
        _listing(report.problems),
        "",
        "## Field disagreements on matched rows",
        "",
        _listing(report.mismatches),
        "",
        "## Client-minus-server latency difference (ms)",
        "",
        "`elapsed` (client-observed) minus `total_latency_ms` (the service's own "
        "handler clock). This is network plus framework overhead: it should be "
        "small and stable. The gate uses the p99 of the absolute difference.",
        "",
        common.to_markdown_table(report.latency_diff, float_format="{:.1f}"),
        "",
        "## Why these are blockers",
        "",
        "An unmatched sample means a number in our slides has no log line behind "
        "it, and the brief treats a number that cannot be traced to a log entry as "
        "unsupported. A duplicate `request_id` makes \"the log line behind this "
        "sample\" undefined. A status disagreement means one of our two instruments "
        "is wrong about what happened, so the error rate cannot be defended. A "
        "`source_row` disagreement means the traffic measured is not the traffic we "
        "think we measured. A large client-minus-server p99 means the load "
        "generator or the clocks are shaping the latency we are about to report, "
        "which the brief rejects as a measurement.",
        "",
    ]
    if report.service_mode is not None:
        parts += [
            "## Which model answered (Assignment 2)",
            "",
            "Checked on every measured `POST /tickets` log line against "
            "`metadata.json`. For a cascade run: `escalated` is logged on every "
            "200/502 line, `cascade_setting` and `small_model_tag` match the run's "
            "configuration, and on every HTTP 200 line `model_tag` is the large "
            "model exactly when `escalated` is true and the small model exactly "
            "when it is false. For a single-model run: no cascade field is set and "
            "`model_tag` is the run's model. A disagreement means the escalation "
            "fraction, and the claim about which model produced each answer, "
            "cannot be derived from this log.",
            "",
            _listing(report.mode_problems),
            "",
        ]
    if not report.ok:
        parts += [
            "## What to do",
            "",
            "Do not quote any figure from this run. Re-run the configuration after "
            "fixing the cause; if the cause is understood and the run is kept for "
            "the record, say in the slide notes that the run was discarded and why.",
            "",
        ]
    return "\n".join(parts)


def write_outputs(
    report: ReconcileReport,
    out_dir: Path,
    *,
    latency_threshold_ms: float,
    max_unmatched: int,
) -> Path:
    """Write the CSV tables and the markdown report; return the markdown path."""
    stem = report.run_id
    common.write_table(report.checks_frame(), out_dir, f"{stem}__checks")
    common.write_table(report.problems, out_dir, f"{stem}__unmatched")
    common.write_table(report.mismatches, out_dir, f"{stem}__mismatches")
    common.write_table(report.latency_diff, out_dir, f"{stem}__latency_diff")
    if report.service_mode is not None:
        # Assignment 2 only, so an Assignment 1 run writes exactly the files it did.
        common.write_table(report.mode_problems, out_dir, f"{stem}__model_answered")
    md_path = out_dir / f"{stem}__report.md"
    md_path.write_text(
        build_report_markdown(
            report,
            latency_threshold_ms=latency_threshold_ms,
            max_unmatched=max_unmatched,
        ),
        encoding="utf-8",
    )
    return md_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    """The command line described in the build contract's CLI section."""
    parser = argparse.ArgumentParser(
        prog="analysis/reconcile.py",
        description=(
            "Inner-join one run's JMeter .jtl to the service's request log on "
            "request_id and refuse the run if the two do not agree. Run this "
            "before quoting any number from a run."
        ),
        epilog=(
            "Exits 1 when the run does not reconcile: unmatched samples above "
            "--max-unmatched, any duplicate request_id, any HTTP status or "
            "source_row disagreement, a client-minus-server latency p99 above "
            "--latency-threshold-ms, or (Assignment 2 runs) a log line whose "
            "'which model answered' fields contradict metadata.json."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="one results/runs/<stamp>_<model>_<plan>_<rate>_run<k> directory",
    )
    parser.add_argument(
        "--latency-threshold-ms",
        type=float,
        default=250.0,
        help="fail if the p99 of |client elapsed - server total_latency_ms| exceeds this",
    )
    parser.add_argument(
        "--max-unmatched",
        type=int,
        default=0,
        help="samples or log lines allowed to have no counterpart on the other side",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("analysis/output/reconcile"),
        help="where the CSV tables and the markdown report are written",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the process exit status (0 reconciles, 1 does not)."""
    args = build_arg_parser().parse_args(argv)
    try:
        report = reconcile_run(
            args.run_dir,
            latency_threshold_ms=args.latency_threshold_ms,
            max_unmatched=args.max_unmatched,
        )
    except common.AnalysisError as exc:
        print(f"reconcile: FAILED to read the evidence: {exc}", file=sys.stderr)
        return 1

    md_path = write_outputs(
        report,
        args.out_dir,
        latency_threshold_ms=args.latency_threshold_ms,
        max_unmatched=args.max_unmatched,
    )

    verdict = "PASS" if report.ok else "FAIL"
    print(f"reconcile: {report.run_id}: {verdict}")
    print(
        f"reconcile: {report.jtl_samples} .jtl sample(s), {report.log_lines} log "
        f"line(s), {report.matched} joined on request_id"
    )
    if report.service_mode == SERVICE_MODE_CASCADE:
        for check in report.checks:
            if check.name == "cascade_escalation_fraction":
                print(f"reconcile: cascade escalation = {check.value}")
    for check in report.warnings:
        print(f"reconcile: WARN {check.name} = {check.value} ({check.detail})")
    # Flush before writing to stderr so the two streams read in order when the
    # operator is watching a terminal rather than a redirected log.
    sys.stdout.flush()
    for check in report.blockers:
        print(
            f"reconcile: BLOCKER {check.name} = {check.value} "
            f"(limit {check.limit}): {check.detail}",
            file=sys.stderr,
        )
    print(f"reconcile: wrote {md_path}")
    if not report.ok:
        print(
            "reconcile: this run does not reconcile with its own logs. Do not "
            "quote any figure from it.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
