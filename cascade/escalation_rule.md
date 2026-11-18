# Escalation rule — Group 10

**What this is.** The written escalation rule required by Step 2 of the brief and submitted as a supporting
file. It must be documented precisely enough that another team could implement it from the description
alone, and it is committed, together with `../predictions/prediction_record_a2.md` and
`../golden/split_a2.csv`, in the commit tagged `a2-predictions-freeze` (`python ../scripts/a2_gate.py`).
After the tag, this file is not edited; a correction goes in a dated appendix in a new commit.

**Owner:** Part 2 — Loh Wen Xuan (design and tuning), with the memory-check evidence from Part 1 — Yeo Kai
Yuan. Read `README.md` in this folder before filling this in.

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
| Small model (classifies first) | TODO(cascade): exact Ollama tag, from `../models/models.yaml` |
| Large model (classifies on escalation) | TODO(cascade): exact Ollama tag, from `../models/models.yaml` |
| Memory check evidence | TODO(cascade): reference the `ollama ps` output / log confirming both tags stay resident together, and where it is kept (e.g. `../docs/environment/`) |
| RAM given to the Ollama container at the time of the check | TODO(cascade): from `../docker-compose.yml`, unchanged from Assignment 1 |

## 2. The rule

**Approach:** TODO(cascade) — one of: category-based / agreement / self-reported confidence / ticket length /
other (named and justified).

**The signal.** TODO(cascade): state exactly what is computed from the small model's own output for a given
ticket — e.g. "the small model's predicted category" or "the small model's predicted category and a
HIGH/LOW confidence word from a second prompt" or "the character length of the ticket narrative."

**The accept/escalate condition.** TODO(cascade): state it as a literal boolean expression over the signal
above, not prose — e.g. `escalate = predicted_category NOT IN {reliable_categories}` or
`escalate = confidence == "LOW"` or `escalate = len(narrative) > length_cutoff`.

**Why this approach, over the brief's other examples.** TODO(cascade): one paragraph. In particular, if the
"agreement" method was considered and rejected, say what its second model call would have cost (brief:
"two small calls may cost as much as one large call; measure it").

**Extra model calls, if any.** TODO(cascade): state whether the rule needs a call beyond the two the cascade
already makes (e.g. a confidence prompt). If yes, that call's latency is counted in every reported cascade
latency figure — say where in the implementation this is accounted for.

## 3. The two settings

Chosen from the tuning set only (`../golden/split_a2.csv`, `set == "tuning"`), so the test set is never
looked at before it is scored.

| | Setting A | Setting B |
|---|---|---|
| Parameter value(s) | TODO(cascade) | TODO(cascade) |
| Escalation fraction on the tuning set | TODO(cascade) | TODO(cascade) |
| Accuracy on the tuning set (for reference only — not a reported result) | TODO(cascade) | TODO(cascade) |

The tuning-set escalation fractions above are also a check on the implementation: replaying the same
tuning-set small-model answers through `../service/cascade.py`'s `should_escalate()` must give exactly these
figures (`../TODO_A2.md` §1.2, rule-fidelity check). Write them as counts (e.g. `31/99`), not just
percentages, so the comparison is exact.

## 4. Tuning evidence

TODO(cascade): how the settings above were chosen — which existing `../results/accuracy/<model>_*/responses.csv`
files were used, filtered to which tuning-set rows, and what the "reliable category" list (or equivalent)
came out to at each setting.

**How often a wrong small-model answer slips through, on the tuning set.** TODO(cascade): the brief's own
check for the category-based method ("check how often a wrong answer slips through because the small model
predicted a safe category") — report the count even if a different method was chosen, since it bears on
section 3's expected accuracy at each setting.

## 5. What the caller sees, and what the log records

Unchanged response shape: `POST /tickets` still returns `{"id", "category", "request_id"}` regardless of
which model answered or whether escalation occurred. The service log records, per request (see
`../service/log_schema.py`): `model_tag` / `model_digest` / `predicted_category` for whichever model actually
produced the final answer, plus the new fields `escalated`, `cascade_setting` (`"A"` or `"B"`),
`small_model_tag` and `small_model_category` (what the small model said, independent of what was returned).
