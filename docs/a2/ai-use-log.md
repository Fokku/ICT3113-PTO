# AI-use log — Assignment 2 (Team 10)

**What this is.** The running record of what AI tools produced for Assignment 2 and what the team did with
it. It is the source for Slide 8's AI declaration (brief, "Copyright, AI Use and Plagiarism": *"The AI
declaration should state what the tools produced and what the team did."*). **Every member appends an entry
as they work**; Part 5 — Koh Tong Wei collates it for Slide 8 (`../../TODO_A2.md` §5.3).

**Note.** `TODO_A2.md`'s scaffold table says this file already held a first entry (the scaffold itself). It
was not in the repository on 2026-11-19, so it was created then, with the Part 1 entry below. Whoever
generated the scaffold should add that entry.

**Rules.** One entry per piece of work. Say which tool, what it produced (files), what a human checked or
changed, and which decisions stayed with the team. The brief puts these with the team, never the tool:
the escalation rule, the running of the tests, and the recommendation. Newest entries at the bottom.

---

## 2026-11-19 — Part 1 (Yeo Kai Yuan): cascade implementation and A2 tooling

**Tool.** Claude Code (Anthropic, Claude Opus 5.5), run by Yeo Kai Yuan in this repository. It used three
parallel sub-agents for the speed-test runner, the speed analysis and the accuracy driver.

**What the tool produced** (`TODO_A2.md` §1.2–§1.4):

- `service/cascade.py`: the cascade implemented from the interface stub. It has two rule shapes, category
  accept-list (brief, example method 1) and ticket length (example method 4). `RULE_SETTINGS` is left
  **empty** for Setting A and Setting B, and a cascade service refuses to start until they are filled.
- `service/main.py`, `service/config.py`, `docker-compose.yml`, `.env.example`: cascade mode, selected
  by `SERVICE_MODE`, `CASCADE_SETTING` and `CASCADE_SMALL_MODEL_TAG`. The HTTP response shape is unchanged.
- `service/log_schema.py` (schema version 2, six appended fields), `service/request_log.py`, and
  `analysis/common.py`. The reader accepts both schema versions, so the Assignment 1 logs stay readable.
- `scripts/cascade_replay.py` + `tests/test_rule_fidelity.py`: the rule-fidelity check (code vs
  `cascade/escalation_rule.md` §3).
- `scripts/a2_env_snapshot.py`: record the environment once and diff it before every configuration.
  `scripts/memory_check_a2.py`: the memory check. `scripts/measure_s_a2.py`: S and the derived rate,
  run length, timeout and pause.
- `scripts/run_accuracy_a2.py`, `scripts/run_load_test_a2.sh`, `jmeter/speed_test_a2.jmx`: the A2
  accuracy driver and speed-test runner. `scripts/run_a2_campaign.sh` runs §1.5 in order once the gate
  passes.
- `slides/drafts_a2/`: drafts of Slides 2 and 5, and the cascade diagram generator.
- `analysis/summarise_load_a2.py`, plus cascade consistency checks in `analysis/reconcile.py`.
- Tests: `tests/test_cascade_routing.py`, `tests/test_a2_calibration.py`,
  `tests/test_run_accuracy_a2.py`, `analysis/tests/test_summarise_load_a2.py`,
  `analysis/tests/test_reconcile_cascade.py`, and updates to `tests/test_log_schema.py`. None of them
  calls a model.

**What was checked.**

- The full `pytest` suite passes.
- All 55 Assignment 1 runs still reconcile under the new log reader. Their regenerated reconcile outputs
  are byte-identical to the committed ones (495 files).
- The tool ran these live on the service host, after Yeo Kai Yuan granted Docker access:
  - the memory check (`docs/environment/a2-memory-check/20261119T073203Z/`);
  - the S measurement (`docs/a2/arrival_rate.json`, S = 3.339 s);
  - the environment baseline (`docs/a2/env_baseline.json`).
- In `--dev` mode only (synthetic tickets, not evidence, under the gitignored `results/dev/`) it also ran:
  - a speed-test rehearsal with a downloaded JMeter 5.6.3, co-hosted;
  - an accuracy-driver run;
  - an in-process cascade smoke test against the real models, with throwaway test rules.
- The first real speed run must still go from the load generator, after the gate.

**Left to the team, deliberately not done by the tool:**

- The escalation rule and its two settings (Part 2; whole team).
- The prediction record (whole team, W.1).
- Every real measurement.
- The recommendation.

The tool did not write anything into `cascade/escalation_rule.md`, `predictions/prediction_record_a2.md`
or `docs/a2/accuracy_limits.md`.

**What the team did with it:** _(Yeo Kai Yuan to complete after review, e.g. "reviewed and kept",
"changed X because Y")._

---

## 2026-11-18 to 2026-11-21 — Part 2 (Loh Wen Xuan): accuracy limits and escalation rule

**Tool.** Claude Code (Anthropic, Claude Opus 5.5), run by Loh Wen Xuan in this repository. No model was
called for any measurement, and no Assignment 1 file was edited.

**What the tool produced** (`TODO_A2.md` §2.2–§2.5), file by file:

| File | Numbers | Text |
|---|---|---|
| `docs/a2/accuracy_limits.md` | Computed by a short Python script over the saved Assignment 1 answers (overall and per-category limits). | Drafted by the tool: reuse-check table, borderline-category notes, how pass/fail is decided. |
| `cascade/escalation_rule.md` | Computed by script from the small model's tuning-row answers (escalation counts 78/99 and 59/99, wrong answers let through). | Drafted by the tool: model pair, the category-based rule, the two settings, the comparison with the other rule ideas, the speed caveat. |
| `tests/test_rule_fidelity.py` | None. | One test edited (Part 1's file): it now compares against a blank temporary document, because it failed once `escalation_rule.md` was filled in. |
| `slides/drafts_a2/slide2_cascade_design.md`, `slide4_accuracy_limits.md` | None. | Drafts only, for whoever builds the slides. The Slide 4 verdict table is left blank. |

The numbers can be reproduced without the tool: the command in `accuracy_limits.md` §4 for the limits, and
`scripts/cascade_replay.py` for the escalation counts.

**What was checked.**

- The one-line command in `accuracy_limits.md` §4 reproduces the limits.
- Part 1's `scripts/cascade_replay.py`, run with the two settings, reproduces 78/99 and 59/99. The
  rule-fidelity tests pass.
- The tuning analysis used only the 99 tuning rows from `golden/split_a2.csv`.
- `escalation_rule.md` was changed to match `service/cascade.py` where they disagreed (a failed small-model
  call fails the request instead of escalating).

**Left to the team, deliberately not done by the tool:**

- Approving Setting A and Setting B (W.1). One `TODO(cascade)` stays in `escalation_rule.md` §1 until then.
- The prediction record, every real measurement, and the recommendation.
- Pass/fail verdicts on Slide 4 (they need Part 3's scores).
- `golden/split_a2.csv`, which the tool did not generate or change.
