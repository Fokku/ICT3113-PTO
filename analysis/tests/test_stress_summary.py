"""Tests for ``analysis/stress_summary.py``.

The ramps here are fabricated with ``conftest``'s JMeter row builder, one shape
per behaviour we have to be able to tell apart: a ramp that breaches the latency
requirement, one that breaches the error-rate limit, one that breaches both in
the same step, one that saturates without breaching anything, and one that never
stressed the system at all and must therefore fail.

Every sample inside one step is given the same ``elapsed`` value, so p50, p95 and
p99 for that step are that value and the expected numbers can be checked by hand.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

from conftest import BASE_TIME, make_jtl_row, make_metadata, write_jtl

from analysis import stress_summary

STEP_SECONDS = 120.0


def build_stress_run(
    root: Path,
    steps: list[dict],
    *,
    step_seconds: float = STEP_SECONDS,
    model: str = "testmodel-1b",
    stamp: str = "20261001T090000Z",
    plan: str = "stress_ramp",
    mode: str = "real",
    label: str = "POST /tickets",
    extra_rows: list[dict] | None = None,
) -> Path:
    """Write a fabricated stepped-ramp run directory.

    ``steps`` is one dict per step: ``n`` samples, all with ``latency_ms``, of
    which the first ``errors`` failed, spread evenly over the first ``span_s``
    seconds of the step (default: the whole step). ``stress_summary.py`` reads
    only ``results.jtl`` and ``metadata.json``, so only those are written.
    """
    run_dir = root / f"{stamp}_{model}_{plan}_ramp_run1"
    run_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for index, step in enumerate(steps):
        n_samples = int(step["n"])
        latency = float(step["latency_ms"])
        n_errors = int(step.get("errors", 0))
        span = float(step.get("span_s", step_seconds))
        start = index * step_seconds
        for sample in range(n_samples):
            offset = start + (sample * span / n_samples)
            failed = sample < n_errors
            rows.append(
                make_jtl_row(
                    timeStamp=int((BASE_TIME + timedelta(seconds=offset)).timestamp() * 1000),
                    elapsed=int(latency),
                    Latency=int(latency) - 1,
                    label=label,
                    responseCode="502" if failed else "200",
                    success="false" if failed else "true",
                    request_id=f"req-{index}-{sample}",
                    source_row=str(10000 + index * 1000 + sample),
                )
            )
    write_jtl(run_dir / "results.jtl", rows + (extra_rows or []))
    meta = make_metadata(run_id=run_dir.name, plan=plan, mode=mode, model_tag="testmodel:1b")
    (run_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return run_dir


def arithmetic_ramp(latencies: list[float], *, rate_start: int = 30, rate_step: int = 30,
                    errors: list[int] | None = None) -> list[dict]:
    """A ramp whose achieved rate tracks an offered rate of 30, 60, 90, ... /min.

    With a 120 s step, an offered rate of R per minute is 2R samples in the step,
    so the achieved rate equals the offered rate exactly and the tracking ratio
    is 1.0 until a test deliberately breaks it.
    """
    return [
        {
            "n": int((rate_start + index * rate_step) * step_seconds_in_minutes()),
            "latency_ms": latency,
            "errors": 0 if errors is None else errors[index],
        }
        for index, latency in enumerate(latencies)
    ]


def step_seconds_in_minutes() -> float:
    """The step duration expressed in minutes (so rate/min -> samples/step)."""
    return STEP_SECONDS / 60.0


def read_steps(out_dir: Path) -> pd.DataFrame:
    """The per-step table as written to disk."""
    return pd.read_csv(out_dir / "stress_steps.csv")


def read_signals(out_dir: Path) -> dict:
    """The one-row saturation-signal table as written to disk."""
    frame = pd.read_csv(out_dir / "stress_signals.csv")
    assert len(frame) == 1
    return frame.iloc[0].to_dict()


# ---------------------------------------------------------------------------
# The limit
# ---------------------------------------------------------------------------

def test_first_step_to_breach_p95_is_reported_as_the_limit(tmp_path, capsys):
    run_dir = build_stress_run(
        tmp_path / "runs", arithmetic_ramp([1000, 1200, 1500, 2000])
    )
    out_dir = tmp_path / "out"

    code = stress_summary.main(
        [
            "--run-dir", str(run_dir),
            "--p95-limit-ms", "1400",
            "--ramp-start-per-min", "30",
            "--ramp-step-per-min", "30",
            "--out-dir", str(out_dir),
            "--no-charts",
        ]
    )

    assert code == 0
    captured = capsys.readouterr()
    assert "Limit: step 3" in captured.out
    assert "p95 1500.0 ms > limit 1400.0 ms" in captured.out
    assert "error rate" not in captured.out.split("Limit:")[1].split("\n")[0]
    steps = read_steps(out_dir)
    assert list(steps["step"]) == [1, 2, 3, 4]
    assert list(steps["offered_per_min"]) == [30.0, 60.0, 90.0, 120.0]
    assert list(steps["achieved_per_min"]) == [30.0, 60.0, 90.0, 120.0]
    assert list(steps["samples"]) == [60, 120, 180, 240]
    assert list(steps["p95_ms"]) == [1000.0, 1200.0, 1500.0, 2000.0]
    assert list(steps["p50_ms"]) == [1000.0, 1200.0, 1500.0, 2000.0]
    assert all(ratio == pytest.approx(1.0) for ratio in steps["tracking_ratio"])
    report = (out_dir / "stress_report.md").read_text(encoding="utf-8")
    assert "First step to cross a criterion: step 3" in report


def test_first_step_to_breach_the_error_rate_is_reported_as_the_limit(tmp_path, capsys):
    # Latency stays flat and well inside the requirement; only errors appear.
    steps = arithmetic_ramp([1000, 1000, 1000], errors=[0, 1, 5])
    run_dir = build_stress_run(tmp_path / "runs", steps)
    out_dir = tmp_path / "out"

    code = stress_summary.main(
        ["--run-dir", str(run_dir), "--p95-limit-ms", "5000",
         "--error-rate-limit", "0.01", "--ramp-start-per-min", "30",
         "--ramp-step-per-min", "30", "--out-dir", str(out_dir), "--no-charts"]
    )

    assert code == 0
    captured = capsys.readouterr()
    # Step 2 has 1 error in 120 samples (0.0083), inside the limit; step 3 has
    # 5 in 180 (0.0278), outside it.
    assert "Limit: step 3" in captured.out
    assert "error rate 0.0278 > limit 0.0100" in captured.out
    assert "p95" not in captured.out.split("Limit:")[1].split("\n")[0]
    steps_table = read_steps(out_dir)
    assert list(steps_table["errors"]) == [0, 1, 5]
    assert steps_table.loc[1, "error_rate"] == pytest.approx(1 / 120)
    assert steps_table.loc[2, "error_rate_pct"] == pytest.approx(100 * 5 / 180)


def test_both_criteria_in_one_step_are_both_named(tmp_path, capsys):
    steps = arithmetic_ramp([1000, 1000, 9000], errors=[0, 0, 40])
    run_dir = build_stress_run(tmp_path / "runs", steps)
    out_dir = tmp_path / "out"

    code = stress_summary.main(
        ["--run-dir", str(run_dir), "--p95-limit-ms", "2000",
         "--ramp-start-per-min", "30", "--ramp-step-per-min", "30",
         "--out-dir", str(out_dir), "--no-charts"]
    )

    assert code == 0
    limit_line = capsys.readouterr().out.split("Limit:")[1].split("\n")[0]
    assert "p95 9000.0 ms > limit 2000.0 ms" in limit_line
    assert "error rate" in limit_line
    assert " and " in limit_line


# ---------------------------------------------------------------------------
# Threshold-free saturation signals
# ---------------------------------------------------------------------------

def test_monotonic_p95_rise_counts_as_saturation_without_any_limit(tmp_path, capsys):
    # No p95 requirement supplied and no errors, so nothing can "trip"; the ramp
    # is still evidence of unbounded growth because every step is worse.
    run_dir = build_stress_run(
        tmp_path / "runs", arithmetic_ramp([1000, 1500, 2200, 3000])
    )
    out_dir = tmp_path / "out"

    code = stress_summary.main(
        ["--run-dir", str(run_dir), "--ramp-start-per-min", "30",
         "--ramp-step-per-min", "30", "--out-dir", str(out_dir), "--no-charts"]
    )

    assert code == 0
    captured = capsys.readouterr()
    assert "Limit: none found within this ramp" in captured.out
    assert "p95 monotonic rise=True" in captured.out
    signals = read_signals(out_dir)
    assert bool(signals["p95_monotonic_rise"]) is True
    assert bool(signals["achieved_plateau"]) is False
    assert signals["p95_rise_factor"] == pytest.approx(3000 / 1500)  # last 3 steps
    report = (out_dir / "stress_report.md").read_text(encoding="utf-8")
    assert "TODO(Part 4 — Teammate X)" in report  # no p95 requirement was supplied


def test_achieved_rate_that_stops_tracking_the_offered_rate_is_saturation(tmp_path, capsys):
    # Offered 30, 60, 90, 120 per minute; the service stops keeping up after 60.
    steps = [
        {"n": 60, "latency_ms": 1000},
        {"n": 120, "latency_ms": 1100},
        {"n": 120, "latency_ms": 1050},   # offered rose, achieved did not
        {"n": 120, "latency_ms": 1100},   # and again
    ]
    run_dir = build_stress_run(tmp_path / "runs", steps)
    out_dir = tmp_path / "out"

    code = stress_summary.main(
        ["--run-dir", str(run_dir), "--offered-rates", "30,60,90,120",
         "--out-dir", str(out_dir), "--no-charts"]
    )

    assert code == 0
    captured = capsys.readouterr()
    assert "achieved-rate plateau=True" in captured.out
    signals = read_signals(out_dir)
    # p95 is not monotonic here, so the plateau is doing the work on its own.
    assert bool(signals["p95_monotonic_rise"]) is False
    assert bool(signals["achieved_plateau"]) is True
    assert signals["tracking_ratio_last"] == pytest.approx(60 / 120)
    assert "offered 60->90/min" in str(signals["plateau_detail"])


def test_a_ramp_that_never_stressed_the_system_fails(tmp_path, capsys):
    run_dir = build_stress_run(
        tmp_path / "runs", arithmetic_ramp([1000, 1000, 1000])
    )
    out_dir = tmp_path / "out"

    code = stress_summary.main(
        ["--run-dir", str(run_dir), "--p95-limit-ms", "5000",
         "--ramp-start-per-min", "30", "--ramp-step-per-min", "30",
         "--out-dir", str(out_dir), "--no-charts"]
    )

    assert code == 1
    captured = capsys.readouterr()
    assert stress_summary.NO_STRESS_MESSAGE in captured.err
    assert "must be re-run at higher rates" in captured.err
    # The tables are still written: the operator needs to see what the ramp did.
    assert (out_dir / "stress_steps.csv").is_file()
    assert stress_summary.NO_STRESS_MESSAGE in (
        out_dir / "stress_report.md"
    ).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Cutting the ramp into steps
# ---------------------------------------------------------------------------

def test_step_seconds_cuts_the_window_and_counts_each_step(tmp_path):
    steps = [
        {"n": 30, "latency_ms": 900},
        {"n": 90, "latency_ms": 1100},
        {"n": 150, "latency_ms": 1300},
    ]
    run_dir = build_stress_run(tmp_path / "runs", steps)
    out_dir = tmp_path / "out"

    assert stress_summary.main(
        ["--run-dir", str(run_dir), "--step-seconds", "120",
         "--out-dir", str(out_dir), "--no-charts"]
    ) == 0

    table = read_steps(out_dir)
    assert list(table["samples"]) == [30, 90, 150]
    assert list(table["start_s"]) == [0.0, 120.0, 240.0]
    assert list(table["end_s"]) == [120.0, 240.0, 360.0]
    assert list(table["duration_s"]) == [120.0, 120.0, 120.0]
    # 30 samples in 120 s is 15 per minute.
    assert list(table["achieved_per_min"]) == [15.0, 45.0, 75.0]


def test_explicit_step_boundaries_are_honoured_and_extra_samples_excluded(tmp_path, capsys):
    run_dir = build_stress_run(
        tmp_path / "runs", arithmetic_ramp([1000, 1200, 1500, 2000])
    )
    out_dir = tmp_path / "out"

    assert stress_summary.main(
        ["--run-dir", str(run_dir), "--step-boundaries", "0,120,240,360",
         "--out-dir", str(out_dir), "--no-charts"]
    ) == 0

    table = read_steps(out_dir)
    # Four boundaries define three steps, so the fourth step of the ramp lies
    # outside the analysed window and must be reported as excluded rather than
    # quietly folded into the last step.
    assert list(table["step"]) == [1, 2, 3]
    assert list(table["samples"]) == [60, 120, 180]
    assert list(table["end_s"]) == [120.0, 240.0, 360.0]
    assert "fall outside the step boundaries" in capsys.readouterr().err
    report = (out_dir / "stress_report.md").read_text(encoding="utf-8")
    assert "excluded by the step boundaries: 240" in report


def test_a_partial_final_step_is_dropped_with_a_warning(tmp_path, capsys):
    steps = arithmetic_ramp([1000, 1100, 1200])
    # A fourth step that the run only got 20 s into before it stopped.
    steps.append({"n": 10, "latency_ms": 9999, "span_s": 20.0})
    run_dir = build_stress_run(tmp_path / "runs", steps)
    out_dir = tmp_path / "out"

    code = stress_summary.main(
        ["--run-dir", str(run_dir), "--step-seconds", "120",
         "--out-dir", str(out_dir), "--no-charts"]
    )

    assert code == 0  # the first three steps rise monotonically
    captured = capsys.readouterr()
    assert "is dropped" in captured.err
    assert "partial step(s) were dropped" in captured.err
    table = read_steps(out_dir)
    assert list(table["step"]) == [1, 2, 3]
    assert 9999.0 not in list(table["p95_ms"])


def test_offered_rate_absent_leaves_the_tracking_signal_unassessed(tmp_path, capsys):
    run_dir = build_stress_run(
        tmp_path / "runs", arithmetic_ramp([1000, 1200, 1500])
    )
    out_dir = tmp_path / "out"

    code = stress_summary.main(
        ["--run-dir", str(run_dir), "--p95-limit-ms", "1400",
         "--out-dir", str(out_dir), "--no-charts"]
    )

    assert code == 0
    captured = capsys.readouterr()
    assert "No offered rate was supplied" in captured.err
    assert "Limit: step 3" in captured.out
    signals = read_signals(out_dir)
    assert bool(signals["offered_known"]) is False
    assert bool(signals["achieved_plateau"]) is False
    assert "not assessed" in str(signals["plateau_detail"])
    table = read_steps(out_dir)
    assert table["offered_per_min"].isna().all()
    # The limit is still reported, with the offered rate honestly shown as n/a.
    assert "Offered rate: n/a" in (out_dir / "stress_report.md").read_text(
        encoding="utf-8"
    )


def test_offered_rates_shorter_than_the_ramp_is_an_error(tmp_path, capsys):
    run_dir = build_stress_run(
        tmp_path / "runs", arithmetic_ramp([1000, 1100, 1200])
    )

    code = stress_summary.main(
        ["--run-dir", str(run_dir), "--offered-rates", "30,60",
         "--out-dir", str(tmp_path / "out"), "--no-charts"]
    )

    assert code == 1
    assert "Give one offered rate per step" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Chart, sampler labels, CLI
# ---------------------------------------------------------------------------

def test_chart_is_written(tmp_path):
    run_dir = build_stress_run(
        tmp_path / "runs", arithmetic_ramp([1000, 1500, 2200, 3000])
    )
    out_dir = tmp_path / "out"

    assert stress_summary.main(
        ["--run-dir", str(run_dir), "--p95-limit-ms", "2000",
         "--ramp-start-per-min", "30", "--ramp-step-per-min", "30",
         "--out-dir", str(out_dir)]
    ) == 0

    png = out_dir / "stress_ramp.png"
    assert png.is_file()
    payload = png.read_bytes()
    assert payload[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(payload) > 5_000


def test_mixed_sampler_labels_warn_and_can_be_filtered(tmp_path, capsys):
    steps = arithmetic_ramp([1000, 1100, 1200])
    search_rows = [
        make_jtl_row(
            timeStamp=int((BASE_TIME + timedelta(seconds=offset)).timestamp() * 1000),
            elapsed=20,
            Latency=19,
            label="GET /search",
            request_id=f"search-{offset}",
        )
        for offset in range(0, 300, 10)
    ]
    run_dir = build_stress_run(tmp_path / "runs", steps, extra_rows=search_rows)
    out_dir = tmp_path / "out"

    # Without --label the two samplers are pooled, which is warned about: the
    # search samples are counted as arrivals and drag the percentiles.
    assert stress_summary.main(
        ["--run-dir", str(run_dir), "--step-seconds", "120",
         "--out-dir", str(out_dir), "--no-charts"]
    ) == 0
    assert "mixes 2 sampler labels" in capsys.readouterr().err
    assert list(read_steps(out_dir)["samples"]) == [72, 132, 186]

    # With --label only the POST sampler is analysed, and the counts match the
    # ramp exactly again.
    assert stress_summary.main(
        ["--run-dir", str(run_dir), "--step-seconds", "120", "--label", "POST /tickets",
         "--out-dir", str(out_dir), "--no-charts"]
    ) == 0
    assert list(read_steps(out_dir)["samples"]) == [60, 120, 180]


def test_a_plan_that_is_not_the_stress_ramp_warns(tmp_path, capsys):
    run_dir = build_stress_run(
        tmp_path / "runs", arithmetic_ramp([1000, 1500, 2200]), plan="load_post_tickets"
    )

    stress_summary.main(
        ["--run-dir", str(run_dir), "--out-dir", str(tmp_path / "out"), "--no-charts"]
    )

    assert "not 'stress_ramp'" in capsys.readouterr().err


def test_missing_run_directory_exits_non_zero(tmp_path, capsys):
    code = stress_summary.main(
        ["--run-dir", str(tmp_path / "nope"), "--out-dir", str(tmp_path / "out")]
    )
    assert code == 1
    assert "No such run directory" in capsys.readouterr().err


def test_help_is_available_without_any_evidence():
    with pytest.raises(SystemExit) as raised:
        stress_summary.parse_args(["--help"])
    assert raised.value.code == 0


def test_defaults_match_the_cli_contract():
    args = stress_summary.parse_args(["--run-dir", "results/runs/example"])
    assert args.error_rate_limit == 0.01
    assert args.step_seconds == 120.0
    assert args.p95_limit_ms is None
    assert args.monotonic_steps == 3
    assert args.out_dir == stress_summary.REPO_ROOT / "analysis" / "output" / "stress"


# ---------------------------------------------------------------------------
# Where step 1 begins (--origin)
# ---------------------------------------------------------------------------

def _late_first_arrival_run(root: Path, lag_s: float = 40.0) -> Path:
    """Steps of 10, 30 and 50 samples, where step 1's arrivals start ``lag_s`` late.

    This is what random arrivals do at a low first rate: the schedule starts at
    BASE_TIME but the first sample is stamped later, while later steps are full.
    Counting steps from the first sample then shifts every boundary by ``lag_s``.
    """
    steps = [{"n": n, "latency_ms": 1000} for n in (10, 30, 50)]
    run_dir = build_stress_run(root, steps)
    jtl = pd.read_csv(run_dir / "results.jtl")
    first = jtl["request_id"].astype(str).str.startswith("req-0-")
    index = jtl.loc[first, "request_id"].astype(str).str.split("-").str[2].astype(int)
    base_ms = int(BASE_TIME.timestamp() * 1000)
    jtl.loc[first, "timeStamp"] = base_ms + int(lag_s * 1000) + index * int((STEP_SECONDS - lag_s) * 1000 / 10)
    jtl.to_csv(run_dir / "results.jtl", index=False)
    return run_dir


def test_steps_from_the_first_sample_are_shifted_by_its_arrival_delay(tmp_path):
    run_dir = _late_first_arrival_run(tmp_path / "runs")
    out_dir = tmp_path / "out"
    stress_summary.main(["--run-dir", str(run_dir), "--step-seconds", "120",
                         "--out-dir", str(out_dir), "--no-charts"])
    assert list(read_steps(out_dir)["samples"]) != [10, 30, 50]


def test_an_explicit_origin_puts_every_sample_back_in_its_own_step(tmp_path, capsys):
    run_dir = _late_first_arrival_run(tmp_path / "runs")
    out_dir = tmp_path / "out"
    stress_summary.main(
        ["--run-dir", str(run_dir), "--step-seconds", "120", "--origin", BASE_TIME.isoformat(),
         "--out-dir", str(out_dir), "--no-charts"]
    )
    assert list(read_steps(out_dir)["samples"]) == [10, 30, 50]
    assert "first sample arrived 40.0 s later" in (out_dir / "stress_report.md").read_text(encoding="utf-8")


def test_origin_jmeter_log_converts_the_local_log_time_to_utc(tmp_path):
    run_dir = _late_first_arrival_run(tmp_path / "runs")
    meta = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    launched = BASE_TIME - timedelta(seconds=0.8)
    meta["started_at_utc"] = launched.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    (run_dir / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    local = BASE_TIME + timedelta(hours=8)  # a UTC+8 load generator
    (run_dir / "jmeter.log").write_text(
        f"{local:%Y-%m-%d %H:%M:%S},000 INFO o.a.j.t.o.OpenModelThreadGroup: Starting OpenModelThreadGroup#1\n",
        encoding="utf-8",
    )
    start = stress_summary.schedule_start_from_jmeter_log(run_dir)
    assert start == pd.Timestamp(BASE_TIME).tz_convert("UTC")
    out_dir = tmp_path / "out"
    stress_summary.main(
        ["--run-dir", str(run_dir), "--step-seconds", "120", "--origin", "jmeter-log",
         "--out-dir", str(out_dir), "--no-charts"]
    )
    assert list(read_steps(out_dir)["samples"]) == [10, 30, 50]


def test_an_origin_after_the_first_sample_is_refused(tmp_path):
    run_dir = _late_first_arrival_run(tmp_path / "runs")
    late = (BASE_TIME + timedelta(seconds=100)).isoformat()
    assert stress_summary.main(
        ["--run-dir", str(run_dir), "--step-seconds", "120", "--origin", late,
         "--out-dir", str(tmp_path / "out"), "--no-charts"]
    ) != 0
