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
| `model_digest` | See the per-model table below. All four match their pin exactly | `../../models/models.yaml` pin | **Yes**, all four. Also confirmed live on the service host: `env_baseline.json` → `matches_assignment_1_pins.digests` all `true` (2026-11-19) |
| `prompt_hash` | `sha256:681131c48bdc15a1` in all four runs | `service/prompt.py` → `PROMPT_HASH` = `sha256:681131c48bdc15a1` (computed from the committed template, 2026-11-18). Running A2 service: `env_baseline.json` → `service.prompt_hash` = `sha256:681131c48bdc15a1` | **Yes** (repo and live service, 2026-11-19) |
| `num_ctx`, `seed` | `4096`, `42` in all four runs | `../../.env.example` / `service/config.py` defaults: `NUM_CTX=4096`, `OLLAMA_SEED=42`. Running A2 service: `env_baseline.json` → `service.num_ctx` 4096, `service.seed` 42 | **Yes** (repo and live service, 2026-11-19) |
| Ollama version | `0.34.3` (`../../models/models.yaml` → `ollama_version`; `../environment/omarchy-Ollama.txt` → `/api/version`) | `env_baseline.json` → `ollama_version` = `0.34.3`, captured on `omarchy` 2026-11-19 | **Yes** |
| Machine | `service_url` `http://192.168.50.130:8000`, which is host `omarchy` (`../environment/omarchy-Service.txt`, `../environment/omarchy-Ollama.txt`) | `env_baseline.json` → `captured_from` = `omarchy`. Same host also ran the memory check (`../environment/a2-memory-check/20261119T073203Z/summary.md`: 31.3 GiB, no container limits) | **Yes**, same host. Part 5 still owns the full environment write-up (`../../TODO_A2.md` §5.1) |

Per-model digests (A1 `metadata.json` against the `../../models/models.yaml` pin):

| Model | A1 run folder | `model_digest` (A1 run = pin) |
|---|---|---|
| `qwen2.5:7b` | `qwen2.5-7b_20261008T123045Z` | `sha256:845dbda0…0a697e` |
| `granite4:3b` | `granite4-3b_20261008T122430Z` | `sha256:89962fcc…6a3e5f` |
| `llama3.2:3b` | `llama3.2-3b_20261008T121848Z` | `sha256:a80c4f17…b5b8b72` |
| `llama3.2:1b-instruct-q4_K_M` | `llama3.2-1b-instruct-q4_K_M_20261008T121612Z` | `sha256:22bc6b92…fafa02` |

All four A1 accuracy runs returned HTTP 200 for all 200 tickets (`metadata.json` → `notes`:
`status_counts={200: 200}`). No ticket is missing or errored, so every test-set row has a real prediction.

**One thing to note for Slide 4.** Every A1 run's `metadata.json` records `"git_dirty": true` at commit
`41d6ce2`, so the working tree had uncommitted changes at the time. The recorded `prompt_hash` matches the
committed template, so the classification prompt was not among those changes. That is the part the reuse
depends on.

If any row differs, the reuse is invalid: re-run that model's accuracy test instead (Part 1, §1.5). The same
check covers all four single models — do it once per model. **Status, 2026-11-21: reuse valid.** Digest, prompt hash,
`num_ctx`, seed, Ollama version and machine all match Assignment 1, both in the repository and on the live
service host (`env_baseline.json`, recorded by Part 1 on 2026-11-19, before any A2 benchmark run).

---

## 1. Overall limit

| | |
|---|---|
| `qwen2.5:7b` accuracy on the **test-set** rows only (count/N) | **75/101 (74.26%)**: 75 right, 26 wrong |
| Overall limit = test-set accuracy − 10 percentage points | **64.26%** (exactly 75/101 − 0.10 = 64.257…%) |
| In counts, out of 101 test-set tickets | **Pass with ≥ 65/101 correct** (64.36%). 64/101 (63.37%) fails |

For comparison only: `qwen2.5:7b` scored 148/200 (74.0%) on the full golden set in Assignment 1. The limit is
based on the test-set figure above, as the brief requires, and not on the full-set figure.

## 2. Per-category limits

For each category: `qwen2.5:7b`'s test-set accuracy on that category, minus 15 percentage points. Counts are
shown because the test set is small — flag any category where the count makes the per-category limit an
unfair test (brief: "Small numbers").

| Category | Test-set tickets (N) | `qwen2.5:7b` correct (n) | `qwen2.5:7b` test accuracy | Limit (accuracy − 15pp) | Pass needs ≥ (correct/N) | Too small to be a fair test? |
|---|---|---|---|---|---|---|
| Credit reporting | 25 | 21 (4 wrong) | 84.00% | 69.00% | 18/25 | No |
| Debt collection | 13 | 10 (3 wrong) | 76.92% | 61.92% | 9/13 | No, but coarse: 1 ticket = 7.7 pp |
| Mortgage | 11 | 4 (7 wrong) | 36.36% | 21.36% | 3/11 | **Borderline**: 1 ticket = 9.1 pp |
| Credit card | 11 | 9 (2 wrong) | 81.82% | 66.82% | 8/11 | **Borderline**: 1 ticket = 9.1 pp |
| Bank account or service | 16 | 15 (1 wrong) | 93.75% | 78.75% | 13/16 | No |
| Consumer loan | 14 | 8 (6 wrong) | 57.14% | 42.14% | 6/14 | No |
| Money transfer or service | 11 | 8 (3 wrong) | 72.73% | 57.73% | 7/11 | **Borderline**: 1 ticket = 9.1 pp |
| **Total** | **101** | **75** | 74.26% | — | — | — |

"Pass needs ≥" is the smallest count `k` with `k/N ≥ n/N − 0.15`, worked out exactly
(`k ≥ n − 0.15·N`, rounded up). It is the §3 rule 3 comparison already done in counts. Part 3 should compare
each configuration's count against this column, not against the rounded percentage.

**Too-small flag.** No category falls under the brief's "fewer than 10" line. The smallest have N = 11, so
none is flagged as too small. Three categories (**Mortgage, Credit card, Money transfer or service**, N = 11
each) sit just above that line, and there one ticket is worth 9.1 points. The 15-point band is 1.65 tickets
wide, so a configuration fails one of these categories by getting **2 more tickets wrong** than `qwen2.5:7b`.
Slide 1 and Slide 4 should mark these three as borderline: a pass or fail there rests on one or two tickets
and is weak evidence either way. Debt collection (N = 13) is close behind. **Mortgage** has a further caveat:
the reference model gets only 4/11 right, so its limit (21.36%, 3/11) is very low. Almost any configuration
passes it, and passing tells us little about whether Mortgage tickets are handled acceptably.

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

The same steps as one command, from the repository root. It needs only the standard library and prints the
§1 and §2 counts:

```
python -c "import csv;R=lambda p:list(csv.DictReader(open(p,encoding='utf-8')));g={r['row_number']:r['label'] for r in R('golden/golden_set.csv')};t={r['row_number'] for r in R('golden/split_a2.csv') if r['set']=='test'};p={r['row_number']:(r['predicted_category'] or 'UNPARSEABLE') for r in R('results/accuracy/qwen2.5-7b_20261008T123045Z/responses.csv')};print('overall',sum(p[r]==g[r] for r in t),len(t));[print(c,sum(p[r]==c for r in t if g[r]==c),sum(g[r]==c for r in t)) for c in sorted({g[r] for r in t})]"
```

Expected output: `overall 75 101`, then per category (correct, N): Bank account or service 15 16, Consumer
loan 8 14, Credit card 9 11, Credit reporting 21 25, Debt collection 10 13, Money transfer or service 8 11,
Mortgage 4 11.

**Computed** 2026-11-18 by Part 2 (Loh Wen Xuan), with an AI assistant running the computation (logged in
`ai-use-log.md`). No model was called. Only `qwen2.5:7b`'s test-set rows were scored here. The other three
models' test-set scores belong to Part 3 (`../../TODO_A2.md` §3.1).

This document feeds: `../../predictions/prediction_record_a2.md` (§4.2), Slide 1 (limits stated on the
cover), and every later accuracy table in `../../analysis/output/accuracy_a2/` (§3.2 — pass/fail verdicts).
