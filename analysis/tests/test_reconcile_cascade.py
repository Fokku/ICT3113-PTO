"""Tests for the Assignment 2 checks in ``analysis/reconcile.py``.

Owner: Yeo Kai Yuan (Part 1).

Two things are proved here. First, that an Assignment 1 run -- metadata with no
``service_mode`` key, 24-field schema-version-1 log lines -- reconciles exactly as
it did before Assignment 2: the same checks, in the same order, with the same
values and words, and the same files. Second, that an Assignment 2 run's log is
checked for "which model answered": a cascade line must say whether it escalated,
name the run's setting and small model, and name the large model exactly when it
escalated; a single-model line must carry no cascade field and name the run's
model. Each failure is built on its own, by breaking one field of one line.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from analysis import reconcile

from conftest import (  # noqa: E402
    UNFINISHED_CODE,
    A2Sample,
    build_a2_run_dir,
    build_run_dir,
    steady_samples,
    to_v1_line,
    write_jtl,
    write_service_log,
)

#: The checks an Assignment 1 run produced before Assignment 2, in order.
A1_CHECK_NAMES = [
    "jtl_samples_without_log_line",
    "log_lines_without_jtl_sample",
    "blank_request_ids",
    "duplicate_request_ids",
    "status_disagreements",
    "source_row_disagreements",
    "client_minus_server_latency_p99_ms",
]

#: The checks every Assignment 2 cascade run adds, after the Assignment 1 ones.
CASCADE_CHECK_NAMES = [
    "unfinished_requests",
    "cascade_escalated_logged",
    "cascade_setting_matches_metadata",
    "cascade_small_model_matches_metadata",
    "cascade_answering_model_consistent",
    "cascade_small_category_logged",
    "cascade_escalation_fraction",
]

SINGLE_CHECK_NAMES = [
    "unfinished_requests",
    "single_mode_cascade_fields_null",
    "single_mode_model_tag_matches_metadata",
]

PATTERN = [False, True, False, False, True, False]


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def make_a1_run(root: Path, **kwargs) -> Path:
    """An Assignment 1-shaped run: schema-version-1 lines, no Assignment 2 metadata."""
    run = build_run_dir(root, **kwargs)
    for name in ("service.jsonl", "warmup.jsonl"):
        path = run.path / name
        if path.is_file():
            write_service_log(path, [to_v1_line(r) for r in read_jsonl(path)])
    assert "service_mode" not in run.metadata and "config" not in run.metadata
    return run.path


def run_cli(run_dir: Path, out_dir: Path) -> int:
    return reconcile.main(["--run-dir", str(run_dir), "--out-dir", str(out_dir)])


def checks(out_dir: Path, run_dir: Path) -> dict[str, dict[str, str]]:
    frame = pd.read_csv(out_dir / f"{run_dir.name}__checks.csv", keep_default_na=False)
    return {row["check"]: row for _, row in frame.iterrows()}


def check_names(out_dir: Path, run_dir: Path) -> list[str]:
    frame = pd.read_csv(out_dir / f"{run_dir.name}__checks.csv", keep_default_na=False)
    return list(frame["check"])


def cascade_run(root: Path, *, line_overrides=None, samples=None, **kwargs) -> Path:
    samples = samples or steady_samples([3000 if f else 1000 for f in PATTERN],
                                        escalated=PATTERN)
    return build_a2_run_dir(root, samples, cascade_setting="A",
                            line_overrides=line_overrides, **kwargs).path


# ---------------------------------------------------------------------------
# Assignment 1 runs are reconciled exactly as before
# ---------------------------------------------------------------------------

def test_an_assignment_1_run_yields_the_same_checks_as_before(tmp_path: Path) -> None:
    run_dir = make_a1_run(tmp_path / "runs", n_samples=12, n_errors=2)
    out_dir = tmp_path / "out"
    assert run_cli(run_dir, out_dir) == 0

    assert check_names(out_dir, run_dir) == A1_CHECK_NAMES
    frame = pd.read_csv(out_dir / f"{run_dir.name}__checks.csv", keep_default_na=False)
    # Values, limits, verdicts and words pinned as the pre-Assignment 2 code wrote them.
    assert frame.drop(columns=["value"]).to_dict("records") == [
        {"check": "jtl_samples_without_log_line", "limit": "<= 0", "verdict": "pass",
         "detail": "every measured sample has a service log line"},
        {"check": "log_lines_without_jtl_sample", "limit": "<= 0", "verdict": "pass",
         "detail": "every log line in the run window has a matching sample"},
        {"check": "blank_request_ids", "limit": "0", "verdict": "pass",
         "detail": "every row carries a request_id"},
        {"check": "duplicate_request_ids", "limit": "0", "verdict": "pass",
         "detail": "request_ids are unique on both sides"},
        {"check": "status_disagreements", "limit": "0", "verdict": "pass",
         "detail": "every matched sample agrees with its log line on HTTP status"},
        {"check": "source_row_disagreements", "limit": "0", "verdict": "pass",
         "detail": "every matched sample agrees with its log line on source_row"},
        {"check": "client_minus_server_latency_p99_ms", "limit": "<= 250",
         "verdict": "pass",
         "detail": "p99 of abs(elapsed minus total_latency_ms); a large value means the "
                   "load generator or the clocks, not the service, are shaping the numbers"},
    ]
    assert list(frame["value"]) == ["0", "0", "jtl=0 log=0", "jtl=0 log=0", "0", "0", "5.0"]

    # The same files as before, and no Assignment 2 section in the report.
    assert sorted(p.name.removeprefix(run_dir.name) for p in out_dir.iterdir()) == sorted(
        [f"__{stem}.{ext}" for stem in ("checks", "unmatched", "mismatches", "latency_diff")
         for ext in ("csv", "md")] + ["__report.md"])
    report = (out_dir / f"{run_dir.name}__report.md").read_text(encoding="utf-8")
    assert "Assignment 2" not in report
    assert "Which model answered" not in report


def test_an_assignment_1_run_with_v2_null_lines_is_also_unchanged(tmp_path: Path) -> None:
    """conftest's default lines are schema version 2 with null cascade fields."""
    run = build_run_dir(tmp_path / "runs", n_samples=5)
    out_dir = tmp_path / "out"
    assert run_cli(run.path, out_dir) == 0
    assert check_names(out_dir, run.path) == A1_CHECK_NAMES


def test_an_assignment_1_timeout_is_still_a_status_disagreement(tmp_path: Path) -> None:
    """The unfinished-request rule is Assignment 2 only; A1 keeps its blocker."""
    run_dir = make_a1_run(tmp_path / "runs", n_samples=4)
    rows = pd.read_csv(run_dir / "results.jtl", dtype=str, keep_default_na=False)
    rows.loc[1, "responseCode"] = UNFINISHED_CODE
    rows.loc[1, "success"] = "false"
    write_jtl(run_dir / "results.jtl", rows.to_dict("records"))
    out_dir = tmp_path / "out"
    assert run_cli(run_dir, out_dir) == 1
    table = checks(out_dir, run_dir)
    assert list(table) == A1_CHECK_NAMES
    assert table["status_disagreements"]["verdict"] == "BLOCKER"
    assert table["status_disagreements"]["value"] == "1"


# ---------------------------------------------------------------------------
# a clean cascade run
# ---------------------------------------------------------------------------

def test_a_clean_cascade_run_passes_with_the_cascade_checks(tmp_path: Path, capsys) -> None:
    run_dir = cascade_run(tmp_path / "runs")
    out_dir = tmp_path / "out"
    assert run_cli(run_dir, out_dir) == 0
    assert check_names(out_dir, run_dir) == A1_CHECK_NAMES + CASCADE_CHECK_NAMES
    table = checks(out_dir, run_dir)
    assert {row["verdict"] for row in table.values()} == {"pass"}
    assert table["cascade_escalation_fraction"]["value"] == "2/6 (33.3%)"
    assert table["cascade_escalation_fraction"]["limit"] == "informational"
    assert "cascade escalation = 2/6 (33.3%)" in capsys.readouterr().out

    report = (out_dir / f"{run_dir.name}__report.md").read_text(encoding="utf-8")
    assert "## Which model answered (Assignment 2)" in report
    assert "Cascade: setting `A`, small `llama3.2:3b`" in report
    assert pd.read_csv(out_dir / f"{run_dir.name}__model_answered.csv").empty


def test_the_warmup_listed_in_metadata_is_excluded(tmp_path: Path) -> None:
    run_dir = cascade_run(tmp_path / "runs")
    meta = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    (run_dir / "warmup.jsonl").unlink()
    # A warm-up line left in service.jsonl, unflagged, known only from metadata.
    lines = read_jsonl(run_dir / "service.jsonl")
    lines.append({**lines[0], "request_id": meta["warmup_request_ids"][2]})
    write_service_log(run_dir / "service.jsonl", lines)
    report = reconcile.reconcile_run(run_dir, latency_threshold_ms=250, max_unmatched=0)
    assert report.ok and report.log_lines == 6


def test_a_length_rule_escalation_with_no_small_category_passes(tmp_path: Path) -> None:
    samples = steady_samples([3000 if f else 1000 for f in PATTERN], escalated=PATTERN)
    samples[1] = A2Sample(10_000, 3000, escalated=True, skipped_small=True)
    run_dir = cascade_run(tmp_path / "runs", samples=samples)
    out_dir = tmp_path / "out"
    assert run_cli(run_dir, out_dir) == 0
    table = checks(out_dir, run_dir)
    assert table["cascade_small_category_logged"]["verdict"] == "pass"
    assert "1 escalated HTTP 200 line(s) had no small-model category" in (
        table["cascade_escalation_fraction"]["detail"])


def test_a_config_named_cascade_is_checked_without_service_mode(tmp_path: Path) -> None:
    run_dir = cascade_run(tmp_path / "runs", metadata_overrides={"service_mode": None,
                                                                 "cascade_setting": None})
    out_dir = tmp_path / "out"
    assert run_cli(run_dir, out_dir) == 0
    table = checks(out_dir, run_dir)
    # The setting is taken from config "cascade-A".
    assert "cascade_setting = A" in table["cascade_setting_matches_metadata"]["detail"]


# ---------------------------------------------------------------------------
# cascade failures, one field at a time
# ---------------------------------------------------------------------------

def test_a_200_line_without_escalated_is_a_blocker(tmp_path: Path, capsys) -> None:
    run_dir = cascade_run(tmp_path / "runs", line_overrides={2: {"escalated": None}})
    out_dir = tmp_path / "out"
    assert run_cli(run_dir, out_dir) == 1
    table = checks(out_dir, run_dir)
    assert table["cascade_escalated_logged"]["verdict"] == "BLOCKER"
    assert table["cascade_escalated_logged"]["value"].startswith("null on 1 of 6")
    assert "BLOCKER cascade_escalated_logged" in capsys.readouterr().err
    problems = pd.read_csv(out_dir / f"{run_dir.name}__model_answered.csv")
    assert list(problems["problem"]) == ["escalated_not_logged"]


def test_an_error_handler_line_without_escalated_is_only_a_warning(tmp_path: Path) -> None:
    samples = steady_samples([3000 if f else 1000 for f in PATTERN], escalated=PATTERN)
    samples[5] = A2Sample(50_000, 20, code="422")
    null_route = {name: None for name in ("escalated", "cascade_setting", "small_model_tag",
                                          "small_model_category", "small_model_latency_ms",
                                          "small_load_duration", "model_tag")}
    run_dir = cascade_run(tmp_path / "runs", samples=samples,
                          line_overrides={5: null_route})
    out_dir = tmp_path / "out"
    assert run_cli(run_dir, out_dir) == 0
    table = checks(out_dir, run_dir)
    assert table["cascade_escalated_logged"]["verdict"] == "WARN"
    # A 422 line is not checked for setting or small model either.
    assert table["cascade_setting_matches_metadata"]["verdict"] == "pass"
    assert table["cascade_escalation_fraction"]["value"] == "2/6 (33.3%)"


def test_a_wrong_cascade_setting_is_a_blocker(tmp_path: Path) -> None:
    run_dir = cascade_run(tmp_path / "runs", line_overrides={0: {"cascade_setting": "B"}})
    out_dir = tmp_path / "out"
    assert run_cli(run_dir, out_dir) == 1
    row = checks(out_dir, run_dir)["cascade_setting_matches_metadata"]
    assert (row["verdict"], row["value"]) == ("BLOCKER", "1")


def test_a_wrong_small_model_is_a_blocker(tmp_path: Path) -> None:
    run_dir = cascade_run(tmp_path / "runs",
                          line_overrides={3: {"small_model_tag": "granite4:3b"}})
    out_dir = tmp_path / "out"
    assert run_cli(run_dir, out_dir) == 1
    row = checks(out_dir, run_dir)["cascade_small_model_matches_metadata"]
    assert (row["verdict"], row["value"]) == ("BLOCKER", "1")


def test_an_escalated_line_answered_by_the_small_model_is_a_blocker(tmp_path: Path) -> None:
    run_dir = cascade_run(tmp_path / "runs", line_overrides={1: {"model_tag": "llama3.2:3b"}})
    out_dir = tmp_path / "out"
    assert run_cli(run_dir, out_dir) == 1
    row = checks(out_dir, run_dir)["cascade_answering_model_consistent"]
    assert (row["verdict"], row["value"]) == ("BLOCKER", "1")
    problems = pd.read_csv(out_dir / f"{run_dir.name}__model_answered.csv")
    assert problems.iloc[0][["problem", "expected", "logged"]].tolist() == [
        "answering_model_disagreement", "qwen2.5:7b", "llama3.2:3b"]


def test_an_accepted_line_answered_by_the_large_model_is_a_blocker(tmp_path: Path) -> None:
    run_dir = cascade_run(tmp_path / "runs", line_overrides={0: {"model_tag": "qwen2.5:7b"}})
    out_dir = tmp_path / "out"
    assert run_cli(run_dir, out_dir) == 1
    assert checks(out_dir, run_dir)["cascade_answering_model_consistent"]["value"] == "1"


def test_a_502_line_is_not_held_to_the_answering_model_rule(tmp_path: Path) -> None:
    samples = steady_samples([3000 if f else 1000 for f in PATTERN], escalated=PATTERN)
    samples[3] = A2Sample(30_000, 1000, code="502", escalated=True)
    run_dir = cascade_run(tmp_path / "runs", samples=samples,
                          line_overrides={3: {"model_tag": "llama3.2:3b"}})
    out_dir = tmp_path / "out"
    assert run_cli(run_dir, out_dir) == 0
    assert checks(out_dir, run_dir)["cascade_answering_model_consistent"]["value"] == "0"


def test_an_accepted_answer_without_a_small_category_is_a_warning(tmp_path: Path) -> None:
    run_dir = cascade_run(tmp_path / "runs",
                          line_overrides={0: {"small_model_category": None}})
    out_dir = tmp_path / "out"
    assert run_cli(run_dir, out_dir) == 0
    row = checks(out_dir, run_dir)["cascade_small_category_logged"]
    assert (row["verdict"], row["value"]) == ("WARN", "1")


def test_metadata_without_the_small_model_is_a_blocker(tmp_path: Path) -> None:
    run_dir = cascade_run(tmp_path / "runs",
                          metadata_overrides={"cascade_small_model_tag": None})
    out_dir = tmp_path / "out"
    assert run_cli(run_dir, out_dir) == 1
    table = checks(out_dir, run_dir)
    assert table["cascade_small_model_matches_metadata"]["verdict"] == "BLOCKER"
    assert "metadata.json records no cascade_small_model_tag" in (
        table["cascade_small_model_matches_metadata"]["detail"])
    assert table["cascade_answering_model_consistent"]["verdict"] == "BLOCKER"


def test_a_cascade_model_tag_label_is_not_taken_for_the_large_model(tmp_path: Path) -> None:
    """A run script may set model_tag to "cascade-A"; that is not a model."""
    run_dir = cascade_run(tmp_path / "runs",
                          metadata_overrides={"cascade_large_model_tag": None,
                                              "model_tag": "cascade-A"})
    out_dir = tmp_path / "out"
    assert run_cli(run_dir, out_dir) == 1
    assert "does not name both cascade models" in (
        checks(out_dir, run_dir)["cascade_answering_model_consistent"]["detail"])


# ---------------------------------------------------------------------------
# unfinished requests (Assignment 2 only)
# ---------------------------------------------------------------------------

def test_an_unfinished_request_is_counted_not_a_disagreement(tmp_path: Path, capsys) -> None:
    samples = steady_samples([3000 if f else 1000 for f in PATTERN], escalated=PATTERN)
    samples[2] = A2Sample(20_000, 300_000, code=UNFINISHED_CODE)
    run_dir = cascade_run(tmp_path / "runs", samples=samples)
    out_dir = tmp_path / "out"
    assert run_cli(run_dir, out_dir) == 0
    table = checks(out_dir, run_dir)
    assert table["status_disagreements"]["value"] == "0"
    assert (table["unfinished_requests"]["verdict"],
            table["unfinished_requests"]["value"]) == ("WARN", "1")
    # The client gave up 10 s before the service finished; that is not a gap
    # between two clocks measuring the same response, so it is left out.
    assert table["client_minus_server_latency_p99_ms"]["value"] == "5.0"
    mismatches = pd.read_csv(out_dir / f"{run_dir.name}__mismatches.csv")
    assert list(mismatches["problem"]) == ["unfinished_request"]
    assert "WARN unfinished_requests = 1" in capsys.readouterr().out


def test_an_unfinished_request_with_no_log_line_is_still_a_blocker(tmp_path: Path) -> None:
    samples = steady_samples([1000] * 4)
    samples[1] = A2Sample(10_000, 300_000, code=UNFINISHED_CODE, log=False)
    run = build_a2_run_dir(tmp_path / "runs", samples)
    out_dir = tmp_path / "out"
    assert run_cli(run.path, out_dir) == 1
    assert checks(out_dir, run.path)["jtl_samples_without_log_line"]["verdict"] == "BLOCKER"


# ---------------------------------------------------------------------------
# single-model Assignment 2 runs
# ---------------------------------------------------------------------------

def test_a_clean_single_model_run_passes(tmp_path: Path) -> None:
    run = build_a2_run_dir(tmp_path / "runs", steady_samples([2000] * 5))
    out_dir = tmp_path / "out"
    assert run_cli(run.path, out_dir) == 0
    assert check_names(out_dir, run.path) == A1_CHECK_NAMES + SINGLE_CHECK_NAMES
    table = checks(out_dir, run.path)
    assert {row["verdict"] for row in table.values()} == {"pass"}
    assert "model_tag = qwen2.5:7b" in table["single_mode_model_tag_matches_metadata"]["detail"]


def test_a_cascade_field_on_a_single_model_line_is_a_blocker(tmp_path: Path) -> None:
    run = build_a2_run_dir(tmp_path / "runs", steady_samples([2000] * 5),
                           line_overrides={2: {"escalated": False, "cascade_setting": "A"}})
    out_dir = tmp_path / "out"
    assert run_cli(run.path, out_dir) == 1
    row = checks(out_dir, run.path)["single_mode_cascade_fields_null"]
    assert (row["verdict"], row["value"]) == ("BLOCKER", "1")
    problems = pd.read_csv(out_dir / f"{run.path.name}__model_answered.csv")
    assert problems.iloc[0]["logged"] == "escalated;cascade_setting"


def test_a_different_model_on_a_single_model_line_is_a_blocker(tmp_path: Path) -> None:
    run = build_a2_run_dir(tmp_path / "runs", steady_samples([2000] * 5),
                           line_overrides={4: {"model_tag": "granite4:3b"}})
    out_dir = tmp_path / "out"
    assert run_cli(run.path, out_dir) == 1
    row = checks(out_dir, run.path)["single_mode_model_tag_matches_metadata"]
    assert (row["verdict"], row["value"]) == ("BLOCKER", "1")


def test_reports_name_the_assignment_2_configuration(tmp_path: Path) -> None:
    run = build_a2_run_dir(tmp_path / "runs", steady_samples([2000] * 3))
    out_dir = tmp_path / "out"
    run_cli(run.path, out_dir)
    report = (out_dir / f"{run.path.name}__report.md").read_text(encoding="utf-8")
    assert ("Assignment 2 configuration: `qwen2.5:7b`, service mode `single`, "
            "gate commit `" + "2" * 40 + "`") in report
