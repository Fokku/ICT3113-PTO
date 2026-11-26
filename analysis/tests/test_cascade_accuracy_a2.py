"""Tests for analysis/cascade_accuracy_a2.py, on fabricated cascade runs under tmp_path.

The fake runs replay the escalation rule over the Assignment 1 answers of granite4:3b and qwen2.5:7b (the
same inputs the determinism cross-check compares against), so every figure the scorer writes has an
independently computed expectation. Nothing here is reported or committed as a result.
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import pytest

from analysis import cascade_accuracy_a2 as cas
from service import cascade

ROOT = cas.ROOT


def _rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _fake_run(results: Path, setting: str, *, error_row: str | None = None, flip_small: str | None = None):
    split = {r["row_number"]: r["set"] for r in _rows(ROOT / "golden/split_a2.csv")}
    test = sorted((r for r, s in split.items() if s == "test"), key=int)
    small = {r["row_number"]: r["predicted_category"] or "UNPARSEABLE" for r in _rows(cas.A1_RUNS[cas.SMALL])}
    large = {r["row_number"]: r["predicted_category"] or "UNPARSEABLE" for r in _rows(cas.A1_RUNS[cas.LARGE])}
    rule = cascade.RULE_SETTINGS[setting]
    run = results / f"cascade-{setting}_20261126T000000Z"
    responses, routing = [], []
    for row in test:
        s = small[row] if row != flip_small else "Credit reporting"
        esc = s not in rule.accept_categories
        final = large[row] if esc else s
        status, err = ("502", "upstream") if row == error_row else ("200", "")
        responses.append(dict(row_number=row, request_id=f"id-{row}", http_status=status,
                              predicted_category="" if err else final, error=err))
        routing.append(dict(row_number=row, request_id=f"id-{row}", http_status=status,
                            predicted_category="" if err else final,
                            model_tag=cas.LARGE if esc else cas.SMALL, escalated="true" if esc else "false",
                            cascade_setting=setting, small_model_tag=cas.SMALL, small_model_category=s))
    _write(run / "responses.csv", responses)
    _write(run / "routing.csv", routing)
    (run / "metadata.json").write_text(json.dumps({"mode": "real", "config": f"cascade-{setting}"}))
    return run


@pytest.fixture()
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    out = tmp_path / "out"
    out.mkdir()
    for name in ("pass_fail_a2.csv", "per_category_a2.csv"):
        shutil.copy(ROOT / "analysis/output/accuracy_a2" / name, out / name)
    monkeypatch.setattr(cas, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(cas, "OUT", out)
    return tmp_path


def _independent_score(setting: str) -> tuple[int, int]:
    golden = {r["row_number"]: r["label"] for r in _rows(ROOT / "golden/golden_set.csv")}
    split = {r["row_number"]: r["set"] for r in _rows(ROOT / "golden/split_a2.csv")}
    small = {r["row_number"]: r["predicted_category"] or "UNPARSEABLE" for r in _rows(cas.A1_RUNS[cas.SMALL])}
    large = {r["row_number"]: r["predicted_category"] or "UNPARSEABLE" for r in _rows(cas.A1_RUNS[cas.LARGE])}
    accept = cascade.RULE_SETTINGS[setting].accept_categories
    correct = escalated = 0
    for row, part in split.items():
        if part != "test":
            continue
        esc = small[row] not in accept
        escalated += esc
        correct += (large[row] if esc else small[row]) == golden[row]
    return correct, escalated


def test_scores_match_an_independent_replay(sandbox: Path) -> None:
    for s in cas.SETTINGS:
        _fake_run(sandbox / "results", s)
    assert cas.main([]) == 0
    verdicts = {r["model_tag"]: r for r in _rows(cas.OUT / "cascade_pass_fail_a2.csv")}
    routing = {r["config"]: r for r in _rows(cas.OUT / "cascade_routing_a2.csv")}
    for s in cas.SETTINGS:
        correct, escalated = _independent_score(s)
        assert int(verdicts[f"cascade-{s}"]["correct"]) == correct
        assert int(routing[f"cascade-{s}"]["escalated"]) == escalated
        assert int(routing[f"cascade-{s}"]["accepted"]) == 101 - escalated
    det = _rows(cas.OUT / "cascade_determinism_a2.csv")
    assert all(d["small_matches_a1"] == "True" for d in det)
    assert all(d["large_matches_a1"] in ("True", "") for d in det)
    assert (cas.OUT / "cascade_report.md").read_text().count("cascade-A") >= 2


def test_an_error_is_wrong_and_a_changed_small_answer_is_flagged(sandbox: Path) -> None:
    split = {r["row_number"]: r["set"] for r in _rows(ROOT / "golden/split_a2.csv")}
    test = sorted((r for r, s in split.items() if s == "test"), key=int)
    _fake_run(sandbox / "results", "A", error_row=test[0], flip_small=test[1])
    _fake_run(sandbox / "results", "B")
    cas.main([])
    routing = {r["config"]: r for r in _rows(cas.OUT / "cascade_routing_a2.csv")}
    assert routing["cascade-A"]["errored"] == "1"
    cm = _rows(next(cas.OUT.glob("cascade-A_*")) / "confusion_matrix.csv")
    assert sum(int(r["ERROR"]) for r in cm) == 1
    det = [d for d in _rows(cas.OUT / "cascade_determinism_a2.csv") if d["config"] == "cascade-A"]
    flipped = [d for d in det if d["row_number"] == test[1]][0]
    granite_a1 = {r["row_number"]: r["predicted_category"] for r in _rows(cas.A1_RUNS[cas.SMALL])}[test[1]]
    assert flipped["small_matches_a1"] == str(granite_a1 == "Credit reporting")
    if granite_a1 != "Credit reporting":
        assert "Mismatched rows" in (cas.OUT / "cascade_report.md").read_text()


def test_two_runs_for_one_setting_need_an_explicit_choice(sandbox: Path) -> None:
    _fake_run(sandbox / "results", "A")
    dup = sandbox / "results" / "cascade-A_20261126T010000Z"
    shutil.copytree(sandbox / "results" / "cascade-A_20261126T000000Z", dup)
    _fake_run(sandbox / "results", "B")
    with pytest.raises(SystemExit, match="exactly one real run"):
        cas.main([])
    assert cas.main(["--run-dir", str(dup), "--run-dir",
                     str(sandbox / "results" / "cascade-B_20261126T000000Z")]) == 0
