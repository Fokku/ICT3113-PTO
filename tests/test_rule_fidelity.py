"""The rule-fidelity check (TODO_A2.md §1.2): the code must reproduce the documented rule.

Owner: Yeo Kai Yuan (Part 1 -- technical core).

Two kinds of test live here:

* Plumbing tests for ``scripts/cascade_replay.py``, run against the real
  Assignment 1 ``responses.csv`` files with *test-only* rules installed in
  ``service.cascade.RULE_SETTINGS``. They check the replay counts against an
  independent count computed here, so the script cannot drift from what it
  claims to do. Escalation counts only -- no golden label is read.
* :func:`test_code_reproduces_escalation_rule_document` -- the real check.
  It is **skipped** until both halves exist (Setting A and Setting B written
  into ``service/cascade.py`` and §1/§3 of ``cascade/escalation_rule.md``
  filled in). From then on it fails the suite whenever the code and the
  frozen document disagree.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import pytest

from service import cascade
from service.categories import CATEGORIES

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import cascade_replay  # noqa: E402

SMALL = "llama3.2:3b"


def tuning_rows() -> list[int]:
    with (REPO_ROOT / "golden" / "split_a2.csv").open(newline="", encoding="utf-8") as handle:
        return sorted(int(r["row_number"]) for r in csv.DictReader(handle) if r["set"] == "tuning")


def a1_predictions(model_dir_glob: str) -> dict[int, str]:
    (path,) = sorted((REPO_ROOT / "results" / "accuracy").glob(f"{model_dir_glob}/responses.csv"))
    with path.open(newline="", encoding="utf-8") as handle:
        return {int(r["row_number"]): r["predicted_category"] for r in csv.DictReader(handle)}


def test_the_replay_never_opens_the_golden_labels() -> None:
    source = (SCRIPTS / "cascade_replay.py").read_text(encoding="utf-8")
    assert "golden_set.csv" not in source
    assert "golden/golden_set" not in source


def test_replay_counts_match_an_independent_count(
    monkeypatch: pytest.MonkeyPatch, capsys, tmp_path: Path
) -> None:
    accept = frozenset({"Mortgage", "Credit reporting"})
    monkeypatch.setattr(
        cascade,
        "RULE_SETTINGS",
        {"A": cascade.CategoryRule(accept_categories=accept), "B": cascade.LengthRule(max_chars=800)},
    )
    rows = tuning_rows()
    predictions = a1_predictions("llama3.2-3b_*")
    with (REPO_ROOT / "data" / "team_rows.csv").open(newline="", encoding="utf-8") as handle:
        csv.field_size_limit(10 ** 9)
        lengths = {int(r["row_number"]): len(r["narrative"]) for r in csv.DictReader(handle)}

    expected_a = sum(1 for row in rows if predictions[row] not in accept)
    expected_b = sum(
        1 for row in rows if lengths[row] > 800 or predictions[row] == "UNPARSEABLE"
    )

    # Compare against a blank document, not the real one: this test checks the replay's counting with
    # made-up rules, and once the real escalation_rule.md has its §3 counts those made-up rules would
    # (correctly) disagree with it. The real comparison is test_code_reproduces_escalation_rule_document.
    blank_doc = tmp_path / "escalation_rule.md"
    blank_doc.write_text(
        "| Escalation fraction on the tuning set | TODO(cascade) | TODO(cascade) |\n", encoding="utf-8"
    )
    assert cascade_replay.main(["--small-model", SMALL, "--json", "--rule-doc", str(blank_doc)]) == 2
    out = capsys.readouterr().out
    import json

    payload = json.loads(out)
    assert payload["n_rows"] == len(rows) == 99
    assert payload["results"]["A"]["count"] == f"{expected_a}/{len(rows)}"
    assert payload["results"]["B"]["count"] == f"{expected_b}/{len(rows)}"


def test_documented_counts_are_parsed_from_section_3(tmp_path: Path) -> None:
    doc = tmp_path / "escalation_rule.md"
    doc.write_text(
        "| | Setting A | Setting B |\n|---|---|---|\n"
        "| Escalation fraction on the tuning set | 31/99 (31.3%) | 58 / 99 |\n",
        encoding="utf-8",
    )
    assert cascade_replay.documented_counts(doc) == {"A": "31/99", "B": "58/99"}
    doc.write_text(
        "| Escalation fraction on the tuning set | TODO(cascade) | TODO(cascade) |\n", encoding="utf-8"
    )
    assert cascade_replay.documented_counts(doc) == {"A": None, "B": None}


def test_a_mismatch_with_the_document_exits_one(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        cascade,
        "RULE_SETTINGS",
        {
            "A": cascade.CategoryRule(accept_categories=frozenset(CATEGORIES)),  # escalates only UNPARSEABLE
            "B": cascade.CategoryRule(accept_categories=frozenset()),  # escalates everything
        },
    )
    doc = tmp_path / "escalation_rule.md"
    doc.write_text("| Escalation fraction on the tuning set | 98/99 | 99/99 |\n", encoding="utf-8")
    assert cascade_replay.main(["--small-model", SMALL, "--rule-doc", str(doc)]) == 1
    doc.write_text("| Escalation fraction on the tuning set | 0/99 | 99/99 |\n", encoding="utf-8")
    predictions = a1_predictions("llama3.2-3b_*")
    unparseable = sum(1 for row in tuning_rows() if predictions[row] == "UNPARSEABLE")
    doc.write_text(
        f"| Escalation fraction on the tuning set | {unparseable}/99 | 99/99 |\n", encoding="utf-8"
    )
    assert cascade_replay.main(["--small-model", SMALL, "--rule-doc", str(doc)]) == 0


def test_unconfigured_settings_cannot_be_confirmed() -> None:
    if all(cascade.RULE_SETTINGS.get(s) is not None for s in ("A", "B")):
        pytest.skip("both settings are configured; covered by the real fidelity test")
    assert cascade_replay.main(["--small-model", SMALL]) == 2


def _documented_small_model() -> str | None:
    text = (REPO_ROOT / "cascade" / "escalation_rule.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.lstrip().startswith("| Small model") and "TODO(" not in line:
            match = re.search(r"`([^`]+)`", line)
            if match:
                return match.group(1)
    return None


def test_code_reproduces_escalation_rule_document() -> None:
    """TODO_A2.md §1.2: the frozen document and the deployed code must agree exactly."""
    configured = all(cascade.RULE_SETTINGS.get(s) is not None for s in ("A", "B"))
    documented = cascade_replay.documented_counts(REPO_ROOT / "cascade" / "escalation_rule.md")
    small = _documented_small_model()
    if not configured or None in documented.values() or small is None:
        pytest.skip(
            "not yet comparable: Setting A/B not in service/cascade.py RULE_SETTINGS, or "
            "cascade/escalation_rule.md §1 small model / §3 tuning counts not filled in"
        )
    assert cascade_replay.main(["--small-model", small]) == 0
