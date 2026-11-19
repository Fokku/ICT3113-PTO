"""Unit tests for the Assignment 2 calibration helpers (no model, no network).

Owner: Yeo Kai Yuan (Part 1 -- technical core).

* ``scripts/measure_s_a2.py`` -- the arithmetic the brief derives from S, checked
  against the brief's own worked examples, and the S-ticket selection rule.
* ``scripts/a2_env_snapshot.py`` -- the pin parser and the diff that decides
  whether a configuration may be measured.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import a2_env_snapshot  # noqa: E402
import measure_s_a2  # noqa: E402


# ---------------------------------------------------------------------------
# measure_s_a2.derive -- the brief's worked examples
# ---------------------------------------------------------------------------

def test_s_of_six_seconds_gives_the_briefs_numbers() -> None:
    """Brief: S = 6 -> one ticket every 12 s = 5/min, run 6 minutes, ~30 tickets,
    5-minute timeout, pause(6 min)."""
    d = measure_s_a2.derive(6.0)
    assert d["rate_per_min"] == 5.0
    assert d["interval_s"] == 12.0
    assert d["duration_s"] == 360
    assert d["expected_tickets_per_run"] == 30.0
    assert d["response_timeout_ms"] == 300_000
    assert d["pause_s"] == 360


def test_s_of_thirty_four_seconds_runs_thirty_four_minutes() -> None:
    """Brief: "With S = 34 it is 34 minutes, also about 30 tickets"."""
    d = measure_s_a2.derive(34.0)
    assert d["duration_s"] == 34 * 60
    assert round(d["expected_tickets_per_run"]) == 30
    assert d["response_timeout_ms"] == 340_000  # 10 x S, above the 5-minute floor
    assert d["pause_s"] == 340 + 60


def test_the_five_minute_minimum_applies_to_a_fast_top_model() -> None:
    d = measure_s_a2.derive(2.3)
    assert d["duration_s"] == 300
    assert d["rate_per_min"] == 13.04
    assert d["upper_bound_within_list"] is True  # ~65 expected, ~89 upper bound


def test_a_very_fast_top_model_would_overrun_the_hundred_ticket_list() -> None:
    d = measure_s_a2.derive(1.0)
    assert d["upper_bound_within_list"] is False


def test_the_pause_always_outlasts_the_timeout_by_a_minute() -> None:
    for s in (0.5, 2.3, 6, 29.9, 30, 31, 120):
        d = measure_s_a2.derive(s)
        assert d["pause_s"] * 1000 >= d["response_timeout_ms"] + 60_000


# ---------------------------------------------------------------------------
# measure_s_a2.choose_s_tickets
# ---------------------------------------------------------------------------

def test_s_tickets_are_typical_length_and_overlap_nothing() -> None:
    team = measure_s_a2.team_rows()
    golden = measure_s_a2.golden_rows()
    workload = measure_s_a2.workload_rows()
    rows, median = measure_s_a2.choose_s_tickets(team, golden, workload)

    assert len(rows) == len(set(rows)) == 3  # three DIFFERENT tickets
    assert not set(rows) & golden
    assert not set(rows) & workload
    assert len(golden) == 200 and len(workload) == 100
    assert median == pytest.approx(749, abs=1)  # the figure docs/a2/arrival-rate.md quotes
    for row in rows:
        assert abs(len(team[row]) - median) <= 10


def test_s_ticket_choice_is_deterministic_with_ties_to_the_lower_row() -> None:
    team = {1: "x" * 10, 2: "x" * 10, 3: "x" * 12, 4: "x" * 8, 5: "x" * 100}
    rows, median = measure_s_a2.choose_s_tickets(team, golden={5}, workload={3})
    assert median == 10
    assert rows == [1, 2, 4]


def test_the_warm_up_tickets_are_hand_written_dev_rows() -> None:
    warmups = measure_s_a2.dev_warmup_tickets()
    assert [row for row, _ in warmups] == ["900000", "900001", "900002"]


# ---------------------------------------------------------------------------
# a2_env_snapshot
# ---------------------------------------------------------------------------

def test_the_pins_are_read_from_models_yaml() -> None:
    pins, version = a2_env_snapshot.pinned_models()
    assert set(pins) == {"llama3.2:1b-instruct-q4_K_M", "llama3.2:3b", "granite4:3b", "qwen2.5:7b"}
    assert all(d.startswith("sha256:") for d in pins.values())
    assert version == "0.34.3"


def _snap(**overrides):
    base = {
        "captured_at_utc": "2026-11-20T00:00:00Z",
        "ollama_version": "0.34.3",
        "model_digests": {"qwen2.5:7b": "sha256:aa"},
        "ollama_env": {"OLLAMA_NUM_PARALLEL": "0", "OLLAMA_MAX_LOADED_MODELS": "0"},
        "service": {"prompt_hash": "sha256:p", "num_ctx": 4096, "seed": 42},
        "jmeter_version": "5.6.3",
    }
    base.update(overrides)
    return base


def test_an_unchanged_environment_has_no_differences_whatever_the_capture_time() -> None:
    assert a2_env_snapshot.differences(_snap(), _snap(captured_at_utc="2026-11-21T09:00:00Z")) == []


@pytest.mark.parametrize(
    ("change", "key"),
    [
        ({"ollama_version": "0.35.0"}, "ollama_version"),
        ({"model_digests": {"qwen2.5:7b": "sha256:bb"}}, "model_digests.qwen2.5:7b"),
        ({"ollama_env": {"OLLAMA_NUM_PARALLEL": "4", "OLLAMA_MAX_LOADED_MODELS": "0"}},
         "ollama_env.OLLAMA_NUM_PARALLEL"),
        ({"service": {"prompt_hash": "sha256:changed", "num_ctx": 4096, "seed": 42}}, "service.prompt_hash"),
        ({"ollama_env": None}, "ollama_env"),  # a check that compared less must not pass
    ],
)
def test_any_change_between_configurations_is_reported(change, key) -> None:
    diffs = a2_env_snapshot.differences(_snap(), _snap(**change))
    assert [d["key"] for d in diffs] == [key]


def test_env_file_keeps_only_ollama_variables(tmp_path: Path) -> None:
    env = tmp_path / "ollama.env"
    env.write_text("PATH=/usr/bin\nOLLAMA_HOST=0.0.0.0:11434\nOLLAMA_NUM_PARALLEL=0\nnot a line\n", encoding="utf-8")
    assert a2_env_snapshot.read_env_file(env) == {"OLLAMA_HOST": "0.0.0.0:11434", "OLLAMA_NUM_PARALLEL": "0"}
