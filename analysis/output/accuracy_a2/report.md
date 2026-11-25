# A2 single-model accuracy — test rows only

Reproduce from the repository root: `python -m analysis.accuracy_a2`.

Reused saved Assignment 1 predictions, restricted to the 101 test rows in `golden/split_a2.csv`, scored against `golden/golden_set.csv`. No model calls or speed measurements.

Reuse validity is documented in `docs/a2/accuracy_limits.md` and `docs/a2/env_baseline.json`; this offline scoring does not re-check the live environment. All A1 runs record a dirty working tree; their recorded prompt hash matches the frozen prompt.

| Model | Correct / test rows | Accuracy | Overall | All categories | Qualifies |
|---|---|---|---|---|---|
| granite4:3b | 63/101 | 62.38% | FAIL | FAIL | FAIL |
| llama3.2:1b-instruct-q4_K_M | 34/101 | 33.66% | FAIL | FAIL | FAIL |
| llama3.2:3b | 54/101 | 53.47% | FAIL | FAIL | FAIL |
| qwen2.5:7b | 75/101 | 74.26% | PASS | PASS | PASS |

Pass/fail uses exact fractions: at least 65/101 overall and every category minimum from `docs/a2/accuracy_limits.md`. Errors and UNPARSEABLE count as wrong. Per-category accuracy uses the true category as the denominator (recall).

No category has fewer than 10 test rows. Mortgage, Credit card and Money transfer or service each have 11 rows and are borderline: one ticket changes accuracy by 9.1 percentage points.

`model_comparison_a2.csv` preserves A1's columns and fractional accuracy units. `pass_fail_a2.csv` is the handoff table for Part 1; `per_category_a2.csv` contains every category verdict. `sources.csv` identifies the inputs and recorded configuration. Each model folder includes a confusion matrix with actual labels as rows and predictions as columns. ERROR is a separate wrong-answer column.

Cascade scoring, determinism checks, escalation analysis and Slide 6 await new A2 runs. These results do not complete those tasks or constitute a final recommendation.
