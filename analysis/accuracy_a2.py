"""Re-score saved A1 predictions on A2 test rows; never calls the service.

Run from the repository root: python -m analysis.accuracy_a2
"""

import csv
import json
from collections import Counter
from fractions import Fraction
from math import ceil
from pathlib import Path

from service.categories import CATEGORIES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis/output/accuracy_a2"
RUNS = {
    "granite4:3b": "granite4-3b_20261008T122430Z",
    "llama3.2:1b-instruct-q4_K_M": "llama3.2-1b-instruct-q4_K_M_20261008T121612Z",
    "llama3.2:3b": "llama3.2-3b_20261008T121848Z",
    "qwen2.5:7b": "qwen2.5-7b_20261008T123045Z",
}


def read(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def write(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def unique(rows, name):
    indexed = {r["row_number"]: r for r in rows}
    if len(indexed) != len(rows):
        raise ValueError(f"Duplicate row_number in {name}")
    return indexed


def main():
    split = unique(read(ROOT / "golden/split_a2.csv"), "split")
    golden = unique(read(ROOT / "golden/golden_set.csv"), "golden")
    test = sorted(r for r, entry in split.items() if entry["set"] == "test")
    if (len(test) != 101 or len(split) != 200 or set(split) != set(golden)
            or any(r["set"] not in {"test", "tuning"} for r in split.values())):
        raise ValueError("Expected a complete 200-row split with 101 test rows")
    if any(r["label"] not in CATEGORIES for r in golden.values()):
        raise ValueError("Unknown golden label")

    # Validate every input before creating outputs. These are pinned A1 runs.
    runs = {}
    for model, folder in RUNS.items():
        directory = ROOT / "results/accuracy" / folder
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        responses = unique(read(directory / "responses.csv"), folder)
        if metadata["model_tag"] != model or metadata["mode"] != "real":
            raise ValueError(f"Unexpected run metadata: {folder}")
        if set(responses) != set(golden):
            raise ValueError(f"Incomplete or unexpected A1 row coverage: {folder}")
        rows = []
        for row in test:
            response = responses[row]
            error = response["http_status"] != "200" or bool(response["error"])
            predicted = response["predicted_category"] or "UNPARSEABLE"
            if predicted not in (*CATEGORIES, "UNPARSEABLE"):
                raise ValueError(f"Unknown prediction: {folder}, row {row}")
            # Failed responses remain in the denominator, never correct.
            if error:
                predicted = "ERROR"
            rows.append(dict(row_number=row, label=golden[row]["label"],
                             predicted_category=predicted, http_status=response["http_status"],
                             error=response["error"], correct=predicted == golden[row]["label"]))
        runs[model] = (folder, metadata, rows)

    reference = runs["qwen2.5:7b"][2]
    counts = Counter(r["label"] for r in reference)
    ref_correct = Counter(r["label"] for r in reference if r["correct"])
    overall_limit = Fraction(sum(r["correct"] for r in reference), 101) - Fraction(1, 10)
    category_limits = {c: Fraction(ref_correct[c], counts[c]) - Fraction(15, 100) for c in CATEGORIES}
    comparisons, verdicts, category_rows, sources = [], [], [], []
    for model, (folder, metadata, rows) in runs.items():
        correct = sum(r["correct"] for r in rows)
        unparseable = sum(r["predicted_category"] == "UNPARSEABLE" for r in rows)
        errors = sum(r["predicted_category"] == "ERROR" for r in rows)
        local_categories, recalls, precisions = [], [], []
        for category in CATEGORIES:
            n = counts[category]
            hits = sum(r["correct"] and r["label"] == category for r in rows)
            predicted_n = sum(r["predicted_category"] == category for r in rows)
            recalls.append(hits / n)
            precisions.append(hits / predicted_n if predicted_n else 0.0)
            limit = category_limits[category]
            needed = max(0, ceil(limit * n))
            local_categories.append(dict(model_tag=model, category=category, correct=hits,
                                         test_set_n=n, accuracy=hits / n,
                                         reference_correct=ref_correct[category], limit_pct=float(limit * 100),
                                         minimum_correct=needed, passes=Fraction(hits, n) >= limit,
                                         too_small=n < 10, borderline=n == 11))
        category_rows.extend(local_categories)
        overall_pass = Fraction(correct, 101) >= overall_limit
        category_pass = all(r["passes"] for r in local_categories)
        verdicts.append(dict(model_tag=model, correct=correct, test_set_n=101,
                             accuracy_pct=correct / 101 * 100, minimum_correct=65,
                             overall_pass=overall_pass, all_categories_pass=category_pass,
                             qualifies=overall_pass and category_pass,
                             failed_categories="; ".join(r["category"] for r in local_categories if not r["passes"])))
        # Same columns and fractional accuracy units as the A1 comparison table.
        comparisons.append(dict(model_tag=model, stamp=folder.rsplit("_", 1)[1], mode="real",
                                golden_rows=101, responses=101, evaluated=101, coverage=1.0,
                                correct=correct, accuracy=correct / 101, unparseable=unparseable,
                                unparseable_rate=unparseable / 101,
                                accuracy_excl_unparseable=correct / (101 - unparseable) if unparseable < 101 else 0.0,
                                macro_recall=sum(recalls) / 7, macro_precision=sum(precisions) / 7,
                                missing_golden_rows=0, errored_responses=errors,
                                duplicate_rows=0, unmatched_responses=0))
        directory = OUT / folder
        columns = [*CATEGORIES, "UNPARSEABLE", "ERROR"]
        matrix = [dict(actual_category=c, **{p: sum(r["label"] == c and r["predicted_category"] == p for r in rows)
                                             for p in columns}) for c in CATEGORIES]
        write(directory / "confusion_matrix.csv", matrix)
        sources.append(dict(model_tag=model, responses=f"results/accuracy/{folder}/responses.csv",
                            metadata=f"results/accuracy/{folder}/metadata.json",
                            model_digest=metadata["model_digest"], prompt_hash=metadata["prompt_hash"],
                            num_ctx=metadata["num_ctx"], seed=metadata["seed"]))

    write(OUT / "model_comparison_a2.csv", comparisons)
    write(OUT / "pass_fail_a2.csv", verdicts)
    write(OUT / "per_category_a2.csv", category_rows)
    write(OUT / "sources.csv", sources)
    report = ["# A2 single-model accuracy — test rows only", "",
              "Reproduce from the repository root: `python -m analysis.accuracy_a2`.", "",
              "Reused saved Assignment 1 predictions, restricted to the 101 test rows in "
              "`golden/split_a2.csv`, scored against `golden/golden_set.csv`. No model calls or speed measurements.", "",
              "Reuse validity is documented in `docs/a2/accuracy_limits.md` and `docs/a2/env_baseline.json`; "
              "this offline scoring does not re-check the live environment. All A1 runs record a dirty working tree; "
              "their recorded prompt hash matches the frozen prompt.", "",
              "| Model | Correct / test rows | Accuracy | Overall | All categories | Qualifies |",
              "|---|---|---|---|---|---|"]
    for v in verdicts:
        status = lambda value: "PASS" if value else "FAIL"
        report.append(f"| {v['model_tag']} | {v['correct']}/101 | {v['accuracy_pct']:.2f}% | "
                      f"{status(v['overall_pass'])} | {status(v['all_categories_pass'])} | {status(v['qualifies'])} |")
    report.extend(["", "Pass/fail uses exact fractions: at least 65/101 overall and every category minimum "
                   "from `docs/a2/accuracy_limits.md`. Errors and UNPARSEABLE count as wrong. "
                   "Per-category accuracy uses the true category as the denominator (recall).", "",
                   "No category has fewer than 10 test rows. Mortgage, Credit card and Money transfer or service "
                   "each have 11 rows and are borderline: one ticket changes accuracy by 9.1 percentage points.", "",
                   "`model_comparison_a2.csv` preserves A1's columns and fractional accuracy units. "
                   "`pass_fail_a2.csv` is the handoff table for Part 1; `per_category_a2.csv` contains every "
                   "category verdict. `sources.csv` identifies the inputs and recorded configuration. "
                   "Each model folder includes a confusion "
                   "matrix with actual labels as rows and predictions as columns. ERROR is a separate wrong-answer column.", "",
                   "Cascade scoring, determinism checks, escalation analysis and Slide 6 await new A2 runs. "
                   "These results do not complete those tasks or constitute a final recommendation.", ""])
    (OUT / "report.md").write_text("\n".join(report), encoding="utf-8")
    for v in verdicts:
        print(f"{v['model_tag']}: {v['correct']}/101 ({v['accuracy_pct']:.2f}%), qualifies={v['qualifies']}")


if __name__ == "__main__":
    main()
