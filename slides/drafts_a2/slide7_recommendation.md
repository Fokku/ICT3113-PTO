# Slide 7 - Predictions, recommendation, defence (draft)

**Brief (verbatim):** "Predictions vs outcomes and why they differed. Recommended configuration, speed gain,
accuracy cost. If the cascade lost, why."
**Owner:** Toh Si Pei (Part 4). Part 5 owns layout and assembly.
**Done when** (`../outline_a2.md`): the recommendation follows visibly from Slides 4 to 6, not from anything
typed from memory.

Every outcome figure comes from `analysis/output/accuracy_a2/` and `analysis/output/speed_a2/`. Predictions are
quoted from the frozen record: `git show a2-predictions-freeze:predictions/prediction_record_a2.md`.
No Assignment 1 speed figure is used (TODO_A2.md, guardrail 10).

---

## Title

Recommendation (DRAFT, team to confirm): `qwen2.5:7b` alone. Neither cascade setting was faster

## Left: predictions against outcomes

Verdict rule: inside the predicted range is right, outside is wrong. Section 1 and Section 3 use the
"would be wrong if" line in the frozen record.

| Prediction (frozen) | Measured | Verdict | Why it differed (a mechanism, not "we underestimated") |
|---|---|---|---|
| Fastest qualifying configuration: qwen2.5:7b alone | `qwen2.5:7b` alone: no cascade setting is distinguishably faster (A slower; B's p50s inside qwen's spread) | Right | |
| qwen2.5:7b median latency 3.0 to 4.0 s | 4.50 s (frozen rule, run 3); per-run 6.12 / 6.54 / 4.50 s | Wrong (above) | *Evidence:* median queue wait up to 2.3 s, Ollama busy 0.52–0.54 (`speed_a2/per_run.csv`); appendix §A.2 |
| Setting A escalation fraction 72-85% | 83/101 (82.2%) test set; 99/132 (75.0%) under load | Right | |
| Setting A overall accuracy 70-79% | 76/101 (75.25%) | Right | |
| Setting A median latency 3.9-5.3 s | 7.63 s (frozen rule, run 2); per-run 9.61 / 7.63 / 9.25 s | Wrong (above) | *Evidence:* escalated tickets' p50 9.23 s vs accepted 2.29 s; Ollama busy 0.92–1.02 |
| Setting B escalation fraction 52-65% | 65/101 (64.4%) test set; 69/132 (52.3%) under load | Right (both inside, at opposite edges) | |
| Setting B overall accuracy 69-76% | 74/101 (73.27%) | Right | |
| Setting B median latency 3.3-4.9 s | 5.57 s (frozen rule, run 2); per-run 5.50 / 5.57 / 5.03 s | Wrong (above) | *Evidence:* escalated p50 9.01 s vs accepted 3.35 s; busy 0.75–0.85 |
| Biggest accuracy losses under Setting B: Mortgage, Bank account, Money transfer | vs `qwen2.5:7b` alone, by category: Consumer loan −2 (6/14 vs 8/14), Bank account −1 (14/16 vs 15/16); Mortgage +1, Credit card +1, Money transfer 0. Accepted-but-wrong by true category: Consumer loan 5, Mortgage 4, Credit reporting 3, Bank account 1 | Wrong (Consumer loan lost most; Money transfer lost nothing) | *Evidence:* `cascade_per_category_a2.csv`, `cascade_routing_a2.csv` |

Section 2's "would be wrong if … the cascade's median is below qwen2.5:7b's": not triggered under the frozen
rule (B 5.57 s vs qwen 4.50 s). Taking every run regardless of the queue flag, B's mean p50 (5.37 s) is slightly
below qwen's (5.72 s), but the ranges overlap (5.03–5.57 inside 4.50–6.54), so it is not a measured difference.
The *Evidence* notes are pointers to the measured mechanism, filled by Part 1. The "why" wording is Part 4's.

Mark any prediction as wrong plainly. Where the team's own guesses differed (sign-off table), that
disagreement can be mentioned in one line.

## Right: the recommendation

**Rule applied (frozen in the record, section 4), in order:**
1. Keep only configurations that pass the overall limit (65/101 or more) and all seven category limits.
2. Drop any configuration with a run flagged as queued or invalid.
3. Rank by the mean of the three per-run p50s. A is faster than B only if A's per-run p50 range lies entirely
   below B's. Overlapping ranges are "not distinguishable".
4. Among indistinguishable ones, take the higher test-set accuracy, then the simpler configuration.
5. A configuration must be distinguishably faster than qwen2.5:7b alone, or the recommendation is qwen2.5:7b.

> **DRAFT by the AI coding tool (2026-11-26), at Yeo Kai Yuan's instruction: the team confirms or changes
> it at the W.2 meeting.** It applies the rule above, mechanically, to the measured figures. The brief makes the
> recommendation the team's responsibility.

**Applying the rule.**
1. All three speed-tested configurations pass both limits: `qwen2.5:7b` 75/101, cascade A 76/101, cascade B
   74/101, every category at or above its minimum (`pass_fail_a2.csv`, `cascade_pass_fail_a2.csv`).
2. Under the frozen §4 no-queue check every configuration has queued runs (`qwen2.5:7b` 2 of 3, A 2 of 3, B 2 of
   3), so strictly none has three valid runs. Why that happened at the brief's own rate is in
   `predictions/prediction_record_a2_appendix.md`.
3–5. On the counted runs, A (7.63 s) and B (5.57 s) are both slower than `qwen2.5:7b` (4.50 s). On the labelled
   secondary reading (halves test only), A is slower (7.63–9.61 vs 4.50–6.12 s) and B is not distinguishable (5.57
   s, inside the range). Neither is distinguishably faster, so rule 5 gives `qwen2.5:7b`. The tie-break (higher
   accuracy, then simpler) also favours it over B: 75 vs 74/101, one model vs two.

**Recommended configuration:** `qwen2.5:7b` alone (the reference).
**Speed gain against qwen2.5:7b alone:** none. It is the reference, and no cascade setting beat it. Cascade A is
3.1 s slower on the counted runs (7.63 vs 4.50 s). Cascade B is 1.1 s slower on the counted runs and
indistinguishable on all runs (per-run 5.03–5.57 vs 4.50–6.54 s).
**Accuracy cost:** none. 75/101 (74.26%), the figure the limits are drawn from.
**Defended against both limits:** overall 75/101 vs the 65/101 minimum. By category (correct vs minimum): Credit
reporting 21 vs 18, Debt collection 10 vs 9, Mortgage 4 vs 3, Credit card 9 vs 8, Bank account 15 vs 13, Consumer
loan 8 vs 6, Money transfer 8 vs 7 (`docs/a2/accuracy_limits.md` §2).

**Why the cascade did not win (stated plainly).** Escalation under load was 75.0% (A) and 52.3% (B), against
82.2% and 64.4% on the test set. On the counted runs, tickets granite answered alone came back with p50 2.29 s (A) and 3.35 s
(B). Escalated tickets took 9.23 s and 9.01 s, because they pay for both models and the wait behind other tickets. The
break-even `L(small) + f × L(large) < L(large)` fails: at these escalation fractions most tickets pay for both
calls. With the arrival rate fixed, Ollama was busy 0.92–1.02 of the time for cascade A and 0.75–0.85 for B,
against 0.52–0.54 for `qwen2.5:7b` alone (`speed_a2/per_run.csv`, `ollama_busy_fraction`). So the cascade costs
more CPU per ticket than the large model alone, which is the outcome `cascade/escalation_rule.md` §4 anticipated
from model size. Cascade B, which escalates least, comes closest, and is still not faster.
**Settings that failed accuracy:** none. Both cascade settings pass both limits, so no "not passing accuracy"
label is needed.

## Traceability rows to add to `../outline_a2.md` (Part 5's map)

| Slide | Figure | Source file | Produced by |
|---|---|---|---|
| 7 | predictions | `predictions/prediction_record_a2.md` at tag `a2-predictions-freeze` | `git show a2-predictions-freeze:predictions/prediction_record_a2.md` |
| 7 | p50 per run, mean, escalation under load, `faster_than_reference` | `analysis/output/speed_a2/per_config.csv` | `python analysis/summarise_load_a2.py` |
| 7 | run validity (queued or valid) | `analysis/output/speed_a2/per_run.csv` | same |
| 7 | overall and per-category accuracy, pass or fail | `analysis/output/accuracy_a2/pass_fail_a2.csv`, `per_category_a2.csv`, `cascade_pass_fail_a2.csv`, `cascade_per_category_a2.csv` | `python -m analysis.accuracy_a2`; `python -m analysis.cascade_accuracy_a2` |
| 7 | escalated vs non-escalated accuracy | `analysis/output/accuracy_a2/cascade_routing_a2.csv` | `python -m analysis.cascade_accuracy_a2` |
| 7 | accepted vs escalated latency, Ollama busy fraction | `analysis/output/speed_a2/per_run.csv`, `per_config.csv` | `python analysis/summarise_load_a2.py --accuracy-verdicts analysis/output/accuracy_a2/verdicts_a2.csv` |
| 7 | the queue-flag explanation | `predictions/prediction_record_a2_appendix.md` | written 2026-11-26 |