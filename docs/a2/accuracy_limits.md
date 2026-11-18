# Accuracy limits — Group 10

**What this is.** Step 1 of the brief, computed. The overall and per-category accuracy limits every
Assignment 2 configuration is scored against. Computed **entirely from Assignment 1 evidence**, by re-scoring
`qwen2.5:7b`'s existing per-ticket predictions against `../../golden/split_a2.csv`'s `test` rows — no new
model calls.

**Owner:** Part 2 — Loh Wen Xuan.

**Source data.**

| What | Where |
|---|---|
| Reference (top) model | `qwen2.5:7b`, by full-golden-set accuracy in `../../analysis/output/accuracy/model_comparison.csv` (74.0%, 148/200) |
| Its per-ticket predictions | `../../results/accuracy/qwen2.5-7b_20261008T123045Z/responses.csv` |
| Golden labels | `../../golden/golden_set.csv` |
| Tuning/test split | `../../golden/split_a2.csv` (99 tuning rows, 101 test rows, by row-number parity) |

---

## 1. Overall limit

| | |
|---|---|
| `qwen2.5:7b` accuracy on the **test-set** rows only (count/N) | TODO(a2): e.g. `NN/101 (XX.X%)` |
| Overall limit = test-set accuracy − 10 percentage points | TODO(a2) |

## 2. Per-category limits

For each category: `qwen2.5:7b`'s test-set accuracy on that category, minus 15 percentage points. Counts are
shown because the test set is small — flag any category where the count makes the per-category limit an
unfair test (brief: "Small numbers").

| Category | Test-set tickets (N) | `qwen2.5:7b` correct (n) | `qwen2.5:7b` test accuracy | Limit (accuracy − 15pp) | Too small to be a fair test? |
|---|---|---|---|---|---|
| Credit reporting | TODO(a2) | TODO(a2) | TODO(a2) | TODO(a2) | TODO(a2) |
| Debt collection | TODO(a2) | TODO(a2) | TODO(a2) | TODO(a2) | TODO(a2) |
| Mortgage | TODO(a2) | TODO(a2) | TODO(a2) | TODO(a2) | TODO(a2) |
| Credit card | TODO(a2) | TODO(a2) | TODO(a2) | TODO(a2) | TODO(a2) |
| Bank account or service | TODO(a2) | TODO(a2) | TODO(a2) | TODO(a2) | TODO(a2) |
| Consumer loan | TODO(a2) | TODO(a2) | TODO(a2) | TODO(a2) | TODO(a2) |
| Money transfer or service | TODO(a2) | TODO(a2) | TODO(a2) | TODO(a2) | TODO(a2) |

A category with fewer than 10 test-set tickets should be flagged: at 8 tickets, one ticket is worth 12.5
points (brief's own example).

## 3. How to reproduce this

1. Load `../../golden/split_a2.csv`, keep `row_number` where `set == "test"`.
2. Load `../../results/accuracy/qwen2.5-7b_20261008T123045Z/responses.csv`, keep those same `row_number`s.
3. Score `predicted_category` against `../../golden/golden_set.csv`'s `label` for each row, overall and per
   category (same scoring rule as Assignment 1: `UNPARSEABLE` counts as wrong).
4. §1 = overall test accuracy − 10. §2 per row = that category's test accuracy − 15.

This document feeds: `../../predictions/prediction_record_a2.md` (§4.2), Slide 1 (limits stated on the
cover), and every later accuracy table in `../../analysis/output/accuracy_a2/` (§3.2 — pass/fail verdicts).
