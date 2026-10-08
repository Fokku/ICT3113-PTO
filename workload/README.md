# `workload/` — the client's workload model and our performance requirements

**Owner: Part 4 — Toh Si Pei**

This folder holds Step 3 (model the client's workload) and the requirements half of Step 4
(set requirements) of the assignment brief, see `../docs/assignment-brief.md`.

It feeds **Slide 3 (Workload Model)** and **Slide 4 (Performance and Accuracy Requirements)**
directly, contributes the sources it cites to **Slide 12 (References)**, and supplies the cost
position that **Slide 11 (Recommendation and Defence)** is defended with.

## What is in here

| File | What it is | Who fills it in |
|---|---|---|
| `README.md` | this file: the order of work and the commands | already written |
| `workload_model.md` | the workload model template — every figure, its source and whether it is an estimate | Part 4 — Toh Si Pei |
| `requirements.md` | the requirements template — one testable row per requirement | Part 4 — Toh Si Pei |
| `scripts/ticket_length_stats.py` | measures the ticket length distribution of our own team rows | already written; Part 4 runs it |
| `output/` | created by the script: tables, charts and a report | created on first run |

## What "done" looks like

1. Every row of every figure table in `workload_model.md` has a value, a unit, a source or a
   stated estimation method, and `Estimate?` answered `Y` or `N`. No `TODO` markers left.
2. `workload_model.md` ends with a list of arrival rates in requests per minute that
   `../scripts/run_load_test.sh` will be run at, including at least one at or above the modelled
   peak. **Part 1 cannot start benchmarking until that list exists** — see the dependency note below.
3. Every requirement in `requirements.md` is testable: a number, a percentile where one is
   relevant, and the load condition under which it must hold, and the row names the analysis
   script that will produce the number.
4. `requirements.md` states the client's relative cost of a misrouted ticket versus a slow triage.
5. Both documents are committed **before the freeze** (see below), because the prediction record
   is written against these requirements and cannot be revised afterwards.

## The order of work

Run these from the repository root. Use the project virtualenv, `.venv/bin/python`.

**Step 1 — measure what we already hold.** The length distribution is the one figure in the
workload model we do not have to estimate, because the narratives our load generator will post
are already in the repository:

```bash
.venv/bin/python workload/scripts/ticket_length_stats.py --out-dir workload/output
```

That writes `workload/output/length_distribution.{csv,md}`, `truncation_risk.{csv,md}`,
`ticket_lengths_per_row.csv`, two PNG charts and `ticket_length_stats.md`. Run it once and read
the report before writing the *Ticket length distribution* section of the workload model. It runs
no model and calls no tokeniser, so it is safe to run at any time, before or after the freeze.

Useful variants:

```bash
# the dev tickets instead of the team rows, or any subset you have cut
.venv/bin/python workload/scripts/ticket_length_stats.py \
    --input data/dev/synthetic_tickets.csv --out-dir workload/output/dev

# check the truncation risk at a different context size
.venv/bin/python workload/scripts/ticket_length_stats.py --num-ctx <tokens> --out-dir workload/output

# tables only, no charts, when you are just re-checking a number
.venv/bin/python workload/scripts/ticket_length_stats.py --no-charts --out-dir workload/output

.venv/bin/python workload/scripts/ticket_length_stats.py --help
```

**Step 2 — fill in `workload_model.md`.** Volume, search rate, peak factor and any figure about
the client are estimates and must carry a citation or a stated estimation method. Do the sections
in the order they appear; the derived arrival rates at the end depend on everything above them.

**Step 3 — fill in `requirements.md`.** Each requirement must follow from a figure in the
workload model. If you cannot point at the figure it came from, the requirement is not justified
and Slide 4 will not survive a question about it.

**Step 4 — hand the arrival-rate list to Part 1.** Post it in the team channel and tell
Yeo Kai Yuan it is final. Each rate is run three times per candidate model (the brief requires
three runs per configuration), so the length of that list sets the size of the whole measurement
campaign. A list with one rate too many costs hours of CPU time; a list without a peak rate makes
Slide 4 untestable.

**Step 5 — commit both documents before the freeze.**

## The freeze gate, and why your deadline is earlier than you think

Step 5 of the brief (test and measure) cannot begin until Steps 1 to 4 are complete: the golden
test set and the prediction record must both be committed, and in our repository the tag
`golden-freeze` is what marks that commit. The gate is enforced in code — every benchmark script
calls it and refuses to run against team data without it:

```bash
.venv/bin/python scripts/freeze_gate.py --json     # exit 0 = benchmarking may start, 3 = blocked
```

Your requirements are an input to the prediction record (Part 2 — the prediction record cannot
predict against requirements that do not exist yet), so **`workload_model.md` and
`requirements.md` must be finished and committed before the freeze**, not alongside it.

**Target freeze date: Tuesday 29 September 2026.** The assignment is due 2359 Friday 9 October
2026. Everything after the freeze — load runs at every rate on every candidate model, three runs
each, the accuracy runs, the stress test, the analysis and twelve slides — has to fit in the days
that remain. Freezing late does not move the deadline; it shortens the measurement campaign.

**Aim to have the arrival-rate list to Part 1 by Friday 26 September 2026**, so that the load
plans and the run scripts can be dry-run in dev mode before the freeze.

## Rules that bite this folder in particular

* **Cite every figure, or state how you estimated it.** The brief asks for this explicitly and
  Slide 3 is marked on it. A number with neither a citation nor a method is treated as
  unsupported.
* **Never invent a number to fill a cell.** Leave the `TODO` marker in place and raise it with the
  team. A plausible-looking invented figure is worse than an empty cell, because nobody will
  question it later.
* **Mark estimates as estimates.** The `Estimate? (Y/N)` column exists so that Slide 3 can state
  clearly which figures are published and which are ours.
* **Do not run a model.** Nothing in Part 4 needs one. `ticket_length_stats.py` deliberately does
  not call a tokeniser: its token counts are an approximation, and the authoritative per-request
  count arrives from the service log (`prompt_eval_count`) once benchmarking begins.
* **Keep the two documents in step.** If a workload figure changes, every requirement justified by
  it has to be revisited. After the freeze, neither can change at all.

## Cross-references

* The brief: `../docs/assignment-brief.md` (Step 3, Step 4, Slides 3, 4 and 11).
* The requirements template: `requirements.md`.
* The workload model template: `workload_model.md`.
* The load-test runner your arrival rates drive: `../scripts/run_load_test.sh`.
* The analysis scripts that will produce the numbers your requirements are judged against:
  `../analysis/summarise_load.py`, `../analysis/accuracy.py`, `../analysis/stress_summary.py`.
