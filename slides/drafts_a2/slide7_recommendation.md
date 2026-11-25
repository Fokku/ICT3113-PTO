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

Recommendation: `<configuration>`, `<one line: why it wins or why qwen2.5:7b stays>`

## Left: predictions against outcomes

Verdict rule: inside the predicted range is right, outside is wrong. Section 1 and Section 3 use the
"would be wrong if" line in the frozen record.

| Prediction (frozen) | Measured | Verdict | Why it differed (a mechanism, not "we underestimated") |
|---|---|---|---|
| Fastest qualifying configuration: qwen2.5:7b alone | `<winner by the section 4 rule>` | | |
| qwen2.5:7b median latency 3.0 to 4.0 s | `<p50 mean and per-run range>` | | |
| Setting A escalation fraction 72-85% | `<n/101>` | | |
| Setting A overall accuracy 70-79% | `<n/101>` | | |
| Setting A median latency 3.9-5.3 s | `<p50>` | | |
| Setting B escalation fraction 52-65% | `<n/101>` | | |
| Setting B overall accuracy 69-76% | `<n/101>` | | |
| Setting B median latency 3.3-4.9 s | `<p50>` | | |
| Biggest accuracy losses under Setting B: Mortgage, Bank account, Money transfer | `<ranking by lowest non-escalated accuracy>` | | |

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

**Recommended configuration:** `<name>`.
**Speed gain against qwen2.5:7b alone:** `<seconds and %, with the per-run p50 ranges for both>`.
**Accuracy cost:** overall `<n/101 vs 75/101>`, and by category `<category: n/N vs qwen n/N>`.
**Defended against both limits:** overall `<n/101 vs the 65/101 minimum>`, every category against its minimum
count (from `docs/a2/accuracy_limits.md` section 2).

**If the cascade did not win (state it plainly):** measured escalation fraction under load `<f>` and on the
test set `<f>`, the two latency figures `<small-only>` and `<escalated>`, and the break-even check:
the cascade only beats qwen alone when `L(small) + f x L(large) < L(large)`.
**Settings that failed accuracy:** show their speed, marked "not passing accuracy".

## Traceability rows to add to `../outline_a2.md` (Part 5's map)

| Slide | Figure | Source file | Produced by |
|---|---|---|---|
| 7 | predictions | `predictions/prediction_record_a2.md` at tag `a2-predictions-freeze` | `git show a2-predictions-freeze:predictions/prediction_record_a2.md` |
| 7 | p50 per run, mean, escalation under load, `faster_than_reference` | `analysis/output/speed_a2/per_config.csv` | `python analysis/summarise_load_a2.py` |
| 7 | run validity (queued or valid) | `analysis/output/speed_a2/per_run.csv` | same |
| 7 | overall and per-category accuracy, pass or fail | `analysis/output/accuracy_a2/<file>` | Part 3's scoring script |
| 7 | escalated vs non-escalated accuracy | `analysis/output/accuracy_a2/<file>` | same |