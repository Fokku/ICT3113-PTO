# Cascade — order of work

**Owner:** Part 2 — Loh Wen Xuan (design and tuning), with Part 1 — Yeo Kai Yuan (the memory check and the
implementation in `../service/`).

**What lives here.** `escalation_rule.md` — the written rule required as a submission supporting file by the
brief's Deliverables section, and one of the three files `../scripts/a2_gate.py` checks before any
Assignment 2 benchmark may run.

**Read first:** `../docs/assignment-2-brief.md` Step 2 ("Design the Cascade"), and `../TODO_A2.md`'s
"Guardrails and shared interfaces" section — in particular guardrail 6 (the rule must never read the true
label at inference time) and guardrail 7 (tune on `../golden/split_a2.csv`'s `tuning` rows only, never the
`test` rows).

## Order of work

1. Wait for (or chase) Part 1's memory check (`TODO_A2.md` §1.1) — it decides which small+large model pair is
   even allowed, and the rule has to target a pair that actually fits in RAM at once. Don't design around a
   pair that doesn't survive `ollama ps`.
2. Pick one approach from the brief's four examples, or a documented alternative (`TODO_A2.md` §2.3).
3. Tune it on `../golden/split_a2.csv`'s `tuning` rows only, reusing the small model's existing
   `../results/accuracy/<model>_<timestamp>/responses.csv` from Assignment 1 — no new model calls needed for
   this step (`TODO_A2.md` §2.4).
4. Choose two settings that give visibly different escalation fractions on the tuning set.
5. Write `escalation_rule.md` from the template already in this folder, precisely enough that another team
   could implement it from the description alone.
6. Hand the settings to Part 1 so they can be wired into `../service/cascade.py` before the A2 gate.
7. Commit `escalation_rule.md` as part of the A2 gate (`TODO_A2.md` §W.1, "Definition of done").

## What this is not

This folder is the rule's *specification*. The implementation lives in `../service/cascade.py` (Part 1's
file); this folder does not contain runnable code.
