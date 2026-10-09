# Predictions against outcomes — Group 10

**What this is.** The account Slide 11 summarises: every prediction in the frozen prediction record
(`git show golden-freeze:predictions/prediction_record.md`, commit `41d6ce2`) set against what we measured, with
a verdict and, where we were wrong, why. The prediction record itself is not edited; this file is the
"later account of where our predictions were wrong" the brief asks for.

**Rules used for the verdicts.** Each prediction is judged by the test the record itself wrote down next to it
("Rows we would call wrong", "Would be wrong if", "Observation that would refute it"). Where a prediction gave a
band, a measurement inside the band is *right*; outside is *wrong*. Every measured figure is copied from a file
under `../analysis/output/`, named in the row. Entries the record marked **not blind** (the 1B model's
accuracy, hardest category and `UNPARSEABLE` count, and the error direction for `llama3.2:3b`) are scored like
the others but earn no credit when right.

---

## 1. Accuracy (Section 2 and Section 3 of the record)

Source: `../analysis/output/accuracy/model_comparison.csv` and each run's `per_category.csv` and
`confusion_matrix.csv`. One serial pass of the 200 golden tickets per model, 8 October 2026.

### 1.1 Overall accuracy

| Model | Predicted (accepted band) | Measured | Verdict |
|---|---|---|---|
| `llama3.2:1b-instruct-q4_K_M` | 38% (33–43), not blind | **26.0%** (52/200) | **Wrong**, by 7 points below the band |
| `llama3.2:3b` | 55% (49–61) | **48.5%** (97/200) | **Wrong**, 0.5 points below the band |
| `granite4:3b` | 60% (54–66) | **66.0%** (132/200) | Right, at the top edge of the band |
| `qwen2.5:7b` | 70% (64–76) | **74.0%** (148/200) | Right |

The ranking was right (accuracy rises with size, and the licence-clean `granite4:3b` beats `llama3.2:3b` in the
same size class), and the two models we predicted best landed inside their bands. **Both Llama models were
worse than we predicted, and the reason is the same for both: we under-estimated how strongly a small model
falls back on one category when the prompt gives it nothing but the category names.** The 1B model answered
*Credit reporting* — the first category in the prompt's list — for 168 of 200 tickets (`per_category.csv`,
`predicted_as`), so it is right on every Credit reporting ticket (41/41) and on almost nothing else. The
excluded Q8_0 run we had seen before writing the record (§0 of the record) answered Credit reporting for 100 of
200; the four-bit build collapses further, which we did not anticipate when the 1B pin changed to Q4_K_M.
`llama3.2:3b` falls back the other way: it answered *Bank account or service* for 94 tickets when 40 are.

### 1.2 Hardest category per model

| Model | Predicted hardest | Measured lowest recall | Verdict |
|---|---|---|---|
| `llama3.2:1b-instruct-q4_K_M` | Debt collection and Money transfer, both near 0% (not blind) | Mortgage, Bank account and Money transfer all 0%; Debt collection 4% | Right that Money transfer and Debt collection are near 0%, wrong that they are the only ones — no credit (not blind) |
| `llama3.2:3b` | Money transfer or service | **Money transfer 0%** (0/19) | Right (error direction possibly coloured, see record §0) |
| `granite4:3b` | Credit card | **Consumer loan 35%** (8/23); Credit card 78% | **Wrong** |
| `qwen2.5:7b` | Credit card | **Consumer loan 57%** (13/23); Credit card 63% second | **Wrong** |

**Why we were wrong about Consumer loan.** The record named Credit card, Bank account, Money transfer and Debt
collection as the hard categories, and did not name Consumer loan at all. For both models that know the
categories reasonably well, Consumer loan is the hardest, and its errors go to *Credit reporting* and *Debt
collection* (`qwen2.5:7b`: 5 to Debt collection, 4 to Credit reporting; `granite4:3b`: 9 to Credit reporting).
These are student-loan and personal-loan tickets whose narrative is about collection calls or the credit file.
Our protocol revision **R5** puts student-loan servicing under Consumer loan, not Debt collection or Credit
reporting, and that is a boundary a model told only the category names cannot see — exactly the mechanism the
record argued for Credit card (R4), applied to a category we did not think to check.

### 1.3 The direction of the errors (Section 3)

| Claim in the record | Measured (`confusion_matrix.csv`) | Verdict |
|---|---|---|
| Credit card → mostly **Bank account**, secondly **Credit reporting** | `qwen2.5:7b` 5 → Bank account, 3 → Credit reporting; `llama3.2:3b` 15 → Bank account, 4 → Credit reporting; `granite4:3b` reversed (4 → Credit reporting, 2 → Bank account) | Right for two of the three larger models |
| Bank account → mostly **Money transfer**, secondly **Credit reporting** | `qwen2.5:7b` 4 → Money transfer, 2 → Credit reporting; `granite4:3b` 3 → Credit reporting, 3 → Credit card, 1 → Money transfer; `llama3.2:3b` no Money transfer errors | Right for `qwen2.5:7b` only |
| Money transfer → **Bank account** | 6 (`qwen2.5:7b`), 9 (`granite4:3b`), 16 (`llama3.2:3b`) of 19 | **Right**, for every model that ever answers Bank account |
| Debt collection → **Credit reporting** | 5 (`qwen2.5:7b`), 14 (`granite4:3b`), 5 (`llama3.2:3b`), 21 (1B) | **Right**, every model |
| **Easiest: Mortgage**, then Credit reporting | Mortgage recall 70% (`qwen2.5:7b`), 63%, 11%, 0% — mid-table or worst for every model; Credit reporting is the easiest for three of four (88%, 90%, 100%) | **Wrong** about Mortgage; right about Credit reporting |
| Credit reporting has the **highest false-positive count** for every model | Highest for `granite4:3b` (34) and the 1B (127); `qwen2.5:7b` has more false Bank account (16) than Credit reporting (14); `llama3.2:3b` 58 false Bank account vs 20 | **Wrong** (two of four) |
| `UNPARSEABLE` counts: 0–1, 0–3, 0–3 and 1–5 (1B) | **0 for every model** | Right for the three larger models; wrong for the 1B (no credit, not blind) |

**Why we were wrong about Mortgage.** We expected Mortgage's distinctive vocabulary to make it easy. It is
the boundary, not the vocabulary, that decides: protocol revision **R1** puts escrow, loss mitigation, payment
disputes and unauthorised changes *at a mortgage servicer* under Mortgage, and those narratives talk about
payments, accounts and loans. `qwen2.5:7b` sends 4 of its 8 Mortgage misses to Bank account and 3 to Consumer
loan; `granite4:3b` sends 5 to Credit card. Six of our 68 labeller disagreements had been about exactly this
boundary — the evidence was in our own resolutions, and we did not read it as a warning about Mortgage.

### 1.4 The accuracy requirements

| Requirement prediction | Measured | Verdict |
|---|---|---|
| R3 (≥ 90% overall): **no candidate meets it**; the best reaches about 70% | Best is `qwen2.5:7b` at 74.0% | **Right** |
| R4 (every category ≥ 80%): **no candidate meets it** | Lowest category recall per model: 0%, 0%, 35%, 57% | **Right** |
| …Mortgage clears 80% for `qwen2.5:7b`, `granite4:3b` and `llama3.2:3b` | 70%, 63%, 11% | **Wrong** (see 1.3) |
| …Credit card and Bank account fail R4 for every model | Credit card fails for all four (63%, 78%, 22%, 7%); Bank account **passes** for three (83%, 83%, 90%) | Half right: Bank account is better than we thought |

---

## 2. Latency, throughput and the bottleneck (Section 1 and Section 2 of the record)

Sources: `../analysis/output/load/load_per_run.csv` (three runs per configuration), the per-run
`../analysis/output/bottleneck/<run>/` breakdowns, `../analysis/output/stress/<run>/`, and the service log lines
in each run directory. All on the service host `omarchy` (Ryzen 9 5900X), 8–9 October 2026.

### 2.1 Single-request latency and R1

| Model | Warm p50 at 1/min: predicted → measured (mean of 3 runs) | p95 at 1/min: predicted → worst run | Verdict |
|---|---|---|---|
| `llama3.2:1b-instruct-q4_K_M` | 850 ms → **501 ms** | 1.8 s → **0.96 s** | p50 **wrong** (41% faster than predicted); p95 right (below the prediction) |
| `llama3.2:3b` | 2.0 s → **1.22 s** | 4.3 s → **2.32 s** | p50 **wrong** (39% faster); p95 right |
| `granite4:3b` | 2.2 s → **1.09 s** | 4.6 s → **2.40 s** | p50 **wrong** (50% faster); p95 right |
| `qwen2.5:7b` | 4.6 s → **2.26 s** | 10.5 s → **5.52 s** | p50 **wrong** (51% faster); p95 right |

Every warm p50 is more than 30% away from its prediction, so by the record's own rule all four latency rows are
wrong — in the same direction, by about half. **R1** (p95 ≤ 10 s at 1/min) was predicted to fail for
`qwen2.5:7b`; it **passes for all four** (worst run 5.52 s). **Prediction wrong.**

**Why.** We split each request into prefill (reading the prompt) and decode (writing the reply) and predicted
both rates from the hardware:

| Model | Prefill tokens/s: predicted → measured at 1/min | Decode tokens/s: predicted → measured at 1/min |
|---|---|---|
| `llama3.2:1b-instruct-q4_K_M` | 280 → **1,599** | 45 → **49.5** |
| `llama3.2:3b` | 115 → **387** | 19 → **16.5** |
| `granite4:3b` | 108 → **532** | 18 → **16.5** |
| `qwen2.5:7b` | 50 → **249** | 9 → **7.3** |

(Aggregate rates over the three 1/min runs, `bottleneck_tokens.csv`.) The decode predictions were right to within
about 20%: decode is bound by memory bandwidth, and we modelled that correctly. Prefill ran **3–6 times faster**
than we assumed. We scaled a guessed 50 tokens/s for a 7B model; llama.cpp's batched prompt evaluation on 12 Zen 3
cores with AVX2 does several times better. Prefill dominates every request, so the error carried straight into
every latency figure — and it was partly offset by two things we under-estimated, below.

### 2.2 The two things we missed inside a request

* **No prompt-prefix reuse.** We predicted Ollama would evaluate only the narrative plus ~15 tokens (median
  ≈ 200), reusing the cached ~115-token instruction prefix. Across the 2,040 load-test requests,
  `prompt_eval_count ≈ 121 + 0.21 × ticket characters` for every model (least-squares fit over the service
  log lines), and the evaluation *time* has the same fixed part (167 ms for the 1B up to 1,148 ms for
  `qwen2.5:7b` at 1/min): the whole prefix is re-evaluated on every request. Median `prompt_eval_count` at 1/min
  was 289–297, under the 300 threshold we wrote as the test, so **the test we set was too loose to catch a
  prediction that was wrong in substance**; we count it as wrong.
* **Our own overhead.** We predicted `service_overhead_ms` (the handler's time outside the model call) and the
  queue residual would each stay under 100 ms. The residual did (8–13 ms mean). The service overhead did
  **not**: a median of 172–197 ms per request for every model and rate — about 40% of the 1B model's latency.
  See 2.4 for where it goes.

### 2.3 Throughput and R2

At 12 tickets/min (R2's condition) every run of every model classified all 120 tickets (0% errors) and finished
within 603 s of the start (`span_s`, limit 660 s): **R2 passes for all four**. We predicted `qwen2.5:7b` would fail
it with a backlog (utilisation ≈ 1.04). With its measured model time of about 2.0–2.1 s per ticket (prefill plus decode), its utilisation at
12/min was about 0.4. **Prediction wrong**, for the reason in 2.1.

### 2.4 The bottleneck

| Claim in the record | Measured | Verdict |
|---|---|---|
| **B — Ollama's single parallel slot**: under load the time that grows is waiting for the slot, recorded in `ollama_other_ms`, not in `queue_residual_ms` | `qwen2.5:7b`: `ollama_other_ms` mean 10 → 488 → 858 ms at 1, 4 and 12/min while `queue_residual_ms` stays 10–13 ms; the same pattern for the 3B models (10 → 167–205 ms at 12/min) | **Right** about the component |
| …it accounts for ≥ 80% of the rise in mean latency, and per-request work stays within ±25% | `qwen2.5:7b` 1 → 12/min: mean total +681 ms, `ollama_other_ms` +848 ms (more than all of the rise, because decode time fell 27%); `prompt_eval_ms` +7% | **Right** |
| …mean `ollama_other_ms` passes 10 s at 12/min for `qwen2.5:7b` | 0.86 s — the service never got near saturation at 12/min | **Wrong** (magnitude; the location was right) |
| `prompt_eval_duration` exceeds `eval_duration` for every model's median request | Prefill 2.5–4× decode for every model | **Right** |
| JMeter `elapsed` minus the service's `total_latency_ms` below 100 ms at the median | Median per run 10.5–53 ms (median of runs 14 ms) | **Right** |
| `service_overhead_ms` below 100 ms | 172–197 ms median | **Wrong** (2.2) |

STRESS-PENDING

### 2.5 R5 — search under mixed load

`GET /search` p95, worst of three runs at 1 ticket + 1 search per minute: 17.2 ms (1B), 17.0 ms (`llama3.2:3b`),
16.5 ms (`granite4:3b`), 139.7 ms (`qwen2.5:7b`) (`load_per_run_by_label.csv`). **R5 passes for all four.** We
predicted every run's search p95 below 100 ms: **right for three models, wrong for `qwen2.5:7b`**, whose worst
run had one slow search — the store is near-empty, so that is CPU contention with a concurrent model call, not
the scan.
