# Prediction record — Group 10

**What this is.** The prediction record required by Step 4 of the brief: (1) where we expect the bottleneck
to be under load and why, (2) for each candidate model the expected golden-set accuracy and expected
single-request latency on our hardware, and (3) which categories we expect to be hardest and why. It is
committed, with `../golden/golden_set.csv`, in the commit tagged `golden-freeze`, and that tagged version is
the prediction of record. It is not edited afterwards; a correction would go in a dated appendix in a new
commit. Slide 11 compares every entry below with the measurements.

**Conventions.** Paths are relative to this file. Field names are the service log keys in
`../service/log_schema.py`, the `.jtl` columns read by `../analysis/common.py`, and the components computed
by `../analysis/bottleneck_hints.py`. "Accuracy" means agreement with the frozen golden labels, scored by
`../analysis/accuracy.py`, with `UNPARSEABLE` counted as wrong (requirement R3 in
`../workload/requirements.md`). Arrival rates and load conditions are the ones fixed in
`../workload/workload_model.md` ("Derived arrival rates for testing").

---

## 0. How this record came to be written late — read before Slide 11

We state this here because the commit history shows it anyway, and an unexplained gap would be worse.

1. **The first `golden-freeze` tag froze an empty template.** The tag was first created on 8 October 2026 at
   12:28 SGT on commit `ef5a1b2`. The golden set in that commit is the golden set in this one (built on
   2 October, unchanged since). The prediction record in that commit was still the unfilled template: no
   prediction had been written. `scripts/freeze_gate.py` passed because it checks that the file is committed,
   not that it says anything.
2. **One measurement happened before any prediction.** At 13:25 SGT the same day, one golden-set accuracy run
   of `llama3.2:1b` was made on the original service host (`tw`). Because it predates every prediction, it is
   not evidence. It has been moved to `../results/excluded/` with an explanation, nothing in it is reported,
   and the test is repeated after this commit on the new environment.
3. **The test environment changed.** The original machines (`tw` and `kthgoat`) became unavailable on
   8 October. Every measurement is now made with the service and Ollama on a separate desktop
   (`omarchy`: AMD Ryzen 9 5900X, 12 cores / 24 threads, 31.3 GiB RAM, Arch Linux, Docker Engine 29.7.2,
   Ollama 0.34.3 — captured in `../docs/environment/omarchy-Ollama.txt`), and JMeter on
   an Apple M3 Pro MacBook. **Every latency prediction below is for that service host.**
4. **Who wrote this, and what they had seen.** This record was drafted on 8 October by Yeo Kai Yuan with an
   AI coding assistant (the brief permits AI tools), from: the hardware facts in `../docs/environment/`,
   the model facts in `../models/candidates.md`, Ollama's documented behaviour, our prompt
   (`../service/prompt.py`), the ticket-length statistics in `../workload/output/`, and the labelling
   evidence in `../labelling/`. No measurement of any model on the new service host existed when it was
   written. One exception must be stated plainly: before drafting, the drafter had seen the
   **predicted-category counts** of the excluded `llama3.2:1b` run (Credit reporting 100, Bank account or
   service 85, Consumer loan 10, `UNPARSEABLE` 3, Mortgage 1, Credit card 1, out of 200), though not its
   accuracy score, and that run's start and end times (about 17 minutes for 200 tickets on `tw`, a
   different machine). **The 1B model's accuracy, hardest-category and `UNPARSEABLE` entries are
   therefore not blind, and we claim no credit for them.** Knowing that the 1B model leans on the first
   listed category may also have coloured the error-direction prediction for `llama3.2:3b` (same family);
   we flag that entry too. While fixing the test harness, the drafter also saw rehearsal timings for
   `llama3.2:1b` on synthetic tickets on the load-generator MacBook (Apple M3 Pro, Ollama inside Docker
   Desktop's VM) — a different machine and CPU architecture from the service host, and never team rows. No
   model had run on the service host when this record was written. Every other entry — the bottleneck,
   the latency figures for the service host, and the accuracy rows for `llama3.2:3b`, `granite4:3b` and
   `qwen2.5:7b` — is blind to our own measurements. After the first draft of this record was committed
   (the 1B accuracy entry of 38% included), the drafter read a teammate's run-log entry
   giving the excluded run's score, 35.0%. The draft commit is the evidence that the 38% came first; the
   entry is still marked not blind.
5. **The template's own rule was broken.** The template said no tool and no single member should supply the
   predictions. Under the deadline, one member drafted with an AI assistant and circulated the draft to the
   other four before the freeze. Their responses are in the sign-off table exactly as given, including
   anyone who did not respond in time.
6. **The tag was moved, deliberately and once.** After this file was committed, `golden-freeze` was moved
   to this commit with `git tag -f` — the re-cut procedure documented in `../scripts/freeze_gate.py` — and the
   move is logged in `../docs/run-log.md`. Every run directory carries the freeze it ran under in its
   `freeze.json`.
7. **The 1B build changed before the freeze.** The earlier draft named the default `llama3.2:1b` build
   (Q8_0). The service host had already pulled and pinned `llama3.2:1b-instruct-q4_K_M` on 2 October, and that
   matched-quantisation decision (`../models/candidates.md`, decision 2) stands: the 1B candidate measured is
   the Q4_K_M build. The excluded run in item 2 was the Q8_0 build on a different machine, so it is not even
   the same weights; the 1B accuracy entries stay marked not blind all the same.
8. **The hardware-dependent entries were completed last, and blind.** The service-time, latency, stress and
   R1/R2 entries (left as hardware placeholders in the circulated draft) were filled in on the evening of 8 October by the same
   drafter and assistant, from three things only: the capture file named in item 3, published
   characteristics of llama.cpp CPU inference on AVX2 desktop processors, and the ticket-length statistics in
   `../workload/output/ticket_length_stats.md`. No model had answered a request on the service host since
   three synthetic smoke-test requests on 2 October, whose timings were not looked at.

---

## Section 1 — Where we expect the bottleneck to be under load

### 1.1 The prediction

**Component: B — Ollama's request admission for the loaded model, i.e. its single parallel slot.** Under
load, the time that grows is time spent waiting for that slot, not time spent computing.

**Mechanism.** `OLLAMA_NUM_PARALLEL` is left unset, and Ollama's documented default is **1** parallel request
per loaded model (`OLLAMA_MAX_QUEUE` default 512). The runner takes a semaphore of that size before it
starts work on a request. Our service imposes no limit of its own: each `POST /tickets` is an async handler
that opens a fresh `httpx` connection to Ollama and awaits it, so every ticket that arrives while another
is being classified is admitted by the service and then waits inside Ollama. Each request holds the slot
for its own **CPU-bound prompt evaluation (prefill)** plus a few decoded tokens. A median prompt is about
330 tokens (≈ 112 tokens of fixed instructions plus a median narrative of 186 approximate tokens, plus the
chat template), while the reply is a category name of 2–6 tokens. So the per-request **service time S** is
dominated by `prompt_eval_duration`, and the queue forms when the arrival rate exceeds 1/S.

**Where in our workload it starts to bind.** The modelled peak (0.024 tickets/minute) never binds anything.
Among the rates we test (1, 4 and 12 per minute, and the stress ramp 1 → 21 per minute), we expect:

| Model | Predicted service time S at the median ticket | Predicted mean S (mean ticket) | Predicted saturation rate ≈ 60 / mean S | First tested rate at which the queue grows without bound |
|---|---|---|---|---|
| `llama3.2:1b-instruct-q4_K_M` | 0.85 s | 0.96 s | ≈ 62 / min | none — not even the steeper ramp's 60/min top step |
| `llama3.2:3b` | 2.0 s | 2.3 s | ≈ 26 / min | 30/min (step 3 of the steeper ramp) |
| `granite4:3b` | 2.2 s | 2.45 s | ≈ 24 / min | 30/min (step 3 of the steeper ramp) |
| `qwen2.5:7b` | 4.6 s | 5.2 s | ≈ 11.5 / min | **12/min — the load test's top rate** (and the ramp's 13/min step) |

**The stress limit we predict for each model** (limit = the first step whose p95 exceeds R1's 10 s or whose
error rate exceeds 5%, as `../docs/playbooks/stress-test.md` defines it; the steeper 10–60/min ramp is run only
when the 1–21/min ramp finds nothing, as that playbook decided in advance):

| Model | 1–21/min ramp | Steeper 10–60/min ramp | First HTTP 502 (`ollama_timeout`) |
|---|---|---|---|
| `llama3.2:1b-instruct-q4_K_M` | no limit (p95 at 21/min ≈ 2 s) | no limit (p95 at 60/min below 10 s) | none in either ramp |
| `llama3.2:3b` | no limit (p95 at 21/min ≈ 8 s) | limit at **30/min** | 40/min step or later |
| `granite4:3b` | limit at **21/min** (p95 ≈ 11 s) — the one 3B-class difference we predict | (run only if the first ramp finds nothing) | none in the 1–21/min ramp |
| `qwen2.5:7b` | limit at **9/min** (p95 > 10 s, queueing on top of a ~5 s service time) | not run | 21/min step or the drain after it |

**Where the wait will show up in our own analysis — a deliberate, checkable claim.** Ollama starts its
`total_duration` clock *before* a request waits for the slot, and only `load_duration`, `prompt_eval_duration`
and `eval_duration` are broken out. So we predict the queueing time will appear in
`analysis/bottleneck_hints.py`'s **`ollama_other_ms`** component (`total_duration` minus load, prompt-eval and
eval), **not** in its `queue_residual_ms` component (`model_latency_ms − total_duration/1e6`), where that
script's own docstring expects to find it.

**Observation that would confirm it** (for any configuration whose arrival rate is above that model's
saturation rate, and most clearly for `qwen2.5:7b` at 12/min and the upper steps of the stress ramp):

* mean `ollama_other_ms` rises from under 100 ms at 1/min to more than 10 s, and accounts for at least 80% of
  the increase in mean `total_latency_ms` over the 1/min runs of the same model;
* the work per request does not change: the median of `(prompt_eval_duration + eval_duration)/1e6` stays
  within ±25% of the same model's 1/min median;
* `queue_residual_ms` and `service_overhead_ms` (`total_latency_ms − model_latency_ms`) each stay below
  100 ms at the median, at every rate;
* JMeter `elapsed` minus the service's `total_latency_ms` (joined on `request_id` by
  `analysis/reconcile.py`) stays below 100 ms at the median — the time is spent inside the service host, not
  on the network or in the load generator;
* `prompt_eval_duration` exceeds `eval_duration` for the median request of every model, so prefill rather
  than decoding sets S. (`bottleneck_hints.py` says decoding "is usually the largest term" on CPU; for this
  workload we predict the opposite.)

**Observation that would refute it:**

* the per-request work grows with load — median `prompt_eval_duration` at 12/min more than 50% above its
  1/min median for the same model. That would mean requests are being evaluated concurrently and competing
  for cores (Ollama chose more than one parallel slot, or the service host is contended), which is
  mechanism A (CPU saturation) rather than a queue in front of one slot; or
* the growing wait appears in `queue_residual_ms` or `service_overhead_ms` instead of `ollama_other_ms`
  (the wait is outside Ollama: in the service's thread pool, its event loop, or connection set-up); or
* `qwen2.5:7b` holds a flat p95 through 12/min and through the stress ramp's 21/min step — S is much smaller
  than we think, and our CPU throughput assumptions (Section 2) are wrong.

**Runner-up: A — the CPU-bound evaluation itself.** With one slot, A and B are two faces of one constraint:
A sets the capacity (60/S per minute) and B is where the backlog accumulates. We rank B first because B is
where the latency growth that the requirements measure will be recorded. If Ollama turns out to run
several requests at once, the same overload would show up as A instead: per-request `prompt_eval_duration`
stretching with concurrency.

**Does it move between models or plans?**

* **Between models:** no. The same component binds for all four; only the rate at which it binds changes,
  in proportion to S (table above).
* **`mixed_load` (1 ticket/min + 1 search/min):** nothing saturates. `GET /search` never calls the model, and
  the store holds at most about 10–15 tickets, so the `LIKE` scan (component E) is not a bottleneck: we
  predict `/search` p95 below 100 ms for every model, and no upward trend in `/search` `total_latency_ms`
  across the run.
* **`stress_ramp`, above saturation:** once a request's wait for the slot passes `OLLAMA_TIMEOUT_S` = 120 s,
  the service returns HTTP 502 with `error` = `ollama_timeout`. JMeter's own response timeout (180 s) is
  longer, so the first errors are the service's 502s, not load-generator timeouts. The service's thread pool
  (40) and Ollama's queue limit (512) are never the binding limits, because the 120 s timeout fires first.

---

## Section 2 — Per-candidate-model predictions

**How the latency figures were derived** (so that a wrong figure can be traced to a wrong assumption).
Single request, warm (model resident, `load_duration` under 50 ms), measured as the service's
`total_latency_ms` and as JMeter `elapsed`. Latency ≈ prompt tokens ÷ prefill rate + reply tokens ÷ decode
rate + about 30 ms of HTTP, JSON and SQLite. We assume a median prompt of ~330 tokens (p95 ~560), a reply of
~5 tokens, and these CPU rates on the service host — prefill bound by compute, decode by memory bandwidth.

**Prefix reuse — a checkable claim of its own.** The instructions (~115 tokens) come before the narrative and
are identical in every request, and Ollama keeps the previous request's KV cache in its one slot, so we predict
it evaluates only the part after the common prefix: about the narrative plus ~15 tokens (median ≈ 200,
p95 ≈ 465), not the whole prompt. We would be wrong if the median `prompt_eval_count` in the service log is
above 300 for any model at 1/min. Every latency below is computed on the ~200 / ~465 evaluated tokens. Decode
rates assume ~38 GB/s of effective dual-channel DDR4 bandwidth divided by the weights' size; prefill rates scale
a ~50 tokens/s figure for a 7B-class Q4_K_M model on 12 Zen 3 cores by non-embedding parameter count:

| Model | Weights (quantisation, size) | Assumed prefill rate (tokens/s) | Assumed decode rate (tokens/s) |
|---|---|---|---|
| `llama3.2:1b-instruct-q4_K_M` | 1.24B, Q4_K_M, 808 MB | 280 | 45 |
| `llama3.2:3b` | 3.21B, Q4_K_M, 2.0 GB | 115 | 19 |
| `granite4:3b` | 3.4B, Q4_K_M, 2.1 GB | 108 | 18 |
| `qwen2.5:7b` | 7.62B, Q4_K_M, 4.7 GB | 50 | 9 |

The measured rates are `prompt_eval_count / prompt_eval_duration` and `eval_count / eval_duration`, which
`analysis/bottleneck_hints.py` reports per run.

| Model (exact Ollama tag) | Expected overall accuracy (%) | Expected hardest category | Expected single-request latency (p50, ms, warm) | Expected p95 at the lowest tested rate, 1/min (R1's condition) | Confidence | Reasoning |
|---|---|---|---|---|---|---|
| `llama3.2:1b-instruct-q4_K_M` | **38** (accept 33–43) — **not blind, see §0** | Debt collection and Money transfer or service, both near 0% — **not blind** | **850** | **1,800** | latency: med; accuracy: n/a (not blind) | Smallest model; with only category names in the prompt it falls back on the two broadest categories. At Q4_K_M, like the other three, it is about 2.4× faster than `llama3.2:3b`, a little less than the 2.9× parameter ratio because small matrices use the cores less efficiently. |
| `llama3.2:3b` | **55** (accept 49–61) | Money transfer or service | **2,000** | **4,300** | accuracy: low; latency: med | Follows the one-line instruction reliably, but with no definitions it over-uses Credit reporting (listed first, mentioned in many complaints) and Bank account or service; the last-listed category, Money transfer or service, is under-predicted. The error direction may be coloured by §0, item 4. |
| `granite4:3b` | **60** (accept 54–66) | Credit card | **2,200** | **4,600** | accuracy: low; latency: med | Same size class as `llama3.2:3b` but newer and tuned for instruction following, so slightly fewer broad-category fall-backs. Its hardest category is decided by our protocol, not the model: rule R4 puts prepaid and gift cards and PayPal Credit under Credit card, which no model told only the category names will guess. |
| `qwen2.5:7b` | **70** (accept 64–76) | Credit card | **4,600** | **10,500** | accuracy: med; latency: med | More than twice the parameters of the 3B class, so the clear-cut tickets (Mortgage, Debt collection, credit-file disputes) are nearly all right. What remains are the boundaries our protocol drew (R4, R6, R2) that are not visible from category names. About 2.3× the 3B models' latency, because prefill cost scales with parameter count. |

**Rows we would call wrong:** any measured overall accuracy outside its accepted band; a different hardest
category (lowest per-category accuracy in `analysis/output/accuracy/`); a measured warm p50 more than 30%
away from the predicted figure; a measured p95 at 1/min above the predicted figure.

**Requirement-level predictions** (against `../workload/requirements.md`):

| Requirement | Prediction | Would be wrong if |
|---|---|---|
| R1 — `POST /tickets` p95 ≤ 10 s at 1/min | **Met by the three smaller models, failed by `qwen2.5:7b`.** Worst-run p95 at 1/min: 1.8 s, 4.3 s and 4.6 s for `llama3.2:1b-instruct-q4_K_M`, `llama3.2:3b` and `granite4:3b`; about 10.5 s for `qwen2.5:7b`, whose longest tickets alone take ~10 s to evaluate. | any of the three smaller models misses it, or `qwen2.5:7b` meets it in all three runs |
| R2 — ≤ 5% errors and no backlog at 12/min | **Met by the three smaller models (utilisation ≈ 0.2, 0.46 and 0.49), failed by `qwen2.5:7b`** (utilisation ≈ 1.04): its queue grows for the whole run, p95 passes 30 s, and at least one of its three runs finishes later than 660 s. Its error rate still stays under 5%, because no wait reaches the 120 s timeout within 600 s of arrivals. | any of the three smaller models fails it, `qwen2.5:7b` meets it, or `qwen2.5:7b` fails it on errors rather than backlog |
| R3 — overall accuracy ≥ 90% | **No candidate meets it.** The best, `qwen2.5:7b`, reaches about 70%. Our own two labellers agreed with each other on only 66% of tickets before resolution (κ = 0.599), and a model given no category definitions cannot learn the boundaries our protocol drew. | any candidate reaches 90% |
| R4 — every category ≥ 80% | **No candidate meets it.** Mortgage clears 80% for `qwen2.5:7b`, `granite4:3b` and `llama3.2:3b`; Credit card and Bank account or service fail for every model. | any candidate has all seven categories at 80% or more |
| R5 — `GET /search` p95 ≤ 2 s under `mixed_load` | **Every candidate meets it**, with `/search` p95 below 100 ms in every run. | any run's `/search` p95 is above 2 s, or above 100 ms |

---

## Section 3 — Which categories we expect to be hardest, and why

Canonical order (the confusion-matrix axis, from `../service/categories.py`): 1 Credit reporting, 2 Debt
collection, 3 Mortgage, 4 Credit card, 5 Bank account or service, 6 Consumer loan, 7 Money transfer or
service. Golden-set counts: 41, 23, 27, 27, 40, 23, 19.

**Hardest first, with the direction of the error.** Per-category accuracy here is recall: the share of tickets
with that golden label that the model labels correctly.

1. **Credit card** — tickets whose true label is Credit card will most often be predicted as **Bank account or
   service** (prepaid and gift cards, which R4 assigns to Credit card), and secondly as **Credit reporting**
   (card complaints about late-payment reporting, which the resolutions kept under Credit card in all
   5 Credit card ↔ Credit reporting disagreements). Mechanism: an *overlap in definitions* that our protocol
   resolved in a way the category name does not reveal.
2. **Bank account or service** — true Bank account tickets will most often be predicted as **Money transfer or
   service**. R6 puts account freezes, closures and unauthorised transactions on a deposit account under
   Bank account, and 11 of the 13 Bank account ↔ Money transfer disagreements between our labellers were
   resolved to Bank account. A model sees "Zelle", "transfer" or "wire" and answers Money transfer.
   Second direction: → **Credit reporting** (12 Bank account ↔ Credit reporting disagreements, 10 resolved to
   Credit reporting under R3, so the boundary is genuinely blurred).
3. **Money transfer or service** — the smallest class (19). Its true tickets will be predicted as **Bank
   account or service** when the narrative is about the customer's bank rather than the transfer. Lower
   per-category accuracy than the larger classes partly because every miss costs 5 percentage points.
4. **Debt collection** — true Debt collection predicted as **Credit reporting** when the collector's conduct
   includes reporting the debt (R2 / E7 put those under Debt collection; a model sees "credit report").

**Easiest:** Mortgage (distinctive vocabulary: mortgage, escrow, servicer, foreclosure, loan modification),
then Credit reporting. **Credit reporting will have the highest *false-positive* count of any category for
every model** — more tickets predicted as Credit reporting than the 41 that are — because so many complaints
of every product mention a credit report or credit score.

**Where `UNPARSEABLE` will land.** Most replies will be a single category name. The normaliser maps a reply
that contains two category names to `UNPARSEABLE` (rule 6), so the few unparseable replies will come from
tickets on the **Credit reporting ↔ Debt collection** boundary, where a model hedges with both names.
Predicted counts out of 200: `qwen2.5:7b` 0–1, `granite4:3b` 0–3, `llama3.2:3b` 0–3, `llama3.2:1b-instruct-q4_K_M` 1–5 (not
blind). A count above 5 for any 3B-or-larger model would make this entry wrong.

**Tie to the labelling evidence.** The three hardest categories for models are the three with the lowest
human one-vs-rest agreement in `../labelling/agreement_report.txt`: Bank account or service κ = 0.448, Credit
reporting 0.523, Credit card 0.542 (Credit reporting is hard for humans in the *other* direction — it is
where disagreements were resolved *to*). The protocol revisions that resolved them — R3 (16 disagreements),
R2 (7), R4 (6), R6 (3) — are exactly the boundaries a model cannot see, because the prompt
(`../service/prompt.py`) lists the category names and nothing else. Worked examples on Slide 6 come from
`../labelling/resolutions.md`.

**Against the per-category requirement (R4, ≥ 80% each).** We expect Credit card and Bank account or service
to fail R4 for every model, and Money transfer or service to fail it for every model except possibly
`qwen2.5:7b`. Cost to the client: at the modelled ~1,496 tickets a year, Credit card and Bank account
together are about 34% of tickets (67 of 200 in the golden set). Misrouting a third of those sends roughly
170 tickets a year to the wrong team, each needing a second hand-off.

---

## Sign-off

Each member's response to the circulated draft, recorded as given. The last column is where a member's own
prediction differed from the team entry.

| Member | Part | Date | Response to the draft, and where they would have predicted differently |
|---|---|---|---|
| Yeo Kai Yuan | Part 1 — service, instrumentation, benchmark harness | 2026-10-08 | Drafted the record (with an AI assistant, see §0). |
| Loh Wen Xuan | Part 2 — labelling protocol, labeller A | — | Draft circulated 8 October 2026; **no response received before the freeze**. |
| Jolie Ngai Ning Li | Part 3 — labeller B, accuracy results | — | Draft circulated 8 October 2026; **no response received before the freeze**. |
| Toh Si Pei | Part 4 — workload model and requirements | — | Draft circulated 8 October 2026; **no response received before the freeze**. |
| Koh Tong Wei | Part 5 — test environment, playbooks, references | — | Draft circulated 8 October 2026; **no response received before the freeze**. |
