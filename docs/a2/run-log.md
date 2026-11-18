# Run log — Assignment 2 (Team 10)

**Owner:** Part 5 — Koh Tong Wei. Same role, same rules as `../run-log.md` played for Assignment 1 — this is
a **separate file**, not an extension of that one, so an Assignment 1 entry is never mistaken for Assignment
2 evidence or vice versa.

**Status:** not started. No real Assignment 2 run may happen before `python ../../scripts/a2_gate.py` exits 0
— see `../../TODO_A2.md`, "Definition of done".

## Rules (same as Assignment 1's run log)

1. One dated entry per configuration (one model-or-cascade-setting × one test kind — accuracy or speed),
   written straight after its runs.
2. Never delete an entry. A discarded or aborted configuration keeps its entry, with the reason; the re-run
   gets a new entry.
3. Dev-mode runs go under *Rehearsals* and are never quoted as evidence.
4. Every figure is copied from `gate.json`, `metadata.json`, a service log, or `analysis/output/`. Square
   brackets mean **not yet filled or not yet confirmed**.
5. Times are UTC, with Singapore time (UTC+8) in brackets.
6. For a cascade entry, record the setting (A or B) and the escalation fraction from the service log
   alongside the usual latency figures.
7. Re-run only for a reason listed in `../playbooks/cascade-test.md` §6, and write the reason here **before**
   re-running. Never re-run because a result looks bad. The invalid run's entry stays, marked invalid.
8. Mark each run valid or invalid against the checklist in `../playbooks/cascade-test.md` §7.

## Environment

TODO(a2): confirm and state here whether the Assignment 1 environment (`../environment/`) is unchanged. If
unchanged, say so and point at `../environment/` rather than re-describing it (`../../TODO_A2.md` §5.1). If
changed, capture it again with `../../scripts/capture_env.sh` and describe the change and why.

## Gate

TODO(a2): once `python ../../scripts/a2_gate.py --json` exits 0, paste its output here verbatim (`gate_commit`,
`gate_tag`, the three blob shas) — this is the Assignment 2 equivalent of Assignment 1's freeze JSON pasted
into the team channel.

## Rehearsals (dev mode — not evidence)

TODO(a2): entries here as the A2 scripts are exercised in `--dev` mode, before the gate.

## Real runs (after the gate)

TODO(a2): one entry per configuration once benchmarking starts — accuracy runs first (brief: "Do the accuracy
test first"), then speed tests for every configuration that passes both accuracy limits plus the cascade in
all cases.
