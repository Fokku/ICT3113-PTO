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
