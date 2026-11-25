# ICT3113 Performance Optimisation and Design — Assignment 2 — Team 10

**Module:** ICT3113 Performance Optimisation and Design
**Assignment:** Assignment 2 — Performance Optimisation: Fast Triage Within an Accuracy Floor (20% of the
final mark). Brief: [`docs/assignment-2-brief.md`](docs/assignment-2-brief.md).
**Team:** Team 10, unchanged from Assignment 1. Same data slice (`data/team_rows.csv`, rows 10000–10999),
same frozen golden set (`golden/golden_set.csv`, 200 tickets, tag `golden-freeze`), same four pinned models
(`models/models.yaml`). No new rows, no new models.
**Deliverable:** one PowerPoint file named **`Group10_A2.pptx`**, **maximum 8 slides**, plus the supporting
files listed under [W.3 Submission checklist](#w3-submission-checklist). Submitted via xSiTe.
**Hard deadline:** **2359, Friday 27 November 2026.** Late submissions lose 15% per day and nothing at all is
accepted more than four days late.

This file is the team's working agreement for Assignment 2, the same way `TODO.md` was for Assignment 1: if a
task is not on this list, nobody is doing it. Tick a box only when the work is actually in the repository.

**Owner:** Part 1 — Yeo Kai Yuan maintains this file; each owner ticks their own boxes and adds any task this
list has missed. **Done looks like:** every box below ticked, and `Group10_A2.pptx` plus its supporting files
submitted on xSiTe.

## Start here — what you need to read

You don't need all of this file. Read the **everyone** row, then your own row, and skip the rest.

| Who | Read | Skip |
|---|---|---|
| **Everyone** | [Carried over](#carried-over-from-assignment-1--read-before-starting-anything) (includes a one-off tag refresh) · [Already scaffolded](#already-scaffolded--fill-these-in-do-not-recreate-them) · [Guardrails](#a-hard-constraints--an-agent-will-not-know-these-unless-you-say-so): the **bold first sentence** of each, since your agent reads the rest via the preamble · [Prompt preamble](#c-a-prompt-preamble-to-paste-into-your-own-ai-session) · [Definition of done, per part](#definition-of-done-per-part) · [Whole team](#whole-team) | The other four parts' sections, and [Dependencies](#dependencies) |
| **Part 1** — Yeo Kai Yuan | [Part 1](#part-1--yeo-kai-yuan-cascade-implementation-memory-check-speed-tests-slides-2-5) · [Shared interfaces](#b-shared-interfaces--pin-these-before-anyones-agent-starts-writing-code) · [The A2 gate](#definition-of-done--the-a2-gate) · `docs/playbooks/cascade-test.md` | |
| **Part 2** — Loh Wen Xuan | [Part 2](#part-2--loh-wen-xuan-accuracy-limits-and-cascade-design-slide-2-with-a-slide-4-with-c) · [Shared interfaces](#b-shared-interfaces--pin-these-before-anyones-agent-starts-writing-code) · [Commit the split first](#commit-goldensplit_a2csv-first-separately--not-bundled-with-the-others) · `cascade/README.md` | |
| **Part 3** — Jolie Ngai Ning Li | [Part 3](#part-3--jolie-ngai-ning-li-accuracy-testing-and-interpretation-slide-4-with-b-slide-6) · [Shared interfaces](#b-shared-interfaces--pin-these-before-anyones-agent-starts-writing-code) · `docs/a2/accuracy_limits.md` §3 (pass/fail rules) | |
| **Part 4** — Toh Si Pei | [Part 4](#part-4--toh-si-pei-predictions-recommendation-and-defence-slide-7) · [The A2 gate](#definition-of-done--the-a2-gate) · `predictions/prediction_record_a2.md` §4 (decision rules) | |
| **Part 5** — Koh Tong Wei | [Part 5](#part-5--koh-tong-wei-environment-playbooks-deck-limitations-slides-1-3-8) · `docs/playbooks/cascade-test.md` · `slides/outline_a2.md` | |

---

## Carried over from Assignment 1 — read before starting anything

Assignment 2 changes none of this; it is reused, not rebuilt.

* **Golden set, frozen:** `golden/golden_set.csv`, 200 tickets, tag `golden-freeze`. Step 1 only *splits* it
  (odd/even by row number); nobody relabels anything.
* **Candidate models, pinned:** `models/models.yaml` — `llama3.2:1b-instruct-q4_K_M`, `llama3.2:3b`,
  `granite4:3b`, `qwen2.5:7b`. No new models may be introduced (brief, "Scope").
* **Top Assignment 1 model, by full-golden-set accuracy:** `qwen2.5:7b` at **74.0%** (148/200,
  `analysis/output/accuracy/model_comparison.csv`). This is the reference model for Step 1's limits. The
  other three, same source: `granite4:3b` 66.0% (132/200), `llama3.2:3b` 48.5% (97/200),
  `llama3.2:1b-instruct-q4_K_M` 26.0% (52/200).
* **Per-ticket Assignment 1 predictions already exist for all four models**, one response per golden-set
  ticket, in `results/accuracy/<model>_<timestamp>/responses.csv` (`row_number,predicted_category,...`). Step
  1's limits and Step 2's rule-tuning are computed **from these files**, not from new model calls — see
  [2.1](#21-split-the-golden-set-by-row-number) and [2.2](#22-compute-the-accuracy-limits-reuse-no-new-calls).
  This is what lets us do all of Step 1 and the tuning half of Step 2 before touching the service at all.
* **The classification prompt, `service/prompt.py`, is unchanged** and stays unchanged all through Assignment
  2 — the brief fixes it for every model in every configuration, cascade included.
* **The freeze-gate pattern** (`scripts/freeze_gate.py`) is the template for [the A2 gate](#definition-of-done--the-a2-gate)
  below: same idea (nothing may be measured before the evidence-of-prediction commit exists), new script,
  new tag.
* **Test machines, `docs/environment/`:** reused as-is unless Part 5 finds a reason to change them (see
  [5.1](#51-test-environment-write-up-reuse-assignment-1)). The client is not paying for more RAM or CPU, so
  neither are we.
* **Every member, once, before starting: refresh the `golden-freeze` tag.** It was moved during Assignment 1
  (to `41d6ce2`), and a plain `git pull` does not update a moved tag. On a clone with the old tag,
  `python scripts/freeze_gate.py` reports BLOCKED and every Assignment 1 run script refuses to run.
  ```
  git fetch --force origin refs/tags/golden-freeze:refs/tags/golden-freeze
  python scripts/freeze_gate.py      # should now say PASS
  ```

---

## Already scaffolded — fill these in, do not recreate them

These exist on disk already, ahead of the gate, so nobody's AI session re-invents their shape. Fill in the
`TODO(a2)` placeholders; don't restructure the files.

| File | State | Owner to fill it in |
|---|---|---|
| [`golden/split_a2.csv`](golden/split_a2.csv) | **Done.** Generated mechanically from `golden/golden_set.csv` by row-number parity: 99 tuning rows, 101 test rows. Nothing left to do here. | — |
| [`scripts/a2_gate.py`](scripts/a2_gate.py) | **Done**, working — ported from `scripts/freeze_gate.py`, gates on `predictions/prediction_record_a2.md`, `cascade/escalation_rule.md` and `golden/split_a2.csv`, tag `a2-predictions-freeze`. Run `python scripts/a2_gate.py` any time to check status. | — |
| [`cascade/README.md`](cascade/README.md) | Done — read-first for Part 2. | — |
| [`cascade/escalation_rule.md`](cascade/escalation_rule.md) | **Filled** 2026-11-21 (Part 2): `granite4:3b` → `qwen2.5:7b`, category-based, Setting A 78/99 and Setting B 59/99 escalated on tuning. Reproduced exactly by `scripts/cascade_replay.py`'s `replay()`. One `TODO(cascade)` left on purpose: the team's sign-off on the settings at W.1 | Part 2 — Loh Wen Xuan, §2.5 |
| [`docs/a2/accuracy_limits.md`](docs/a2/accuracy_limits.md) | **Filled** 2026-11-21 (Part 2): overall limit 64.26% (≥ 65/101), per-category limits with minimum counts, reuse check passed against `docs/a2/env_baseline.json` | Part 2 — Loh Wen Xuan, §2.2 |
| [`docs/a2/arrival-rate.md`](docs/a2/arrival-rate.md) | **Filled** 2026-11-19: S = 3.339 s → 8.98/min, 300 s runs, 300 000 ms timeout, 360 s pause (machine-readable copy: `docs/a2/arrival_rate.json`) | Part 1 — Yeo Kai Yuan, §1.3 |
| [`predictions/prediction_record_a2.md`](predictions/prediction_record_a2.md) | Skeleton with `TODO(a2)` placeholders and the sign-off table | Part 4 — Toh Si Pei, §4.2, whole team in §W.1 |
| [`slides/outline_a2.md`](slides/outline_a2.md) | Done — the Assignment 2 build plan, mirroring `slides/outline.md`'s format, one section per slide with the brief's requirements as checkboxes | Part 5 — Koh Tong Wei assembles from it, §5.5 |
| [`service/cascade.py`](service/cascade.py) | **Implemented and wired into `POST /tickets`** (2026-11-19, §1.2). Same signatures and the same leakage guardrail. `RULE_SETTINGS` for Setting A and B are still `None`: Part 2's settings get copied in there, and a cascade service refuses to start until they are. | Part 1 — Yeo Kai Yuan, §1.2 |
| [`workload/speed_test_rows_a2.txt`](workload/speed_test_rows_a2.txt) + [`data/speed_test_tickets_a2.csv`](data/speed_test_tickets_a2.csv) | **Done.** The fixed 100-ticket speed-test workload (70 typical, 30 long by narrative length), seeded selection from the 800 non-golden team rows, sized so no ticket repeats within a run. The `.txt` is a required submission supporting file; the `.csv` is the matching JMeter input. | — (review only) |
| [`docs/playbooks/cascade-test.md`](docs/playbooks/cascade-test.md) | Drafted — states what's new versus `load-test.md` only (gate, rate, ticket list, two-model warm-up); one `TODO(a2)` left for the actual run command once §1.3's script exists | Part 5 — Koh Tong Wei, §5.2 |
| [`docs/a2/run-log.md`](docs/a2/run-log.md) | Skeleton, same rules as `docs/run-log.md` (Assignment 1's) — a **separate file**, so an A1 entry is never mistaken for A2 evidence | Part 5 — Koh Tong Wei, §5.2 |
| [`docs/a2/ai-use-log.md`](docs/a2/ai-use-log.md) | Running log of what AI tools produced and what the team did with it, the source for Slide 8's AI declaration. (The file was missing until 2026-11-19, when Part 1 created it with the first entry. The scaffold's own entry still needs adding.) | **Every member**, as they work; Part 5 collates, §5.3 |
| [`tests/test_cascade.py`](tests/test_cascade.py) | **Done** — 4 structural guardrail tests: `should_escalate()`, `SmallModelAnswer` and `classify_with_cascade()` can't carry a label-shaped field, and `CascadeResult` names the final answer generically. Passing now against the stub; keep passing once implemented. | — (extend if you add more fields) |

`scripts/a2_gate.py` currently reports **blocked**, correctly — none of the three required files has real
content or a commit yet. Run `python scripts/a2_gate.py` yourself to see the live list of what's still
missing; it is more current than any status note in this file.

---

## Guardrails and shared interfaces — read before prompting an AI assistant

Five people will be prompting five separate AI sessions this week, each blind to what the other four are
building. Two different failure modes follow from that, and this section exists to head off both: an agent
doing something the brief forbids because it was never told, and two agents independently inventing
incompatible shapes for the same file. Paste the relevant parts of this section into your own session before
you ask it to build anything.

### A. Hard constraints — an agent will not know these unless you say so

An AI assistant optimises for "make the tests pass" and "make the number better." Several of the brief's
rules exist specifically to stop a well-meaning agent from doing exactly that in a way that invalidates the
result. Tell your agent these explicitly; do not assume general competence covers them.

1. **No new models, ever.** Only the four tags already pinned in `models/models.yaml`. An agent hunting for
   "a smaller model that might classify better" is out of scope regardless of how it reasons about it.
2. **The classification prompt is frozen.** `service/prompt.py`'s template, and therefore `PROMPT_HASH`, does
   not change for any model in any configuration — including inside the cascade. An agent "tuning the prompt
   so the small model classifies better" breaks the one fixed point every other number depends on. This does
   **not** forbid a separate, rule-only prompt if the escalation rule needs one (brief, Example method 3: a
   second call asking for HIGH/LOW confidence) — the restriction is only on the prompt actually used to
   classify the ticket, which must be the one unchanged template for every call that produces a category.
3. **No caching, anywhere, ever** — not of a final classification, not of a small-model answer reused across
   the two cascade settings to save a call. Every ticket in every reported run gets a real model call. This
   is easy for an agent to violate by accident while "optimising" the cascade driver script.
4. **Ollama's inference settings are recorded once and never touched again** — thread count, parallelism,
   context length, `OLLAMA_NUM_PARALLEL`, `OLLAMA_MAX_LOADED_MODELS`. An agent asked to "make the cascade run
   faster" by raising `OLLAMA_NUM_PARALLEL` for that configuration only silently breaks comparability with
   every other configuration's numbers.
5. **No new component.** The escalation rule may add at most one extra model call (a second prompt, a second
   small model, a confidence ask). It may never add a trained classifier, a retrieval step, or anything that
   was not part of the Assignment 1 system.
6. **The escalation rule must never see the true label at inference time.** `service/cascade.py`'s
   decision path reads only what the small model itself produced — its predicted category, its raw text, a
   confidence word, the ticket's length. It is fine, and required, to *tune* the rule's settings by checking
   against golden labels on the tuning set offline (§2.4) — but the deployed decision function in the service
   must not import or read `golden/golden_set.csv`. An agent writing the rule from "make accuracy go up" as
   the only instruction will reach for the label if it is anywhere in scope, because that is the easiest way
   to raise the number. Watch for it in review.
7. **Tune on tuning rows only, score on test rows only.** Any script that touches accuracy to choose a
   setting must filter `golden/split_a2.csv` to `set == "tuning"` first. An agent asked to "find the best
   threshold" over the whole 200 will find one — and it will mean nothing, because the brief's whole point is
   that the test-set score must come from a rule that never saw those tickets.
8. **Exactly two cascade settings, not more.** An agent iterating "just try a few more thresholds and report
   the best one" is quietly p-hacking the result and also blowing the time budget.
9. **`POST /tickets`'s response shape does not change.** The caller cannot tell which model answered from the
   HTTP response — only the service log carries that. Do not let an agent add `model_used` or `escalated` to
   the JSON response because it seems convenient for debugging.
10. **No Assignment 1 speed figures may be reused for anything**, `qwen2.5:7b` included — every speed-tested
    configuration is freshly measured under Assignment 2's conditions (new arrival rate from S, same
    workload-ticket list, same warm-up). An agent drafting Slide 5 by reading `analysis/output/load/` (the
    Assignment 1 directory) is using disallowed numbers; Assignment 2's figures belong under a separate
    output path (§1.4) so this mistake is structurally harder to make.
11. **Accuracy reuse runs one way only.** Single-model accuracy *may* reuse Assignment 1's `responses.csv`,
    filtered to test-set rows (§3.1) — that is the one sanctioned reuse. It does not extend to reusing one
    cascade setting's figures for the other, or to reusing speed numbers (rule 10).
12. **The prediction record and the final escalation-rule settings are whole-team judgements.** The same rule
    already in `README.md` for Assignment 1 applies here: no agent, and no single member, supplies them alone
    (§4.2, §W.1). An agent may draft candidate numbers from the tuning-set data; the team commits the figures
    together, in the meeting, out loud.
13. **If a proposed change's scope is genuinely unclear, ask before collecting measurements, don't guess.**
    The brief says this outright: *"Teams that are unsure whether a proposed change is within scope should
    ask before collecting measurements."* An agent will always produce *a* justification for why its chosen
    interpretation is fine — that is not the same as the interpretation being within scope. If a change to
    the escalation rule, the cascade, or the test procedure doesn't clearly fall under "may change" in the
    brief's Scope section, flag it to the module team before running anything on it, not after.
14. **Ignore the `A2 candidate:` comments in the Assignment 1 code — they predate this brief.** Assignment 1
    marked every deliberate non-optimisation with `A2 candidate:` (README, "Slide 2"), expecting Assignment 2
    to be service tuning. The real brief went another way, and several of those comments now describe things
    it **forbids**. An agent opening these files will read them as instructions, so tell it this explicitly.
    Leave the comments in place (they are Assignment 1 evidence); just don't act on them.

    | `A2 candidate:` comment | Status under the A2 brief |
    |---|---|
    | `service/prompt.py` — few-shot examples, category definitions, shorter instructions, structured `format` | **Forbidden** — "the classification prompt... is unchanged" |
    | `service/categories.py` — constrained decoding / JSON schema | **Forbidden** — changes how every model classifies, and voids the A1 accuracy reuse ("nothing has changed") |
    | `service/categories.py` — embedding nearest-neighbour | **Forbidden** — "additional classifiers, retrieval" |
    | `service/categories.py` — richer alias/synonym table | **Out of scope** — changes the normaliser, so the reused A1 single-model accuracy would no longer be comparable |
    | `docker-compose.yml` — raise `OLLAMA_NUM_PARALLEL` | **Forbidden** — "changes to Ollama's inference settings (... parallelism)" |
    | `docker-compose.yml` — `OLLAMA_MAX_LOADED_MODELS > 1` | **Not needed** — `0` is Ollama's default, which on CPU already allows up to 3 resident models. Leave it at `0` for every configuration (§1.1) |
    | `service/ollama_client.py` — streaming early-stop, client reuse, retry/hedge | **Not in the brief's "may change" list** — ask first (guardrail 13). Hedging also adds model calls that would distort the cascade's cost |
    | `service/main.py` semaphore, `service/db.py`, `service/request_log.py`, `Dockerfile` workers | **Not in the "may change" list** — and the brief's own premise is that service code costs milliseconds. Ask first |
    | `scripts/run_accuracy.py`, `scripts/smoke_test.sh` — concurrency, keep-alive | Test tooling, not the system under test. Harmless but unnecessary |
15. **The Assignment 1 run scripts do not enforce the A2 gate.** `scripts/run_accuracy.py` and
    `scripts/run_load_test.sh` check only `golden-freeze`, which already passes. Run unmodified, they will
    happily start an A2 benchmark before `a2-predictions-freeze` exists, and the brief would then treat the
    predictions as written after measurement. Every A2 run must go through `scripts/a2_gate.py`: build it
    into the A2 scripts (§1.3), and until those exist, run `python scripts/a2_gate.py` yourself first. Exit
    3 means stop.
16. **Don't edit Assignment 1 files — create the `_a2` counterpart.** `predictions/prediction_record.md` and
    `golden/golden_set.csv` are frozen A1 evidence. Editing either breaks `freeze_gate.py` for the whole
    team, and with it every A1 script. The same goes for A1 results under `results/`, `TODO.md`,
    `slides/outline.md`, `docs/run-log.md` and the A1 deck tooling. An agent asked to "fill in the
    predictions" or "update the outline" will open the A1 file unless it's told otherwise. Every A2
    document has its own file, listed in "Already scaffolded" above.

### B. Shared interfaces — pin these before anyone's agent starts writing code

Five independent sessions will each invent file shapes if not told what to produce. Where two parts' outputs
meet, a mismatch here is a merge-time bug, not a review-time one — fix it now, not after Part 3's analysis
script fails to parse Part 1's log line.

| Interface | Fixed shape | Who writes it | Who reads it |
|---|---|---|---|
| Canonical categories | The 7 names and order in `service/categories.py`'s `CATEGORIES` tuple, plus `"UNPARSEABLE"`. Never retype these by hand. | — (already fixed) | everyone |
| `golden/split_a2.csv` | Columns exactly `row_number,set`, `set ∈ {tuning,test}` | Part 2, §2.1 | Part 2 (§2.2, §2.4), Part 3 (§3.1) |
| New service-log fields | Appended at the **end** of `LOG_FIELDS` in `service/log_schema.py` (never reorder the existing 24), `LOG_SCHEMA_VERSION` bumped. `analysis/common.py`'s log reader rejects any log whose fields differ from `LOG_FIELDS`, so make it accept **both** versions (24-field A1 logs stay readable — they're evidence) — see §1.2. Proposed names: `escalated` (bool\|null), `cascade_setting` (`"A"`\|`"B"`\|null), `small_model_tag` (str\|null), `small_model_category` (str\|null — what the small model actually said, independent of what the service returned). The existing `model_tag`/`model_digest`/`predicted_category` fields continue to describe whichever model's answer the service actually returned, which is already "which model produced the final classification" for the brief's purposes. | Part 1, §1.2 | Part 1 (§1.4), Part 3 (§3.1, §3.3) |
| `docs/a2/accuracy_limits.md` | States, in this order: overall limit (%), then a per-category table with columns `category, top_model_test_accuracy_pct, limit_pct, test_set_n`, then which categories are flagged too small | Part 2, §2.2 | Part 3 (§3.2), Part 4 (§4.2), Part 5 (Slide 1) |
| `cascade/escalation_rule.md` | States, in this fixed order: method name, the exact signal computed, the exact accept/escalate condition as a literal boolean expression (not prose), the two settings as literal parameter values, the small+large tag pair, the `ollama ps` evidence | Part 2, §2.5 (content) + Part 1, §1.1 (memory evidence) | Part 1 (§1.2, implements it verbatim), Part 5 (Slide 2) |
| Cascade setting names | **"Setting A" / "Setting B"** everywhere — logs, docs, slides, scripts. Never "loose/strict" in one place and "1/2" in another. | Part 2, §2.4 | everyone |
| New top-level files/paths already decided | `golden/split_a2.csv`, `cascade/escalation_rule.md`, `cascade/README.md`, `predictions/prediction_record_a2.md`, `docs/a2/accuracy_limits.md`, `docs/a2/arrival-rate.md`, `docs/a2/run-log.md`, `docs/a2/ai-use-log.md`, `docs/playbooks/cascade-test.md`, `workload/speed_test_rows_a2.txt`, `data/speed_test_tickets_a2.csv`, `service/cascade.py`, `tests/test_cascade.py`, `scripts/a2_gate.py`, `slides/outline_a2.md`, output dir `analysis/output/accuracy_a2/`, git tag `a2-predictions-freeze`, deck `Group10_A2.pptx` | as named throughout this file (most already created — see "Already scaffolded" above) | everyone — don't rename these locally |

### C. A prompt preamble to paste into your own AI session

Adapt the bracketed parts and give this to your assistant before asking for anything substantive, so it has
the same constraints a teammate reading this file would have:

> This is Team 10's ICT3113 Assignment 2 repository. The brief is `docs/assignment-2-brief.md`; the team's
> task breakdown is `TODO_A2.md`. I am **[your name]**, owner of **[Part N]**. My task right now is
> **[section number and title from TODO_A2.md]**. Read `TODO_A2.md`'s "Guardrails and shared interfaces"
> section in full before writing anything — in particular: don't introduce new models, don't change
> `service/prompt.py`, don't cache classification results, don't change Ollama inference settings between
> configurations, and if this touches the escalation rule, never read the true golden label at inference
> time. Ignore the `A2 candidate:` comments in the existing code — they predate this brief and several are
> now forbidden (guardrail 14). Don't edit Assignment 1 files; every A2 document has its own `_a2` file
> (guardrail 16). Don't start any real benchmark until `python scripts/a2_gate.py` exits 0 — the Assignment 1
> run scripts don't check it (guardrail 15). When you finish, add an entry to `docs/a2/ai-use-log.md`
> saying what you produced; I'll record what the team did with it. Use the exact file paths, field names and setting names ("Setting A"/"Setting B") given in that
> section's interface table, because four other people's work has to match them exactly. If a task would
> require a judgement call the brief assigns to the whole team (the prediction record, the final rule
> settings), draft options but flag that it needs a team decision rather than committing it yourself.

---

## Team roster

| Part | Owner | Slides | Works mainly in |
|---|---|---|---|
| Part 1 — cascade implementation, memory check, speed tests | **Yeo Kai Yuan** | 2 (with B), 5 | `service/`, `scripts/`, `jmeter/`, `analysis/` |
| Part 2 — accuracy limits, cascade design and tuning | **Loh Wen Xuan** | 2 (with A), 4 (with C) | `golden/`, `cascade/`, `docs/a2/` |
| Part 3 — accuracy testing and interpretation | **Jolie Ngai Ning Li** | 4 (with B), 6 | `analysis/`, `analysis/output/accuracy_a2/` |
| Part 4 — predictions, recommendation, defence | **Toh Si Pei** | 7 | `predictions/` |
| Part 5 — environment, playbooks, deck, limitations | **Koh Tong Wei** | 1, 3, 8 | `docs/environment/`, `docs/playbooks/`, `slides/` |

Slide content is specified slide by slide in the brief's table ([docs/assignment-2-brief.md §Deliverables](docs/assignment-2-brief.md)).
This list only says who builds each slide and when.

### Definition of done, per part

Each part is done when its row is true. This tells each member's AI agent when to stop.

| Part | Done when |
|---|---|
| 1 | Memory check recorded with `ollama ps` evidence. `service/cascade.py` implemented and wired into `service/main.py`, and the rule-fidelity check (§1.2) passes. Log schema extended with A1 logs still readable. S and the arrival rate recorded, and the 100-ticket bound checked. Every configuration "done" per `docs/playbooks/cascade-test.md` §7. Slides 2 (with Part 2) and 5 drafted. |
| 2 | `golden/split_a2.csv` committed first. `docs/a2/accuracy_limits.md` filled in, with the reuse check passed. `cascade/escalation_rule.md` filled in, with tuning-set figures as counts and no `TODO(` left. Settings handed to Part 1. Slides 2 (with Part 1) and 4 (with Part 3) drafted. |
| 3 | All four single models and both cascade settings scored on the 101 test rows using the rules in `docs/a2/accuracy_limits.md` §3. Determinism cross-check done. Escalated vs non-escalated accuracy reported. Pass/fail table handed to Part 1. Slides 4 (with Part 2) and 6 drafted. |
| 4 | `predictions/prediction_record_a2.md` complete (including the §4 thresholds), committed and tagged, with `python scripts/a2_gate.py` passing. Recommendation made using the §4 "fastest" rule. Every prediction compared with its outcome. Slide 7 drafted. |
| 5 | Environment confirmed. Playbook rehearsed. `docs/a2/run-log.md` complete. AI-use log complete. Traceability map in `slides/outline_a2.md` complete. `Group10_A2.pptx` assembled (8 slides max) and submitted with the three supporting files. |

---

## Part 1 — Yeo Kai Yuan (cascade implementation, memory check, speed tests; Slides 2, 5)

### 1.1 Memory check — do this before designing anything

The brief is explicit that this comes first: a cascade is only a valid result if both models stay resident
throughout. This gates which pairs Part 2 may even propose.

- [x] For each of the three plausible pairs (small = `llama3.2:1b-instruct-q4_K_M`, `llama3.2:3b` or
      `granite4:3b`; large = `qwen2.5:7b`), load both tags on the service host, send a few tickets through
      each, and run `ollama ps` to confirm **both** are listed as resident at once.
      **Done 2026-11-19 with `scripts/memory_check_a2.py`: all three pairs fit.** `ollama ps` lists both models
      after alternating small/large calls, with no reload after the first load. Resident: 5.65 GiB (1b),
      7.10 GiB (llama3.2:3b), 7.05 GiB (granite4:3b). Evidence:
      [`docs/environment/a2-memory-check/20261119T073203Z/summary.md`](docs/environment/a2-memory-check/20261119T073203Z/summary.md).
- [x] Record the RAM given to the Ollama container (`docker-compose.yml`) next to each pair's result, and
      keep the raw `ollama ps` output as evidence. **Done:** 31.3 GiB host, no container memory or CPU limit,
      in the same summary. Each pair's raw `ollama ps`, `/api/ps` and `docker stats` sit beside it — Part 2 cites it in the escalation rule document, and the
      design criterion in the brief ("Design (Step 2), 6%") explicitly asks for this check to be reported.
- [x] *(Not needed: every pair fits.)* If no pair fits, stop and tell the whole team immediately — the design in §2 has to change to "cascade
      not feasible, single model recommended" before the A2 gate, not after. The brief's own fallback: "report
      that a cascade is not feasible on this machine, show the `ollama ps` evidence, and recommend a single
      model". What changes:
      - **Slide 2:** the intended design, plus the `ollama ps` evidence for every pair tried.
      - **Slides 4–6:** single models only.
      - **Slide 7:** the fastest qualifying single model.
      - **Slide 8:** infeasibility listed as a limitation.
      - **Prediction record:** the cascade rows say "not feasible".

      The ~31 GiB host makes this unlikely, but decide it before the gate if it happens.
- [x] Hand the surviving pair(s) to Part 2 as soon as it's confirmed, so the escalation rule can target a real
      pair. **Done in the repository:** the memory-evidence and RAM rows of `cascade/escalation_rule.md` §1
      (Part 1's rows, per the interface table) now say all three pairs fit and cite the summary. Part 2
      chooses the pair.
- [x] Leave `OLLAMA_MAX_LOADED_MODELS` and `OLLAMA_NUM_PARALLEL` at `0` (`.env.example`) for **every** A2
      configuration. `0` is Ollama's default, which on CPU already allows up to 3 resident models, so the
      cascade needs no change here. Changing parallelism is forbidden by the brief, and changing either for the
      cascade only would break comparability (guardrail 14). `docker-compose.yml` sets no `mem_limit`, so "the
      RAM given to the Ollama container" is the host's RAM. Record that, as the brief asks.
- [x] **Check residency in the logs, not just with `ollama ps` before the run.** *(Built in:
      `analysis/summarise_load_a2.py` flags any measured request with `load_duration` > 1000 ms as a
      "loading result". `scripts/run_load_test_a2.sh` also records `ollama ps` before and after every run.)* Ollama unloads a model that
      has been idle for `OLLAMA_KEEP_ALIVE` (default 5 minutes; the service doesn't override it). At a low
      escalation fraction the large model can sit idle that long mid-run, and the next escalation then pays a
      reload. The brief calls that "not a cascade result; it is a loading result". `load_duration` is already
      in every log line: any escalated request with a large `load_duration` means a reload. Flag that run
      rather than reporting it as a cascade result.

### 1.2 Cascade implementation in `POST /tickets`

- [x] `service/cascade.py`: **implemented** (2026-11-19). It has a category-rule and a length-rule shape
      (the brief's methods 1 and 4, the two needing no extra model call), `classify_with_cascade()`, and
      wiring into `service/main.py`. A failed small call is a 502, never a hidden escalation. Was: **stub already in place** (interface only, both functions raise
      `NotImplementedError`) — `SmallModelAnswer`/`CascadeResult` dataclasses, `should_escalate()` and
      `classify_with_cascade()` signatures fixed, with the leakage guardrail written into the docstring.
      Implement `should_escalate()` from Part 2's `cascade/escalation_rule.md` §2–3 once it's written, then
      `classify_with_cascade()`, then wire both into `service/main.py`. Not wired in yet on purpose.
- [ ] **Copy Setting A and Setting B into `service/cascade.py` `RULE_SETTINGS`** once Part 2 hands them over.
      It is one `CategoryRule(...)` or `LengthRule(...)` per setting, copied verbatim from
      `cascade/escalation_rule.md` §3. Then run the rule-fidelity check below and regenerate the Slide 2
      diagram. *Blocked on Part 2.* If Part 2 picks agreement or self-reported confidence instead, that rule
      needs a new rule class and its extra call (see the module docstring).
- [x] Extend `service/main.py` so `POST /tickets` can run in three modes selected by configuration, not by
      the caller: single-model (today's behaviour, unchanged), and cascade at setting A or setting B. The
      response shape to the caller does not change — "the caller should not be able to tell which model
      produced the answer" (brief).
- [x] *(Done: schema version 2, 30 fields. All 55 A1 runs still reconcile, and their regenerated reconcile
      outputs are byte-identical to the committed ones.)*
      Extend `service/log_schema.py` / `service/request_log.py` with the fields the brief requires: which
      model produced the final classification, and whether escalation occurred, on every request — this is
      what makes the escalation fraction derivable from the logs rather than asserted. Two things break when
      you do, and both must be handled deliberately, not patched over:
      - `tests/test_log_schema.py` pins `len(LOG_FIELDS) == 24`. Update it to the new count on purpose; don't
        delete the assertion.
      - `analysis/common.py`'s `read_service_log` raises if a log's fields differ from `LOG_FIELDS` in
        either direction. Once the new fields exist, every A1 run's `service.jsonl` (24 fields) would fail to
        load. Make the reader accept both schema versions, filling the new fields as null for A1 lines, so
        the A1 evidence stays re-checkable. Then re-run `python analysis/reconcile.py` on one A1 run to prove
        it.
- [x] Confirm `OLLAMA_NUM_PARALLEL`, `OLLAMA_MAX_LOADED_MODELS`, thread count and context length are
      unchanged from Assignment 1 and record them once (**done:** `docs/a2/env_baseline.json`, recorded
      2026-11-19. Ollama 0.34.3, all four digests and `OLLAMA_*` match Assignment 1, `num_ctx` 4096, seed 42,
      prompt hash `sha256:681131c48bdc15a1`) — the brief forbids changing inference settings
      between configurations.
- [x] Tests (`tests/test_cascade_routing.py`, `tests/test_rule_fidelity.py`, `tests/test_a2_calibration.py`): cascade routing logic with both model calls stubbed (no model contacted by the test suite), same
      pattern as Assignment 1's `pytest` suite.
- [ ] **Rule-fidelity check: the code must reproduce the documented rule.** Offline, feed the small model's
      A1 answers on the tuning-set rows through the real `should_escalate()` at Setting A and Setting B. The
      escalation fraction it produces must equal the tuning-set figure in `cascade/escalation_rule.md` §3
      **exactly** — same rows, same answers, a deterministic rule. A mismatch means the code and the document
      disagree. Fix that before the gate, since the document is what gets frozen and submitted. Worth making
      this a `pytest` test once both exist. **Tooling done:** `python scripts/cascade_replay.py --small-model <tag>`
      (exit 0 = match), and `tests/test_rule_fidelity.py::test_code_reproduces_escalation_rule_document`.
      That test skips until both the settings and §3's counts exist, then fails the suite on any mismatch.

### 1.3 Run scripts for Assignment 2

- [x] `scripts/a2_gate.py`: **already built and working** — the A2 equivalent of `scripts/freeze_gate.py`:
      checks `predictions/prediction_record_a2.md`, `cascade/escalation_rule.md` and `golden/split_a2.csv` are
      committed, tracked, unmodified, and present in the tree of a commit tagged `a2-predictions-freeze`,
      plus that neither markdown document still carries a `TODO(` placeholder. See
      [Definition of done](#definition-of-done--the-a2-gate).
- [x] *(Done: `scripts/run_accuracy_a2.py`. It also writes `routing.csv`. Score with
      `python analysis/accuracy.py --results results/accuracy_a2 --out-dir analysis/output/accuracy_a2`.)*
      Extend `scripts/run_accuracy.py` (or add `scripts/run_accuracy_a2.py`) to accept `--config
      <model|cascade-a|cascade-b>` and `--rows test` so it sends only the even-row (test-set) tickets, calls
      `scripts/a2_gate.py` before posting anything, and records which model answered each ticket from the new
      log fields.
- [x] *(Done: `scripts/run_load_test_a2.sh` + `jmeter/speed_test_a2.jmx`, rehearsed in `--dev` mode on
      2026-11-19. JMeter 5.6.3 accepts `rate(8.98/min)`, both runs reconciled, and the summariser read
      them. The run command for the playbook (`docs/playbooks/cascade-test.md` §4.5, Part 5 to paste in),
      from the load generator:
      `SERVICE_SSH=<user>@<service-host> SERVICE_REPO=<checkout> scripts/run_load_test_a2.sh --config <qwen2.5:7b|granite4:3b|...|cascade-A|cascade-B> [--small-model <tag>] --host <service-host> --runs 3`.
      Rate, run length, timeout and pause come from `docs/a2/arrival_rate.json`.)*
      Extend `scripts/run_load_test.sh` (or add an A2 variant) to: (a) derive the arrival rate from the
      **top model's** speed per the brief's S-based procedure, not from the Assignment 1 workload rate; (b)
      send **three** fixed warm-up tickets per run, not Assignment 1's one (brief, "Each run"), and for a
      cascade configuration make sure one reaches the large model, then confirm `ollama ps` lists both before
      the run starts — the warm-up tickets must not overlap the speed-test workload or the S tickets
      (`docs/playbooks/cascade-test.md` §4.2); (c) set the HTTP timeout to `10×S` (min 5 minutes) and the Open Model Thread Group's trailing
      pause to timeout + 1 minute.
- [x] *(Done 2026-11-19, `scripts/measure_s_a2.py`: **S = 3.339 s** from rows 10685 / 10910 / 10627
      (3.851 / 3.339 / 3.029 s) → 8.98/min, 300 s runs, about 45 tickets per run, safe bound 65 ≤ 100.)*
      Measure S: restart Ollama, warm up, send three different typical-length tickets to `qwen2.5:7b` one at
      a time (not the same ticket three times), take the middle time. Record the three timings, the three
      row numbers, and S itself in `docs/a2/arrival-rate.md` (template already exists — fill it in) for Slide 3.
- [x] *(Done: `docs/a2/env_baseline.json` via `scripts/a2_env_snapshot.py record`. `run_load_test_a2.sh`
      runs `a2_env_snapshot.py check` before every configuration and refuses to measure on any difference.)*
      **Before the first run**, record software versions, model digests and Ollama settings once (brief,
      Set-up) — reuse `docs/environment/` if genuinely unchanged from Assignment 1, otherwise re-capture with
      `scripts/capture_env.sh`. **Check they are unchanged before each configuration** — a quick diff against
      the recorded values, not a one-off capture, since this is a per-configuration check, not a per-campaign
      one.

### 1.4 Analysis script updates

- [x] *(Done: `analysis/summarise_load_a2.py` → `analysis/output/speed_a2/`, no p99 anywhere. The A1
      summariser now skips `speed_a2` runs.)* Extend `analysis/summarise_load.py` (or add `analysis/summarise_load_a2.py`) to report p50 per run with
      spread, p95 pooled across three runs (state the actual count — the brief's "about 90" assumes ~30 per
      run; ours will be nearer 195 if the 5-minute minimum applies), throughput and error rate — same
      shape as Assignment 1, same script where possible. **Do not add p99** — the brief is explicit the
      sample is too small for it, which is easy to get wrong if the script reuses a generic
      percentile-reporting helper that emits p50/p95/p99 by default.
- [x] Report requests sent, completed, errored and **unfinished per run — never drop a run with unfinished
      requests from the output.** The brief: *"A run with unfinished requests is reported as such, not thrown
      away."* An agent asked to "clean up the results" or "filter bad runs" will reach for exactly this
      filter; it's wrong here.
- [x] Add escalation-fraction reporting from the service logs (not from the accuracy-test figure) per cascade
      speed run, and flag any run where the two escalation fractions differ by more than the "large gap"
      threshold fixed in `predictions/prediction_record_a2.md` §4 (default 15 percentage points), as the
      brief asks ("explain any large gap").
- [x] **No-queue check on every speed run.** *(Queue wait = median `ollama_other_ms` as
      `analysis/bottleneck_hints.py` defines it. Note for the §4 decision: the ±20% halves test is
      symmetric as written, so a run whose second half is *faster* is also flagged "queued". The dev
      rehearsal hit exactly that, at −21.6%. The team may want "no more than 20% slower" instead.)* The 2×S rate exists so "no queue builds" (brief), but a slow
      configuration (e.g. a cascade setting with heavy escalation) can still take longer than 2S per ticket.
      Its p50 then depends on how long the run lasted, not on the configuration. Report, per run: first-half
      vs second-half p50, and median `ollama_other_ms` (queue wait, from `analysis/bottleneck_hints.py`).
      A run failing the threshold in `predictions/prediction_record_a2.md` §4 (default: halves within ±20%,
      queue wait under 100 ms) is reported but flagged as queued, and not compared on p50.
- [x] *(Done: cascade and single-mode consistency checks. A1 runs give byte-identical output.)* Extend `analysis/reconcile.py` to join on the new "which model answered" log field as well as
      `request_id`, so a cascade run can still be checked end to end against its `.jtl`.

### 1.5 After the A2 gate passes — run everything

Nothing in this block may start before `python scripts/a2_gate.py` exits 0. *(Status 2026-11-19: every
script below exists and enforces the gate. The block is waiting on the gate itself: Part 2's rule and
settings, then the W.1 prediction record. Once the gate passes, the whole block is two commands from the load
generator, each with a `--dry-run` that prints its plan:
`scripts/run_a2_campaign.sh accuracy --small-model <tag> --host <service-host>`, then, after Part 3's pass/fail
table, `scripts/run_a2_campaign.sh speed --small-model <tag> --host <service-host> --singles "<passing singles>"`.
The speed phase also reconciles every new run and summarises.)*

- [ ] Confirm the gate: `python scripts/a2_gate.py --json` exits 0, keep its output.
- [ ] Accuracy test, test-set rows only, for: `qwen2.5:7b` alone (reference), each other single model alone,
      and the cascade at both settings. Single-model accuracy may reuse Assignment 1's `responses.csv` filtered
      to even rows (brief, Step 4) — **do not re-run those**; only the two cascade settings need new calls.
- [ ] Speed test, three runs each, for: `qwen2.5:7b` alone (required reference), every single model that
      passed both accuracy limits, and the cascade at both settings **regardless of whether it passed** —
      brief: *"If the cascade fails the accuracy limits, still report its speed, marked as not passing
      accuracy."* Carry the pass/fail verdict from [3.2](#32-check-against-the-limits) onto every place the
      cascade's speed is shown (Slide 5, Slide 6's chart), so a fast-but-failing number is never presented
      unlabelled next to the ones that qualify. Same fixed workload-ticket list and warm-up procedure for
      every configuration ([Part 5](#52-playbooks-update) owns that list).
- [ ] Reconcile every run: `python analysis/reconcile.py --run-dir results/runs/<dir>`.
- [ ] Check every run against the definition of done in `docs/playbooks/cascade-test.md` §7. Re-run only for a
      reason listed in §6 there, never because a number looks bad, and keep the invalid run.
- [ ] An accuracy-test ticket that errors (e.g. HTTP 502) counts as wrong and is reported, never retried
      singly. Any error is investigated; an infrastructure fault invalidates the whole run (rule in
      `predictions/prediction_record_a2.md` §4).
- [ ] Hand the rebuilt `analysis/output/` to Part 3 (accuracy) and Part 4 (recommendation).

### 1.6 Slides 2 and 5

- [ ] **Slide 2 — Cascade design** (with Loh Wen Xuan). *Structure and diagram drafted in
      `slides/drafts_a2/` (`slide2_cascade_design.md`, and `cascade_diagram.py`, which draws from
      `service/cascade.py`). Final once the pair and settings are in.* Diagram of the two-model call path, the escalation
      rule in full, the two settings tested, why this rule, and the `ollama ps` memory-check evidence from
      [1.1](#11-memory-check--do-this-before-designing-anything).
- [ ] **Slide 5 — Speed results.** *Structure drafted in `slides/drafts_a2/slide5_speed_results.md`,
      every figure mapped to an `analysis/output/speed_a2/` column. Numbers come after the runs.* p50 per run with spread, pooled p95, throughput and error rate for every
      speed-tested configuration, and the escalation fraction under load for the cascade. Every figure from
      `analysis/output/`.

---

## Part 2 — Loh Wen Xuan (accuracy limits and cascade design; Slide 2 with A, Slide 4 with C)

Part 2 sets the pace of Assignment 2 the same way it did Assignment 1: the A2 gate cannot pass until the
escalation rule is written and the predictions are ready to commit, and nothing may be benchmarked until the
gate opens. Everything below is computable from data already in the repository — no code, no model calls.

### 2.1 Split the golden set by row number

- [x] `golden/split_a2.csv` already generated: `row_number,set`, `set` = `tuning` for odd `row_number`, `test`
      for even — 99 tuning rows, 101 test rows. **Commit it today, on its own** — the brief: *"Commit this
      split before you do anything else."* Don't wait for the W.1 prediction meeting; see "Definition of
      done" for why bundling it with the final commit is wrong.
- [x] Counts sanity-checked (99/101, close to the brief's "about 90" test-set estimate) and already noted in
      `docs/a2/accuracy_limits.md`'s source-data table.

### 2.2 Compute the accuracy limits (reuse, no new calls)

- [x] `docs/a2/accuracy_limits.md` (template already exists — fill it in): using `qwen2.5:7b`'s existing `responses.csv`
      (`results/accuracy/qwen2.5-7b_20261008T123045Z/responses.csv`) filtered to `golden/split_a2.csv`'s
      `test` rows and scored against `golden/golden_set.csv`, compute:
      - **Overall limit** = `qwen2.5:7b`'s test-set accuracy − 10 percentage points.
      - **Per-category limit**, for each of the seven categories = `qwen2.5:7b`'s test-set accuracy on that
        category − 15 percentage points.
- [x] Show counts (right/wrong), not just percentages, for the overall figure and every category — the test
      set is 101 tickets and some categories will have under 10, so a bare percentage is misleading without
      the count behind it (brief, "Small numbers").
- [x] Flag any category too small (brief's own example: 8 tickets ⇒ one ticket is 12.5 points) for the
      per-category limit to be a fair test, and say so in the document and on Slide 1. *(None under 10;
      Mortgage, Credit card and Money transfer flagged borderline at N = 11. Slide 1 still needs it from Part 5.)*
- [ ] Hand the two limit numbers (overall %, per-category table) to Part 4 for the predictions meeting and to
      Part 3 for scoring every other configuration against them.

### 2.3 Design the escalation rule

- [x] Pick one approach from the brief's four examples (category-based, agreement, self-reported confidence,
      ticket length) or a documented alternative, using the pair(s) Part 1 confirms both fit in memory
      ([1.1](#11-memory-check--do-this-before-designing-anything)). Category-based is the natural first choice: it needs
      no extra model call beyond the two the cascade already makes, and it can be tuned entirely from
      existing A1 per-ticket predictions.
- [x] Justify the choice against the alternatives in one paragraph — in particular, rule out or cost the
      "agreement" method's extra model call (brief: "two small calls may cost as much as one large call;
      measure it") before dropping it.

### 2.4 Tune the two settings, on the tuning set only

- [x] Using the small model's existing `responses.csv`, **filtered to `golden/split_a2.csv`'s `tuning` rows
      only**, work out which predicted categories the small model gets right reliably (category-based rule)
      or the equivalent signal for whichever method was chosen in [2.3](#23-design-the-escalation-rule).
      **Never look at the small model's Assignment 1 results on the tuning set's labels through the test-set
      tickets** — the test set is scored blind, at the end, by Part 3.
- [x] Choose two settings (e.g. two different "reliable category" lists, or two length cut-offs) that give
      visibly different escalation fractions on the tuning set, so the two reported settings actually show a
      trade-off rather than two near-identical points.
- [x] For the chosen rule, estimate on the tuning set: how often a *wrong* small-model answer slips through
      because it predicted a "safe"/accepted category (brief, Example method 1) — this number belongs in the
      escalation rule document and feeds Part 4's predictions.

### 2.5 Write the escalation rule document (required supporting file)

- [x] `cascade/escalation_rule.md` (template already exists — fill it in): the rule stated precisely enough that another team could implement
      it from the description alone — exact signal, exact accept/escalate condition, the two settings as
      concrete parameter values, and the memory-check evidence from Part 1. This is one of the three
      supporting files the brief requires at submission, and it must be committed **before** the A2 gate,
      alongside the prediction record.
- [ ] Hand the finished settings to Part 1 as soon as they're settled so [1.2](#12-cascade-implementation-in-post-tickets)
      can wire them in before the gate.

### 2.6 Slide 2 (with Yeo Kai Yuan) and Slide 4 (with Jolie Ngai Ning Li)

- [x] **Slide 2 — Cascade design** (with Part 1): own the "escalation rule in full", "settings tested" and
      "why this rule" portions; Part 1 owns the diagram and the memory-check evidence.
- [ ] **Slide 4 — Accuracy results** (with Jolie Ngai Ning Li): own the overall/per-category limit lines drawn on
      the chart and the "which pass the limits" verdicts; Jolie Ngai Ning Li owns the measured accuracy numbers
      and the escalated/non-escalated breakdown.

---

## Part 3 — Jolie Ngai Ning Li (accuracy testing and interpretation; Slide 4 with B, Slide 6)

Blocked on the A2 gate for the cascade's test-set figures; the single-model test-set figures can be computed
the moment `golden/split_a2.csv` exists, since they are pure re-scoring of Assignment 1 data.

### 3.1 Score every configuration on the test set

- [x] As soon as [2.1](#21-split-the-golden-set-by-row-number) lands: score all four single models' existing
      `responses.csv` files against `golden/golden_set.csv`, restricted to `golden/split_a2.csv`'s `test`
      rows — overall accuracy (count and %), per-category accuracy (count and %), confusion matrix. This does
      not need the gate; it uses only Assignment 1 evidence.
      **Done 2026-11-25:** `python -m analysis.accuracy_a2` writes all four single-model test-set scores,
      per-category tables and confusion matrices to `analysis/output/accuracy_a2/`.
      `pass_fail_a2.csv` is ready for Part 1 to review; no handoff or speed test has been performed here.
      Only `qwen2.5:7b` passes overall and all seven categories. Cascade tasks remain outstanding.
- [ ] **State on Slide 4 (not just in this repo) that single-model accuracy was reused from Assignment 1, not
      re-run** — the brief requires this said in the report, not just done quietly: *"Score only the test-set
      rows, and say in the report that you did this."* Name the four digests/prompt/Ollama version/machine as
      unchanged, which is the condition that makes the reuse valid.
- [x] **Before relying on any reused A1 figure, confirm the reuse is valid** — fill in the table in
      `docs/a2/accuracy_limits.md` ("Is the reuse valid?") for each of the four models: digest, prompt hash,
      `num_ctx`/seed, Ollama version and machine all unchanged. Any mismatch means re-run that model.
      **Done (Part 2, 2026-11-21):** the "Is the reuse valid?" table in `docs/a2/accuracy_limits.md` records
      reuse as valid for all four models. Digests match the `models/models.yaml` pins, the prompt hash is
      `sha256:681131c48bdc15a1`, `num_ctx` is 4096, the seed is 42, Ollama is 0.34.3 and the host is `omarchy`,
      all as in A1. The live service was checked through `docs/a2/env_baseline.json` (2026-11-19). Part 3
      did not check the live environment again.
- [ ] After the gate and Part 1's benchmark pass: score the cascade at both settings the same way, from the
      new `responses.csv` produced by `run_accuracy_a2.py`.
- [ ] **Determinism cross-check** (cheap, and the strongest evidence the reuse is sound): every model runs
      at temperature 0 with a fixed seed, so the small model's answer inside the cascade run
      (`small_model_category` in the service log) must equal that model's A1 `predicted_category` on the
      same test-set row. Compare all 101 rows. Any mismatch means something changed between A1 and A2
      (prompt, digest, `num_ctx`, Ollama version). Find out what before reporting either result.
- [ ] `analysis/output/accuracy_a2/` (new output directory): one table per configuration, plus a
      `model_comparison_a2.csv` in the same shape as Assignment 1's, so every number traces to a file.

### 3.2 Check against the limits

- [ ] For every configuration, mark pass/fail against Part 2's overall limit and each per-category limit from
      `docs/a2/accuracy_limits.md`, and flag which categories are too small to be a fair per-category test.
      Apply the rules in `docs/a2/accuracy_limits.md` §3 exactly: inclusive at the boundary, compared as exact
      counts, never rounded percentages. A borderline category decides the recommendation, so this is where a
      rounding slip costs most.
      **Partly done 2026-11-25 (single models only):** `analysis/output/accuracy_a2/pass_fail_a2.csv` and
      `per_category_a2.csv` hold the pass/fail results for the four single models, using exact fractions
      that pass when equal to the limit. Only `qwen2.5:7b` passes (75/101, all seven categories). `granite4:3b` (63/101),
      `llama3.2:3b` (54/101) and `llama3.2:1b-instruct-q4_K_M` (34/101) fail overall and per category. No category
      has fewer than 10 test rows. Mortgage, Credit card and Money transfer or service (11 rows each) are flagged
      as borderline. **Still to do:** the cascade at Settings A and B, after Part 1's runs.
- [ ] Hand the pass/fail table to Part 1 before the speed tests start — single models that fail accuracy do
      not get a speed test (brief).

### 3.3 Escalated vs non-escalated accuracy (cascade only)

- [ ] From the cascade's service logs, split the test-set results into "answered by the small model" and
      "escalated to the large model", and report accuracy separately for each group, at both settings. This is
      the number that shows whether the rule is actually catching the tickets the small model gets wrong
      (brief, Step 4).
- [ ] Compare the test-set escalation fraction here against the under-load escalation fraction Part 1 reports
      from the speed test ([1.4](#14-analysis-script-updates)); explain any gap above the threshold in
      `predictions/prediction_record_a2.md` §4, since the ticket sets differ.

### 3.4 Confusion matrices and trade-off data

- [ ] Produce one confusion matrix per configuration (test set), and name which categories a configuration
      loses the most accuracy on when the small model's answer is accepted — the brief's prediction target
      for [Part 4's record](#part-4--toh-si-pei-predictions-recommendation-and-defence-slide-7).
      **Partly done 2026-11-25 (single models only):** one test-set confusion matrix per single model in
      `analysis/output/accuracy_a2/<run folder>/confusion_matrix.csv`. Rows are the actual label and columns
      are the prediction, with UNPARSEABLE and ERROR as separate columns. Each matrix sums to 101. **Still to
      do:** the cascade matrices at Settings A and B, and naming the categories where accepting the small
      model's answer loses the most accuracy. Both need Part 1's cascade runs.
- [ ] Build the (accuracy, median latency) point for every configuration and setting, once Part 1's speed
      numbers exist, for the Slide 6 chart — one point per configuration/setting, with the overall limit as a
      horizontal reference line.

### 3.5 Slides 4 and 6

- [ ] **Slide 4 — Accuracy results** (with Loh Wen Xuan): measured overall and per-category accuracy with counts
      for every configuration, escalation fraction, and escalated-vs-non-escalated accuracy.
- [ ] **Slide 6 — Trade-off.** One chart, accuracy vs. latency, one point per configuration and setting, the
      overall limit drawn as a line, with a short interpretation of where the cascade sits relative to the
      single models.

---

## Part 4 — Toh Si Pei (predictions, recommendation and defence; Slide 7)

Part 4's Assignment 1 role (workload model, requirements) has no direct Assignment 2 equivalent — the
workload model is reused, not rebuilt — so Part 4's Assignment 2 work is the prediction record and the final
recommendation, the same items Part 4 held the pen on for Slide 11 in Assignment 1.

### 4.1 Reuse the Assignment 1 workload model — one check, no rebuild

- [ ] Read `workload/workload_model.md` for the client's peak arrival rate. Once Part 1 reports S and the
      derived test rate ([1.3](#13-run-scripts-for-assignment-2)), state whether the Assignment 2 test rate is above
      or below that peak, and write the one-paragraph consequence (brief: "say which case you are in, on the
      limitations slide") — hand this paragraph to Part 5 for Slide 8.

### 4.2 Hold the pen on the prediction record

- [x] Once Part 2's limits ([2.2](#22-compute-the-accuracy-limits-reuse-no-new-calls)) and rule settings
      ([2.4](#24-tune-the-two-settings-on-the-tuning-set-only)) exist, run the whole-team prediction meeting
      ([W.1](#w1-prediction-record-meeting--before-the-a2-gate)) and write `predictions/prediction_record_a2.md`
      from its template (to be created alongside this file), covering exactly the three things the brief asks
      for:
      - which configuration is expected to be the fastest that satisfies both accuracy limits, with reasons;
      - for the cascade, the expected escalation fraction, accuracy and median latency **at each of the two
        settings**;
      - which categories are expected to lose the most accuracy when the small model's answer is accepted.
- [x] Re-read each prediction and ask whether a measurement could prove it wrong — a vague prediction earns
      nothing, same rule as Assignment 1.
- [x] Commit the record as part of the A2 gate (see [Definition of done](#definition-of-done--the-a2-gate)).

### 4.3 Recommendation, after the results

- [ ] Once Part 1's speed tests and Part 3's accuracy tests are both in, identify the fastest configuration
      that satisfies both accuracy limits on the test set, from the team's own measurements, at the chosen
      arrival rate. Apply the "what fastest means" rule frozen in `predictions/prediction_record_a2.md` §4
      exactly as written, including the overlap and tie-break steps. Don't choose a different metric after
      seeing the results. Use only runs marked valid; flagged-as-queued runs aren't compared on p50.
- [ ] State how much faster it is than `qwen2.5:7b` alone, and how much accuracy it gives up overall and by
      category.
- [ ] If the cascade is not the fastest qualifying configuration, say so and explain why, citing the measured
      escalation fraction and the two latency figures (brief, Step 5) — do not let the deck imply the cascade
      won if it did not.
- [ ] If no configuration besides `qwen2.5:7b` alone satisfies the limits, the recommendation is `qwen2.5:7b`,
      and the slide describes what was attempted and what it cost.
- [ ] Go back through `predictions/prediction_record_a2.md` and account for each prediction that was wrong and
      why — that account is marked, not the correctness of the predictions.

### 4.4 Slide 7

- [ ] **Slide 7 — Predictions, recommendation, defence.** Predictions against outcomes with reasons for the
      gap, the recommended configuration defended against both accuracy limits, the speed gain and accuracy
      cost, and a plain statement if the cascade did not help.

---

## Part 5 — Koh Tong Wei (environment, playbooks, deck, limitations; Slides 1, 3, 8)

### 5.1 Test environment write-up (reuse Assignment 1)

- [ ] Confirm the service, Ollama and load-generator machines are unchanged from Assignment 1
      (`docs/environment/`); if anything changed (OS update, different machine), re-run
      `scripts/capture_env.sh` for the affected role and say explicitly why the change was necessary — the
      brief does not forbid it but asks it to be reported.
- [ ] Confirm, and state on the slide, that the RAM given to Docker and to the Ollama container is unchanged
      from Assignment 1 — the client is not adding compute or memory, so the Assignment 1 figures are the
      ones that matter here too.

### 5.2 Playbooks update

- [x] `docs/playbooks/cascade-test.md` drafted: covers what's new versus `load-test.md` (the A2 gate, the
      derived arrival rate, the fixed ticket list, the two-model warm-up and `ollama ps` check). Review it and
      fill in the one `TODO(a2)` (the actual run command, once §1.3's script exists).
- [x] Fixed workload-ticket list **already chosen and generated**: `workload/speed_test_rows_a2.txt` (100
      distinct row numbers — 70 typical from the interquartile length band, 30 long from the 85th percentile
      up, seeded selection from the 800 non-golden team rows) and `data/speed_test_tickets_a2.csv` (the
      matching narratives, same columns as `data/team_rows.csv`, for the JMeter CSV Data Set Config, **recycle
      off**). Sized so no ticket repeats within a run: with S ≈ 2.3 s the 5-minute minimum gives ~65 requests
      per run, and a repeated prompt would be served from Ollama's cache. Once S is measured, confirm
      the safe upper bound (expected + 3 × √expected) is ≤ 100, using the check in `docs/a2/arrival-rate.md` §2. `speed_test_rows_a2.txt` is one of the three required submission
      supporting files.
- [ ] Run one complete A2 speed test yourself from the playbook, with Yeo Kai Yuan watching but not helping,
      and fix anything you had to ask about.

### 5.3 References, licences and AI declaration

- [ ] Confirm `docs/references.md` and the model-licence acknowledgements from Assignment 1 are still
      accurate (no new models, so this should be nearly unchanged) and add any Assignment 2-specific source.
- [ ] Write the AI declaration for Slide 8: what AI tools produced (cascade scaffolding code, JMeter plan
      edits) versus what the team decided (the escalation rule, which tests to run, the recommendation).
      Build it from `docs/a2/ai-use-log.md`, which **every member appends to as they work**. The brief wants
      "what the tools produced and what the team did", and reconstructing that from memory on the last day is
      unreliable.

### 5.4 Limitations

- [ ] Collect onto Slide 8: sample size (101 test-set tickets, some categories under 10), one machine, one
      arrival rate (and whether it is above or below the client's peak, from
      [4.1](#41-reuse-the-assignment-1-workload-model--one-check-no-rebuild)), and that the test-set tickets
      already appeared in Assignment 1's model runs (brief's own "honest caveat" in Step 1).

### 5.5 Deck assembly

- [x] `slides/outline_a2.md` already written: the Assignment 2 build plan, one section per slide with the
      brief's required content as checkboxes, owner and source files — same role `slides/outline.md` played
      for Assignment 1. Work every other owner's slide from that file, not from the brief directly.
- [ ] Build `slides/Group10_A2.pptx` (or an `_a2` variant of the existing `slides/` tooling) to exactly 8
      slides in the brief's order — one slide per numbered requirement, no agenda slide, no closing slide.
- [ ] Assemble from every owner's drafts once they're in, and do the final read-through: no figure on Slide
      4 to 7 that does not also appear in `analysis/output/` (brief: "Every figure on slides 4 to 7 must be
      traceable to a log or .jtl file in the repository"). Fill in the traceability map in
      `slides/outline_a2.md` as each figure goes onto a slide, so the check is a lookup, not a hunt.
- [ ] Check the file name is exactly `Group10_A2.pptx`, and that Slide 1 carries the group number, every
      name, every student ID, the repository link, the top model's Assignment 1 accuracy, and both limits
      from `docs/a2/accuracy_limits.md`.

### 5.6 Slides 1, 3 and 8

- [ ] **Slide 1 — Cover.** Group, names, IDs, repository link, top model and its Assignment 1 accuracy,
      overall and per-category limits.
- [ ] **Slide 3 — Test environment and method.** Machines (or refer to Assignment 1), arrival rate and why,
      workload tickets, warm-up and drain procedure, any change from Assignment 1.
- [ ] **Slide 8 — Limitations, references, AI declaration.**

---

## Whole team

### W.1 Prediction record meeting — before the A2 gate

Everyone attends. Last thing done before the gate; cannot be revised afterwards.

- [ ] Meet once Part 2's limits and tuned settings exist and fill in
      `predictions/prediction_record_a2.md` together. Toh Si Pei (Part 4) holds the pen; the predictions are
      the whole team's.
- [ ] Re-read each prediction and ask whether a measurement could prove it wrong.
- [ ] Commit `predictions/prediction_record_a2.md` **on its own** — `golden/split_a2.csv` and
      `cascade/escalation_rule.md` should already be committed well before this meeting, not bundled in here
      (see "Definition of done" for why) — then tag and perform the gate.

### W.2 Recommendation meeting — after the results

- [ ] Meet once `analysis/output/` and `analysis/output/accuracy_a2/` both hold the Assignment 2 figures, and
      decide the recommended configuration together (Part 4 drafts it beforehand from §4.3).
- [ ] Check the recommendation against both accuracy limits, requirement by requirement.
- [ ] Write down, plainly, if no configuration besides `qwen2.5:7b` alone qualifies.

### W.3 Submission checklist

- [ ] `Group10_A2.pptx`, maximum 8 slides, assembled and proofread.
- [ ] Supporting files in the same submission: `predictions/prediction_record_a2.md`,
      `cascade/escalation_rule.md`, `workload/speed_test_rows_a2.txt`.
- [ ] Repository pushed, with the `a2-predictions-freeze` tag and the raw `.jtl` files and service logs for
      every Assignment 2 run kept under `results/` and `logs/` — not submitted, but may be requested.
- [ ] Repository link on Slide 1 opens, and `docker compose` still rebuilds and runs the service with the
      cascade code included.
- [ ] Uploaded to xSiTe before 2359 Friday 27 November 2026.

---

## Dependencies

### What is blocked, and by what

1. **Every Assignment 2 benchmark run is blocked on the A2 gate**, the same way Assignment 1's runs were
   blocked on `golden-freeze`. `scripts/run_accuracy_a2.py` and the A2 load-test script must call
   `scripts/a2_gate.py` and refuse to proceed.
2. **The A2 gate is blocked on Part 2** (limits + tuned settings + escalation rule document) **and the whole
   team's prediction meeting** ([W.1](#w1-prediction-record-meeting--before-the-a2-gate)).
3. **Part 2's rule tuning is blocked on Part 1's memory check** ([1.1](#11-memory-check--do-this-before-designing-anything)) —
   the rule can only target a pair that actually fits in RAM together.
4. **Part 3's cascade accuracy scoring** is blocked on the gate and on Part 1's cascade accuracy runs; its
   single-model test-set scoring is **not** blocked — it needs only `golden/split_a2.csv`.
5. **Slide 6 (trade-off)** needs both Part 3's accuracy numbers and Part 1's speed numbers. **Slide 7
   (recommendation)** needs everything.
6. **Deck assembly** is blocked on every owner's slide draft.

### What is NOT blocked — nobody should be idle before the gate

- the cascade implementation in `service/cascade.py` and the `main.py` routing (Part 1) — can be built and
  unit-tested against stubbed model calls without touching the gate;
- the golden-set split and the accuracy-limit computation (Part 2, [2.1](#21-split-the-golden-set-by-row-number)–[2.2](#22-compute-the-accuracy-limits-reuse-no-new-calls)) — pure re-scoring of Assignment 1 data;
- the escalation-rule design and tuning (Part 2, [2.3](#23-design-the-escalation-rule)–[2.4](#24-tune-the-two-settings-on-the-tuning-set-only)) — also pure re-scoring, on the tuning half;
- single-model test-set accuracy scoring (Part 3, [3.1](#31-score-every-configuration-on-the-test-set)) — reuses Assignment 1 `responses.csv`;
- the memory check (Part 1, [1.1](#11-memory-check--do-this-before-designing-anything)) — needs the service host but not the gate;
- the A2 playbook, the fixed workload-ticket list and the environment confirmation (Part 5);
- measuring S and the derived arrival rate (Part 1, [1.3](#13-run-scripts-for-assignment-2)) — this is calibration, not a
  benchmark result, and does not touch team rows or the golden set.

### Dependency diagram

```mermaid
flowchart TD
    MEM[Part 1 - memory check, ollama ps evidence]
    SPLIT[Part 2 - golden/split_a2.csv]
    LIM[Part 2 - accuracy limits, from reused A1 data]
    RULE[Part 2 - escalation rule + two settings, from reused A1 data]
    ESCDOC[cascade/escalation_rule.md]
    PRED[predictions/prediction_record_a2.md]
    GATE{{A2 GATE - tag a2-predictions-freeze<br/>python scripts/a2_gate.py exits 0}}
    CODE[Part 1 - cascade implemented in service]
    RUN[Part 1 - accuracy + speed runs, all configurations]
    AN[analysis/output + accuracy_a2 - scored, reconciled]
    S4[Slide 4 - accuracy results]
    S5[Slide 5 - speed results]
    S6[Slide 6 - trade-off]
    S7[Part 4 - Slide 7 recommendation]
    DECK[Part 5 - Group10_A2.pptx, max 8 slides]

    MEM --> RULE
    SPLIT --> LIM
    SPLIT --> RULE
    RULE --> ESCDOC
    LIM --> PRED
    RULE --> PRED
    ESCDOC --> GATE
    PRED --> GATE
    GATE --> RUN
    CODE --> RUN
    RUN --> AN
    AN --> S4
    AN --> S5
    S4 --> S6
    S5 --> S6
    AN --> S7
    PRED --> S7
    S4 --> DECK
    S5 --> DECK
    S6 --> DECK
    S7 --> DECK
```

Read the diagram as: everything feeding the gate must be finished before the A2 gate is cut; everything below
it happens afterward.

---

## Definition of done — the A2 gate

`scripts/a2_gate.py` exists and is working (tested — currently reports blocked, correctly, since none of the
three files has real content yet):

```
python scripts/a2_gate.py            # human-readable explanation, exit 0 if gated
python scripts/a2_gate.py --json     # machine-readable, for the run scripts
```

**Exit code 0 and `{"ok": true, ...}` means gated. Exit code 3 and a list of reasons means not gated**, no
matter who believes otherwise. The script checks **three** files (not two — Assignment 2 adds the golden-set
split to the two Assignment 1 gated), across seven conditions:

1. `predictions/prediction_record_a2.md` exists, is tracked by git, and has no uncommitted modifications.
2. `cascade/escalation_rule.md` likewise.
3. `golden/split_a2.csv` likewise.
4. The git tag `a2-predictions-freeze` exists.
5. All three files are present **in the tagged commit's tree**, i.e. committed at or before the tag — not
   necessarily all in the *same* commit (see the ordering below).
6. None of the three has been revised since the tag (tagged blob == `HEAD` blob, for each).
7. **Neither** `predictions/prediction_record_a2.md` **nor** `cascade/escalation_rule.md` contains a `TODO(`
   or `<<<` placeholder, so an untouched template can't pass as either document. (`golden/split_a2.csv` is
   data, not prose, so it isn't placeholder-checked — same as Assignment 1 never checked `golden_set.csv` for
   placeholders.)

On success: `{"ok": true, "gate_commit", "gate_tag", "prediction_sha", "escalation_rule_sha", "split_sha"}`.

### Commit `golden/split_a2.csv` first, separately — not bundled with the others

The brief is explicit about this one, and it is easy to get backwards: *"Commit this split before you do
anything else"* (Step 1). That means **on its own, immediately**, before any tuning or design work reads it
— so the commit history proves the split predates every decision made from it, the same way the golden set
itself had to predate Assignment 1's measurements. It does **not** need to land in the same commit as the
prediction record: condition 5 above only requires it be present, unmodified, by the time of the tag — and a
file committed early stays present in every later commit's tree unless something deletes it. So: commit the
split today, commit the escalation rule and accuracy limits as they're finished, and only the prediction
record waits for the final W.1 meeting.

### The gate, step by step

- [ ] `golden/split_a2.csv` committed **now, on its own** — see above. Don't wait for the prediction meeting.
- [ ] `docs/a2/accuracy_limits.md` committed, with the overall limit, every per-category limit, and the
      counts behind each percentage (Part 2), as soon as it's filled in.
- [ ] `cascade/escalation_rule.md` committed: rule, signal, both settings, memory-check evidence (Part 1 +
      Part 2), as soon as it's filled in.
- [ ] `predictions/prediction_record_a2.md` written in the prediction meeting ([W.1](#w1-prediction-record-meeting--before-the-a2-gate)),
      then committed in its own final commit. Nothing else belongs in that commit — the other two files are
      already committed by this point.
- [ ] Tag that final commit:
      `git tag -a a2-predictions-freeze -m "A2 predictions and escalation rule frozen before the first A2 benchmark run"`.
- [ ] `python scripts/a2_gate.py --json` exits 0. Paste its output into the team channel.
- [ ] Push the commit **and the tag** (`git push --follow-tags`).

Every run directory created afterwards should store the same JSON verbatim as `gate.json`, the A2 analogue of
Assignment 1's `freeze.json`, so each run carries its own proof that it happened after the gate.

### Before the gate, use dev mode

The same `--dev` convention as Assignment 1 applies to any new A2 scripts: bypass the gate, read only
`data/dev/synthetic_tickets.csv`, write only under a gitignored `results/dev/`, stamp `"mode": "dev"`, and
refuse to touch `data/team_rows.csv` or `golden/`. **Dev-mode output is never evidence and must never appear
on a slide.**
