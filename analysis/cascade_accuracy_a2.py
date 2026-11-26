"""Score the cascade's A2 accuracy runs on the test rows, against the same limits as the single models.

Run from the repository root:  python -m analysis.cascade_accuracy_a2

Owner: Part 1 -- Yeo Kai Yuan (hand-off to Part 3, TODO_A2.md §3.1-§3.3). It never calls the service.

Inputs:
* ``results/accuracy_a2/cascade-A_<stamp>/`` and ``cascade-B_<stamp>/``, written by
  ``scripts/run_accuracy_a2.py --config cascade-A|cascade-B --rows test``: ``responses.csv`` (what the
  caller received), ``routing.csv`` (which model answered, from the service log) and ``metadata.json``.
  Exactly one real run per setting is expected; pass ``--run-dir`` to choose when there are more.
* The limits exactly as Part 3 applied them to the single models: the ``qwen2.5:7b`` rows of
  ``analysis/output/accuracy_a2/per_category_a2.csv`` (``minimum_correct`` per category) and
  ``pass_fail_a2.csv`` (overall ``minimum_correct``). Both come from ``docs/a2/accuracy_limits.md``.
* For the determinism cross-check (TODO_A2.md §3.1): the Assignment 1 ``responses.csv`` of
  ``granite4:3b`` and ``qwen2.5:7b`` -- the same files Part 3 scored.

Rules (the same as ``analysis/accuracy_a2.py`` and prediction record §4): an errored ticket (HTTP status
not 200, or an error) counts as ERROR, which is wrong, and stays in the denominator. ``UNPARSEABLE`` is
wrong. Per-category accuracy uses the true category as denominator.

Writes to ``analysis/output/accuracy_a2/``:
  cascade_pass_fail_a2.csv     one row per setting, same columns as pass_fail_a2.csv
  cascade_per_category_a2.csv  one row per setting x category, same columns as per_category_a2.csv
  cascade_routing_a2.csv       escalation fraction, accuracy when accepted vs escalated (§3.3)
  cascade_determinism_a2.csv   small-model (and escalated large-model) answer vs its A1 answer, per row
  verdicts_a2.csv              config,passes_accuracy for every configuration (for summarise_load_a2.py)
  cascade-<S>_<stamp>/confusion_matrix.csv
  cascade_report.md
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from service.categories import CATEGORIES  # noqa: E402

RESULTS = ROOT / "results/accuracy_a2"
OUT = ROOT / "analysis/output/accuracy_a2"
SMALL, LARGE = "granite4:3b", "qwen2.5:7b"
A1_RUNS = {
    SMALL: ROOT / "results/accuracy/granite4-3b_20261008T122430Z/responses.csv",
    LARGE: ROOT / "results/accuracy/qwen2.5-7b_20261008T123045Z/responses.csv",
}
SETTINGS = ("A", "B")


def read(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def by_row(rows: list[dict], name: str) -> dict[str, dict]:
    indexed = {r["row_number"]: r for r in rows}
    if len(indexed) != len(rows):
        raise SystemExit(f"duplicate row_number in {name}")
    return indexed


def find_run(setting: str, chosen: list[Path]) -> Path:
    prefix = f"cascade-{setting}_"
    picked = [p for p in chosen if p.name.startswith(prefix)]
    if not picked:
        picked = sorted(p for p in RESULTS.glob(f"{prefix}*") if p.is_dir()
                        and json.loads((p / "metadata.json").read_text())["mode"] == "real")
    if len(picked) != 1:
        raise SystemExit(
            f"expected exactly one real run for Setting {setting} under {RESULTS}, "
            f"found {[p.name for p in picked]}; choose with --run-dir"
        )
    return picked[0]


def limits() -> tuple[int, dict[str, int]]:
    overall = {r["model_tag"]: r for r in read(OUT / "pass_fail_a2.csv")}[LARGE]
    per_cat = {r["category"]: int(r["minimum_correct"])
               for r in read(OUT / "per_category_a2.csv") if r["model_tag"] == LARGE}
    if set(per_cat) != set(CATEGORIES):
        raise SystemExit("per_category_a2.csv lacks a qwen2.5:7b row for every category")
    return int(overall["minimum_correct"]), per_cat


def score(setting: str, run: Path, golden: dict, test: list[str], a1: dict, min_overall: int,
          min_cat: dict[str, int]) -> dict:
    meta = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
    if meta.get("mode") != "real" or meta.get("config") != f"cascade-{setting}":
        raise SystemExit(f"{run.name}: not a real cascade-{setting} run (metadata.json)")
    responses = by_row(read(run / "responses.csv"), f"{run.name}/responses.csv")
    routing = by_row(read(run / "routing.csv"), f"{run.name}/routing.csv")
    if set(responses) != set(test):
        raise SystemExit(f"{run.name}: responses.csv does not cover exactly the 101 test rows")

    rows = []
    for row in test:
        resp, route = responses[row], routing.get(row, {})
        errored = resp["http_status"] != "200" or bool(resp["error"])
        predicted = "ERROR" if errored else (resp["predicted_category"] or "UNPARSEABLE")
        escalated = {"true": True, "false": False}.get(route.get("escalated", ""))
        rows.append(dict(row_number=row, label=golden[row], predicted=predicted,
                         correct=predicted == golden[row], escalated=escalated,
                         model_tag=route.get("model_tag", ""),
                         small=route.get("small_model_category", ""),
                         setting_logged=route.get("cascade_setting", "")))

    correct = sum(r["correct"] for r in rows)
    counts = Counter(r["label"] for r in rows)
    cat_rows = []
    for c in CATEGORIES:
        hits = sum(r["correct"] and r["label"] == c for r in rows)
        cat_rows.append(dict(model_tag=f"cascade-{setting}", category=c, correct=hits, test_set_n=counts[c],
                             accuracy=hits / counts[c], minimum_correct=min_cat[c],
                             passes=hits >= min_cat[c], too_small=counts[c] < 10,
                             borderline=counts[c] == 11))
    overall_pass = correct >= min_overall
    cats_pass = all(r["passes"] for r in cat_rows)
    verdict = dict(model_tag=f"cascade-{setting}", correct=correct, test_set_n=len(rows),
                   accuracy_pct=correct / len(rows) * 100, minimum_correct=min_overall,
                   overall_pass=overall_pass, all_categories_pass=cats_pass,
                   qualifies=overall_pass and cats_pass,
                   failed_categories="; ".join(r["category"] for r in cat_rows if not r["passes"]))

    known = [r for r in rows if r["escalated"] is not None]
    esc = [r for r in known if r["escalated"]]
    acc = [r for r in known if not r["escalated"]]
    slips = [r for r in acc if not r["correct"]]
    routing_row = dict(
        config=f"cascade-{setting}", run_dir=f"results/accuracy_a2/{run.name}", test_rows=len(rows),
        routing_known=len(known), escalated=len(esc), accepted=len(acc),
        escalation_fraction=len(esc) / len(known) if known else "",
        accepted_correct=sum(r["correct"] for r in acc), escalated_correct=sum(r["correct"] for r in esc),
        accepted_wrong_slips=len(slips),
        slip_true_categories="; ".join(f"{c} {n}" for c, n in Counter(r["label"] for r in slips).most_common()),
        errored=sum(r["predicted"] == "ERROR" for r in rows),
        unparseable=sum(r["predicted"] == "UNPARSEABLE" for r in rows),
        wrong_setting_in_log=sum(1 for r in known if r["setting_logged"] != setting),
        answered_by_small_but_flagged_escalated=sum(1 for r in esc if r["model_tag"] == SMALL),
    )

    determinism = []
    for r in rows:
        small_a1 = a1[SMALL][r["row_number"]]["predicted_category"] or "UNPARSEABLE"
        large_a1 = a1[LARGE][r["row_number"]]["predicted_category"] or "UNPARSEABLE"
        determinism.append(dict(
            config=f"cascade-{setting}", row_number=r["row_number"],
            small_model_category=r["small"], granite_a1=small_a1,
            small_matches_a1=(r["small"] == small_a1) if r["small"] else "",
            escalated=r["escalated"], final_category=r["predicted"],
            qwen_a1=large_a1 if r["escalated"] else "",
            large_matches_a1=(r["predicted"] == large_a1) if r["escalated"] else ""))
    matrix_cols = [*CATEGORIES, "UNPARSEABLE", "ERROR"]
    matrix = [dict(actual_category=c, **{p: sum(r["label"] == c and r["predicted"] == p for r in rows)
                                         for p in matrix_cols}) for c in CATEGORIES]
    write(OUT / run.name / "confusion_matrix.csv", matrix)
    return dict(verdict=verdict, categories=cat_rows, routing=routing_row, determinism=determinism,
                run=run, meta=meta)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run-dir", action="append", type=Path, default=[],
                        help="a cascade-A_*/cascade-B_* run directory (repeatable)")
    args = parser.parse_args(argv)
    chosen = [p if p.is_absolute() else ROOT / p for p in args.run_dir]

    split = by_row(read(ROOT / "golden/split_a2.csv"), "split")
    golden = {r["row_number"]: r["label"] for r in read(ROOT / "golden/golden_set.csv")}
    test = sorted((r for r, e in split.items() if e["set"] == "test"), key=int)
    if len(test) != 101:
        raise SystemExit("expected 101 test rows in golden/split_a2.csv")
    a1 = {m: by_row(read(p), str(p)) for m, p in A1_RUNS.items()}
    min_overall, min_cat = limits()

    results = [score(s, find_run(s, chosen), golden, test, a1, min_overall, min_cat) for s in SETTINGS]
    write(OUT / "cascade_pass_fail_a2.csv", [r["verdict"] for r in results])
    write(OUT / "cascade_per_category_a2.csv", [c for r in results for c in r["categories"]])
    write(OUT / "cascade_routing_a2.csv", [r["routing"] for r in results])
    write(OUT / "cascade_determinism_a2.csv", [d for r in results for d in r["determinism"]])
    # Every configuration's verdict in one table, in the shape summarise_load_a2.py's
    # --accuracy-verdicts reads: Part 3's single-model verdicts plus the cascade's.
    singles = [dict(config=r["model_tag"], passes_accuracy=str(r["qualifies"] == "True").lower(),
                    source="pass_fail_a2.csv") for r in read(OUT / "pass_fail_a2.csv")]
    write(OUT / "verdicts_a2.csv", singles + [
        dict(config=r["verdict"]["model_tag"], passes_accuracy=str(r["verdict"]["qualifies"]).lower(),
             source="cascade_pass_fail_a2.csv") for r in results])

    flag = lambda v: "PASS" if v else "FAIL"  # noqa: E731
    lines = ["# A2 cascade accuracy — test rows only", "",
             "Reproduce from the repository root: `python -m analysis.cascade_accuracy_a2`.", "",
             f"New A2 runs of the cascade (`{SMALL}` first, `{LARGE}` on escalation) on the 101 test rows, "
             "scored against `golden/golden_set.csv` with the same limits Part 3 applied to the single models "
             f"(at least {min_overall}/101 overall, and each category's `minimum_correct` in "
             "`per_category_a2.csv`). Errors count as wrong and stay in the denominator.", "",
             "| Configuration | Run | Correct / test rows | Accuracy | Overall | All categories | Qualifies | Failed categories |",
             "|---|---|---|---|---|---|---|---|"]
    for r in results:
        v = r["verdict"]
        lines.append(f"| {v['model_tag']} | `{r['run'].name}` | {v['correct']}/101 | {v['accuracy_pct']:.2f}% | "
                     f"{flag(v['overall_pass'])} | {flag(v['all_categories_pass'])} | {flag(v['qualifies'])} | "
                     f"{v['failed_categories'] or '—'} |")
    lines += ["", "## Per category (correct / N, pass needs)", "",
              "| Category | N | Needs | " + " | ".join(r["verdict"]["model_tag"] for r in results) + " |",
              "|---|---|---|" + "---|" * len(results)]
    for i, c in enumerate(CATEGORIES):
        first = results[0]["categories"][i]
        cells = [f"{r['categories'][i]['correct']}{'' if r['categories'][i]['passes'] else ' ✗'}" for r in results]
        lines.append(f"| {c} | {first['test_set_n']} | {first['minimum_correct']} | " + " | ".join(cells) + " |")
    lines += ["", "## Escalated vs accepted (from the service log, via `routing.csv`)", "",
              "| Configuration | Escalated | Accepted (granite answer kept) | Right when accepted | Right when escalated | Accepted but wrong | Errors |",
              "|---|---|---|---|---|---|---|"]
    for r in results:
        g = r["routing"]
        frac = f"{g['escalated']}/{g['routing_known']}"
        lines.append(f"| {g['config']} | {frac} ({g['escalated'] / g['routing_known']:.1%}) | {g['accepted']} | "
                     f"{g['accepted_correct']}/{g['accepted']} | {g['escalated_correct']}/{g['escalated']} | "
                     f"{g['accepted_wrong_slips']}{' (' + g['slip_true_categories'] + ')' if g['slip_true_categories'] else ''} | "
                     f"{g['errored']} |")
    lines += ["", "## Determinism cross-check (TODO_A2.md §3.1)", "",
              f"Same prompt, digest, seed and `num_ctx` as Assignment 1, at temperature 0, so `{SMALL}`'s answer "
              "inside the cascade should equal its Assignment 1 answer on the same row, and so should "
              f"`{LARGE}`'s on escalated rows.", "",
              "| Configuration | Small model = A1 | Large model = A1 (escalated rows) |", "|---|---|---|"]
    for r in results:
        d = r["determinism"]
        sm = [x for x in d if x["small_matches_a1"] != ""]
        lg = [x for x in d if x["large_matches_a1"] != ""]
        lines.append(f"| cascade-{r['verdict']['model_tag'][-1]} | {sum(x['small_matches_a1'] for x in sm)}/{len(sm)} | "
                     f"{sum(x['large_matches_a1'] for x in lg)}/{len(lg)} |")
    mismatches = [x for r in results for x in r["determinism"]
                  if x["small_matches_a1"] is False or x["large_matches_a1"] is False]
    if mismatches:
        lines += ["", "Mismatched rows (investigate before relying on the reused single-model figures):", ""]
        lines += [f"- {x['config']} row {x['row_number']}: small {x['small_model_category']!r} vs A1 "
                  f"{x['granite_a1']!r}; final {x['final_category']!r}"
                  + (f" vs qwen A1 {x['qwen_a1']!r}" if x['qwen_a1'] else "") for x in mismatches]
    lines += ["", "Files: `cascade_pass_fail_a2.csv`, `cascade_per_category_a2.csv`, `cascade_routing_a2.csv`, "
              "`cascade_determinism_a2.csv`, and a confusion matrix per run folder (actual rows, predicted "
              "columns, ERROR separate).", ""]
    (OUT / "cascade_report.md").write_text("\n".join(lines), encoding="utf-8")
    for r in results:
        v, g = r["verdict"], r["routing"]
        print(f"{v['model_tag']}: {v['correct']}/101 ({v['accuracy_pct']:.2f}%) qualifies={v['qualifies']}; "
              f"escalated {g['escalated']}/{g['routing_known']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
