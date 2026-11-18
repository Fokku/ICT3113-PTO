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

**Who wrote this, and how.** TODO(a2): name the drafter(s), whether an AI assistant was used (permitted under
the brief), and what evidence existed when it was written (reused Assignment 1 data only, or anything else).
Follow `../README.md`'s existing rule: **no tool, no agent and no single member may supply this record alone**
— draft individually first, then agree it together in the meeting (`../TODO_A2.md` §W.1).

---

## Section 1 — Fastest configuration expected to satisfy both accuracy limits

**The prediction.** TODO(a2): name the configuration (a specific single model, or the cascade at a specific
setting) and why, referencing the accuracy limits in `../docs/a2/accuracy_limits.md` and the Assignment 1
latency figures for the single models.

**Reasoning.** TODO(a2): one paragraph, citing the mean-latency formula from the brief
(`small-model latency + escalation fraction × large-model latency`) if the prediction is the cascade.

**Would be wrong if:** TODO(a2) — state the observation that would refute it.

## Section 2 — Cascade predictions, at each setting

| | Setting A | Setting B |
|---|---|---|
| Expected escalation fraction (test set, under load) | TODO(a2) | TODO(a2) |
| Expected overall accuracy (test set) | TODO(a2) | TODO(a2) |
| Expected median latency | TODO(a2) | TODO(a2) |
| Would be wrong if | TODO(a2) | TODO(a2) |

**Reasoning.** TODO(a2): derive these from `../cascade/escalation_rule.md` §3's tuning-set figures and the
Assignment 1 per-model latency figures (`../predictions/outcomes.md` §2.1), adjusted for the escalation
fraction using the brief's formula.

## Section 3 — Categories expected to lose the most accuracy when the small model's answer is accepted

**The prediction.** TODO(a2): name the categories, ranked, and why — tie to the small model's known Assignment
1 confusions (`../predictions/outcomes.md` §1.2–1.3) and to which categories the escalation rule is least
likely to catch.

**Rows we would call wrong:** TODO(a2) — a different ranking of lowest non-escalated accuracy by category, as
measured in `../analysis/output/accuracy_a2/`.

---

## Section 4 — Analysis thresholds, fixed before measurement

These lines decide whether a run is valid and whether a gap needs explaining. They are agreed here, before
any result exists, so nobody can move them after seeing the numbers. Defaults are proposed; the team confirms
or changes each one, then deletes the `TODO(a2)` marker. `../scripts/a2_gate.py` blocks until every marker
is gone.

| Threshold | Proposed default | Why | Team decision |
|---|---|---|---|
| **No-queue check** (is a speed run valid?) | Second-half p50 within ±20% of first-half p50, **and** median `ollama_other_ms` (queue wait, from `../analysis/bottleneck_hints.py`) under 100 ms | The brief's 2×S rate exists so "no queue builds". A slow cascade setting can still exceed 2S per ticket; then p50 tracks run length, not the configuration. 100 ms is Assignment 1's own queueing threshold (`prediction_record.md` §1.1) | TODO(a2): confirm or change |
| **"Large gap"** between accuracy-test and speed-test escalation fractions | More than 15 percentage points | The two fractions come from different tickets (101 test-set vs the 100-ticket workload), so some gap is expected. The brief says "explain any large gap" but doesn't define "large" | TODO(a2): confirm or change |
| **What "fastest" means** (decides the Step 5 recommendation) | Rank by the **mean of the three per-run p50s**. A is faster than B only if A's per-run p50 range (min–max) lies entirely below B's; overlapping ranges are "not distinguishable". Among indistinguishable qualifying configurations, pick the **higher test-set accuracy**, then the **simpler** one (single model over cascade). A configuration must be distinguishably faster than `qwen2.5:7b` alone, or the recommendation is `qwen2.5:7b`. | Matches what the brief has you report (Slide 5: "p50 per run with spread") and predict (Step 3: "median latency"), so predictions score directly. Pooled p95 has no spread, so it can't show a real difference. The client accepts lower accuracy only "provided it is faster": without a demonstrable speed gain the accuracy loss isn't justified | TODO(a2): confirm or change |
| **Errored ticket in an accuracy test** (e.g. HTTP 502) | Counts as **wrong**, and the count is reported. Never retry a single ticket. Any error is investigated; if an infrastructure fault caused it, the **whole** run is invalid and re-run under the re-run policy (`../docs/playbooks/cascade-test.md` §6) | Excluding it changes the number of tickets scored and breaks the brief's "same tickets" comparison. Retrying contradicts "once per configuration". A serial, unloaded run shouldn't time out, so an error signals a fault. Counting it wrong matches A1's treatment of `UNPARSEABLE`: a deployed system would misroute it | TODO(a2): confirm or change |

A speed run that fails the no-queue check is still reported, flagged as queued, not compared on p50.

---

## Sign-off

Each member's own figures, recorded before the team entry above was agreed, per `../README.md`'s rule that
this record cannot be supplied by one person or one tool alone.

| Member | Part | Date | Where their own prediction differed from the team entry |
|---|---|---|---|
| Yeo Kai Yuan | Part 1 | TODO(a2) | TODO(a2) |
| Loh Wen Xuan | Part 2 | TODO(a2) | TODO(a2) |
| Jolie Ngai Ning Li | Part 3 | TODO(a2) | TODO(a2) |
| Toh Si Pei | Part 4 | TODO(a2) | TODO(a2) |
| Koh Tong Wei | Part 5 | TODO(a2) | TODO(a2) |
