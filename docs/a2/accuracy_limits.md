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

**Is the reuse valid? Check before computing anything below.** The brief allows reusing A1 predictions only
"as long as nothing has changed (same digest, prompt, Ollama version and machine)". Compare the A1 run's
`metadata.json` (same folder as `responses.csv`) with the current service:

| Item | A1 run (`metadata.json`) | Now | Same? |
|---|---|---|---|
| `model_digest` | TODO(a2) | `../../models/models.yaml` pin | TODO(a2) |
| `prompt_hash` | TODO(a2) | `GET /health` → `prompt_hash` | TODO(a2) |
| `num_ctx`, `seed` | TODO(a2) | `GET /health` / `.env` | TODO(a2) |
| Ollama version | `../../models/models.yaml` → `ollama_version` (0.34.3) | `ollama --version` on the service host | TODO(a2) |
| Machine | `service_host_info` | the A2 service host | TODO(a2) |

If any row differs, the reuse is invalid: re-run that model's accuracy test instead (Part 1, §1.5). The same
check covers all four single models — do it once per model.

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

## 3. How pass/fail is decided

Every configuration is judged against §1 and §2 with these rules. They follow the brief's wording, so they
are fixed, not team choices.

1. **Overall:** pass if test-set accuracy **≥** the overall limit. Equal to the limit passes.
2. **Per category:** pass if the configuration's category accuracy **≥** `qwen2.5:7b`'s category accuracy −
   15. The brief fails only "more than 15 percentage points below", so exactly 15 below passes.
3. **Compare exact fractions, never rounded percentages.** Use counts: `correct / N`. With ~14 tickets in a
   category, rounding to one decimal place can flip a verdict at the boundary. Round only for display.
4. **`UNPARSEABLE` counts as wrong**, as in Assignment 1.
5. **Too-small categories** (fewer than 10 test-set tickets, the brief's own example) are still judged, and
   flagged on Slide 4 as too small for the per-category limit to be a fair test. Flagging doesn't change the
   verdict.
6. A configuration passes only if it passes the overall limit **and** all seven category limits.

## 4. How to reproduce this

1. Load `../../golden/split_a2.csv`, keep `row_number` where `set == "test"`.
2. Load `../../results/accuracy/qwen2.5-7b_20261008T123045Z/responses.csv`, keep those same `row_number`s.
3. Score `predicted_category` against `../../golden/golden_set.csv`'s `label` for each row, overall and per
   category (same scoring rule as Assignment 1: `UNPARSEABLE` counts as wrong).
4. §1 = overall test accuracy − 10. §2 per row = that category's test accuracy − 15.

This document feeds: `../../predictions/prediction_record_a2.md` (§4.2), Slide 1 (limits stated on the
cover), and every later accuracy table in `../../analysis/output/accuracy_a2/` (§3.2 — pass/fail verdicts).
