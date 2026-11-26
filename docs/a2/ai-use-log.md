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

---

## 2026-11-25 — Part 3 (Jolie Ngai Ning Li): single-model test-set scoring

**Tool.** Claude Code (Anthropic, Claude Opus 5.5), run by Jolie Ngai Ning Li in this repository. No model was called for any
measurement, and no Assignment 1 file was edited.

**What the tool produced** (`TODO_A2.md` §3.1, §3.2 and §3.4, single models only):

- `analysis/accuracy_a2.py`: scores the four saved Assignment 1 runs on the 101 test rows only.
- `analysis/output/accuracy_a2/`: `model_comparison_a2.csv`, `pass_fail_a2.csv`,
  `per_category_a2.csv`, `sources.csv`, `report.md`, and one confusion matrix per model.
- `TODO_A2.md` §3.1: ticked the single-model scoring task, and ticked the reuse-validity task by pointing to
  Part 2's completed table in `docs/a2/accuracy_limits.md`. §3.2 (pass/fail) and §3.4 (confusion matrices)
  stay unticked. Each has a "partly done, single models only" note, because the cascade is not scored yet.
  Every other task stays unticked.

The numbers can be reproduced without the tool: `python -m analysis.accuracy_a2`.

**What was checked.**

- The four pinned A1 response files cover the frozen golden rows exactly once. Scoring uses only
  the 101 test rows from `golden/split_a2.csv`; tuning rows are excluded.
- Overall scores reproduce 63/101 (Granite), 34/101 (Llama 1B), 54/101 (Llama 3B), and 75/101 (Qwen).
- Pass/fail uses exact fractions: reference accuracy minus 10 percentage points overall and 15 per
  category. Only Qwen passes the overall limit and all seven category limits.
- Output coverage, category totals, confusion-matrix totals and the documented category minimum
  counts were independently checked. Removing the duplicate files left the scores unchanged.
- Every output cell was recomputed by a separate script that shares no code with `accuracy_a2.py`: each
  confusion-matrix cell, per-category count, macro recall and precision, and each `sources.csv` digest,
  prompt hash, `num_ctx` and seed against the run's `metadata.json`. There were no mismatches.
  `model_comparison_a2.csv` has the same columns as A1's `analysis/output/accuracy/model_comparison.csv`.
  Rerunning the script reproduces the committed outputs byte for byte. None of the 101 test responses was
  an error or UNPARSEABLE.
- Reuse validity relies on Part 2's documented baseline; the live environment was not checked again.

**Left to the team, deliberately not done by the tool:**

- The prediction record and team sign-off.
- Running the real A2 benchmarks. Cascade scoring, determinism checks and escalation analysis
  remain outstanding until the new runs are available.
- Slides 4 and 6, and the final recommendation.
- Sharing the pass/fail table with Part 1; it is ready locally and has not been sent to anyone.


---

## 2026-11-26 — Part 1 (Yeo Kai Yuan): settings in code, the A2 runs, and the figures

**Tool.** Claude Code (Anthropic, Claude Opus 5.5), run by Yeo Kai Yuan in this repository, on the service host
`omarchy`, driving the MacBook load generator over SSH.

**What the tool produced or did** (`TODO_A2.md` §1.2, §1.5, §1.6):

- `service/cascade.py` `RULE_SETTINGS`: Setting A and Setting B copied verbatim from the frozen
  `cascade/escalation_rule.md` §3. `scripts/cascade_replay.py` reproduces 78/99 and 59/99, MATCH; the
  rule-fidelity test now runs and passes. Three routing tests that assumed the empty state now set it
  explicitly.
- `analysis/cascade_accuracy_a2.py` (+ tests): scores the cascade's A2 accuracy runs with the limits Part 3
  applied to the single models (read from Part 3's CSVs), the escalated-vs-accepted split and the determinism
  cross-check. Output: `analysis/output/accuracy_a2/cascade_*`.
- `analysis/summarise_load_a2.py`: (1) the halves check made one-sided, as the frozen prediction record §4
  words it, before any real run; (2) a per-run Ollama busy fraction (utilisation) and the p50 of accepted
  vs escalated tickets (joined on `request_id`); (3) a labelled `--secondary-no-queue-wait` mode.
- `predictions/prediction_record_a2_appendix.md`: a dated appendix, kept outside the frozen record so the gate
  still passes. It explains why the frozen no-queue check flagged six of nine runs, including two of the
  reference model's, at the brief's own rate. The handling (frozen rule as the primary result, plus a labelled
  secondary reading) was decided by Yeo Kai Yuan when the tool raised the issue mid-campaign.
- **The real A2 runs**, started by the tool at Yeo Kai Yuan's instruction, from `omarchy` over SSH to the
  MacBook (`docs/a2/run-log.md`): the cascade accuracy runs at both settings, and the speed runs for
  `qwen2.5:7b`, cascade A and cascade B. Before them: the triage image rebuilt, the environment re-captured
  (`docs/environment/a2/`) and checked against `docs/a2/env_baseline.json`, and the gate confirmed.
- Data fills: `docs/a2/run-log.md` (environment, gate, rehearsal and run entries),
  `docs/playbooks/cascade-test.md` (warm-up tickets, `ollama ps` evidence location, run command — facts about
  Part 1's runner), Slide 2 and Slide 5 drafts (Part 1's), and measured figures into the Slide 4, 6 and 7
  drafts. Teammates' interpretation lines were left for them.
- A **draft** recommendation on Slide 7 (`qwen2.5:7b` alone, from the frozen §4 rule applied to the measured
  figures), marked as the tool's draft for the team to confirm or change, with predictions-vs-outcomes
  verdicts (mechanical: inside or outside the frozen range) and evidence pointers. The "why it differed"
  wording was left to Part 4.

**What was checked.** The full `pytest` suite passes. Every speed run was reconciled with
`analysis/reconcile.py`. The determinism cross-check compares every cascade answer with the Assignment 1
answer for the same row. Figures in the drafts were copied from the output CSVs, not typed from memory.

**Mistake made and fixed.** Mid-campaign, the tool committed analysis-code changes on the service host,
which put the two checkouts at different commits. The runner's own check then stopped cascade A **before
anything was measured**; the checkouts were realigned (no service code had changed) and the cascades
relaunched. Recorded in `docs/a2/run-log.md`.

**Left to the team, deliberately not done by the tool:** confirming or changing the recommendation and its
defence (Part 4, W.2); the "why it differed" reasoning on Slide 7; the interpretation lines on Slides 4 and 6
and the Slide 6 chart (Part 3); the deck, environment statement, limitations and AI declaration (Part 5);
reviewing the dated appendix to the prediction record (whole team).

---

## 2026-11-26 — Part 3 (Jolie Ngai Ning Li): cascade checks, escalation comparison, Slides 4 and 6

**Tool.** Claude Code (Anthropic, Claude Opus 5.5), run by Jolie Ngai Ning Li in this repository. No model
was called and no run was started. The work only read the A1 and A2 run files and the output CSVs. No
result file, Assignment 1 file, or teammate's script was edited.

**What the tool produced:**

- `slides/drafts_a2/slide6_tradeoff_chart.py` (standard library only) writes `slide6_tradeoff.svg` (the
  Slide 6 chart) and `slide6_tradeoff_points.csv` (every plotted value). It reads only
  `analysis/output/accuracy_a2/` and `analysis/output/speed_a2/per_config.csv`. The limit line is computed
  from `qwen2.5:7b`'s row, not typed in.
- `slides/drafts_a2/slide6_tradeoff.md`: the title, which latency the chart uses (the frozen rule's counted
  run, with queued runs drawn faint and not counted), the interpretation and the production notes.
- `slides/drafts_a2/slide4_accuracy_results.md`: the interpretation line and a table of where accepting
  granite's answer cost accuracy, using the frozen record §3 measure (non-escalated accuracy by true
  category). This feeds Slide 7's prediction check.


**What was checked.**

- Part 1's cascade figures were recomputed from each accuracy run's raw `responses.csv` and `service.jsonl`,
  without using `analysis/cascade_accuracy_a2.py` or `routing.csv`. Results: A 76/101, B 74/101, every
  per-category count, the escalated vs accepted split (A 13/18 and 63/83; B 23/36 and 51/65) and the
  determinism cross-check (101/101 granite, 83/83 and 65/65 qwen). All match. Routing followed the setting's
  accept-list on all 202 tickets, and the answer returned always matched the logged answer.
- Both cascade confusion matrices sum to 101, with diagonals equal to the scores.
- Escalation under load was recomputed from each speed run's `service.jsonl` with warm-up excluded: A 33/44
  and B 23/44 in every run. The gaps against the test set (−7.2 pp and −12.1 pp) are within the 15 pp
  threshold. None of the speed-test tickets is a golden-set row.
- The service URL changed from 192.168.50.130 to 192.168.50.129. `docs/a2/run-log.md` records this as a
  DHCP change on the same `omarchy` host, so the "same machine" reuse statement stands.
- The chart was rendered and inspected for label collisions. Its colours passed the palette validator for
  colour-blind separation.

**Left to the team, deliberately not done by the tool:**

- Part 2's half of Slide 4 (the limit lines and verdicts) and Part 5's assembly.
- The verdict on the §3 category prediction and the recommendation (Part 4, Slide 7). The tool supplied the
  counts only.
- Sending the results to Part 4. They are ready in the repository and have not been sent to anyone.
