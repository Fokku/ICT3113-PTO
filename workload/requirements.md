# Performance and accuracy requirements

**What this document is for.** The requirements half of Step 4 of the brief: the service quality
we promise the client, stated so that a test can prove or disprove each one. Every requirement
here is justified from a figure in `workload_model.md`, and every one is checked against our own
measurements in Step 6. The brief is blunt about the consequence: *"a recommendation that
contradicts your stated requirements ... fails regardless of which model it picks."*

**Owner: Part 4 — Teammate C.**
`TODO(Yeo Kai Yuan): replace "Teammate C" with the real name once the team roles are confirmed.`

**Which slide this feeds.** **Slide 4 — Performance and Accuracy Requirements**. The cost position
at the end of this document also feeds **Slide 11 — Predictions, Recommendation and Defence**.

**What "done" looks like.** Every row below is complete, and each one satisfies all three parts of
the brief's definition of testable:

1. **a number** — the threshold, with its unit;
2. **a percentile where relevant** — for anything measured across many requests, a single number
   with no percentile is not a requirement, because half the requests could miss it and the
   requirement would still be "met";
3. **the load condition under which it must hold** — the arrival rate, the plan, and the model.
   A latency requirement with no load condition is trivially satisfiable at an arrival rate of one
   request per hour.

A fourth part is ours rather than the brief's, and it is why the last column exists: **a
requirement we have no way to measure is not a requirement.** Before writing a threshold, check
that the script named in the final column will actually produce that number. If it will not, either
change the requirement or raise it with Part 1 — Yeo Kai Yuan before the freeze.
`TODO(Yeo Kai Yuan): replace with the real name.`

---

## The requirements

Columns are fixed — do not add, remove or reorder them. Every cell marked `TODO` is a decision
that belongs to Part 4; the *How it will be measured* column is already filled in because it is a
fact about this repository rather than a judgement.

| ID | Metric | Threshold | Percentile | Load condition | Justification | How it will be measured (script + output) |
|---|---|---|---|---|---|---|
| R1 | `POST /tickets` end-to-end response time | TODO(Part 4 — Teammate C) | TODO(Part 4 — Teammate C) | TODO(Part 4 — Teammate C) | TODO(Part 4 — Teammate C) | `analysis/summarise_load.py --runs results/runs --plan load_post_tickets` → latency tables under `analysis/output/load/`, from the `.jtl` of each run, cross-checked against the service log by `analysis/reconcile.py` |
| R2 | Tickets classified per hour at sustained load | TODO(Part 4 — Teammate C) | TODO(Part 4 — Teammate C) | TODO(Part 4 — Teammate C) | TODO(Part 4 — Teammate C) | `analysis/summarise_load.py --runs results/runs` → achieved throughput and error rate under `analysis/output/load/`, at the arrival rate named in the load condition |
| R3 | Overall classification accuracy on the golden set | TODO(Part 4 — Teammate C) | TODO(Part 4 — Teammate C) | TODO(Part 4 — Teammate C) | TODO(Part 4 — Teammate C) | `analysis/accuracy.py --results results/accuracy --golden golden/golden_set.csv` → overall accuracy under `analysis/output/accuracy/` |
| R4 | Per-category classification accuracy on the golden set | TODO(Part 4 — Teammate C) | TODO(Part 4 — Teammate C) | TODO(Part 4 — Teammate C) | TODO(Part 4 — Teammate C) | `analysis/accuracy.py --results results/accuracy --golden golden/golden_set.csv` → per-category table and confusion matrix under `analysis/output/accuracy/` |
| R5 *(optional)* | `GET /search` response time under mixed load | TODO(Part 4 — Teammate C) | TODO(Part 4 — Teammate C) | TODO(Part 4 — Teammate C) | TODO(Part 4 — Teammate C) | `analysis/summarise_load.py --runs results/runs --plan mixed_load` → latency tables under `analysis/output/load/`, split by sampler label |

R1 to R4 are the minimum the brief demands. R5 is optional: the brief offers "the latency of
`GET /search` under mixed load" as an example of a response-time requirement, and we have a
mixed-load plan that would measure it. Keep it only if you intend to justify and test it; an
untested requirement on Slide 4 is worse than no requirement.
`TODO(Part 4 — Teammate C): decide whether R5 stays. If it goes, delete the row.`

---

## Notes on each row — what makes it testable

### R1 — response time for `POST /tickets`

* **What the number must be.** A latency, with its unit, that an agent waiting on a triage result
  would accept. Derive it from usability rather than from what the hardware happens to manage:
  deciding the threshold from a measurement you have already seen is circular, and the brief asks
  for requirements set *before* the benchmarks.
* **Percentile.** Required. Our analysis reports p50, p95 and p99 for every run, so the
  requirement may bind any of them; say which, and say it in the same words the analysis output
  uses. `TODO(Part 4 — Teammate C): choose the percentile and say why that one.`
* **Load condition.** Required: an arrival rate from the *Derived arrival rates for testing*
  section of `workload_model.md`, plus which plan and which candidate model. If the workload model
  implies a peak, the brief requires the requirement to cater for the peak — so state whether R1
  holds at the average rate, at the peak rate, or at both with different thresholds.
* **Justification.** Point at the workload figure it comes from. "Agents triage between calls and
  a wait longer than X loses the thread of the conversation" is a justification; "X seems
  reasonable" is not.
* **Watch out.** This is end-to-end latency including the model call, measured open-loop, so it
  includes any time the request spends queued inside Ollama. That is deliberate: it is what the
  agent experiences.

### R2 — throughput

* **What the number must be.** A rate with an explicit period (tickets per hour is the brief's own
  example) that covers the volume from `workload_model.md` — including the peak, if there is one.
  Check the arithmetic against the arrival-rate list: a throughput requirement that exceeds the
  highest rate we will test at cannot be demonstrated.
* **Percentile.** Usually not applicable; write `n/a` rather than leaving it blank, so it is clear
  the column was considered. If you require a *sustained* rate over a window, say the window.
* **Load condition.** The arrival rate and duration at which the throughput must be sustained, and
  the error-rate ceiling that goes with it. Throughput with errors is not throughput: a service
  that fails fast has excellent throughput and no value, so state the maximum acceptable error
  rate as part of this requirement.
* **Justification.** Tie it to tickets per hour of opening, or to peak arrival rate, from the
  workload model. Say whether the client must clear the backlog within the working day.

### R3 — overall accuracy

* **What the number must be.** A percentage (or a proportion — be consistent), measured on the
  golden set, over all seven categories.
* **Percentile.** Not applicable: accuracy is a single proportion over a fixed set of tickets.
  Write `n/a`.
* **Load condition.** Still required, and easy to get wrong. Accuracy is measured by
  `scripts/run_accuracy.py`, which sends the golden set through `POST /tickets` one at a time, not
  under load. State that explicitly — "measured serially, not under load" — so nobody later reads
  the accuracy figure as holding at peak. If you *want* accuracy to hold under load too, that is a
  separate requirement and a separate test.
* **Justification.** This is where the cost of a misrouted ticket enters (see the section below).
  An accuracy threshold is a statement about how much manual re-routing the client will tolerate.
* **Watch out.** State how `UNPARSEABLE` replies count. A model reply we could not map onto a
  category is not a correct classification; whether you count it as an error or report it
  separately, decide now and write it down, because it changes the number.
  `TODO(Part 4 — Teammate C): decide how UNPARSEABLE counts, and say so here.`

### R4 — per-category accuracy

* **What the number must be.** A floor that every category must clear, or a floor per category if
  some matter more to the client than others. A high overall accuracy can hide a category the
  model never gets right, which is exactly the failure a routing system cannot afford — the brief
  asks for per-category accuracy for this reason.
* **Percentile.** Not applicable; write `n/a`.
* **Load condition.** As R3: measured serially on the golden set.
* **Justification.** Say which categories the client cannot afford to misroute and why. If you set
  one floor for all seven, justify that too.
* **Watch out.** The golden set holds 150 to 200 tickets across seven categories, so some
  categories will have few examples and their accuracy will be a coarse fraction. Acknowledge that
  small-sample limitation in the justification rather than being caught by it on Slide 10.

### R5 — `GET /search` under mixed load (optional)

* **What the number must be.** A latency with a percentile, under the mixed plan, while ticket
  classification is running at a stated rate. The interesting question is whether a read endpoint
  stays responsive while the model saturates the machine, so the load condition is the whole point
  of this requirement.
* **Watch out.** `GET /search` is a full-table `LIKE` scan in the baseline, so its latency depends
  on how many tickets are already stored. State the store size the requirement assumes, or the
  number is not reproducible.

---

## Checklist before the freeze

Work through this before committing. After the freeze, none of it can be changed.

* [ ] Every `TODO` in the table above is replaced by a real decision.
* [ ] Every threshold has a unit.
* [ ] Every requirement that is measured across many requests names a percentile; the ones that
      are not say `n/a` rather than being left blank.
* [ ] Every requirement names its load condition: arrival rate, plan and candidate model — or
      states explicitly that it is measured serially.
* [ ] If `workload_model.md` implies a peak, at least one requirement holds *at the peak*, and the
      arrival-rate list contains a rate at or above that peak.
* [ ] Every justification points at a specific figure in `workload_model.md`.
* [ ] Every row's *How it will be measured* column names a script that exists and an output we
      will actually produce. Walk the list with Part 1 — Yeo Kai Yuan.
      `TODO(Yeo Kai Yuan): replace with the real name.`
* [ ] The error-rate ceiling for R2 is stated.
* [ ] The treatment of `UNPARSEABLE` in R3 and R4 is stated.
* [ ] The cost position below is written.
* [ ] `workload_model.md` and this file agree with each other.
* [ ] Both files are committed, and the commit is before the `golden-freeze` tag. Confirm with:

```bash
.venv/bin/python scripts/freeze_gate.py --json
```

---

## The client's cost position — which is worse, a misrouted ticket or a slow triage?

The brief states that neither it nor the client tells us whether a misrouted ticket or a slow
triage costs more, and that **our workload model and requirements must take a position**. Step 6
then requires the recommendation to follow from that position, and **Slide 11** is where it is
defended. Our candidate models will not agree: the small ones are fast and wrong more often, the
larger ones are slower and more accurate. Without a stated position, the recommendation between
them is arbitrary, and an arbitrary recommendation cannot be defended.

`TODO(Part 4 — Teammate C): write the cost position here, in a short paragraph, and make it
decisive.` Work it through in terms the client would recognise:

* **What does a misrouted ticket actually cost?** A ticket routed to the wrong team is presumably
  read, bounced and re-routed — so the cost is an agent's handling time, twice, plus the delay to
  the customer. Is there a regulatory clock on complaint handling that a misroute eats into?
  Is there a category where a misroute is worse than an inconvenience?
* **What does a slow triage cost?** If classification takes seconds rather than milliseconds, who
  waits? If tickets are triaged in a batch overnight, a slow model costs nothing until the batch
  no longer finishes before the shift starts. If an agent waits at the screen, it costs their time
  directly. This depends on the working pattern you assumed in `workload_model.md` — make sure the
  two agree.
* **Which one binds?** State it plainly: *the client would rather wait than misroute*, or *the
  client would rather misroute occasionally than have agents waiting*. Then show that R1 to R4
  reflect that choice — a team that says accuracy matters more but sets a tight latency threshold
  and a loose accuracy floor has contradicted itself, and Slide 11 will not survive it.
* **Say what would change your mind.** Which measured outcome would make you swap the position?
  That sentence is worth writing: it is the difference between a position and an opinion.

`TODO(Part 4 — Teammate C): state which requirement is the one you would relax first if no
candidate model meets all of them.` The brief says plainly that finding no candidate meets every
requirement is a strong result when it is measured carefully and argued clearly — but the argument
is much easier to make if the order of concession was decided *before* the measurements arrived.
