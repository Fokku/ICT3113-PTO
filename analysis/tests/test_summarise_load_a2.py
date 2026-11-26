"""Tests for ``analysis/summarise_load_a2.py``.

Owner: Yeo Kai Yuan (Part 1).

Every fixture is fabricated by ``conftest.build_a2_run_dir``: no model is run and
no number produced here is ever reported. The expected values are hand-computed
from the fixtures' known latencies, with the derivation next to each assertion,
so a change in a definition shows up as a failing number rather than a silently
different table.

The campaign built once for the module covers each case the brief and the
playbook name: three single-model reference runs, a cascade with mixed
escalation (including a length-rule escalation), a cascade setting with two
queued runs and a large escalation gap, a run with unfinished and errored
requests, a run with a mid-run model reload, a run that sent more tickets than
the list holds, and an Assignment 1 run that must be ignored.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pandas as pd
import pytest

from analysis import summarise_load_a2

from conftest import (  # noqa: E402
    UNFINISHED_CODE,
    A2Sample,
    build_a2_accuracy_dir,
    build_a2_run_dir,
    build_run_dir,
    make_jtl_row,
    steady_samples,
)

PATTERN_A = [False, True, False, False, True, False]   # 2 of 6 escalated
PATTERN_B = [True, True, False, True, True, False]     # 4 of 6 escalated


def _parse(value: str) -> object:
    """A CSV cell back to what was written: blank -> None, True/False, int, float, text."""
    if value == "":
        return None
    if value in ("True", "False"):
        return value == "True"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    try:
        return float(value)
    except ValueError:
        return value


def read_rows(path: Path) -> list[dict[str, object]]:
    """The rows of one of the script's CSV outputs, with typed cells."""
    with path.open(newline="", encoding="utf-8") as handle:
        return [{key: _parse(value) for key, value in row.items()}
                for row in csv.DictReader(handle)]


def first_row(tmp_path: Path, name: str = "per_run.csv") -> dict[str, object]:
    return read_rows(tmp_path / "out" / name)[0]


def build_campaign(root: Path) -> dict[str, Path]:
    """The module's fabricated campaign; returns the paths a test needs."""
    runs = root / "runs"
    # qwen2.5:7b, the reference: elapsed 2000..2500 step 100, shifted 0/100/200.
    for k, shift in enumerate([0, 100, 200], 1):
        build_a2_run_dir(runs, steady_samples([2000 + shift + 100 * i for i in range(6)]),
                         config="qwen2.5:7b", run_index=k)

    # cascade-A: accepted answers take 1000/1100/1200 ms, escalations 3000 ms.
    # In run 1 the second escalation is a length-rule one (no small-model call).
    for k, accepted in enumerate([1000, 1100, 1200], 1):
        samples = [
            A2Sample(offset_ms=10_000 * i, elapsed_ms=3000 if flag else accepted,
                     escalated=flag, skipped_small=(k == 1 and i == 4))
            for i, flag in enumerate(PATTERN_A)
        ]
        build_a2_run_dir(runs, samples, cascade_setting="A", run_index=k)

    # cascade-B: run 1 valid; run 2 queued by halves (+50%); run 3 queued by a
    # 150 ms median queue wait.
    flat = [3000 if flag else 1000 for flag in PATTERN_B]
    build_a2_run_dir(runs, steady_samples(flat, escalated=PATTERN_B),
                     cascade_setting="B", run_index=1)
    build_a2_run_dir(runs, steady_samples([3000, 3000, 1000, 4500, 4500, 1500],
                                          escalated=PATTERN_B),
                     cascade_setting="B", run_index=2)
    build_a2_run_dir(runs, steady_samples(flat, escalated=PATTERN_B, other_ms=150.0),
                     cascade_setting="B", run_index=3)

    # granite4:3b, one run: an unfinished request (client timed out at 300 s, the
    # service finished and stored it) and an errored one (502, not stored).
    build_a2_run_dir(runs, [
        A2Sample(0, 1500),
        A2Sample(10_000, 1600),
        A2Sample(20_000, 300_000, code=UNFINISHED_CODE),
        A2Sample(30_000, 1700),
        A2Sample(40_000, 1800),
        A2Sample(50_000, 1900),
        A2Sample(60_000, 120_000, code="502"),
    ], config="granite4:3b")

    # llama3.2:3b: one request paid a 5 s model load mid-run.
    reload_samples = steady_samples([1200] * 6)
    reload_samples[3] = A2Sample(30_000, 8000, load_ms=5000.0)
    build_a2_run_dir(runs, reload_samples, config="llama3.2:3b")

    # llama3.2:1b: 101 samples, more than the 100-ticket list holds.
    build_a2_run_dir(runs, steady_samples([900] * 101, interval_ms=3000),
                     config="llama3.2:1b-instruct-q4_K_M")

    # An Assignment 1 run in the same folder: never read.
    build_run_dir(runs)

    acc = root / "accuracy_a2"
    build_a2_accuracy_dir(acc, setting="A", stamp="20261118T120000Z", escalated=[True] * 10)
    build_a2_accuracy_dir(acc, setting="A", stamp="20261119T120000Z",
                          escalated=[True] * 4 + [False] * 6)
    build_a2_accuracy_dir(acc, setting="A", stamp="20261120T120000Z",
                          escalated=[False] * 10, rows_set="tuning")
    build_a2_accuracy_dir(acc, setting="B", stamp="20261119T130000Z",
                          escalated=[True] + [False] * 9)

    verdicts = root / "verdicts.csv"
    with verdicts.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["config", "passes_accuracy"])
        writer.writerows([["qwen2.5:7b", "true"], ["cascade-A", "true"],
                          ["cascade-B", "false"], ["granite4:3b", "true"]])
    return {"runs": runs, "acc": acc, "verdicts": verdicts, "out": root / "out"}


@pytest.fixture(scope="module")
def campaign(tmp_path_factory) -> dict[str, object]:
    """Build the campaign once, run the CLI once, and read the outputs back."""
    root = tmp_path_factory.mktemp("a2")
    paths = build_campaign(root)
    status = summarise_load_a2.main([
        "--runs", str(paths["runs"]), "--out-dir", str(paths["out"]),
        "--accuracy-root", str(paths["acc"]), "--accuracy-verdicts", str(paths["verdicts"]),
    ])
    per_run = read_rows(paths["out"] / "per_run.csv")
    per_config = read_rows(paths["out"] / "per_config.csv")
    return {
        "status": status,
        "paths": paths,
        "per_run": per_run,
        "per_config": per_config,
        "columns": [pd.read_csv(paths["out"] / name, nrows=0).columns.tolist()
                    for name in ("per_run.csv", "per_config.csv")],
        "runs": {row["run_id"]: row for row in per_run},
        "configs": {row["config"]: row for row in per_config},
        "report": (paths["out"] / "report.md").read_text(encoding="utf-8"),
    }


def run_row(campaign, fragment: str) -> dict[str, object]:
    """The one per-run row whose run_id contains ``fragment``."""
    matches = [row for run_id, row in campaign["runs"].items() if fragment in run_id]
    assert len(matches) == 1, f"{fragment!r} matched {len(matches)} rows"
    return matches[0]


def run_cli(tmp_path: Path, runs: Path, *extra: str) -> int:
    return summarise_load_a2.main(["--runs", str(runs), "--out-dir", str(tmp_path / "out"),
                                   "--accuracy-root", str(tmp_path / "no-accuracy"), *extra])


# ---------------------------------------------------------------------------
# the campaign: every run is there, nothing else is
# ---------------------------------------------------------------------------

def test_the_cli_succeeds_and_every_speed_run_is_reported(campaign) -> None:
    assert campaign["status"] == 0
    # 3 qwen + 3 cascade-A + 3 cascade-B + granite + llama3.2:3b + llama3.2:1b.
    assert len(campaign["per_run"]) == 12
    assert all("_speed_a2_" in run_id for run_id in campaign["runs"])
    # The Assignment 1 run in the same folder is never read.
    assert not any("load_post_tickets" in run_id for run_id in campaign["runs"])
    assert set(campaign["configs"]) == {
        "qwen2.5:7b", "granite4:3b", "llama3.2:1b-instruct-q4_K_M", "llama3.2:3b",
        "cascade-A", "cascade-B",
    }
    # The reference first, then the single models, then the cascade.
    order = [row["config"] for row in campaign["per_config"]]
    assert order[0] == "qwen2.5:7b"
    assert order[-2:] == ["cascade-A", "cascade-B"]


def test_reference_run_figures_are_exact(campaign) -> None:
    row = run_row(campaign, "qwen2.5-7b_speed_a2_5pm_run1")
    assert (row["sent"], row["completed"], row["errored"], row["unfinished"]) == (6, 6, 0, 0)
    # elapsed 2000, 2100, ..., 2500: median of six = (2200 + 2300) / 2.
    assert row["p50_ms"] == pytest.approx(2250.0)
    assert row["n_latency"] == 6
    # Starts at 0, 10, ..., 50 s: midpoint 25 s, so 3 + 3. First half
    # 2000/2100/2200 -> 2100; second 2300/2400/2500 -> 2400; +300/2100 = +14.29%.
    assert (row["n_first_half"], row["n_second_half"]) == (3, 3)
    assert row["p50_first_half_ms"] == pytest.approx(2100.0)
    assert row["p50_second_half_ms"] == pytest.approx(2400.0)
    assert row["halves_change_pct"] == pytest.approx(100 * 300 / 2100)
    # ollama_other_ms is fabricated as exactly 10 ms on every line.
    assert row["queue_wait_median_ms"] == pytest.approx(10.0)
    assert row["queue_residual_median_ms"] == pytest.approx(5.0)
    assert row["no_queue_check"] == "pass"
    # span: first start 0 s to last end 50 s + 2.5 s = 52.5 s.
    assert row["span_s"] == pytest.approx(52.5)
    assert row["throughput_rps"] == pytest.approx(6 / 52.5)
    assert row["error_rate_pct"] == pytest.approx(0.0)
    # GET /stats: 100 before, 106 after.
    assert (row["stats_total_before"], row["stats_total_after"], row["stats_delta"]) == (
        100, 106, 6)
    assert row["stats_delta_equals_completed"] is True
    assert row["warmup_requests"] == 3
    assert row["max_load_duration_ms"] == pytest.approx(1.0)
    assert row["valid"] is True
    assert row["reasons"] is None
    # A single-model run has no escalation figure.
    assert row["escalation_fraction"] is None and row["escalated_count"] is None


def test_reference_configuration_spread_and_pooled_p95(campaign) -> None:
    cfg = campaign["configs"]["qwen2.5:7b"]
    assert (cfg["n_runs"], cfg["n_valid_runs"]) == (3, 3)
    assert cfg["p50_per_run_ms"] == "run1=2250.0; run2=2350.0; run3=2450.0"
    assert cfg["p50_mean_ms"] == pytest.approx(2350.0)
    assert (cfg["p50_min_ms"], cfg["p50_max_ms"]) == (pytest.approx(2250.0), pytest.approx(2450.0))
    assert cfg["p50_sd_ms"] == pytest.approx(100.0)  # sample SD of 2250, 2350, 2450
    # 18 pooled values; sorted[16] = 2600, sorted[17] = 2700; linear index
    # 0.95 * 17 = 16.15 -> 2600 + 0.15 * 100 = 2615.
    assert cfg["pooled_p95_ms"] == pytest.approx(2615.0)
    assert cfg["pooled_n"] == 18
    span = {1: 52.5, 2: 52.6, 3: 52.7}  # last end = 50 s + 2500/2600/2700 ms
    assert cfg["throughput_mean_rps"] == pytest.approx(sum(6 / s for s in span.values()) / 3)
    assert cfg["faster_than_reference"] == "reference"
    assert cfg["passes_accuracy"] == "true" and cfg["label"] is None


# ---------------------------------------------------------------------------
# the cascade
# ---------------------------------------------------------------------------

def test_cascade_escalation_fraction_per_run_and_pooled(campaign) -> None:
    row = run_row(campaign, "cascade-A_speed_a2_5pm_run1")
    assert row["cascade_setting"] == "A"
    # 2 of 6 escalated, one of them by the length rule (no small-model call).
    assert (row["escalated_count"], row["escalation_total"]) == (2, 6)
    assert row["escalation_fraction"] == pytest.approx(2 / 6)
    # Four answers at 1000 ms and two at 3000 ms: the median is 1000.
    assert row["p50_ms"] == pytest.approx(1000.0)
    assert row["valid"] is True
    assert row["reconcile_ok"] is True

    cfg = campaign["configs"]["cascade-A"]
    assert (cfg["escalated_count"], cfg["escalation_total"]) == (6, 18)
    assert cfg["escalation_fraction"] == pytest.approx(6 / 18)
    assert cfg["p50_per_run_ms"] == "run1=1000.0; run2=1100.0; run3=1200.0"
    # 4 x 1000, 4 x 1100, 4 x 1200, 6 x 3000: sorted[16] = sorted[17] = 3000.
    assert cfg["pooled_p95_ms"] == pytest.approx(3000.0) and cfg["pooled_n"] == 18
    # [1000, 1200] lies entirely below qwen2.5:7b's [2250, 2450].
    assert cfg["faster_than_reference"] == "yes: distinguishably faster"


def test_accuracy_escalation_uses_the_newest_test_set_run(campaign) -> None:
    cfg = campaign["configs"]["cascade-A"]
    # The newest A directory is a tuning-set run (skipped); the oldest is 10/10.
    assert cfg["accuracy_run_id"] == "cascade-A_20261119T120000Z"
    assert (cfg["accuracy_escalated_count"], cfg["accuracy_escalation_total"]) == (4, 10)
    assert cfg["accuracy_escalation_fraction"] == pytest.approx(0.4)
    # 100 * (6/18 - 0.4) = -6.67 pp, inside the 15 pp threshold.
    assert cfg["escalation_gap_pp"] == pytest.approx(100 * (6 / 18 - 0.4))
    assert cfg["escalation_gap_flag"] is False
    assert "rows_set='tuning'" in campaign["report"]
    assert "older test-set accuracy run(s) not used: `cascade-A_20261118T120000Z`" in (
        campaign["report"])


def test_a_large_escalation_gap_is_flagged(campaign) -> None:
    cfg = campaign["configs"]["cascade-B"]
    # Only run 1 is valid: 4 of 6 escalated against 1 of 10 in the accuracy test.
    assert (cfg["escalated_count"], cfg["escalation_total"]) == (4, 6)
    assert cfg["escalation_gap_pp"] == pytest.approx(100 * (4 / 6 - 0.1))
    assert cfg["escalation_gap_flag"] is True
    row = run_row(campaign, "cascade-B_speed_a2_5pm_run1")
    assert row["escalation_gap_flag"] is True
    assert "explain it" in row["notes"]
    assert "explain any large gap" in campaign["report"]


def test_queued_runs_are_flagged_and_not_compared_on_p50(campaign) -> None:
    halves = run_row(campaign, "cascade-B_speed_a2_5pm_run2")
    # First half 3000/3000/1000 -> 3000; second 4500/4500/1500 -> 4500: +50%.
    assert halves["halves_change_pct"] == pytest.approx(50.0)
    assert halves["no_queue_check"] == "queued"
    assert halves["queued"] is True and halves["valid"] is False
    assert "flagged as queued, not compared on p50" in halves["reasons"]

    waiting = run_row(campaign, "cascade-B_speed_a2_5pm_run3")
    assert waiting["halves_change_pct"] == pytest.approx(0.0)
    assert waiting["queue_wait_median_ms"] == pytest.approx(150.0)
    assert waiting["no_queue_check"] == "queued"
    assert "median queue wait 150.0 ms" in waiting["reasons"]

    cfg = campaign["configs"]["cascade-B"]
    assert (cfg["n_runs"], cfg["n_valid_runs"], cfg["runs_counted"]) == (3, 1, "run1")
    # Both queued runs are still listed, marked, with their p50.
    assert cfg["p50_per_run_ms"] == "run1=3000.0; run2=3000.0 [queued]; run3=3000.0 [queued]"
    assert cfg["p50_min_ms"] == pytest.approx(3000.0) and cfg["p50_max_ms"] == pytest.approx(3000.0)
    assert cfg["pooled_n"] == 6
    # [3000, 3000] lies entirely above qwen2.5:7b's [2250, 2450].
    assert cfg["faster_than_reference"] == "no: slower"
    assert "ONLY 1 VALID RUN(S)" in cfg["warning"]
    # Part 3's verdict says it fails accuracy: still reported, labelled.
    assert cfg["passes_accuracy"] == "false"
    assert cfg["label"] == "not passing accuracy"
    assert "cascade-B: NOT PASSING ACCURACY" in campaign["report"]


# ---------------------------------------------------------------------------
# unfinished, errored, reload, repeats
# ---------------------------------------------------------------------------

def test_a_run_with_unfinished_requests_is_reported_not_dropped(campaign) -> None:
    row = run_row(campaign, "granite4-3b_speed_a2")
    assert (row["sent"], row["completed"], row["errored"], row["unfinished"]) == (7, 5, 1, 1)
    # Completed elapsed 1500, 1600, 1700, 1800, 1900.
    assert row["p50_ms"] == pytest.approx(1700.0) and row["n_latency"] == 5
    # Midpoint 30 s: first half 1500/1600 -> 1550 (the 20 s request is unfinished);
    # second 1700/1800/1900 -> 1800 (the 60 s request errored).
    assert row["p50_first_half_ms"] == pytest.approx(1550.0)
    assert row["p50_second_half_ms"] == pytest.approx(1800.0)
    assert row["halves_change_pct"] == pytest.approx(100 * 250 / 1550)
    # The service stored the unfinished request too: delta 6 = completed + 1.
    assert row["stats_delta"] == 6
    assert row["stats_delta_equals_completed"] is False
    assert row["stats_consistent"] is True
    # error rate counts errored and unfinished: 2 / 7.
    assert row["error_rate_pct"] == pytest.approx(100 * 2 / 7)
    # span: 0 s to max(20 + 300, 60 + 120) = 320 s.
    assert row["throughput_rps"] == pytest.approx(5 / 320)
    # Only the six HTTP 200 log lines carry Ollama timings.
    assert row["n_queue_wait"] == 6
    # Unfinished requests are not a validity failure (playbook section 6).
    assert row["reconcile_ok"] is True
    assert row["valid"] is True
    assert "1 unfinished request(s)" in row["notes"]
    cfg = campaign["configs"]["granite4:3b"]
    assert (cfg["sent_total"], cfg["unfinished_total"], cfg["errored_total"]) == (7, 1, 1)
    assert "FEWER THAN 3 RUNS (n=1)" in cfg["warning"]


def test_a_mid_run_reload_is_a_loading_result(campaign) -> None:
    row = run_row(campaign, "llama3.2-3b_speed_a2")
    assert row["reload"] is True
    assert row["reload_requests"] == 1
    assert row["max_load_duration_ms"] == pytest.approx(5000.0)
    assert row["valid"] is False
    assert "loading result" in row["reasons"]
    cfg = campaign["configs"]["llama3.2:3b"]
    assert cfg["faster_than_reference"] == "not comparable: no valid runs"
    assert cfg["passes_accuracy"] == "unknown"


def test_more_samples_than_the_ticket_list_is_a_repeat(campaign) -> None:
    row = run_row(campaign, "llama3.2-1b-instruct-q4_K_M_speed_a2")
    assert row["sent"] == 101 and row["distinct_source_rows"] == 101
    assert row["repeats"] is True
    assert row["valid"] is False
    assert "sent 101 > 100 tickets" in row["reasons"]


def test_a_faster_second_half_is_not_a_queue(tmp_path: Path) -> None:
    # prediction_record_a2.md §4 (frozen): second-half p50 no more than 20% ABOVE the first's.
    # First half 3000/3000/3000 -> 3000; second 2000/2000/2000 -> 2000: -33%, not queued.
    build_a2_run_dir(tmp_path / "runs", steady_samples([3000, 3000, 3000, 2000, 2000, 2000]))
    assert run_cli(tmp_path, tmp_path / "runs") == 0
    row = first_row(tmp_path)
    assert row["halves_change_pct"] == pytest.approx(-100 / 3)
    assert row["no_queue_check"] != "queued"
    assert row["queued"] is False


def test_a_repeated_source_row_is_a_repeat_even_under_the_limit(tmp_path: Path) -> None:
    samples = steady_samples([1000] * 5)
    samples[4] = A2Sample(40_000, 1000, source_row="20000")
    build_a2_run_dir(tmp_path / "runs", samples)
    assert run_cli(tmp_path, tmp_path / "runs") == 0
    row = first_row(tmp_path)
    assert row["repeats"] is True
    assert "repeat a source_row" in row["reasons"]


# ---------------------------------------------------------------------------
# the brief's prohibitions
# ---------------------------------------------------------------------------

def test_no_p99_anywhere_in_the_outputs(campaign) -> None:
    out: Path = campaign["paths"]["out"]
    files = sorted(out.iterdir())
    assert {path.name for path in files} == {
        "per_run.csv", "per_run.md", "per_config.csv", "per_config.md", "report.md"}
    for path in files:
        assert "p99" not in path.name.lower()
        assert "p99" not in path.read_text(encoding="utf-8").lower(), path.name
    for columns in campaign["columns"]:
        assert not [c for c in columns if "99" in c]
    # ...and the report says so in words.
    assert "no 99th-percentile figure appears anywhere in this output" in campaign["report"]


def test_the_report_states_its_definitions_and_thresholds(campaign) -> None:
    report = campaign["report"]
    for needle in ("## Definitions used in this report", "## Thresholds in force",
                   "at most +20%", "under 100 ms", "more than 15 pp",
                   "above 1000 ms", "at most 100 sent", "Split by time at the midpoint",
                   "`ollama_other_ms`", "No Assignment 1 speed figure is used"):
        assert needle in report, needle


def test_thresholds_come_from_the_command_line(tmp_path: Path) -> None:
    build_a2_run_dir(tmp_path / "runs", steady_samples([1000, 1000, 1000, 1150, 1150, 1150]))
    # +15% passes at the default +20% and fails at +10%.
    assert run_cli(tmp_path, tmp_path / "runs") == 0
    row = first_row(tmp_path)
    assert row["no_queue_check"] == "pass"
    assert run_cli(tmp_path, tmp_path / "runs", "--halves-tolerance", "0.10") == 0
    row = first_row(tmp_path)
    assert row["no_queue_check"] == "queued"
    assert "limit +10%" in row["reasons"]


def test_the_halves_are_split_by_time_not_by_count(tmp_path: Path) -> None:
    # Four arrivals in the first 3 s and one at 100 s: the midpoint is 50 s, so the
    # halves hold 4 and 1 samples (an equal-count split would give 3 and 2).
    samples = [A2Sample(0, 1000), A2Sample(1000, 1000), A2Sample(2000, 1000),
               A2Sample(3000, 2000), A2Sample(100_000, 2000)]
    build_a2_run_dir(tmp_path / "runs", samples)
    assert run_cli(tmp_path, tmp_path / "runs") == 0
    row = first_row(tmp_path)
    assert (row["n_first_half"], row["n_second_half"]) == (4, 1)
    assert row["p50_first_half_ms"] == pytest.approx(1000.0)
    assert row["p50_second_half_ms"] == pytest.approx(2000.0)
    assert row["halves_change_pct"] == pytest.approx(100.0)


def test_overlapping_ranges_are_not_distinguishable(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    for k, value in enumerate([2000, 2100, 2200], 1):
        build_a2_run_dir(runs, steady_samples([value] * 4), config="qwen2.5:7b", run_index=k)
    for k, value in enumerate([1800, 1900, 2000], 1):
        build_a2_run_dir(runs, steady_samples([value] * 4), config="granite4:3b",
                         run_index=k)
    assert run_cli(tmp_path, runs) == 0
    configs = {row["config"]: row for row in read_rows(tmp_path / "out" / "per_config.csv")}
    granite = configs["granite4:3b"]
    # [1800, 2000] touches qwen2.5:7b's [2000, 2200]: not entirely below.
    assert granite["faster_than_reference"] == "no: not distinguishable (p50 ranges overlap)"


def test_output_never_goes_to_the_assignment_1_load_directory(tmp_path: Path) -> None:
    build_a2_run_dir(tmp_path / "runs", steady_samples([1000] * 4))
    for target in (summarise_load_a2.A1_LOAD_OUT_DIR,
                   summarise_load_a2.A1_LOAD_OUT_DIR / "speed_a2"):
        status = summarise_load_a2.main(["--runs", str(tmp_path / "runs"),
                                         "--out-dir", str(target)])
        assert status == 1
    assert not (summarise_load_a2.A1_LOAD_OUT_DIR / "speed_a2").exists()
    assert not (summarise_load_a2.A1_LOAD_OUT_DIR / "per_run.csv").exists()


def test_the_default_output_directory_is_speed_a2() -> None:
    parser = summarise_load_a2.build_arg_parser()
    assert parser.get_default("out_dir") == Path("analysis/output/speed_a2")
    assert parser.get_default("runs") == Path("results/runs")
    assert parser.get_default("halves_tolerance") == 0.20
    assert parser.get_default("queue_wait_ms") == 100.0
    assert parser.get_default("gap_threshold_pp") == 15.0
    assert parser.get_default("reload_threshold_ms") == 1000.0
    assert parser.get_default("max_tickets") == 100


# ---------------------------------------------------------------------------
# validity checks on a single run
# ---------------------------------------------------------------------------

def _one_run(tmp_path: Path, **kwargs) -> dict[str, object]:
    build_a2_run_dir(tmp_path / "runs", steady_samples([1000] * 4), **kwargs)
    assert run_cli(tmp_path, tmp_path / "runs") == 0
    return first_row(tmp_path)


def test_a_missing_gate_makes_the_run_invalid(tmp_path: Path) -> None:
    row = _one_run(tmp_path, gate_ok=None)
    assert row["gate_ok"] is False and row["valid"] is False
    assert "gate.json missing" in row["reasons"]


def test_a_stats_delta_that_does_not_match_makes_the_run_invalid(tmp_path: Path) -> None:
    row = _one_run(tmp_path, stats_delta=2)
    assert row["stats_delta"] == 2 and row["completed"] == 4
    assert row["stats_consistent"] is False
    assert "stats delta 2 inconsistent with completed 4" in row["reasons"]


def test_missing_stats_make_the_run_invalid(tmp_path: Path) -> None:
    run = build_a2_run_dir(tmp_path / "runs", steady_samples([1000] * 4),
                           metadata_overrides={"stats_total_before": None,
                                               "stats_total_after": None})
    (run.path / "stats_before.json").unlink()
    assert run_cli(tmp_path, tmp_path / "runs") == 0
    row = first_row(tmp_path)
    assert row["stats_delta"] is None
    assert "GET /stats total before/after not recorded" in row["reasons"]


def test_stats_are_read_from_the_saved_bodies_when_metadata_lacks_them(tmp_path: Path) -> None:
    build_a2_run_dir(tmp_path / "runs", steady_samples([1000] * 4),
                     metadata_overrides={"stats_total_before": None,
                                         "stats_total_after": None})
    assert run_cli(tmp_path, tmp_path / "runs") == 0
    row = first_row(tmp_path)
    assert (row["stats_total_before"], row["stats_total_after"], row["stats_delta"]) == (
        100, 104, 4)
    assert row["valid"] is True


def test_models_not_resident_before_the_run_make_it_invalid(tmp_path: Path) -> None:
    row = _one_run(tmp_path, cascade_setting="A",
                   metadata_overrides={"all_expected_resident_before": False})
    assert "not every expected model was resident before the run" in row["reasons"]


def test_residency_after_the_run_is_only_a_note(tmp_path: Path) -> None:
    row = _one_run(tmp_path, metadata_overrides={"all_expected_resident_after": False})
    assert row["valid"] is True
    assert "OLLAMA_KEEP_ALIVE" in row["notes"]


def test_fewer_than_three_warmups_make_the_run_invalid(tmp_path: Path) -> None:
    row = _one_run(tmp_path, n_warmup=1)
    assert row["warmup_requests"] == 1
    assert "1 warm-up request(s) found, 3 required" in row["reasons"]


def test_a_dev_mode_run_is_never_valid(tmp_path: Path, capsys) -> None:
    build_a2_run_dir(tmp_path / "runs", steady_samples([1000] * 4),
                     metadata_overrides={"mode": "dev"})
    assert run_cli(tmp_path, tmp_path / "runs") == 0
    row = first_row(tmp_path)
    assert row["valid"] is False and "mode=dev" in row["reasons"]
    assert "NOT evidence" in capsys.readouterr().err


def test_a_failing_reconciliation_makes_the_run_invalid(tmp_path: Path) -> None:
    # A cascade line that claims the large model answered without escalating.
    row = _one_run(tmp_path, cascade_setting="A",
                   line_overrides={1: {"model_tag": "qwen2.5:7b"}})
    assert row["reconcile_ok"] is False
    assert "reconcile.py: 1 blocker(s)" in row["reasons"]


def test_warmups_listed_only_in_metadata_are_excluded(tmp_path: Path) -> None:
    run = build_a2_run_dir(tmp_path / "runs", steady_samples([1000] * 4))
    (run.path / "warmup.jsonl").unlink()
    with run.jtl.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(make_jtl_row()))
        writer.writerow(make_jtl_row(elapsed=60_000,
                                     request_id=run.metadata["warmup_request_ids"][1],
                                     source_row="30001"))
    assert run_cli(tmp_path, tmp_path / "runs") == 0
    row = first_row(tmp_path)
    assert row["sent"] == 4 and row["p50_ms"] == pytest.approx(1000.0)
    assert row["warmup_requests"] == 3


# ---------------------------------------------------------------------------
# failing loudly
# ---------------------------------------------------------------------------

def test_no_speed_a2_runs_exits_non_zero(tmp_path: Path, capsys) -> None:
    build_run_dir(tmp_path / "runs")  # an Assignment 1 run only
    assert run_cli(tmp_path, tmp_path / "runs") == 1
    err = capsys.readouterr().err
    assert "No speed_a2 run directories" in err
    assert not (tmp_path / "out").exists()


def test_a_missing_runs_directory_exits_non_zero(tmp_path: Path) -> None:
    assert run_cli(tmp_path, tmp_path / "nowhere") == 1


def test_a_run_without_metadata_exits_non_zero(tmp_path: Path, capsys) -> None:
    run = build_a2_run_dir(tmp_path / "runs", steady_samples([1000] * 4))
    (run.path / "metadata.json").unlink()
    assert run_cli(tmp_path, tmp_path / "runs") == 1
    assert "metadata.json is missing" in capsys.readouterr().err


def test_a_malformed_verdicts_file_exits_non_zero(tmp_path: Path, capsys) -> None:
    build_a2_run_dir(tmp_path / "runs", steady_samples([1000] * 4))
    verdicts = tmp_path / "verdicts.csv"
    verdicts.write_text("config,passes_accuracy\nqwen2.5:7b,maybe\n", encoding="utf-8")
    assert run_cli(tmp_path, tmp_path / "runs", "--accuracy-verdicts", str(verdicts)) == 1
    assert "passes_accuracy must be true or false" in capsys.readouterr().err
    verdicts.write_text("model,verdict\nqwen2.5:7b,true\n", encoding="utf-8")
    assert run_cli(tmp_path, tmp_path / "runs", "--accuracy-verdicts", str(verdicts)) == 1


def test_verdicts_match_either_spelling_of_a_tag(tmp_path: Path) -> None:
    build_a2_run_dir(tmp_path / "runs", steady_samples([1000] * 4))
    verdicts = tmp_path / "verdicts.csv"
    verdicts.write_text("config,passes_accuracy\nqwen2.5-7b,TRUE\n", encoding="utf-8")
    assert run_cli(tmp_path, tmp_path / "runs", "--accuracy-verdicts", str(verdicts)) == 0
    cfg = first_row(tmp_path, "per_config.csv")
    assert cfg["passes_accuracy"] == "true"


def test_fewer_than_three_runs_is_warned_loudly(tmp_path: Path, capsys) -> None:
    build_a2_run_dir(tmp_path / "runs", steady_samples([1000] * 4))
    assert run_cli(tmp_path, tmp_path / "runs") == 0
    err = capsys.readouterr().err
    assert "only 1 run(s) found" in err
    report = (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    assert "only 1 run(s) found" in report


def test_runs_at_different_rates_are_warned(tmp_path: Path, capsys) -> None:
    build_a2_run_dir(tmp_path / "runs", steady_samples([1000] * 4), rate="5pm")
    build_a2_run_dir(tmp_path / "runs", steady_samples([1000] * 4), rate="6pm",
                     config="granite4:3b")
    assert run_cli(tmp_path, tmp_path / "runs") == 0
    assert "Runs differ in rate" in capsys.readouterr().err


def test_metadata_written_by_the_contract_is_what_the_fixture_writes(tmp_path: Path) -> None:
    """Guard the fixture itself: the keys the run-script contract promises are present."""
    run = build_a2_run_dir(tmp_path / "runs", steady_samples([1000] * 4), cascade_setting="A")
    meta = json.loads((run.path / "metadata.json").read_text(encoding="utf-8"))
    for key in ("assignment", "config", "service_mode", "cascade_setting",
                "cascade_small_model_tag", "cascade_large_model_tag", "gate_commit",
                "s_seconds", "warmup_request_ids", "warmup_request_id",
                "stats_total_before", "stats_total_after", "all_expected_resident_before",
                "all_expected_resident_after", "env_check_ok", "jtl_samples", "mode"):
        assert key in meta, key
    assert meta["freeze_commit"] is None
    assert run.path.name == "20261120T090000Z_cascade-A_speed_a2_5pm_run1"


def test_an_unmeasured_run_is_reported_not_fatal(tmp_path: Path) -> None:
    """scripts/run_load_test_a2.sh keeps a run it refused to measure (models not
    resident) with ``measured: false`` and no results.jtl. Playbook section 6: it is
    reported as invalid, never dropped, and never breaks the rest of the campaign."""
    runs = tmp_path / "runs"
    for k in (1, 2, 3):
        build_a2_run_dir(runs, steady_samples([1000, 1100, 1200, 1300]), run_index=k)
    unmeasured = runs / "20261120T100000Z_cascade-A_speed_a2_5pm_run1"
    unmeasured.mkdir(parents=True)
    (unmeasured / "gate.json").write_text('{"ok": true}', encoding="utf-8")
    (unmeasured / "metadata.json").write_text(json.dumps({
        "run_id": unmeasured.name, "mode": "real", "plan": "speed_a2", "config": "cascade-A",
        "service_mode": "cascade", "cascade_setting": "A", "measured": False,
        "all_expected_resident_before": False,
        "notes": "NOT MEASURED: expected model(s) not all resident before the run; ",
    }), encoding="utf-8")

    assert run_cli(tmp_path, runs) == 0
    rows = {row["run_id"]: row for row in read_rows(tmp_path / "out" / "per_run.csv")}
    row = rows[unmeasured.name]
    assert row["valid"] is False
    assert row["sent"] == 0
    assert row["p50_ms"] is None
    assert "not measured" in str(row["reasons"]).lower()
    configs = {row["config"]: row for row in read_rows(tmp_path / "out" / "per_config.csv")}
    assert configs["cascade-A"]["n_valid_runs"] == 0
    assert configs["qwen2.5:7b"]["n_valid_runs"] == 3
