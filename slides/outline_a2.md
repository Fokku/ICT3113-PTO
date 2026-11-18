# Slide outline — Group10_A2.pptx

## About this document

**What it is for.** The build plan for the Assignment 2 deck, the same role `outline.md` played for
Assignment 1. Lists all eight required slides in the brief's order, the content the brief requires for each,
who owns it, which files supply the numbers, and what "done" looks like. Work slide by slide from this file.

**Owner:** Part 5 — Koh Tong Wei assembles the deck. Every slide has a named content owner below; the
assembler does not write content, only places it.

**Done when.** Every checkbox below is ticked against the actual deck; every number on every slide names the
file it came from (brief: "every figure on slides 4 to 7 must be traceable to a log or .jtl file in the
repository"); the deck is exactly 8 slides or fewer; the three supporting files are in the same submission.

---

## Submission constraints — settle before building a single slide

* **Maximum 8 slides**, file name **`Group10_A2.pptx`**, due **2359 Friday 27 November 2026** via xSiTe.
* **Supporting files, in the same submission:**

| Required supporting file | What we submit | Owner |
|---|---|---|
| The prediction record (Step 3) | `predictions/prediction_record_a2.md`, as gated at the `a2-predictions-freeze` tag | Part 4 — Toh Si Pei holds the pen; whole team signs |
| The written escalation rule (Step 2) | `cascade/escalation_rule.md` | Part 2 — Loh Wen Xuan (design), Part 1 — Yeo Kai Yuan (memory evidence) |
| The list of row numbers used as the speed-test workload | `workload/speed_test_rows_a2.txt` | Part 5 — Koh Tong Wei |

* **Repository evidence, not submitted but examined.** The `a2-predictions-freeze` tag, every run's raw `.jtl`
  and service logs under `results/` and `logs/`. Enforced by `python scripts/a2_gate.py`.

### Ownership map

| Slide | Title | Owner(s) |
|---|---|---|
| 1 | Cover | Koh Tong Wei |
| 2 | Cascade design | Yeo Kai Yuan (diagram, memory evidence) + Loh Wen Xuan (rule, settings, why) |
| 3 | Test environment and method | Koh Tong Wei |
| 4 | Accuracy results | Loh Wen Xuan (limits) + Jolie Ngai Ning Li (measured figures) |
| 5 | Speed results | Yeo Kai Yuan |
| 6 | Trade-off | Jolie Ngai Ning Li (chart, with Yeo Kai Yuan's latency data) |
| 7 | Predictions, recommendation, defence | Toh Si Pei |
| 8 | Limitations, references, AI declaration | Koh Tong Wei |

---

### Traceability map — fill in as each figure goes onto a slide

The brief: "Every figure on slides 4 to 7 must be traceable to a log or .jtl file in the repository." Add a
row for every number placed on Slides 4–7, when it's placed. Before submission, every row must point to a
file that exists in the repository, and the number must match it. Part 5 checks the table, not the deck.

| Slide | Figure (as shown) | Source file | Produced by (script / command) |
|---|---|---|---|
| | | | |

---

## Slide 1 — Cover

**The brief requires (verbatim):** "Group, names, IDs, repository link. Top model and its Assignment 1
accuracy. Overall and per-category limits."

- [ ] Group 10, names and student IDs from `slides/team.yaml` (reused from Assignment 1).
- [ ] Repository link.
- [ ] Top model: `qwen2.5:7b`, 74.0% (148/200) on the full Assignment 1 golden set — `../analysis/output/accuracy/model_comparison.csv`.
- [ ] Overall and per-category limits from `docs/a2/accuracy_limits.md` §1–2.

**Done when:** all four items present and every figure traces to the named file.

## Slide 2 — Cascade design

**The brief requires (verbatim):** "Diagram. Escalation rule in full. Settings tested. Why this rule."

- [ ] Diagram of the two-model call path (small model → rule → optionally large model).
- [ ] The rule stated in full, from `cascade/escalation_rule.md` §2.
- [ ] Setting A and Setting B as literal parameter values, from `cascade/escalation_rule.md` §3.
- [ ] Why this rule over the brief's other examples, from `cascade/escalation_rule.md` §2.
- [ ] The memory-check evidence (`ollama ps` showing both models resident) — brief's own Design criterion.

**Done when:** a reader who has not seen the code could reimplement the rule from this slide alone.

## Slide 3 — Test environment and method

**The brief requires (verbatim):** "Machines (or refer to Assignment 1). Arrival rate and why you chose it.
Workload tickets. Warm-up and drain procedure. Any change from Assignment 1."

- [ ] Machines: reference `../docs/environment/` (Assignment 1), confirm unchanged or explain any change.
- [ ] Arrival rate and why, from `docs/a2/arrival-rate.md` §1–2.
- [ ] The fixed workload-ticket row numbers, from `workload/speed_test_rows_a2.txt`.
- [ ] Warm-up (both models for the cascade) and drain procedure, from `docs/playbooks/cascade-test.md`.
- [ ] Whether the test rate is above or below the client's peak, from `docs/a2/arrival-rate.md` §4.

**Done when:** the procedure is specific enough that a competent tester with no further questions could
repeat it (same standard as Assignment 1's playbooks).

## Slide 4 — Accuracy results

**The brief requires (verbatim):** "Overall and per-category accuracy for every configuration, with counts.
Which pass the limits. Escalation fraction; accuracy of escalated vs non-escalated tickets."

- [ ] Overall and per-category accuracy (count and %) for every configuration, test-set rows only, from
      `analysis/output/accuracy_a2/`.
- [ ] Pass/fail against `docs/a2/accuracy_limits.md`, per configuration.
- [ ] Escalation fraction (test-set, from the accuracy run's logs) at both settings.
- [ ] Accuracy of escalated vs non-escalated tickets, at both settings.
- [ ] Any category flagged too small for a fair per-category test, carried over from `docs/a2/accuracy_limits.md`.
- [ ] State plainly that the four single models' accuracy figures are reused from Assignment 1 (same digest,
      prompt, Ollama version, machine), not re-run — the brief requires this said on the slide, not just true
      in the repository.

**Done when:** every number names its source file in `analysis/output/accuracy_a2/`.

## Slide 5 — Speed results

**The brief requires (verbatim):** "p50 per run with spread, pooled p95, throughput and error rate for every
speed-tested configuration. Escalation fraction under load."

- [ ] p50 per run (3 runs) with mean and spread, for every speed-tested configuration.
- [ ] Pooled p95 across the three runs, per configuration, with the actual request count it's based on.
- [ ] Achieved throughput and error rate, per run.
- [ ] Escalation fraction under load (from service logs), both cascade settings — and the comparison against
      the accuracy-test escalation fraction, explaining any large gap.
- [ ] Requests sent/completed/errored/unfinished, per run — reported even when non-zero.
- [ ] If a cascade setting failed its accuracy limits (Slide 4), its speed figures here are still shown but
      visibly marked as not passing accuracy (brief, Step 4) — never presented unlabelled alongside the
      qualifying configurations.
- [ ] No p99 anywhere on this slide — brief: "the sample is too small."

**Done when:** every number traces to a `.jtl` file or a run's `service.jsonl` under `results/`.

## Slide 6 — Trade-off

**The brief requires (verbatim):** "One chart: accuracy vs latency, one point per configuration and setting,
overall limit drawn as a line. Short interpretation."

- [ ] One chart: x = median latency, y = test-set overall accuracy, one point per speed-tested configuration
      (single models) and both cascade settings.
- [ ] The overall accuracy limit drawn as a horizontal reference line.
- [ ] A cascade setting that fails the accuracy limit still gets a point (its speed was still measured), but
      visually distinguished (e.g. a hollow marker) from the points that pass — the chart should make "fast
      but failing" readable at a glance, not just in the surrounding text.
- [ ] Short interpretation: where the cascade sits relative to the single models, and whether it beats the
      best qualifying single model on speed.

**Done when:** every plotted point's two coordinates each trace to a number already shown on Slides 4 and 5.

## Slide 7 — Predictions, recommendation, defence

**The brief requires (verbatim):** "Predictions vs outcomes and why they differed. Recommended configuration,
speed gain, accuracy cost. If the cascade lost, why."

- [ ] `predictions/prediction_record_a2.md` vs measured outcomes, per section, with reasons for any gap.
- [ ] Recommended configuration, defended against both accuracy limits.
- [ ] Speed gain vs `qwen2.5:7b` alone; accuracy cost overall and by category.
- [ ] If the cascade is not the recommendation: explicit statement why, citing measured escalation fraction
      and the two latency figures.

**Done when:** the recommendation follows visibly from Slides 4–6, not from anything typed from memory.

## Slide 8 — Limitations, references, AI declaration

**The brief requires (verbatim):** "What the results do not show (sample size, one machine, one arrival rate,
seen tickets). References. Model licences. AI use."

- [ ] Sample size: ~101 test-set tickets, with any category flagged too small named again.
- [ ] One machine, one arrival rate — and whether that rate is above or below the client's peak
      (`docs/a2/arrival-rate.md` §4).
- [ ] The test-set tickets already appeared in Assignment 1 model runs (brief's own "honest caveat", Step 1).
- [ ] References: `../docs/references.md`, reused and extended if needed.
- [ ] Model licences: reused from `../models/candidates.md` (no new models).
- [ ] AI declaration: what AI tools produced vs what the team decided, per
      `../TODO_A2.md`'s guardrails section.

**Done when:** nothing on this slide is new work — it is a collection of statements already made elsewhere in
the repository, pointed at from here.
