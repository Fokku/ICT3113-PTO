"""Tests for ``analysis/summarise_load.py``.

Owner: Yeo Kai Yuan (technical core).

Every fixture here is fabricated by the builders in ``conftest.py``: no model is
run, no real ``.jtl`` is read, and no number produced by these tests is ever
reported. The point is to prove the arithmetic and the failure behaviour, so the
expected values below are hand-computed from the fixture's known latencies and
written out with their derivation rather than copied from a run of the script.
"""

from __future__ import annotations

import csv
import json
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

from analysis import common, summarise_load

# ``conftest.py`` sits in this directory and pytest puts the directory on
# sys.path, so its builders can be imported directly. The fixtures come from the
# same file by the usual pytest mechanism.
from conftest import (  # noqa: E402
    BASE_TIME,
    FakeRun,
    build_run_dir,
    iso_ms,
    make_jtl_row,
    make_log_line,
    write_jtl,
    write_service_log,
)

# The fixture builder writes elapsed = total_latency_ms + 5, one sample per
# ``interval_ms``, latency rising by ``latency_step_ms`` per sample.
CLIENT_OVERHEAD_MS = 5


# ---------------------------------------------------------------------------
# helpers used by more than one test
# ---------------------------------------------------------------------------

def read_jtl_rows(path: Path) -> list[dict[str, str]]:
    """The raw rows of a fabricated ``.jtl``, so a test can add one and write it back."""
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_log_records(path: Path) -> list[dict]:
    """The raw records of a fabricated service log."""
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def append_warmup_sample(
    run: FakeRun,
    *,
    request_id: str = "warmup-appended",
    elapsed_ms: int = 30_000,
    server_latency_ms: float = 29_990.0,
) -> None:
    """Add one warm-up-flagged sample to both sides of a fabricated run.

    ``build_run_dir`` keeps its warm-up line in ``warmup.jsonl`` and gives it no
    ``.jtl`` row, which is the real layout. To test that the *exclusion* works we
    need a warm-up sample that is present in both files, which is what happens if
    the run script's warm-up traffic goes through JMeter.
    """
    moment = BASE_TIME - timedelta(seconds=5)
    rows = read_jtl_rows(run.jtl)
    rows.append(
        make_jtl_row(
            timeStamp=int(moment.timestamp() * 1000),
            elapsed=elapsed_ms,
            Latency=elapsed_ms - 1,
            request_id=request_id,
            source_row="900000",
        )
    )
    write_jtl(run.jtl, rows)

    records = read_log_records(run.service_log)
    records.append(
        make_log_line(
            ts=iso_ms(moment),
            request_id=request_id,
            source_row="900000",
            warmup=True,
            total_latency_ms=server_latency_ms,
            model_latency_ms=server_latency_ms - 10,
        )
    )
    write_service_log(run.service_log, records)


def summarise(run: FakeRun) -> summarise_load.RunSummary:
    """Summarise one fabricated run directory."""
    info = common.parse_run_dir_name(run.path)
    assert info is not None, f"{run.path.name} is not a valid run directory name"
    return summarise_load.summarise_run(info)


# ---------------------------------------------------------------------------
# per-run arithmetic
# ---------------------------------------------------------------------------

def test_per_run_percentiles_and_throughput_on_a_known_sample_set(build_run) -> None:
    """Known answers, hand-computed from the fixture's latencies."""
    run = build_run(
        n_samples=10,
        base_latency_ms=1000,
        latency_step_ms=10,
        interval_ms=1000,
        n_errors=0,
    )
    metrics = summarise(run).metrics

    # Client-observed elapsed values are 1005, 1015, ... 1095 ms.
    # Linear interpolation on the sorted sample:
    #   p50 -> position 0.50 * 9 = 4.50 -> 1045 + 0.50 * 10 = 1050.0
    #   p95 -> position 0.95 * 9 = 8.55 -> 1085 + 0.55 * 10 = 1090.5
    #   p99 -> position 0.99 * 9 = 8.91 -> 1085 + 0.91 * 10 = 1094.1
    assert metrics["samples"] == 10
    assert metrics["client_min_ms"] == pytest.approx(1005.0)
    assert metrics["client_max_ms"] == pytest.approx(1095.0)
    assert metrics["client_p50_ms"] == pytest.approx(1050.0)
    assert metrics["client_p95_ms"] == pytest.approx(1090.5)
    assert metrics["client_p99_ms"] == pytest.approx(1094.1)

    # The span runs from the first sample's start (t = 0) to the last sample's
    # completion (starts at t = 9 s, takes 1.095 s).
    expected_span = 9.0 + 1.095
    assert metrics["span_s"] == pytest.approx(expected_span)
    assert metrics["throughput_rps"] == pytest.approx(10 / expected_span)
    assert metrics["throughput_per_hour"] == pytest.approx(10 / expected_span * 3600)
    assert metrics["ok_throughput_rps"] == pytest.approx(metrics["throughput_rps"])


def test_server_latency_reported_alongside_the_client_figure(build_run) -> None:
    """The service's own total_latency_ms is reported next to JMeter's elapsed."""
    run = build_run(n_samples=10, base_latency_ms=1000, latency_step_ms=10, n_errors=0)
    metrics = summarise(run).metrics

    # Server latencies are 1000 ... 1090 ms, i.e. the client figures minus 5 ms.
    assert metrics["server_p50_ms"] == pytest.approx(1045.0)
    assert metrics["server_p95_ms"] == pytest.approx(1085.5)
    assert metrics["server_p99_ms"] == pytest.approx(1089.1)
    for percentile in ("p50", "p95", "p99"):
        assert metrics[f"client_{percentile}_ms"] - metrics[
            f"server_{percentile}_ms"
        ] == pytest.approx(CLIENT_OVERHEAD_MS)
    assert metrics["service_log_lines"] == 10


def test_error_rate_arithmetic(build_run) -> None:
    """Error rate is failed samples over all samples; ok_throughput counts only successes."""
    run = build_run(n_samples=10, n_errors=2, interval_ms=1000)
    metrics = summarise(run).metrics

    assert metrics["samples"] == 10
    assert metrics["errors"] == 2
    assert metrics["error_rate_pct"] == pytest.approx(20.0)
    # Both throughputs share the same span, so their ratio is 8/10 exactly.
    assert metrics["ok_throughput_rps"] == pytest.approx(0.8 * metrics["throughput_rps"])
    assert metrics["ok_throughput_per_hour"] == pytest.approx(
        metrics["ok_throughput_rps"] * 3600
    )


def test_a_clean_run_reports_no_error_rate(build_run) -> None:
    """The arithmetic must not manufacture errors where the .jtl has none."""
    metrics = summarise(build_run(n_samples=6, n_errors=0)).metrics
    assert metrics["errors"] == 0
    assert metrics["error_rate_pct"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# warm-up exclusion
# ---------------------------------------------------------------------------

def test_warmup_exclusion_changes_the_answer(build_run) -> None:
    """A warm-up sample present in both files must not reach the percentiles."""
    run = build_run(n_samples=10, base_latency_ms=1000, latency_step_ms=10, n_errors=0)
    clean = summarise(run).metrics

    append_warmup_sample(run, elapsed_ms=30_000, server_latency_ms=29_990.0)
    with_warmup = summarise(run).metrics

    # Control: the warm-up sample is genuinely in the file and would move the
    # answer a long way if it were counted.
    all_elapsed = common.read_jtl(run.jtl)["elapsed"]
    assert len(all_elapsed) == 11
    naive_p99 = common.percentile(all_elapsed, 0.99)
    assert naive_p99 > clean["client_p99_ms"] + 1000

    # The script excludes it, so the measurement is unchanged.
    assert with_warmup["warmup_samples_excluded"] == 1
    assert with_warmup["samples"] == clean["samples"]
    assert with_warmup["client_p99_ms"] == pytest.approx(clean["client_p99_ms"])
    assert with_warmup["client_max_ms"] == pytest.approx(clean["client_max_ms"])
    # ... and the server-side figures are unchanged too.
    assert with_warmup["server_p99_ms"] == pytest.approx(clean["server_p99_ms"])
    assert with_warmup["service_log_lines"] == clean["service_log_lines"]


def test_the_run_scripts_warmup_line_is_not_counted_as_a_sample(build_run) -> None:
    """warmup.jsonl holds a line with no .jtl row; that must not become a sample."""
    run = build_run(n_samples=5, include_warmup=True)
    assert (run.path / "warmup.jsonl").is_file()
    metrics = summarise(run).metrics
    assert metrics["samples"] == 5
    assert metrics["service_log_lines"] == 5
    assert metrics["warmup_samples_excluded"] == 0


# ---------------------------------------------------------------------------
# per-configuration grouping and the fewer-than-three-runs warning
# ---------------------------------------------------------------------------

def test_per_configuration_grouping_and_spread(tmp_path: Path) -> None:
    """Repeat runs are grouped by (model, plan, rate); spread is across those runs."""
    root = tmp_path / "runs"
    for index, base in enumerate((1000, 1100, 1200), start=1):
        build_run_dir(
            root,
            rate="60pm",
            run_index=index,
            n_samples=10,
            base_latency_ms=base,
            latency_step_ms=10,
        )
    for index, base in enumerate((2000, 2100), start=1):
        build_run_dir(
            root,
            rate="120pm",
            run_index=index,
            n_samples=10,
            base_latency_ms=base,
            latency_step_ms=10,
        )

    summaries = [summarise_load.summarise_run(i) for i in common.iter_run_dirs(root)]
    frame, warnings = summarise_load.per_config_frame(summaries)

    configs = frame[["rate", "runs"]].drop_duplicates().set_index("rate")["runs"].to_dict()
    assert configs == {"60pm": 3, "120pm": 2}

    # p50 of each 60pm run is base + 45 + 5 client overhead, so 1050/1150/1250.
    p50 = frame[(frame["rate"] == "60pm") & (frame["metric"] == "client_p50_ms")]
    assert len(p50) == 1
    row = p50.iloc[0]
    assert row["mean"] == pytest.approx(1150.0)
    assert row["min"] == pytest.approx(1050.0)
    assert row["max"] == pytest.approx(1250.0)
    assert row["sd"] == pytest.approx(100.0)
    assert row["run_indexes"] == "1;2;3"
    assert row["warning"] == ""

    # The 120pm configuration has two runs, so it is flagged.
    thin = frame[(frame["rate"] == "120pm") & (frame["metric"] == "client_p50_ms")].iloc[0]
    assert "FEWER THAN 3 RUNS" in thin["warning"]
    assert any("120pm" in w for w in warnings)
    assert not any("60pm" in w for w in warnings)


def test_single_run_sd_is_not_reported_as_zero(build_run) -> None:
    """One run must never look precise: the SD is n/a, not 0."""
    run = build_run(n_samples=5)
    summaries = [summarise(run)]
    frame, _ = summarise_load.per_config_frame(summaries)
    row = frame[frame["metric"] == "client_p50_ms"].iloc[0]
    assert row["runs"] == 1
    assert pd.isna(row["sd"])


def test_fewer_than_three_runs_is_said_loudly(tmp_path: Path, capsys) -> None:
    """The brief: a single run is not a measurement. Say so on stderr and on paper."""
    root = tmp_path / "runs"
    build_run_dir(root, rate="60pm", run_index=1, n_samples=8)
    out_dir = tmp_path / "out"

    status = summarise_load.main(["--runs", str(root), "--out-dir", str(out_dir)])
    captured = capsys.readouterr()

    # Not an exit failure -- the run is real, it is just not yet a measurement.
    assert status == 0
    assert "WARNING" in captured.err
    assert "only 1 run(s) found" in captured.err
    assert "single run is not a measurement" in captured.err

    config_md = (out_dir / "load_per_config.md").read_text(encoding="utf-8")
    assert "FEWER THAN 3 RUNS" in config_md
    summary_md = (out_dir / "load_summary.md").read_text(encoding="utf-8")
    assert "Warnings" in summary_md
    assert "only 1 run(s) found" in summary_md


def test_three_runs_are_not_warned_about(tmp_path: Path, capsys) -> None:
    """The complement of the test above: a complete configuration is quiet."""
    root = tmp_path / "runs"
    for index in (1, 2, 3):
        build_run_dir(root, rate="60pm", run_index=index, n_samples=8)
    status = summarise_load.main(
        ["--runs", str(root), "--out-dir", str(tmp_path / "out")]
    )
    captured = capsys.readouterr()
    assert status == 0
    assert "FEWER THAN 3 RUNS" not in captured.err
    assert "WARNING" not in captured.err


def test_dev_mode_runs_are_flagged_as_not_evidence(tmp_path: Path, capsys) -> None:
    """A dev-mode run is synthetic-ticket traffic and must not slip into a slide."""
    root = tmp_path / "runs"
    for index in (1, 2, 3):
        build_run_dir(
            root, run_index=index, n_samples=5, metadata_overrides={"mode": "dev"}
        )
    status = summarise_load.main(
        ["--runs", str(root), "--out-dir", str(tmp_path / "out")]
    )
    captured = capsys.readouterr()
    assert status == 0
    assert "DEV MODE" in captured.err
    assert "NOT evidence" in captured.err


# ---------------------------------------------------------------------------
# tables, definitions and charts
# ---------------------------------------------------------------------------

def test_tables_and_definitions_are_written(tmp_path: Path) -> None:
    """A marker must be able to check our definitions without reading the code."""
    root = tmp_path / "runs"
    for index in (1, 2, 3):
        build_run_dir(root, run_index=index, n_samples=6)
    out_dir = tmp_path / "out"

    assert summarise_load.main(["--runs", str(root), "--out-dir", str(out_dir)]) == 0

    for stem in ("load_per_run", "load_per_config"):
        assert (out_dir / f"{stem}.csv").is_file()
        assert (out_dir / f"{stem}.md").is_file()

    per_run = (out_dir / "load_per_run.csv").read_text(encoding="utf-8")
    assert per_run.count("\n") == 4  # header plus three runs
    for column in ("client_p99_ms", "server_p99_ms", "throughput_per_hour", "error_rate_pct"):
        assert column in per_run

    report = (out_dir / "load_summary.md").read_text(encoding="utf-8")
    assert "JMeter `elapsed`" in report
    assert "Achieved throughput" in report
    assert "per hour" in report
    assert "Linear interpolation" in report
    assert "Warm-up" in report
    assert "reconcile.py" in report


def test_one_chart_per_model_is_created(tmp_path: Path) -> None:
    """Slide 9 wants latency against arrival rate, one chart per candidate model."""
    root = tmp_path / "runs"
    for model in ("testmodel-1b", "othermodel-3b"):
        for rate in ("60pm", "120pm"):
            for index in (1, 2, 3):
                build_run_dir(
                    root,
                    model=model,
                    rate=rate,
                    run_index=index,
                    n_samples=6,
                    base_latency_ms=1000 + 100 * index,
                )
    out_dir = tmp_path / "out"

    assert summarise_load.main(["--runs", str(root), "--out-dir", str(out_dir)]) == 0

    charts = sorted(p.name for p in out_dir.glob("*.png"))
    assert charts == [
        "latency_vs_rate_othermodel-3b.png",
        "latency_vs_rate_testmodel-1b.png",
    ]
    for name in charts:
        assert (out_dir / name).stat().st_size > 0
        assert name in (out_dir / "load_summary.md").read_text(encoding="utf-8")


def test_ramp_runs_are_left_to_the_stress_script(tmp_path: Path) -> None:
    """A stepped ramp has no single arrival rate, so it gets no latency-vs-rate line."""
    root = tmp_path / "runs"
    build_run_dir(root, plan="stress_ramp", rate="ramp", run_index=1, n_samples=6)
    out_dir = tmp_path / "out"
    assert summarise_load.main(["--runs", str(root), "--out-dir", str(out_dir)]) == 0
    assert not list(out_dir.glob("*.png"))
    # It is still summarised as a run, so the sample counts are not lost.
    assert "stress_ramp" in (out_dir / "load_per_run.csv").read_text(encoding="utf-8")


def test_mixed_load_samples_are_also_split_by_label(build_run) -> None:
    """POST /tickets and GET /search latencies must not be pooled silently."""
    run = build_run(plan="mixed_load", n_samples=10, n_errors=0)
    rows = read_jtl_rows(run.jtl)
    for row in rows[5:]:
        row["label"] = "GET /search"
    write_jtl(run.jtl, rows)

    summary = summarise(run)
    assert set(summary.by_label) == {"POST /tickets", "GET /search"}
    assert summary.by_label["GET /search"]["samples"] == 5
    assert summary.by_label["POST /tickets"]["samples"] == 5
    # The headline row still counts every sample, and names the labels it pooled.
    assert summary.metrics["samples"] == 10
    assert summary.row()["labels"] == "GET /search;POST /tickets"

    frame = summarise_load.per_label_frame([summary])
    assert sorted(frame["label"]) == ["GET /search", "POST /tickets"]


# ---------------------------------------------------------------------------
# filters and failure behaviour
# ---------------------------------------------------------------------------

def test_model_and_plan_filters(tmp_path: Path) -> None:
    """--model accepts the Ollama tag or its sanitised form; --plan is exact."""
    root = tmp_path / "runs"
    build_run_dir(root, model="testmodel-1b", plan="load_post_tickets", n_samples=5)
    build_run_dir(root, model="othermodel-3b", plan="load_post_tickets", n_samples=5)
    build_run_dir(root, model="testmodel-1b", plan="mixed_load", n_samples=5)

    out_dir = tmp_path / "out"
    assert (
        summarise_load.main(
            [
                "--runs",
                str(root),
                "--out-dir",
                str(out_dir),
                "--model",
                "testmodel:1b",
                "--plan",
                "load_post_tickets",
            ]
        )
        == 0
    )
    per_run = (out_dir / "load_per_run.csv").read_text(encoding="utf-8")
    assert per_run.count("\n") == 2  # header plus the single matching run
    assert "othermodel" not in per_run
    assert "mixed_load" not in per_run


def test_a_filter_that_matches_nothing_exits_non_zero(tmp_path: Path, capsys) -> None:
    """Summarising zero runs and printing an empty table is the failure we cannot afford."""
    root = tmp_path / "runs"
    build_run_dir(root, model="testmodel-1b", n_samples=5)
    status = summarise_load.main(
        ["--runs", str(root), "--out-dir", str(tmp_path / "out"), "--model", "absent:7b"]
    )
    assert status != 0
    assert "No runs" in capsys.readouterr().err


def test_no_runs_found_exits_non_zero(tmp_path: Path, capsys) -> None:
    """An empty or absent results directory is a failure, not an empty report."""
    empty = tmp_path / "empty"
    empty.mkdir()
    assert summarise_load.main(["--runs", str(empty), "--out-dir", str(tmp_path / "o")]) != 0
    assert "no directories matching" in capsys.readouterr().err

    assert (
        summarise_load.main(
            ["--runs", str(tmp_path / "missing"), "--out-dir", str(tmp_path / "o")]
        )
        != 0
    )
    assert "No such results directory" in capsys.readouterr().err


def test_missing_metadata_exits_non_zero(tmp_path: Path, capsys) -> None:
    """A run without its model pin and freeze commit is not evidence."""
    root = tmp_path / "runs"
    run = build_run_dir(root, n_samples=5)
    (run.path / "metadata.json").unlink()

    status = summarise_load.main(
        ["--runs", str(root), "--out-dir", str(tmp_path / "out")]
    )
    assert status != 0
    err = capsys.readouterr().err
    assert "metadata.json" in err
    assert "is not" in err  # "...is not evidence"


def test_no_output_is_written_when_a_run_is_unusable(tmp_path: Path) -> None:
    """Fail before writing tables, so a half-written report cannot be quoted."""
    root = tmp_path / "runs"
    run = build_run_dir(root, n_samples=5)
    (run.path / "metadata.json").unlink()
    out_dir = tmp_path / "out"

    assert summarise_load.main(["--runs", str(root), "--out-dir", str(out_dir)]) != 0
    assert not out_dir.exists()
