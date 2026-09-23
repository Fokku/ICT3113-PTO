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
warm-up ``request_id`` comes from ``warmup.jsonl`` and from ``metadata.json``,
and ``exclude_warmup()`` is applied to the service log as a belt-and-braces
guard. Counting the warm-up as an unmatched log line would be a false alarm,
because JMeter never sampled it.

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

    # The warm-up is not part of the measured set on either side.
    warm_ids = warmup_request_ids(run_dir, metadata)
    jtl = jtl.loc[~id_strings(jtl["request_id"]).isin(warm_ids)].copy()
    log = log.loc[~id_strings(log["request_id"]).isin(warm_ids)].copy()

    jtl["request_id"] = id_strings(jtl["request_id"])
    log["request_id"] = id_strings(log["request_id"])
    jtl_measured = int(len(jtl))
    log_measured = int(len(log))

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
    if not joined.empty:
        client_code = status_strings(joined["responseCode"])
        server_code = status_strings(joined["status"])
        for rid, client, server in zip(
            joined["request_id"], client_code, server_code, strict=True
        ):
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
        diff = pd.to_numeric(joined["elapsed"], errors="coerce") - pd.to_numeric(
            joined["total_latency_ms"], errors="coerce"
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
            "source_row disagreement, or a client-minus-server latency p99 above "
            "--latency-threshold-ms."
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
