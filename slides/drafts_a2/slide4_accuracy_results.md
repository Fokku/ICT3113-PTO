# Slide 4 — Accuracy results (draft)

**Brief (verbatim):** "Overall and per-category accuracy for every configuration, with counts. Which pass the
limits. Escalation fraction; accuracy of escalated vs non-escalated tickets."
**Owners:** Jolie Ngai Ning Li (Part 3) owns the measured accuracy numbers. Loh Wen Xuan (Part 2) owns the
limit lines and the "which pass the limits" verdicts. Part 5 owns layout and assembly.
**Done when** (`../outline_a2.md`): every number names its source file in `analysis/output/accuracy_a2/`.

All figures are on the **101 test-set rows only** (`golden/split_a2.csv`, `set = test`), scored against
`golden/golden_set.csv`. Single-model figures come from `python -m analysis.accuracy_a2`. Cascade figures
are added once Part 1's A2 accuracy runs exist. Nothing is typed in by hand.

**Status:** single-model rows filled in (final). Cascade rows, escalation and the escalated vs
non-escalated split are placeholders until the cascade runs.

---

## Title

Accuracy on the 101 test-set tickets: `<one line: which configurations pass both limits>`

## Required statement: reuse of Assignment 1 predictions (must appear on the slide)

> Single-model accuracy is **reused from Assignment 1, not re-run**. We scored only the 101 test-set rows
> of the saved A1 predictions. The reuse is valid because nothing changed: same model digests, same prompt
> (`sha256:681131c48bdc15a1`), same `num_ctx` (4096) and seed (42), same Ollama version (0.34.3), same
> machine (`omarchy`).

Digests, for the speaker notes or a footnote (`analysis/output/accuracy_a2/sources.csv`):

| Model | Digest |
|---|---|
| `qwen2.5:7b` | `sha256:845dbda0…0a697e` |
| `granite4:3b` | `sha256:89962fcc…6a3e5f` |
| `llama3.2:3b` | `sha256:a80c4f17…b5b8b72` |
| `llama3.2:1b-instruct-q4_K_M` | `sha256:22bc6b92…fafa02` |

Footnote: every A1 run's `metadata.json` records `git_dirty: true`. The recorded prompt hash still matches
the frozen prompt (`docs/a2/accuracy_limits.md`).

## Main table: overall accuracy and verdict (`pass_fail_a2.csv`)

Overall limit: **at least 65/101** (`qwen2.5:7b`'s 75/101 minus 10 percentage points = 64.26%).

| Configuration | Correct / 101 | Accuracy | Overall (≥ 65) | All 7 categories | Passes both limits |
|---|---|---|---|---|---|
| `qwen2.5:7b` alone (reference) | 75 | 74.26% | PASS | PASS | **Yes** |
| `granite4:3b` alone | 63 | 62.38% | FAIL | FAIL | No |
| `llama3.2:3b` alone | 54 | 53.47% | FAIL | FAIL | No |
| `llama3.2:1b-instruct-q4_K_M` alone | 34 | 33.66% | FAIL | FAIL | No |
| Cascade, Setting A | `<n>` | `<%>` | `<>` | `<>` | `<>` |
| Cascade, Setting B | `<n>` | `<%>` | `<>` | `<>` | `<>` |

Cascade = `granite4:3b` first, escalating to `qwen2.5:7b`. Setting A accepts granite's answer only for
Mortgage, Consumer loan or Debt collection. Setting B also accepts Credit card (`cascade/escalation_rule.md`).

## Per-category table: correct / N, with the minimum to pass (`per_category_a2.csv`)

✗ marks a category below its minimum. The minimums come from `docs/a2/accuracy_limits.md` §2
(`qwen2.5:7b`'s category accuracy minus 15 percentage points).

| Category (N) | Minimum | qwen2.5:7b | granite4:3b | llama3.2:3b | llama3.2:1b | Cascade A | Cascade B |
|---|---|---|---|---|---|---|---|
| Credit reporting (25) | 18 | 21 | 22 | 17 ✗ | 25 | `<>` | `<>` |
| Debt collection (13) | 9 | 10 | 5 ✗ | 9 | 1 ✗ | `<>` | `<>` |
| Mortgage (11)* | 3 | 4 | 5 | 2 ✗ | 0 ✗ | `<>` | `<>` |
| Credit card (11)* | 8 | 9 | 10 | 3 ✗ | 1 ✗ | `<>` | `<>` |
| Bank account or service (16) | 13 | 15 | 13 | 15 | 0 ✗ | `<>` | `<>` |
| Consumer loan (14) | 6 | 8 | 3 ✗ | 8 | 7 | `<>` | `<>` |
| Money transfer or service (11)* | 7 | 8 | 5 ✗ | 0 ✗ | 0 ✗ | `<>` | `<>` |

\* **Borderline categories:** 11 test tickets each, so one ticket moves accuracy by 9.1 percentage points.
No category has fewer than 10 test tickets, so none is excluded from the per-category check.

Per-category accuracy uses the true category as the denominator (recall). Errors and UNPARSEABLE count as
wrong. None of the 404 single-model test responses was an error or UNPARSEABLE.

## Cascade only: escalation and escalated vs non-escalated accuracy

| | Setting A | Setting B |
|---|---|---|
| Escalation fraction (test set) | `<n>/101 (<%>)` | `<n>/101 (<%>)` |
| Accuracy when granite's answer was accepted | `<n>/<m> (<%>)` | `<n>/<m> (<%>)` |
| Accuracy when escalated to qwen2.5:7b | `<n>/<m> (<%>)` | `<n>/<m> (<%>)` |
| Tuning-set expectation (`cascade/escalation_rule.md` §3) | `<from §3>` | `<from §3>` |

One line of interpretation: does the rule catch the tickets granite gets wrong? In other words, is
accuracy on accepted tickets close to granite's precision on those categories?

Source: `analysis/output/accuracy_a2/<cascade file>`, from the accuracy run's `routing.csv` / service log.

## Small print: determinism cross-check

On all 101 test rows, granite's answer inside the cascade run (`small_model_category`) matched its A1
`predicted_category` on `<n>/101` rows. This supports the reuse statement above. Any mismatch is explained
here before either figure is reported.

## Traceability rows to add to `../outline_a2.md` (Part 5's map)

| Slide | Figure | Source file | Produced by |
|---|---|---|---|
| 4 | overall accuracy and pass/fail, every configuration | `analysis/output/accuracy_a2/pass_fail_a2.csv` | `python -m analysis.accuracy_a2` |
| 4 | per-category correct / N and pass/fail | `analysis/output/accuracy_a2/per_category_a2.csv` | same |
| 4 | reuse statement: digests, prompt hash, `num_ctx`, seed | `analysis/output/accuracy_a2/sources.csv`, `docs/a2/accuracy_limits.md` | same |
| 4 | overall and per-category minimums | `docs/a2/accuracy_limits.md` §1–§2 | Part 2 |
| 4 | escalation fraction, escalated vs non-escalated accuracy | `analysis/output/accuracy_a2/<cascade file>` | `<cascade scoring command>` |
| 4 | determinism cross-check | `analysis/output/accuracy_a2/<determinism file>` | `<command>` |
