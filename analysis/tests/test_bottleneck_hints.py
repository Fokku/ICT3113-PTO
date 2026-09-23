"""Tests for ``analysis/bottleneck_hints.py``.

Each fabricated run below is built so that one component of the request clearly
dominates, which is what lets the verdict be asserted. The breakdown is an
identity -- the six components sum to ``total_latency_ms`` -- so the fixtures are
written with that arithmetic done by hand:

``total_latency_ms = service overhead + queue residual + (Ollama's total_duration,
itself load + prompt evaluation + generation + the remainder we report as
ollama_other_ms)``.

Nothing here runs a model and none of these numbers is ever reported.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

from conftest import BASE_TIME, iso_ms, make_log_line, make_metadata, write_service_log

from analysis import bottleneck_hints

MS = 1_000_000  # nanoseconds per millisecond, for readable fixtures


def build_log_run(
    root: Path,
    records: list[dict],
    *,
    model_tag: str = "testmodel:1b",
    mode: str = "real",
    plan: str = "load_post_tickets",
    stamp: str = "20261001T090000Z",
    model: str = "testmodel-1b",
) -> Path:
    """Write a run directory holding just what this script reads."""
    run_dir = root / f"{stamp}_{model}_{plan}_60pm_run1"
    run_dir.mkdir(parents=True, exist_ok=True)
    write_service_log(run_dir / "service.jsonl", records)
    meta = make_metadata(run_id=run_dir.name, plan=plan, mode=mode, model_tag=model_tag)
    (run_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return run_dir


def timed_request(
    *,
    total_latency_ms: float,
    model_latency_ms: float,
    total_duration_ms: float,
    load_ms: float,
    prompt_eval_ms: float,
    eval_ms: float,
    seconds: int = 0,
    **overrides,
) -> dict:
    """One log line whose timings are written in milliseconds for readability.

    ``overrides`` are applied last, so a test can replace any of the defaults
    (including the request id) without colliding with them.
    """
    fields = {
        "ts": iso_ms(BASE_TIME + timedelta(seconds=seconds)),
        "request_id": f"req-{seconds}",
        "source_row": str(10000 + seconds),
        "total_latency_ms": total_latency_ms,
        "model_latency_ms": model_latency_ms,
        "total_duration": int(total_duration_ms * MS),
        "load_duration": int(load_ms * MS),
        "prompt_eval_duration": int(prompt_eval_ms * MS),
        "eval_duration": int(eval_ms * MS),
    }
    fields.update(overrides)
    return make_log_line(**fields)


#: A request whose time is dominated by each component in turn. Every dict is
#: internally consistent: the six components sum to total_latency_ms.
DOMINANT_CASES: dict[str, dict[str, float]] = {
    "service_overhead_ms": dict(
        total_latency_ms=5000.0, model_latency_ms=990.0, total_duration_ms=990.0,
        load_ms=10.0, prompt_eval_ms=400.0, eval_ms=570.0,
    ),
    "queue_residual_ms": dict(
        total_latency_ms=5010.0, model_latency_ms=5000.0, total_duration_ms=990.0,
        load_ms=10.0, prompt_eval_ms=400.0, eval_ms=570.0,
    ),
    "load_ms": dict(
        total_latency_ms=6000.0, model_latency_ms=5990.0, total_duration_ms=5980.0,
        load_ms=5000.0, prompt_eval_ms=400.0, eval_ms=570.0,
    ),
    "prompt_eval_ms": dict(
        total_latency_ms=5600.0, model_latency_ms=5590.0, total_duration_ms=5580.0,
        load_ms=10.0, prompt_eval_ms=5000.0, eval_ms=570.0,
    ),
    "eval_ms": dict(
        total_latency_ms=1000.0, model_latency_ms=990.0, total_duration_ms=990.0,
        load_ms=10.0, prompt_eval_ms=400.0, eval_ms=570.0,
    ),
}


def read_breakdown(out_dir: Path) -> pd.DataFrame:
    """The component breakdown table as written to disk."""
    return pd.read_csv(out_dir / "bottleneck_breakdown.csv").set_index("component")


# ---------------------------------------------------------------------------
# The verdict: one run per dominant component
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("component", sorted(DOMINANT_CASES))
def test_the_largest_component_is_named_in_the_verdict(tmp_path, component, capsys):
    run_dir = build_log_run(
        tmp_path / "runs",
        [timed_request(seconds=index, **DOMINANT_CASES[component]) for index in range(3)],
    )
    out_dir = tmp_path / "out"

    assert bottleneck_hints.main(
        ["--run-dir", str(run_dir), "--out-dir", str(out_dir), "--no-charts"]
    ) == 0

    assert f"Largest mean component: {component}" in capsys.readouterr().out
    report = (out_dir / "bottleneck_report.md").read_text(encoding="utf-8")
    assert f"**{component}**" in report
    # The verdict explains the mechanism rather than leaving the reader a number.
    assert bottleneck_hints.COMPONENT_VERDICTS[component][:40] in report


def test_components_sum_to_the_measured_total_latency(tmp_path):
    case = DOMINANT_CASES["eval_ms"]
    run_dir = build_log_run(
        tmp_path / "runs", [timed_request(seconds=index, **case) for index in range(4)]
    )
    out_dir = tmp_path / "out"

    assert bottleneck_hints.main(
        ["--run-dir", str(run_dir), "--out-dir", str(out_dir), "--no-charts"]
    ) == 0

    breakdown = read_breakdown(out_dir)
    means = {name: breakdown.loc[name, "mean_ms"] for name in bottleneck_hints.COMPONENTS}
    assert means["service_overhead_ms"] == pytest.approx(10.0)
    assert means["queue_residual_ms"] == pytest.approx(0.0)
    assert means["load_ms"] == pytest.approx(10.0)
    assert means["prompt_eval_ms"] == pytest.approx(400.0)
    assert means["eval_ms"] == pytest.approx(570.0)
    # Ollama's own total is not exactly load + prefill + generation; the
    # remainder is reported, not distributed.
    assert means["ollama_other_ms"] == pytest.approx(10.0)
    assert sum(means.values()) == pytest.approx(breakdown.loc["total_latency_ms", "mean_ms"])
    shares = breakdown.loc[list(bottleneck_hints.COMPONENTS), "share_of_mean_total_pct"]
    assert float(shares.sum()) == pytest.approx(100.0)
    assert (out_dir / "bottleneck_breakdown.md").is_file()


def test_the_queue_term_is_labelled_a_residual(tmp_path):
    case = DOMINANT_CASES["queue_residual_ms"]
    run_dir = build_log_run(tmp_path / "runs", [timed_request(**case)])
    out_dir = tmp_path / "out"

    assert bottleneck_hints.main(
        ["--run-dir", str(run_dir), "--out-dir", str(out_dir), "--no-charts"]
    ) == 0

    breakdown = read_breakdown(out_dir)
    assert breakdown.loc["queue_residual_ms", "mean_ms"] == pytest.approx(4010.0)
    assert "RESIDUAL" in breakdown.loc["queue_residual_ms", "note"]
    report = (out_dir / "bottleneck_report.md").read_text(encoding="utf-8")
    assert "**residual**" in report
    # The report must name the other things that inflate it, so nobody quotes it
    # as measured queueing time.
    assert "container" in report
    assert "connection" in report


# ---------------------------------------------------------------------------
# Requests we cannot break down
# ---------------------------------------------------------------------------

def test_requests_with_no_ollama_timings_are_excluded_and_counted(tmp_path, capsys):
    good = [timed_request(seconds=index, **DOMINANT_CASES["eval_ms"]) for index in range(3)]
    failed = [
        make_log_line(
            ts=iso_ms(BASE_TIME + timedelta(seconds=10 + index)),
            request_id=f"failed-{index}",
            source_row=str(20000 + index),
            status=502,
            predicted_category=None,
            raw_model_output=None,
            error="ollama_timeout",
            model_latency_ms=120000.0,
            total_duration=None,
            load_duration=None,
            prompt_eval_count=None,
            prompt_eval_duration=None,
            eval_count=None,
            eval_duration=None,
        )
        for index in range(2)
    ]
    run_dir = build_log_run(tmp_path / "runs", good + failed)
    out_dir = tmp_path / "out"

    assert bottleneck_hints.main(
        ["--run-dir", str(run_dir), "--out-dir", str(out_dir), "--no-charts"]
    ) == 0

    captured = capsys.readouterr()
    assert "Requests in the breakdown: 3" in captured.out
    assert "excluded for missing Ollama timings: 2" in captured.out
    assert "2 of 5 POST /tickets request(s) returned no Ollama timings" in captured.err
    report = (out_dir / "bottleneck_report.md").read_text(encoding="utf-8")
    assert "Requests excluded because Ollama returned no timings: 2" in report
    assert "ollama_timeout" in report
    # The 120 s timeout must not appear in the breakdown: it cannot be
    # attributed to a stage, so it would only distort the means.
    per_request = pd.read_csv(out_dir / "bottleneck_per_request.csv")
    assert len(per_request) == 3
    assert 120000.0 not in list(per_request["model_latency_ms"])


def test_a_run_whose_every_model_call_failed_exits_non_zero(tmp_path, capsys):
    failed = [
        make_log_line(
            request_id=f"failed-{index}",
            status=502,
            predicted_category=None,
            raw_model_output=None,
            error="ollama_connect_error",
            total_duration=None,
            load_duration=None,
            prompt_eval_duration=None,
            eval_duration=None,
        )
        for index in range(3)
    ]
    run_dir = build_log_run(tmp_path / "runs", failed)

    code = bottleneck_hints.main(
        ["--run-dir", str(run_dir), "--out-dir", str(tmp_path / "out"), "--no-charts"]
    )

    assert code == 1
    assert "no breakdown" in capsys.readouterr().err


def test_non_ticket_lines_are_counted_separately_not_as_failures(tmp_path):
    records = [timed_request(seconds=index, **DOMINANT_CASES["eval_ms"]) for index in range(2)]
    records += [
        make_log_line(
            ts=iso_ms(BASE_TIME + timedelta(seconds=30)),
            request_id="search-1",
            endpoint="/search",
            method="GET",
            source_row=None,
            ticket_chars=None,
            predicted_category=None,
            raw_model_output=None,
            model_tag=None,
            model_digest=None,
            prompt_hash=None,
            num_ctx=None,
            seed=None,
            model_latency_ms=None,
            total_duration=None,
            load_duration=None,
            prompt_eval_count=None,
            prompt_eval_duration=None,
            eval_count=None,
            eval_duration=None,
            total_latency_ms=12.3,
        )
    ]
    run_dir = build_log_run(tmp_path / "runs", records)
    out_dir = tmp_path / "out"

    assert bottleneck_hints.main(
        ["--run-dir", str(run_dir), "--out-dir", str(out_dir), "--no-charts"]
    ) == 0

    report = (out_dir / "bottleneck_report.md").read_text(encoding="utf-8")
    assert "Measured POST /tickets requests: 2" in report
    assert "Requests excluded because Ollama returned no timings: 0" in report
    assert "Non-/tickets log lines skipped (no model call to break down): 1" in report


def test_warmup_lines_are_excluded(tmp_path):
    records = [timed_request(seconds=index, **DOMINANT_CASES["eval_ms"]) for index in range(2)]
    # A warm-up line pays the model-load cost. exclude_warmup() must drop it even
    # if it reaches service.jsonl, or load_ms would dominate every run.
    records.append(
        timed_request(
            seconds=99, warmup=True, request_id="warm",
            total_latency_ms=9000.0, model_latency_ms=8990.0,
            total_duration_ms=8980.0, load_ms=8000.0, prompt_eval_ms=400.0, eval_ms=570.0,
        )
    )
    run_dir = build_log_run(tmp_path / "runs", records)
    out_dir = tmp_path / "out"

    assert bottleneck_hints.main(
        ["--run-dir", str(run_dir), "--out-dir", str(out_dir), "--no-charts"]
    ) == 0

    breakdown = read_breakdown(out_dir)
    assert breakdown.loc["load_ms", "mean_ms"] == pytest.approx(10.0)
    assert breakdown.loc["total_latency_ms", "mean_ms"] == pytest.approx(1000.0)


def test_a_negative_residual_is_reported_and_only_clamped_in_the_chart(tmp_path, capsys):
    # Our own clock says the HTTP call took less than Ollama says it spent: the
    # residual goes negative and must be visible, not hidden.
    run_dir = build_log_run(
        tmp_path / "runs",
        [
            timed_request(
                total_latency_ms=990.0, model_latency_ms=980.0, total_duration_ms=990.0,
                load_ms=10.0, prompt_eval_ms=400.0, eval_ms=570.0,
            )
        ],
    )
    out_dir = tmp_path / "out"

    assert bottleneck_hints.main(
        ["--run-dir", str(run_dir), "--out-dir", str(out_dir)]
    ) == 0

    assert "negative queue_residual_ms" in capsys.readouterr().err
    breakdown = read_breakdown(out_dir)
    assert breakdown.loc["queue_residual_ms", "mean_ms"] == pytest.approx(-10.0)
    assert (out_dir / "bottleneck_stacked.png").is_file()


# ---------------------------------------------------------------------------
# Tokens per second and num_ctx truncation
# ---------------------------------------------------------------------------

def test_token_throughput_arithmetic(tmp_path):
    # 300 prompt tokens in 400 ms is 750 tokens/s; 5 generated tokens in 570 ms
    # is 5 / 0.57 tokens/s.
    run_dir = build_log_run(
        tmp_path / "runs",
        [
            timed_request(seconds=index, prompt_eval_count=300, eval_count=5,
                          **DOMINANT_CASES["eval_ms"])
            for index in range(2)
        ],
    )
    out_dir = tmp_path / "out"

    assert bottleneck_hints.main(
        ["--run-dir", str(run_dir), "--out-dir", str(out_dir), "--no-charts"]
    ) == 0

    tokens = pd.read_csv(out_dir / "bottleneck_tokens.csv").set_index("stage")
    prefill = tokens.loc["prompt evaluation"]
    assert prefill["requests"] == 2
    assert prefill["total_tokens"] == pytest.approx(600)
    assert prefill["total_seconds"] == pytest.approx(0.8)
    assert prefill["aggregate_tokens_per_s"] == pytest.approx(750.0)
    assert prefill["mean_tokens_per_s"] == pytest.approx(750.0)
    assert prefill["mean_tokens_per_request"] == pytest.approx(300.0)
    generation = tokens.loc["generation"]
    assert generation["aggregate_tokens_per_s"] == pytest.approx(5 / 0.57)
    assert generation["p50_tokens_per_s"] == pytest.approx(5 / 0.57)
    assert (out_dir / "bottleneck_tokens.md").is_file()


def test_num_ctx_truncation_is_flagged(tmp_path, capsys):
    run_dir = build_log_run(
        tmp_path / "runs",
        [
            # A short ticket: 300 prompt tokens of a 4096-token window.
            timed_request(seconds=0, prompt_eval_count=300, num_ctx=4096,
                          **DOMINANT_CASES["eval_ms"]),
            # A ticket whose prompt filled the window exactly: Ollama truncates
            # silently, so this classification saw a cut-off ticket.
            timed_request(seconds=1, prompt_eval_count=4096, num_ctx=4096,
                          ticket_chars=1999, **DOMINANT_CASES["eval_ms"]),
        ],
    )
    out_dir = tmp_path / "out"

    assert bottleneck_hints.main(
        ["--run-dir", str(run_dir), "--out-dir", str(out_dir), "--no-charts"]
    ) == 0

    assert "truncating the prompt" in capsys.readouterr().err
    suspects = pd.read_csv(out_dir / "ctx_truncation_suspects.csv")
    assert len(suspects) == 1
    assert suspects.loc[0, "prompt_eval_count"] == 4096
    assert suspects.loc[0, "num_ctx"] == 4096
    assert suspects.loc[0, "ctx_ratio"] == pytest.approx(1.0)
    assert suspects.loc[0, "ticket_chars"] == 1999
    assert suspects.loc[0, "source_row"] == 10001
    report = (out_dir / "bottleneck_report.md").read_text(encoding="utf-8")
    assert "prompt_eval_count` sits at or above the warning fraction" in report
    assert "**1**" in report


def test_the_truncation_warning_fraction_is_configurable(tmp_path):
    run_dir = build_log_run(
        tmp_path / "runs",
        [timed_request(prompt_eval_count=3000, num_ctx=4096, **DOMINANT_CASES["eval_ms"])],
    )
    out_dir = tmp_path / "out"

    # 3000/4096 is 0.73: not a suspect at the default fraction, but a suspect if
    # the operator asks for a wider margin.
    assert bottleneck_hints.main(
        ["--run-dir", str(run_dir), "--out-dir", str(out_dir), "--no-charts"]
    ) == 0
    assert pd.read_csv(out_dir / "ctx_truncation_suspects.csv").empty

    assert bottleneck_hints.main(
        ["--run-dir", str(run_dir), "--out-dir", str(out_dir),
         "--ctx-warn-fraction", "0.7", "--no-charts"]
    ) == 0
    assert len(pd.read_csv(out_dir / "ctx_truncation_suspects.csv")) == 1


# ---------------------------------------------------------------------------
# Outputs, the conftest run builder, and the CLI
# ---------------------------------------------------------------------------

def test_stacked_chart_and_per_request_evidence_are_written(tmp_path):
    run_dir = build_log_run(
        tmp_path / "runs",
        [timed_request(seconds=index, **DOMINANT_CASES["eval_ms"]) for index in range(3)],
    )
    out_dir = tmp_path / "out"

    assert bottleneck_hints.main(
        ["--run-dir", str(run_dir), "--out-dir", str(out_dir)]
    ) == 0

    png = out_dir / "bottleneck_stacked.png"
    payload = png.read_bytes()
    assert payload[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(payload) > 5_000
    per_request = pd.read_csv(out_dir / "bottleneck_per_request.csv")
    assert list(per_request.columns) == list(bottleneck_hints.PER_REQUEST_COLUMNS)
    assert len(per_request) == 3
    # Every row can be found again in service.jsonl by request_id and timestamp.
    assert list(per_request["request_id"]) == ["req-0", "req-1", "req-2"]
    assert all(str(ts).endswith("Z") for ts in per_request["ts"])


def test_runs_against_the_shared_run_builder(build_run):
    # The conftest builder is what the other analysis tests use; a run it writes
    # must work here too, errors and all (its error samples carry no timings).
    run = build_run(n_samples=10, n_errors=2)
    out_dir = run.path.parent / "out"

    assert bottleneck_hints.main(
        ["--run-dir", str(run.path), "--out-dir", str(out_dir), "--no-charts"]
    ) == 0

    per_request = pd.read_csv(out_dir / "bottleneck_per_request.csv")
    assert len(per_request) == 8
    breakdown = read_breakdown(out_dir)
    assert breakdown.loc["service_overhead_ms", "mean_ms"] == pytest.approx(10.0)


def test_missing_run_directory_exits_non_zero(tmp_path, capsys):
    code = bottleneck_hints.main(
        ["--run-dir", str(tmp_path / "nope"), "--out-dir", str(tmp_path / "out")]
    )
    assert code == 1
    assert "No such run directory" in capsys.readouterr().err


def test_help_is_available_without_any_evidence():
    with pytest.raises(SystemExit) as raised:
        bottleneck_hints.parse_args(["--help"])
    assert raised.value.code == 0


def test_defaults_match_the_cli_contract():
    args = bottleneck_hints.parse_args(["--run-dir", "results/runs/example"])
    assert args.out_dir == bottleneck_hints.REPO_ROOT / "analysis" / "output" / "bottleneck"
    assert args.ctx_warn_fraction == 0.98
