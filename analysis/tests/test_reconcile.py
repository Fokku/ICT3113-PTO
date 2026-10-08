"""Tests for ``analysis/reconcile.py``.

Owner: Yeo Kai Yuan (technical core).

Each failure mode is exercised on its own, because the script's value is that it
refuses a run rather than blessing it quietly, and a script that fails for the
wrong reason is no better than one that passes for the wrong reason.

Fixtures come from the builders in ``conftest.py``. ``build_run_dir``'s
``drop_log_for_last`` / ``drop_jtl_for_first`` knobs give the unmatched cases;
the field disagreements are built here as explicit ``.jtl``/log pairs so the one
deliberately broken field is visible in the test rather than buried in a
generator.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

from analysis import common, reconcile

# ``conftest.py`` sits in this directory and pytest puts the directory on
# sys.path, so its builders can be imported directly.
from conftest import (  # noqa: E402
    BASE_TIME,
    build_run_dir,
    iso_ms,
    make_jtl_row,
    make_log_line,
    make_metadata,
    write_jtl,
    write_service_log,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Pair:
    """One ``.jtl`` sample and the service log line that should match it.

    Defaults describe a healthy pair: HTTP 200 on both sides, the same source
    row, and 5 ms of client-side overhead on top of the server's own timing.
    """

    request_id: str
    elapsed_ms: int = 1005
    server_latency_ms: float = 1000.0
    jtl_code: str = "200"
    log_status: int = 200
    success: str = "true"
    jtl_source_row: str = "10000"
    log_source_row: str = "10000"


def write_pair_run(
    root: Path,
    pairs: list[Pair],
    *,
    stamp: str = "20261001T090000Z",
    model: str = "testmodel-1b",
    plan: str = "load_post_tickets",
    rate: str = "60pm",
    run_index: int = 1,
    include_warmup: bool = False,
) -> Path:
    """Write a run directory whose two sides are exactly ``pairs``.

    Samples are placed one second apart from ``BASE_TIME``. Repeating a
    ``request_id`` in ``pairs`` is how the duplicate-id case is built.
    """
    run_dir = root / f"{stamp}_{model}_{plan}_{rate}_run{run_index}"
    run_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    records: list[dict] = []
    for index, pair in enumerate(pairs):
        moment = BASE_TIME + timedelta(seconds=index)
        rows.append(
            make_jtl_row(
                timeStamp=int(moment.timestamp() * 1000),
                elapsed=pair.elapsed_ms,
                Latency=pair.elapsed_ms - 1,
                responseCode=pair.jtl_code,
                success=pair.success,
                request_id=pair.request_id,
                source_row=pair.jtl_source_row,
            )
        )
        records.append(
            make_log_line(
                ts=iso_ms(moment),
                request_id=pair.request_id,
                source_row=pair.log_source_row or None,
                status=pair.log_status,
                total_latency_ms=pair.server_latency_ms,
                model_latency_ms=pair.server_latency_ms - 10,
            )
        )
    write_jtl(run_dir / "results.jtl", rows)
    write_service_log(run_dir / "service.jsonl", records)

    if include_warmup:
        # A warm-up line with no .jtl sample: it must not be reported as an
        # unmatched log line, because JMeter never sampled it.
        write_service_log(
            run_dir / "warmup.jsonl",
            [
                make_log_line(
                    ts=iso_ms(BASE_TIME - timedelta(seconds=5)),
                    request_id="warmup-00000000",
                    source_row="900000",
                    warmup=True,
                    total_latency_ms=9000.0,
                )
            ],
        )

    meta = make_metadata(run_id=run_dir.name, plan=plan, rate_per_min=60, run_index=run_index)
    (run_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return run_dir


def healthy_pairs(count: int) -> list[Pair]:
    """``count`` well-formed pairs with rising latencies."""
    return [
        Pair(request_id=f"req-{index:04d}", elapsed_ms=1005 + index * 10,
             server_latency_ms=1000.0 + index * 10,
             jtl_source_row=str(10000 + index), log_source_row=str(10000 + index))
        for index in range(count)
    ]


def run_cli(run_dir: Path, out_dir: Path, *extra: str) -> int:
    """Invoke the reconcile CLI exactly as the playbook does."""
    return reconcile.main(
        ["--run-dir", str(run_dir), "--out-dir", str(out_dir), *extra]
    )


def read_csv(path: Path) -> pd.DataFrame:
    """Read one of the report CSVs back, preserving empty tables."""
    return pd.read_csv(path, keep_default_na=False)


def checks(out_dir: Path, run_dir: Path) -> dict[str, dict[str, str]]:
    """The checks table as ``{check name: row}``."""
    frame = read_csv(out_dir / f"{run_dir.name}__checks.csv")
    return {row["check"]: row for _, row in frame.iterrows()}


# ---------------------------------------------------------------------------
# the clean case
# ---------------------------------------------------------------------------

def test_a_clean_run_reconciles_and_exits_zero(build_run, tmp_path: Path, capsys) -> None:
    """The happy path: every sample has its log line, nothing disagrees."""
    run = build_run(n_samples=12, n_errors=2)
    out_dir = tmp_path / "out"

    assert run_cli(run.path, out_dir) == 0
    captured = capsys.readouterr()
    assert "PASS" in captured.out
    assert "BLOCKER" not in captured.err

    report = (out_dir / f"{run.path.name}__report.md").read_text(encoding="utf-8")
    assert "**Verdict: PASS**" in report
    # The model pin travels with the verdict, so the report identifies what ran.
    assert "testmodel:1b" in report

    table = checks(out_dir, run.path)
    assert {row["verdict"] for row in table.values()} == {"pass"}
    assert table["jtl_samples_without_log_line"]["value"] == "0"
    assert table["log_lines_without_jtl_sample"]["value"] == "0"
    assert read_csv(out_dir / f"{run.path.name}__unmatched.csv").empty
    assert read_csv(out_dir / f"{run.path.name}__mismatches.csv").empty


def test_the_warmup_line_is_not_an_unmatched_log_line(tmp_path: Path) -> None:
    """warmup.jsonl has no .jtl sample by design; that is not a defect."""
    run_dir = write_pair_run(tmp_path / "runs", healthy_pairs(5), include_warmup=True)
    out_dir = tmp_path / "out"

    assert run_cli(run_dir, out_dir) == 0
    report = reconcile.reconcile_run(run_dir, latency_threshold_ms=250, max_unmatched=0)
    assert report.jtl_samples == 5
    assert report.log_lines == 5
    assert report.matched == 5


def test_latency_difference_percentiles_are_reported(tmp_path: Path) -> None:
    """The distribution of (client elapsed - server total_latency_ms) is reported."""
    # Differences of 10, 20, 30, 40 ms by construction.
    pairs = [
        Pair(request_id=f"req-{i:04d}", elapsed_ms=1000 + 10 * (i + 1),
             server_latency_ms=1000.0)
        for i in range(4)
    ]
    run_dir = write_pair_run(tmp_path / "runs", pairs)
    out_dir = tmp_path / "out"

    assert run_cli(run_dir, out_dir) == 0
    frame = read_csv(out_dir / f"{run_dir.name}__latency_diff.csv").set_index("statistic")
    assert float(frame.loc["rows_compared", "signed_ms"]) == 4.0
    assert float(frame.loc["min", "signed_ms"]) == pytest.approx(10.0)
    assert float(frame.loc["max", "signed_ms"]) == pytest.approx(40.0)
    assert float(frame.loc["p50", "signed_ms"]) == pytest.approx(
        common.percentile([10, 20, 30, 40], 0.50)
    )
    assert float(frame.loc["p99", "signed_ms"]) == pytest.approx(
        common.percentile([10, 20, 30, 40], 0.99)
    )


# ---------------------------------------------------------------------------
# failure mode: samples with no log line
# ---------------------------------------------------------------------------

def test_jtl_samples_without_a_log_line_fail(build_run, tmp_path: Path, capsys) -> None:
    """A latency number with no log line behind it cannot be reported."""
    run = build_run(n_samples=12, drop_log_for_last=2)
    out_dir = tmp_path / "out"

    assert run_cli(run.path, out_dir) == 1
    captured = capsys.readouterr()
    assert "FAIL" in captured.out
    assert "jtl_samples_without_log_line" in captured.err
    assert "do not" in captured.err.lower()

    table = checks(out_dir, run.path)
    assert table["jtl_samples_without_log_line"]["verdict"] == "BLOCKER"
    assert table["jtl_samples_without_log_line"]["value"] == "2"
    problems = read_csv(out_dir / f"{run.path.name}__unmatched.csv")
    assert list(problems["problem"]) == ["jtl_sample_without_log_line"] * 2
    assert sorted(problems["request_id"]) == ["req-0010", "req-0011"]
    report = (out_dir / f"{run.path.name}__report.md").read_text(encoding="utf-8")
    assert "**Verdict: FAIL**" in report
    assert "req-0010" in report


def test_max_unmatched_tolerates_exactly_what_it_allows(build_run, tmp_path: Path) -> None:
    """--max-unmatched is a deliberate, stated tolerance, not a silent one."""
    run = build_run(n_samples=12, drop_log_for_last=2)
    out_dir = tmp_path / "out"

    assert run_cli(run.path, out_dir, "--max-unmatched", "2") == 0
    table = checks(out_dir, run.path)
    # Forgiven, but not hidden: a tolerated unmatched sample is still a warning.
    assert table["jtl_samples_without_log_line"]["verdict"] == "WARN"
    assert table["jtl_samples_without_log_line"]["limit"] == "<= 2"
    # The offending ids are still listed, so the tolerance is auditable.
    assert len(read_csv(out_dir / f"{run.path.name}__unmatched.csv")) == 2

    # One fewer allowance and the same run is refused.
    assert run_cli(run.path, out_dir, "--max-unmatched", "1") == 1


# ---------------------------------------------------------------------------
# failure mode: log lines with no sample
# ---------------------------------------------------------------------------

def test_log_lines_without_a_jtl_sample_fail(build_run, tmp_path: Path, capsys) -> None:
    """Traffic the load generator did not record makes every denominator wrong."""
    run = build_run(n_samples=12, drop_jtl_for_first=2)
    out_dir = tmp_path / "out"

    assert run_cli(run.path, out_dir) == 1
    assert "log_lines_without_jtl_sample" in capsys.readouterr().err

    table = checks(out_dir, run.path)
    assert table["log_lines_without_jtl_sample"]["verdict"] == "BLOCKER"
    assert table["log_lines_without_jtl_sample"]["value"] == "2"
    problems = read_csv(out_dir / f"{run.path.name}__unmatched.csv")
    assert list(problems["problem"]) == ["log_line_without_jtl_sample"] * 2
    assert sorted(problems["request_id"]) == ["req-0000", "req-0001"]


# ---------------------------------------------------------------------------
# failure mode: duplicate request_ids
# ---------------------------------------------------------------------------

def test_duplicate_request_ids_fail(tmp_path: Path, capsys) -> None:
    """A duplicate id makes "the log line behind this sample" undefined."""
    pairs = healthy_pairs(4)
    pairs.append(Pair(request_id=pairs[0].request_id, jtl_source_row="10000",
                      log_source_row="10000"))
    run_dir = write_pair_run(tmp_path / "runs", pairs)
    out_dir = tmp_path / "out"

    assert run_cli(run_dir, out_dir) == 1
    assert "duplicate_request_ids" in capsys.readouterr().err

    table = checks(out_dir, run_dir)
    assert table["duplicate_request_ids"]["verdict"] == "BLOCKER"
    problems = read_csv(out_dir / f"{run_dir.name}__unmatched.csv")
    duplicates = problems[problems["problem"] == "duplicate_request_id"]
    assert sorted(duplicates["side"]) == ["jtl", "service_log"]
    assert set(duplicates["request_id"]) == {"req-0000"}
    assert set(duplicates["count"]) == {2}
    # The duplicate must not inflate the matched count by fanning the join out.
    report = reconcile.reconcile_run(run_dir, latency_threshold_ms=250, max_unmatched=0)
    assert report.matched == 4


def test_rows_without_a_request_id_fail(tmp_path: Path, capsys) -> None:
    """Nothing can be joined to a row with no id, so it cannot be reported either."""
    pairs = healthy_pairs(4)
    pairs[2] = Pair(request_id="", jtl_source_row="10002", log_source_row="10002")
    run_dir = write_pair_run(tmp_path / "runs", pairs)
    out_dir = tmp_path / "out"

    assert run_cli(run_dir, out_dir) == 1
    assert "blank_request_ids" in capsys.readouterr().err

    table = checks(out_dir, run_dir)
    assert table["blank_request_ids"]["verdict"] == "BLOCKER"
    assert table["blank_request_ids"]["value"] == "jtl=1 log=1"
    problems = read_csv(out_dir / f"{run_dir.name}__unmatched.csv")
    blanks = problems[problems["problem"] == "blank_request_id"]
    assert sorted(blanks["side"]) == ["jtl", "service_log"]

    # The blank row is not also counted as unmatched or duplicated: the report
    # names the defect once, and the other three pairs still join.
    report = reconcile.reconcile_run(run_dir, latency_threshold_ms=250, max_unmatched=0)
    assert report.jtl_samples == 4
    assert report.matched == 3
    assert [c.name for c in report.blockers] == ["blank_request_ids"]


# ---------------------------------------------------------------------------
# failure mode: field disagreements
# ---------------------------------------------------------------------------

def test_status_disagreement_fails(tmp_path: Path, capsys) -> None:
    """The client said 200 and the service logged 502: one of them is wrong."""
    pairs = healthy_pairs(5)
    pairs[2] = Pair(
        request_id="req-0002",
        elapsed_ms=1025,
        server_latency_ms=1020.0,
        jtl_code="200",
        log_status=502,
        success="true",
        jtl_source_row="10002",
        log_source_row="10002",
    )
    run_dir = write_pair_run(tmp_path / "runs", pairs)
    out_dir = tmp_path / "out"

    assert run_cli(run_dir, out_dir) == 1
    assert "status_disagreements" in capsys.readouterr().err

    table = checks(out_dir, run_dir)
    assert table["status_disagreements"]["verdict"] == "BLOCKER"
    assert table["status_disagreements"]["value"] == "1"
    # Everything else about the run is fine, so only this check fires.
    assert [name for name, row in table.items() if row["verdict"] == "BLOCKER"] == [
        "status_disagreements"
    ]

    mismatches = read_csv(out_dir / f"{run_dir.name}__mismatches.csv")
    assert list(mismatches["problem"]) == ["status_disagreement"]
    assert mismatches.iloc[0]["request_id"] == "req-0002"
    # Read back through pandas, so compare as text: the CSV holds 200 and 502.
    assert str(mismatches.iloc[0]["jtl_value"]) == "200"
    assert str(mismatches.iloc[0]["log_value"]) == "502"


def test_matching_statuses_are_compared_across_types(tmp_path: Path) -> None:
    """JMeter writes the code as text and the log as an integer; 200 == "200"."""
    pairs = [
        Pair(request_id="req-0000", jtl_code="200", log_status=200),
        Pair(request_id="req-0001", jtl_code="502", log_status=502, success="false"),
    ]
    run_dir = write_pair_run(tmp_path / "runs", pairs)
    assert run_cli(run_dir, tmp_path / "out") == 0


def test_source_row_disagreement_fails(tmp_path: Path, capsys) -> None:
    """If the row numbers differ, the traffic measured is not the traffic we think."""
    pairs = healthy_pairs(5)
    pairs[1] = Pair(
        request_id="req-0001",
        jtl_source_row="10001",
        log_source_row="10007",
    )
    run_dir = write_pair_run(tmp_path / "runs", pairs)
    out_dir = tmp_path / "out"

    assert run_cli(run_dir, out_dir) == 1
    assert "source_row_disagreements" in capsys.readouterr().err

    mismatches = read_csv(out_dir / f"{run_dir.name}__mismatches.csv")
    assert list(mismatches["problem"]) == ["source_row_disagreement"]
    assert str(mismatches.iloc[0]["jtl_value"]) == "10001"
    assert str(mismatches.iloc[0]["log_value"]) == "10007"


def test_a_missing_source_row_is_a_warning_not_a_blocker(tmp_path: Path, capsys) -> None:
    """A plan may omit the header; that costs traceability but breaks no join."""
    pairs = healthy_pairs(4)
    pairs[0] = Pair(request_id="req-0000", jtl_source_row="10000", log_source_row="")
    run_dir = write_pair_run(tmp_path / "runs", pairs)
    out_dir = tmp_path / "out"

    assert run_cli(run_dir, out_dir) == 0
    assert "WARN source_row_unset" in capsys.readouterr().out
    table = checks(out_dir, run_dir)
    assert table["source_row_unset"]["verdict"] == "WARN"
    assert table["source_row_disagreements"]["verdict"] == "pass"


# ---------------------------------------------------------------------------
# failure mode: client and server latency drifting apart
# ---------------------------------------------------------------------------

def test_client_server_latency_gap_above_the_threshold_fails(
    tmp_path: Path, capsys
) -> None:
    """A large gap means the rig or the clocks, not the service, shaped the numbers."""
    pairs = [
        Pair(request_id=f"req-{i:04d}", elapsed_ms=1900, server_latency_ms=1000.0)
        for i in range(5)
    ]
    run_dir = write_pair_run(tmp_path / "runs", pairs)
    out_dir = tmp_path / "out"

    assert run_cli(run_dir, out_dir) == 1
    assert "client_minus_server_latency_p99_ms" in capsys.readouterr().err

    table = checks(out_dir, run_dir)
    row = table["client_minus_server_latency_p99_ms"]
    assert row["verdict"] == "BLOCKER"
    assert float(row["value"]) == pytest.approx(900.0)
    assert row["limit"] == "<= 250"

    # The same run passes when the threshold is deliberately widened, which is
    # how a team would record "we know, and here is why it is acceptable".
    assert run_cli(run_dir, out_dir, "--latency-threshold-ms", "1000") == 0


def test_a_negative_gap_also_fails(tmp_path: Path) -> None:
    """The service cannot take longer than the client observed: that is a clock fault."""
    pairs = [
        Pair(request_id=f"req-{i:04d}", elapsed_ms=1000, server_latency_ms=1400.0)
        for i in range(5)
    ]
    run_dir = write_pair_run(tmp_path / "runs", pairs)
    out_dir = tmp_path / "out"

    assert run_cli(run_dir, out_dir) == 1
    row = checks(out_dir, run_dir)["client_minus_server_latency_p99_ms"]
    assert row["verdict"] == "BLOCKER"
    frame = read_csv(out_dir / f"{run_dir.name}__latency_diff.csv").set_index("statistic")
    assert float(frame.loc["p99", "signed_ms"]) == pytest.approx(-400.0)
    assert float(frame.loc["p99", "absolute_ms"]) == pytest.approx(400.0)


# ---------------------------------------------------------------------------
# unreadable evidence
# ---------------------------------------------------------------------------

def test_missing_metadata_is_a_read_failure(build_run, tmp_path: Path, capsys) -> None:
    """A run without its model pin and freeze commit cannot be signed off."""
    run = build_run(n_samples=5)
    (run.path / "metadata.json").unlink()

    assert run_cli(run.path, tmp_path / "out") == 1
    err = capsys.readouterr().err
    assert "FAILED to read the evidence" in err
    assert "metadata.json" in err


def test_a_jtl_without_request_ids_cannot_be_joined(tmp_path: Path, capsys) -> None:
    """Without -Jsample_variables there is no join, and the script must say why."""
    run_dir = write_pair_run(tmp_path / "runs", healthy_pairs(3))
    jtl = run_dir / "results.jtl"
    with jtl.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    columns = [c for c in rows[0] if c != "request_id"]
    with jtl.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows({c: row[c] for c in columns} for row in rows)

    assert run_cli(run_dir, tmp_path / "out") == 1
    err = capsys.readouterr().err
    assert "request_id" in err
    assert "sample_variables" in err


def test_reports_for_different_runs_do_not_overwrite_each_other(tmp_path: Path) -> None:
    """One out-dir holds the whole campaign, so the run id is part of every stem."""
    root = tmp_path / "runs"
    first = build_run_dir(root, run_index=1, n_samples=4)
    second = build_run_dir(root, run_index=2, n_samples=4)
    out_dir = tmp_path / "out"

    assert run_cli(first.path, out_dir) == 0
    assert run_cli(second.path, out_dir) == 0
    reports = sorted(p.name for p in out_dir.glob("*__report.md"))
    assert reports == [f"{first.path.name}__report.md", f"{second.path.name}__report.md"]


def test_mixed_run_with_blank_search_source_rows_reconciles(tmp_path: Path) -> None:
    """GET /search samples carry no source_row; the POST rows must still match.

    Regression: with any blank cell in the .jtl's source_row column, pandas typed
    the column as float, 10000 became "10000.0", and every POST /tickets sample
    of a mixed_load run was reported as naming a different course row (found in
    the 8 October 2026 dev rehearsal).
    """
    pairs = healthy_pairs(6)
    pairs += [
        Pair(request_id=f"search-{index:04d}", jtl_source_row="", log_source_row="")
        for index in range(4)
    ]
    run_dir = write_pair_run(tmp_path / "runs", pairs, plan="mixed_load", rate="1pm")
    out_dir = tmp_path / "out"

    assert run_cli(run_dir, out_dir) == 0
    assert checks(out_dir, run_dir)["source_row_disagreements"]["value"] == "0"
