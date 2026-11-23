#!/usr/bin/env python3
"""Rule-fidelity check: replay a small model's Assignment 1 answers through the real rule.

Owner: Part 1 -- Yeo Kai Yuan (technical core). TODO_A2.md §1.2, last bullet:

    "Offline, feed the small model's A1 answers on the tuning-set rows through
    the real should_escalate() at Setting A and Setting B. The escalation
    fraction it produces must equal the tuning-set figure in
    cascade/escalation_rule.md §3 exactly -- same rows, same answers, a
    deterministic rule. A mismatch means the code and the document disagree."

What it reads, and what it never reads
--------------------------------------
* ``golden/split_a2.csv`` -- the **row numbers** of the chosen set (``tuning``
  by default). Never the golden set's label file: no label is needed to count
  escalations, so none is opened.
* The small model's Assignment 1 ``results/accuracy/<model>_<stamp>/responses.csv``
  -- its ``predicted_category`` per row is exactly what the service's
  normaliser returned, i.e. exactly what ``SmallModelAnswer.predicted_category``
  would hold for that ticket (temperature 0, fixed seed, same prompt).
* ``data/team_rows.csv`` -- narrative lengths only, for a length rule.
* ``service/cascade.py`` -- the real :func:`should_escalate`, with whatever is
  in ``RULE_SETTINGS``. Nothing here re-implements the rule.
* ``cascade/escalation_rule.md`` §3 -- the documented counts, e.g. ``31/99``.

Usage
-----
    python scripts/cascade_replay.py --small-model llama3.2:3b
    python scripts/cascade_replay.py --small-model llama3.2:3b --json
    python scripts/cascade_replay.py --small-model llama3.2:3b --rows test   # NOT for tuning

Exit codes: 0 the code reproduces the document exactly; 1 a mismatch; 2 cannot
compare yet (a setting not configured in ``service/cascade.py``, or the document
still holds a placeholder), or misuse.

``--rows test`` only replays the test rows to *predict* the test-set escalation
fraction (for the prediction record); it is never used to choose a setting --
TODO_A2.md guardrail 7.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from service import cascade  # noqa: E402
from service.categories import CATEGORIES, UNPARSEABLE  # noqa: E402

SPLIT_REL = "golden/split_a2.csv"
TEAM_ROWS_REL = "data/team_rows.csv"
RULE_DOC_REL = "cascade/escalation_rule.md"
A1_ACCURACY_REL = "results/accuracy"

csv.field_size_limit(10 ** 9)

EXIT_MATCH, EXIT_MISMATCH, EXIT_CANNOT = 0, 1, 2


def sanitise(tag: str) -> str:
    """Same rule as analysis/common.sanitise_model_tag, without importing pandas."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", tag).strip("-")


def split_rows(path: Path, which: str) -> list[int]:
    """Row numbers of one set from the split. Reads ``row_number,set`` only."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if list(reader.fieldnames or []) != ["row_number", "set"]:
            raise SystemExit(f"{path}: expected columns row_number,set, got {reader.fieldnames}")
        rows = [int(r["row_number"]) for r in reader if r["set"].strip() == which]
    if not rows:
        raise SystemExit(f"{path} has no rows with set == {which!r}")
    return sorted(rows)


def a1_responses(root: Path, small_model: str, explicit: Path | None) -> Path:
    """The small model's one Assignment 1 ``responses.csv`` (never results/excluded/)."""
    if explicit is not None:
        return explicit
    matches = sorted(root.glob(f"{sanitise(small_model)}_*/responses.csv"))
    if len(matches) != 1:
        raise SystemExit(
            f"expected exactly one A1 run for {small_model!r} under {root}, found "
            f"{[str(m) for m in matches]}; pass --responses explicitly"
        )
    return matches[0]


def read_predictions(path: Path) -> dict[int, tuple[str | None, int]]:
    """``{row_number: (predicted_category or None if errored, http_status)}``."""
    out: dict[int, tuple[str | None, int]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for record in csv.DictReader(handle):
            status = int(record.get("http_status") or 0)
            category = (record.get("predicted_category") or "").strip() or None
            out[int(record["row_number"])] = (category if status == 200 else None, status)
    return out


def narrative_lengths(path: Path) -> dict[int, int]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {int(r["row_number"]): len(r["narrative"] or "") for r in csv.DictReader(handle)}


def replay(rows: list[int], predictions: dict, lengths: dict, setting: str) -> dict:
    """Count escalations at ``setting`` using the real ``cascade.should_escalate``."""
    escalated, accepted, not_replayable = [], [], []
    for row in rows:
        category, status = predictions.get(row, (None, 0))
        if category is None:
            # The small model did not answer in Assignment 1 (or the row is
            # missing): the live service would return 502, not route it.
            not_replayable.append(row)
            continue
        if category not in CATEGORIES and category != UNPARSEABLE:
            raise SystemExit(f"row {row}: {category!r} is not a canonical category")
        answer = cascade.SmallModelAnswer(
            predicted_category=category,
            raw_text=None,
            narrative_chars=lengths[row],
            result=None,
        )
        (escalated if cascade.should_escalate(answer, setting=setting) else accepted).append(row)
    replayed = len(escalated) + len(accepted)
    return {
        "setting": setting,
        "rule": cascade.rule_for(setting).describe(),
        "escalated": len(escalated),
        "replayed": replayed,
        "count": f"{len(escalated)}/{replayed}",
        "fraction": (len(escalated) / replayed) if replayed else None,
        "not_replayable_rows": not_replayable,
        "escalated_rows": escalated,
    }


def documented_counts(doc: Path) -> dict[str, str | None]:
    """The two ``n/N`` counts in §3's "Escalation fraction on the tuning set" row."""
    text = doc.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.lstrip().startswith("|") and "Escalation fraction on the tuning set" in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            found = {}
            for setting, cell in zip(("A", "B"), cells[1:3]):
                match = re.search(r"(\d+)\s*/\s*(\d+)", cell)
                found[setting] = f"{match.group(1)}/{match.group(2)}" if match and "TODO(" not in cell else None
            return found
    return {"A": None, "B": None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cascade_replay.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--small-model", required=True, help="the cascade's small model tag, e.g. llama3.2:3b")
    parser.add_argument("--rows", choices=("tuning", "test"), default="tuning")
    parser.add_argument("--responses", type=Path, default=None, help="explicit A1 responses.csv")
    parser.add_argument("--split", type=Path, default=REPO_ROOT / SPLIT_REL)
    parser.add_argument("--team-rows", type=Path, default=REPO_ROOT / TEAM_ROWS_REL)
    parser.add_argument("--rule-doc", type=Path, default=REPO_ROOT / RULE_DOC_REL)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    rows = split_rows(args.split, args.rows)
    responses = a1_responses(REPO_ROOT / A1_ACCURACY_REL, args.small_model, args.responses)
    predictions = read_predictions(responses)
    lengths = narrative_lengths(args.team_rows)

    results: dict[str, dict] = {}
    unconfigured: list[str] = []
    for setting in ("A", "B"):
        try:
            results[setting] = replay(rows, predictions, lengths, setting)
        except cascade.CascadeNotConfiguredError as exc:
            unconfigured.append(f"Setting {setting}: {exc}")

    documented = documented_counts(args.rule_doc) if args.rows == "tuning" else {"A": None, "B": None}
    verdicts = {}
    for setting, result in results.items():
        doc = documented.get(setting)
        verdicts[setting] = None if doc is None else (doc == result["count"])

    payload = {
        "small_model": args.small_model,
        "responses": str(responses.relative_to(REPO_ROOT) if responses.is_relative_to(REPO_ROOT) else responses),
        "rows_set": args.rows,
        "n_rows": len(rows),
        "results": {k: {kk: vv for kk, vv in v.items() if kk != "escalated_rows"} for k, v in results.items()},
        "documented": documented,
        "matches_document": verdicts,
        "unconfigured": unconfigured,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Replaying {payload['responses']} on {len(rows)} {args.rows} rows through service/cascade.py")
        for setting in ("A", "B"):
            if setting not in results:
                continue
            r = results[setting]
            line = f"  Setting {setting}: escalated {r['count']}"
            if r["fraction"] is not None:
                line += f" ({100 * r['fraction']:.1f}%)"
            if r["not_replayable_rows"]:
                line += f"; {len(r['not_replayable_rows'])} row(s) had no A1 answer"
            doc = documented.get(setting)
            if args.rows == "tuning":
                line += f"; escalation_rule.md §3 says {doc or 'nothing yet'}"
                if doc is not None:
                    line += " -> MATCH" if verdicts[setting] else " -> MISMATCH"
            print(line)
            print(f"      rule: {r['rule']}")
        for problem in unconfigured:
            print(f"  {problem}", file=sys.stderr)

    if args.rows == "test":
        return EXIT_MATCH if not unconfigured else EXIT_CANNOT
    if any(v is False for v in verdicts.values()):
        print("cascade_replay: the code and cascade/escalation_rule.md DISAGREE. Fix one of "
              "them before the A2 gate -- the document is what gets frozen.", file=sys.stderr)
        return EXIT_MISMATCH
    if unconfigured or any(v is None for v in verdicts.values()) or len(verdicts) < 2:
        print("cascade_replay: cannot confirm fidelity yet (a setting is not configured in "
              "service/cascade.py, or §3 has no n/N count).", file=sys.stderr)
        return EXIT_CANNOT
    return EXIT_MATCH


if __name__ == "__main__":
    raise SystemExit(main())
