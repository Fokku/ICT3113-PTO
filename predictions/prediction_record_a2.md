# Prediction record — Assignment 2 — Group 10

**What this is.** The prediction record required by Step 3 of the Assignment 2 brief
(`../docs/assignment-2-brief.md`): (1) which configuration is expected to be the fastest that satisfies both
accuracy limits, with reasons; (2) for the cascade, the expected escalation fraction, accuracy and median
latency **at each of the two settings**; (3) which categories are expected to lose the most accuracy when the
small model's answer is accepted. It is committed, with `../cascade/escalation_rule.md` and
`../golden/split_a2.csv`, in the commit tagged `a2-predictions-freeze` (`python ../scripts/a2_gate.py`). It is
not edited afterwards; a correction goes in a dated appendix in a new commit, the same convention as
Assignment 1's record and `../predictions/outcomes.md`.

**Conventions.** Paths are relative to this file. "Accuracy" means agreement with the frozen golden labels on
the **test-set** rows of `../golden/split_a2.csv` only, `UNPARSEABLE` counted as wrong (same rule as
Assignment 1, `../workload/requirements.md` R3). "Satisfies both accuracy limits" means against
`../docs/a2/accuracy_limits.md`. Latency and escalation-fraction figures are under the arrival rate derived
in `../docs/a2/arrival-rate.md`.

**Who wrote this, and how.** All five members wrote their own guesses first, then the team agreed the final entry for Sections 1 to 3 on 2026-11-25 by written confirmation in the team chat, with each member confirming individually. Toh Si Pei held the pen and used an AI assistant to suggest candidate figures, compare the five guesses and draft the team entry. The AI only proposed figures and wording. Toh Si Pei decided what to use and the team confirmed the final entry. Evidence available when the record was written: Assignment 1 results, the accuracy limits, the escalation rule, test-set scores for the four single models, and two Assignment 2 measurements taken before any benchmark run (S = 3.339 s for qwen2.5:7b, and a service overhead of about 0.55 s per request). No Assignment 2 speed or accuracy benchmark had been run.

---

## Section 1 — Fastest configuration expected to satisfy both accuracy limits

**The prediction.** qwen2.5:7b alone.

**Reasoning.** It is the only single model that passes both limits on the test set. It scores 75/101 against
an overall limit of 65/101 or more. granite4:3b (63/101), llama3.2:3b (54/101) and llama3.2:1b (34/101) all
fail the overall limit. Granite also fails Consumer loan, Debt collection and Money transfer. A cascade's mean
latency is roughly service overhead + small model time + escalation fraction x large model time. At the tuning
set escalation fractions (78/99 for Setting A and 59/99 for Setting B), the extra granite call costs more than
the escalations save, because more than half of tickets pay for both models. Expected qwen2.5:7b median
latency: 3.0 to 4.0 s.

**Would be wrong if:** a cascade setting passes both accuracy limits (overall and all seven categories), no run
is flagged as queued, and its three per-run p50 ranges lie entirely below qwen2.5:7b's.

## Section 2 — Cascade predictions, at each setting

| | Setting A | Setting B |
|---|---|---|
| Expected escalation fraction (test set, under load) | 72-85% | 52-65% |
| Expected overall accuracy (test set) | 70-79% | 69-76% |
| Expected median latency | 3.9-5.3 s | 3.3-4.9 s |
| Would be wrong if | The measured escalation fraction, accuracy or median latency falls outside its range, or the cascade's median is below qwen2.5:7b's | The measured escalation fraction, accuracy or median latency falls outside its range, or the cascade's median is below qwen2.5:7b's |

**Reasoning.** Escalation fractions start from the tuning set figures in `../cascade/escalation_rule.md`
section 3 (78/99 and 59/99), widened for sampling noise on 101 test tickets. Accuracy is centred on the tuning
set accuracies (75/99 and 74/99) and on qwen2.5:7b's 75/101. For median latency, more than 50% of tickets are
escalated at both settings, so the median ticket pays for both calls. That is about 0.6 s service overhead +
1.3 s granite + 2.7 s qwen, against about 3.3 s for qwen alone. Setting B escalates fewer tickets and queues
less, so its median should be somewhat lower than A's.

## Section 3 — Categories expected to lose the most accuracy when the small model's answer is accepted

**The prediction.** Under Setting B, ranked: 1. Mortgage, 2. Bank account or service, 3. Money transfer or
service.

**Why.** Setting B accepts granite's "Credit card" answers, which were only 57.9% right on the tuning set. Of
the 8 accepted but wrong answers, 3 were really Mortgage, 2 were Bank account and 1 was Money transfer. Test
set sizes are Mortgage 11, Bank account 16 and Money transfer 11. Bank account's limit is 13/16 or more, which
is granite's own score, so losing 3 tickets from qwen's 15/16 would fail it. Under Setting A, which does not
accept "Credit card", we expect little loss because all 21 accepted tuning answers were right.

**Rows we would call wrong:** a different ranking of lowest non-escalated accuracy by category in
`../analysis/output/accuracy_a2/`.

---

## Section 4 — Analysis thresholds, fixed before measurement

These lines decide whether a run is valid and whether a gap needs explaining. They are agreed here, before
any result exists, so nobody can move them after seeing the numbers. Defaults are proposed; the team confirms
or changes each one, then deletes the marker. `../scripts/a2_gate.py` blocks until every marker
is gone.

| Threshold | Proposed default | Why | Team decision |
|---|---|---|---|
| **No-queue check** (is a speed run valid?) | Second-half p50 no more than 20% above first-half p50, **and** median `ollama_other_ms` (queue wait, from `../analysis/bottleneck_hints.py`) under 100 ms | The brief's 2×S rate exists so "no queue builds". A slow cascade setting can still exceed 2S per ticket; then p50 tracks run length, not the configuration. 100 ms is Assignment 1's own queueing threshold (`prediction_record.md` §1.1) | Confirmed |
| **"Large gap"** between accuracy-test and speed-test escalation fractions | More than 15 percentage points | The two fractions come from different tickets (101 test-set vs the 100-ticket workload), so some gap is expected. The brief says "explain any large gap" but doesn't define "large" | Confirmed |
| **What "fastest" means** (decides the Step 5 recommendation) | Rank by the **mean of the three per-run p50s**. A is faster than B only if A's per-run p50 range (min–max) lies entirely below B's; overlapping ranges are "not distinguishable". Among indistinguishable qualifying configurations, pick the **higher test-set accuracy**, then the **simpler** one (single model over cascade). A configuration must be distinguishably faster than `qwen2.5:7b` alone, or the recommendation is `qwen2.5:7b`. A configuration with any run flagged as queued is not eligible for the recommendation until re-run validly. A cascade setting is only eligible if it passes both accuracy limits. | Matches what the brief has you report (Slide 5: "p50 per run with spread") and predict (Step 3: "median latency"), so predictions score directly. Pooled p95 has no spread, so it can't show a real difference. The client accepts lower accuracy only "provided it is faster": without a demonstrable speed gain the accuracy loss isn't justified | Confirmed |
| **Errored ticket in an accuracy test** (e.g. HTTP 502) | Counts as **wrong**, and the count is reported. Never retry a single ticket. Any error is investigated; if an infrastructure fault caused it, the **whole** run is invalid and re-run under the re-run policy (`../docs/playbooks/cascade-test.md` §6) | Excluding it changes the number of tickets scored and breaks the brief's "same tickets" comparison. Retrying contradicts "once per configuration". A serial, unloaded run shouldn't time out, so an error signals a fault. Counting it wrong matches A1's treatment of `UNPARSEABLE`: a deployed system would misroute it | Confirmed |

A speed run that fails the no-queue check is still reported, flagged as queued, not compared on p50.

---

## Sign-off

Each member's own figures, recorded before the team entry above was agreed, per `../README.md`'s rule that
this record cannot be supplied by one person or one tool alone.

| Member | Part | Date | Where their own prediction differed from the team entry |
|---|---|---|---|
| Yeo Kai Yuan | Part 1 | 2026-11-24 | Sections 1 and 3 same as the team entry. Ranges differed at the edges: Setting A escalation went up to 88% (team 85%), Setting B escalation started at 50% (team 52%), Setting B accuracy was 65-74% (team 69-76%), Setting A latency went up to 5.5 s (team 5.3 s). |
| Loh Wen Xuan | Part 2 | 2026-11-24 | Sections 1 and 3 same as the team entry. Ranges differed at the edges: Setting A escalation started at 70% (team 72%), Setting B escalation went up to 68% (team 65%), Setting B accuracy started at 66% (team 69%), Setting A latency started at 3.7 s (team 3.9 s). |
| Jolie Ngai Ning Li | Part 3 | 2026-11-23 | Section 1 same. Setting B accuracy went up to 80% (team 76%) and Setting B latency was 3.5-5.0 s (team 3.3-4.9 s). Other ranges slightly different at the edges. Section 3 listed only Mortgage and Bank account, with no Money transfer. |
| Toh Si Pei | Part 4 | 2026-11-23 | Sections 1 and 3 same as the team entry. Setting B latency was 4.0-5.3 s (team 3.3-4.9 s). Other ranges slightly different at the edges. My figures started from AI-supplied candidates. |
| Koh Tong Wei | Part 5 | 2026-11-23 | Section 1 same. Setting B accuracy went up to 78% (team 76%) and Setting B latency was 3.3-4.3 s (team 3.3-4.9 s). Section 3 ranked Money transfer second and Bank account third (team has Bank account second). Other ranges slightly different at the edges. |