# Escalation rule — Group 10

**What this is.** The written escalation rule required by Step 2 of the brief and submitted as a supporting
file. It must be documented precisely enough that another team could implement it from the description
alone, and it is committed, together with `../predictions/prediction_record_a2.md` and
`../golden/split_a2.csv`, in the commit tagged `a2-predictions-freeze` (`python ../scripts/a2_gate.py`).
After the tag, this file is not edited; a correction goes in a dated appendix in a new commit.

**Owner:** Part 2 — Loh Wen Xuan (design and tuning), with the memory-check evidence from Part 1 — Yeo Kai
Yuan. Read `README.md` in this folder before filling this in.

**Status.** Part 2 drafted the approach, the model pair and the two settings on 2026-11-18, from Assignment 1
evidence only (no model calls). Under `../TODO_A2.md` guardrail 12 the final settings are a whole-team
decision. TODO(cascade): record the team's confirmation of Setting A and Setting B, with the date, at the
W.1 meeting, then delete this marker. If the team changes a setting, re-run the tuning figures in §3 and §4.

**Guardrail — read before writing section 2.** The rule below describes a decision function that runs
*inside the service, at inference time, on a ticket whose true category is unknown*. It may only use
something the small model itself produced for that ticket (its predicted category, its raw reply text, a
confidence word, the ticket's own length). It may never reference `../golden/golden_set.csv` or any golden
label — that file is used only *offline*, in section 4 below, to choose the rule's settings from the tuning
set.

---

## 1. The model pair

| | |
|---|---|
| Small model (classifies first) | `granite4:3b` (digest `sha256:89962fcc75239ac434cdebceb6b7e0669397f92eaef9c487774b718bc36a3e5f`, `../models/models.yaml`) |
| Large model (classifies on escalation) | `qwen2.5:7b` (digest `sha256:845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`, `../models/models.yaml`) |
| Memory check evidence | *(Part 1, 2026-11-19.)* **The chosen pair fits.** `ollama ps` lists both `granite4:3b` (2.5 GB) and `qwen2.5:7b` (5.1 GB) resident after alternating small/large calls, 100% CPU, `num_ctx` 4096, with 0 reloads after the first load. Raw output: `../docs/environment/a2-memory-check/20261119T073203Z/granite4-3b__qwen2.5-7b/ollama_ps.txt`. **Every candidate pair fits.** `llama3.2:1b-instruct-q4_K_M`, `llama3.2:3b` and `granite4:3b` each stay resident together with `qwen2.5:7b`: `ollama ps` lists both after alternating small/large calls, with no reload after the first load. Resident: 5.65 / 7.10 / 7.05 GiB. Evidence: `../docs/environment/a2-memory-check/20261119T073203Z/summary.md`, with each pair's raw `ollama ps` in its own sub-folder (`scripts/memory_check_a2.py`). The same check is repeated before every cascade speed run (`ollama_ps_before.txt` in each run folder). |
| RAM given to the Ollama container at the time of the check | *(Part 1.)* No limit, so the whole host: 31.3 GiB on `omarchy` (Ryzen 9 5900X). `docker-compose.yml` sets no `mem_limit`/`cpus`, unchanged from Assignment 1 (`docker inspect`: Memory 0, NanoCpus 0). `OLLAMA_NUM_PARALLEL=0` and `OLLAMA_MAX_LOADED_MODELS=0` (Ollama's defaults), recorded in `../docs/a2/env_baseline.json`. |

**Why this pair.** `qwen2.5:7b` is the large model because it is the reference model (top Assignment 1
accuracy), so the cascade's escalated tickets get the most accurate answer available. The small model has to
be one of the other three candidates. On the tuning set (§4), only `granite4:3b` predicts any category
reliably enough to accept:

- `llama3.2:1b-instruct-q4_K_M` answers "Credit reporting" for 85 of the 99 tuning tickets and is right on
  16 of them. It has no category worth accepting, so its cascade would escalate almost everything.
- `llama3.2:3b` is right on 43/99 overall. Its most-used predictions are right less than half the time
  (Bank account or service 21/51, Credit reporting 10/21, Debt collection 4/14). We tried all 128
  accept-sets. Every one that keeps tuning accuracy at `qwen2.5:7b` alone's 73/99 escalates at least 94/99,
  so it would be a slower `qwen2.5:7b`.

Memory does not decide the pair: Part 1's check shows all three small models fit alongside `qwen2.5:7b`.
Tuning-set accuracy alone decides it.

## 2. The rule

**Approach:** category-based (the brief's Example method 1).

**The signal.** The small model's predicted category for the ticket: `granite4:3b`'s reply to the unchanged
classification prompt (`../service/prompt.py`, `PROMPT_HASH` `sha256:681131c48bdc15a1`), passed through the
service's existing normaliser `service.categories.normalise_category()`. The result is exactly one of the
seven canonical names in `service.categories.CATEGORIES`, or `"UNPARSEABLE"`. In `../service/cascade.py`
this is `SmallModelAnswer.predicted_category`. Nothing else is read: not the raw text, not the ticket's
length, and never a golden label.

**The accept/escalate condition.** For the active setting `s ∈ {"A", "B"}`:

```
ACCEPT["A"] = {"Mortgage", "Consumer loan", "Debt collection"}
ACCEPT["B"] = {"Mortgage", "Consumer loan", "Debt collection", "Credit card"}

escalate = answer.predicted_category not in ACCEPT[s]
```

That is the whole rule. Consequences an implementer needs:

1. **Exact string match** against the canonical names above (case and spelling as in `CATEGORIES`). The
   normaliser has already produced canonical names, so no further cleaning happens here.
2. **`"UNPARSEABLE"` is never in an accept-set**, so an unparseable small-model reply is always escalated.
3. **If the small-model call fails** (an Ollama error or timeout, so there is no reply to normalise), the
   request fails. It is **not** escalated: there is no retry and no fallback to the large model. The log
   records `escalated = false`, `small_model_category = null` and the error in the existing `error` field.
   This is how `../service/cascade.py` behaves. The rule only decides between two answers, and a failed call
   has no answer to decide on. In an accuracy run such a ticket counts as wrong and is investigated as an
   infrastructure fault (`../predictions/prediction_record_a2.md` §4). Contrast an `"UNPARSEABLE"` reply in
   point 2: the model did answer, so that ticket is escalated.
4. **When not escalated**, the small model's category is the final answer. `model_tag` / `model_digest` /
   `predicted_category` in the log are `granite4:3b`'s.
5. **When escalated**, `qwen2.5:7b` is called **once** with the same unchanged prompt, and its normalised
   category is final, even if it is `"UNPARSEABLE"`. There is no third call, no retry, and no fallback to the
   small model's answer. `model_tag` / `model_digest` / `predicted_category` are `qwen2.5:7b`'s.
6. The setting is chosen by service configuration, never by the caller. The response body stays
   `{"id", "category", "request_id"}` (§5).

Read as a sentence: *accept the small model's answer only when it says Mortgage, Consumer loan or Debt
collection (Setting A), or one of those or Credit card (Setting B); send every other ticket to `qwen2.5:7b`.*

**Why this approach, over the brief's other examples.** We chose category-based because it adds no model
call. Every ticket pays one `granite4:3b` call, and only escalated tickets pay a second. It is also the
approach whose tuning we can do entirely from Assignment 1's per-ticket predictions, with no new calls before
the gate. We scored the alternatives on the same 99 tuning tickets:

- **Agreement** (`granite4:3b` vs `llama3.2:3b`, escalate when they disagree) escalates 59/99, the **same
  fraction as Setting B**, and gets 76/99 right against Setting B's 74/99. That is a two-ticket difference on
  99 tickets, within noise. To get it, it adds a `llama3.2:3b` call to **every** ticket, and that model is
  the same size class as `granite4:3b` (3.21 B vs 3.4 B parameters). At an equal escalation fraction, it
  roughly doubles the cost every ticket pays, with no measurable accuracy gain. It also needs three models
  resident at once, which the memory check does not cover. The brief says "two small calls may cost as much
  as one large call; measure it". We did not run a speed test for it, since speed tests come after the gate.
  It loses on cost even if the extra call were free of queueing, because its escalation fraction is no
  lower. Agreement with `llama3.2:1b-instruct-q4_K_M` instead is worse on both counts: 68/99 escalated and
  67/99 right.
- **Ticket length** does not predict `granite4:3b`'s errors in our data. On the tuning set the median
  narrative is 774 characters for its wrong answers and 720 for its right ones. At the 70th-percentile
  cut-off (918 characters), short tickets are right 50/70 (71%) and long tickets 19/29 (66%). Escalating
  long tickets catches only 10 of granite's 30 errors at 29/99 escalated, and lands at 70/99 overall, below
  `qwen2.5:7b` alone (73/99). The brief says this method is "only useful if length actually predicts
  errors". Here it does not.
- **Self-reported confidence** needs either a change to the classification prompt (forbidden) or a second,
  separate confidence call on every ticket, whose time counts. That cost is the same as agreement's. It also
  has no Assignment 1 data to tune from, so we would have to make new model calls on the tuning set before
  the gate, and the brief warns small models are "often confident and wrong". We rejected it without
  building it.

**Extra model calls, if any.** None. The rule reads only the small model's existing classification. The
cascade makes at most the two calls every cascade makes: `granite4:3b` always, and `qwen2.5:7b` on
escalation. Both calls' times fall inside the request's measured latency, because both happen inside the one
`POST /tickets` request that JMeter times.

## 3. The two settings

Chosen from the tuning set only (`../golden/split_a2.csv`, `set == "tuning"`), so the test set is never
looked at before it is scored.

| | Setting A | Setting B |
|---|---|---|
| Parameter value(s) | `ACCEPT = {"Mortgage", "Consumer loan", "Debt collection"}` | `ACCEPT = {"Mortgage", "Consumer loan", "Debt collection", "Credit card"}` |
| Escalation fraction on the tuning set | **78/99** (78.8%), 21 accepted | **59/99** (59.6%), 40 accepted |
| Accuracy on the tuning set (for reference only — not a reported result) | **75/99** (75.8%). Accepted: 21/21 right. Escalated: 54/78 right | **74/99** (74.7%). Accepted: 32/40 right. Escalated: 42/59 right |
| Wrong small-model answers that slip through (accepted but wrong) | **0** of `granite4:3b`'s 30 errors | **8** of 30 (all 8 are tickets granite called "Credit card") |
| Passes both limits on the tuning set? (`qwen2.5:7b` tuning figures, same −10 / −15 pp rules) | Yes, all seven categories | Yes, but Mortgage and Money transfer are each **one ticket** from failing (§4) |

For reference, on the same 99 tuning tickets: `qwen2.5:7b` alone 73/99, `granite4:3b` alone 69/99.

**How each setting was chosen.** Both come from a stated criterion, not from picking whichever number looked
best:

- **Setting A, the "reliable categories" setting.** Accept only the predicted categories `granite4:3b` got
  right **every** time on the tuning set: Mortgage 12/12, Consumer loan 5/5, Debt collection 4/4. This is
  the brief's Example method 1 taken literally.
- **Setting B, the "lowest escalation that still passes" setting.** We tried every possible accept-set
  (2⁷ = 128) on the tuning set. Setting B is the one with the lowest escalation fraction that still passes
  both limits, measured against `qwen2.5:7b`'s tuning-set figures. One condition applies: an accepted
  category must have at least 5 tuning-set predictions behind it. Without that condition the lowest is
  56/99, which also accepts Money transfer or service. That choice would rest on granite predicting Money
  transfer just 3 times (2 right), too few to call the category reliable.

The escalation fractions differ by 19 tickets (19.2 pp), so the two settings show a real trade-off: Setting
A has no slips but escalates almost four tickets in five, and Setting B escalates 19 fewer at the cost of 8
slips.

The tuning-set escalation fractions above are also a check on the implementation: replaying the same
tuning-set small-model answers through `../service/cascade.py`'s `should_escalate()` must give exactly these
figures (`../TODO_A2.md` §1.2, rule-fidelity check). Write them as counts (e.g. `31/99`), not just
percentages, so the comparison is exact.

**Rule-fidelity inputs for Part 1.** Feed `granite4:3b`'s `predicted_category` from
`../results/accuracy/granite4-3b_20261008T122430Z/responses.csv`, for the 99 `tuning` rows only, through
`should_escalate()`. Expect **78** escalations at Setting A and **59** at Setting B. Granite's predicted
categories on those 99 rows are: Credit reporting 30, Bank account or service 26, Credit card 19, Mortgage
12, Consumer loan 5, Debt collection 4, Money transfer or service 3, `UNPARSEABLE` 0. So Setting A escalates
30 + 26 + 19 + 3 = 78, and Setting B escalates 30 + 26 + 3 = 59.

## 4. Tuning evidence

**Files used.** `granite4:3b`'s and `qwen2.5:7b`'s Assignment 1 per-ticket predictions,
`../results/accuracy/granite4-3b_20261008T122430Z/responses.csv` and
`../results/accuracy/qwen2.5-7b_20261008T123045Z/responses.csv` (`llama3.2:3b` and
`llama3.2:1b-instruct-q4_K_M`'s files for the pair choice in §1). All of them were filtered to the 99 rows
with `set == "tuning"` in `../golden/split_a2.csv` **before** any scoring, and scored against
`../golden/golden_set.csv`. No test-set row was used to choose anything in this document. No model was
called.

**`granite4:3b`'s precision by predicted category on the tuning set.** "When granite says X, how often is X
right?" is what the category-based rule depends on:

| Granite predicted | Tickets | Granite right | Precision | `qwen2.5:7b` right on the same tickets | In Setting A? | In Setting B? |
|---|---|---|---|---|---|---|
| Mortgage | 12 | 12 | 100% | 12 | Yes | Yes |
| Consumer loan | 5 | 5 | 100% | 4 | Yes | Yes |
| Debt collection | 4 | 4 | 100% | 3 | Yes | Yes |
| Bank account or service | 26 | 20 | 76.9% | 19 | No | No |
| Money transfer or service | 3 | 2 | 66.7% | 2 | No | No (n < 5) |
| Credit card | 19 | 11 | 57.9% | 12 | No | Yes |
| Credit reporting | 30 | 15 | 50.0% | 21 | No | No |

**Per-category accuracy on the tuning set** (by true category, correct/N):

| True category | N | `qwen2.5:7b` alone | Setting A | Setting B | `granite4:3b` alone |
|---|---|---|---|---|---|
| Credit reporting | 16 | 15 | 15 | 15 | 15 |
| Debt collection | 10 | 7 | 8 | 8 | 4 |
| Mortgage | 16 | 15 | 15 | **13** (−12.5 pp) | 12 |
| Credit card | 16 | 8 | 8 | 12 | 11 |
| Bank account or service | 24 | 18 | 18 | 16 (−8.3 pp) | 20 |
| Consumer loan | 9 | 5 | 6 | 6 | 5 |
| Money transfer or service | 8 | 5 | 5 | **4** (−12.5 pp) | 2 |
| **Total** | **99** | **73** | **75** | **74** | **69** |

**Accept-sets we considered and did not pick**, to show where the trade-off breaks (all on the tuning set):

| Accept-set | Escalated | Right | Slips | Fails a tuning-set limit? |
|---|---|---|---|---|
| Setting A: {Mortgage, Consumer loan, Debt collection} | 78/99 | 75/99 | 0 | No |
| Setting B: A + Credit card | 59/99 | 74/99 | 8 | No |
| A + Bank account or service | 52/99 | 76/99 | 6 | **Yes**: Money transfer 3/8 vs `qwen2.5:7b` 5/8 (−25 pp) |
| A + Bank account + Money transfer + Credit card | 30/99 | 75/99 | 15 | **Yes**: Money transfer 2/8 (−37.5 pp) |
| All seven (= `granite4:3b` alone) | 0/99 | 69/99 | 30 | **Yes**: Debt collection, Mortgage, Money transfer |

Any accept-set that includes "Bank account or service" fails Money transfer on the tuning set.
`granite4:3b` files Money transfer tickets under Bank account (4 of the 6 Bank-account slips), and in an
8-ticket category each one costs 12.5 points. That is why neither setting accepts Bank account, even though
its precision (76.9%) is higher than Credit card's.

**How often a wrong small-model answer slips through, on the tuning set.** `granite4:3b` is wrong on 30 of
the 99 tuning tickets.

- **Setting A: 0 of the 30 slip through.** All 30 are escalated. The 21 accepted tickets are all right.
- **Setting B: 8 of the 30 slip through**, all predicted "Credit card". Their true categories: Mortgage 3,
  Bank account or service 2, Consumer loan 1, Credit reporting 1, Money transfer or service 1. The other 22
  errors are escalated. `qwen2.5:7b` would have got 5 of those 8 slipped tickets right, so accepting Credit
  card costs about 5 right answers. Granite's 11 correct Credit-card answers, where `qwen2.5:7b` is weaker,
  win most of them back. The net is one ticket fewer right than Setting A (74 vs 75), for 19 fewer
  escalations.

**What this means for the predictions (Part 4, `../predictions/prediction_record_a2.md` §2–3).** These
inputs are drafted for the team. The team makes the predictions.

- *Which categories lose the most when the small model's answer is accepted:* under Setting B, the slips
  land in **Mortgage** (3) and **Bank account or service** (2), so those are the most likely to lose
  accuracy. **Money transfer or service** is the most fragile in percentage terms because it is small.
  Under Setting A the tuning set shows no loss from accepted answers in any category.
- *Speed:* the brief's formula gives mean cascade latency ≈ L(granite) + f × L(qwen), where f is the
  escalation fraction. A setting beats `qwen2.5:7b` alone only if L(granite) < (1 − f) × L(qwen). At the
  tuning-set fractions that means granite would need to take under **0.21 × L(qwen)** for Setting A, and
  under **0.40 × L(qwen)** for Setting B. Granite's weights are about 0.45× qwen's by size (2.10 GB vs
  4.68 GB), and on CPU, time per token tends to grow with weight size. By that reasoning **both settings may
  well be no faster than `qwen2.5:7b` alone**, Setting A especially. This is a size-based argument, not a
  measurement: Assignment 1 speed figures may not be reused (`../TODO_A2.md` guardrail 10), and only the A2
  speed tests can settle it. The brief accepts this outcome ("it is acceptable to conclude that the cascade
  did not improve on it"). It is also why we did not trade per-category accuracy for a lower escalation
  fraction to chase a speed win: every accept-set below 59/99 already fails a tuning-set limit.

**Reproducing §3–4.** Load `../golden/split_a2.csv` and keep the 99 `tuning` row numbers. Load the two
`responses.csv` files above and keep those rows, treating an empty `predicted_category` as `UNPARSEABLE`.
For each setting: `escalated = granite_pred ∉ ACCEPT`, then `final = qwen_pred if escalated else
granite_pred`. Score `final` against `../golden/golden_set.csv`'s `label`. The counts above follow directly.

## 5. What the caller sees, and what the log records

Unchanged response shape: `POST /tickets` still returns `{"id", "category", "request_id"}` regardless of
which model answered or whether escalation occurred. The service log records, per request (see
`../service/log_schema.py`): `model_tag` / `model_digest` / `predicted_category` for whichever model actually
produced the final answer, plus the new fields `escalated`, `cascade_setting` (`"A"` or `"B"`),
`small_model_tag` and `small_model_category` (what the small model said, independent of what was returned).
