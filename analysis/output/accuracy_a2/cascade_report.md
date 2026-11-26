# A2 cascade accuracy — test rows only

Reproduce from the repository root: `python -m analysis.cascade_accuracy_a2`.

New A2 runs of the cascade (`granite4:3b` first, `qwen2.5:7b` on escalation) on the 101 test rows, scored against `golden/golden_set.csv` with the same limits Part 3 applied to the single models (at least 65/101 overall, and each category's `minimum_correct` in `per_category_a2.csv`). Errors count as wrong and stay in the denominator.

| Configuration | Run | Correct / test rows | Accuracy | Overall | All categories | Qualifies | Failed categories |
|---|---|---|---|---|---|---|---|
| cascade-A | `cascade-A_20261126T094140Z` | 76/101 | 75.25% | PASS | PASS | PASS | — |
| cascade-B | `cascade-B_20261126T095101Z` | 74/101 | 73.27% | PASS | PASS | PASS | — |

## Per category (correct / N, pass needs)

| Category | N | Needs | cascade-A | cascade-B |
|---|---|---|---|---|
| Credit reporting | 25 | 18 | 21 | 21 |
| Debt collection | 13 | 9 | 10 | 10 |
| Mortgage | 11 | 3 | 5 | 5 |
| Credit card | 11 | 8 | 9 | 10 |
| Bank account or service | 16 | 13 | 15 | 14 |
| Consumer loan | 14 | 6 | 8 | 6 |
| Money transfer or service | 11 | 7 | 8 | 8 |

## Escalated vs accepted (from the service log, via `routing.csv`)

| Configuration | Escalated | Accepted (granite answer kept) | Right when accepted | Right when escalated | Accepted but wrong | Errors |
|---|---|---|---|---|---|---|
| cascade-A | 83/101 (82.2%) | 18 | 13/18 | 63/83 | 5 (Mortgage 2; Credit reporting 2; Consumer loan 1) | 0 |
| cascade-B | 65/101 (64.4%) | 36 | 23/36 | 51/65 | 13 (Consumer loan 5; Mortgage 4; Credit reporting 3; Bank account or service 1) | 0 |

## Determinism cross-check (TODO_A2.md §3.1)

Same prompt, digest, seed and `num_ctx` as Assignment 1, at temperature 0, so `granite4:3b`'s answer inside the cascade should equal its Assignment 1 answer on the same row, and so should `qwen2.5:7b`'s on escalated rows.

| Configuration | Small model = A1 | Large model = A1 (escalated rows) |
|---|---|---|
| cascade-A | 101/101 | 83/83 |
| cascade-B | 101/101 | 65/65 |

Files: `cascade_pass_fail_a2.csv`, `cascade_per_category_a2.csv`, `cascade_routing_a2.csv`, `cascade_determinism_a2.csv`, and a confusion matrix per run folder (actual rows, predicted columns, ERROR separate).
