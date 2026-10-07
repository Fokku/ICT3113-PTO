# Performance and accuracy requirements

**What this document is for.** The requirements half of Step 4 of the brief: the service quality
we promise the client, stated so that a test can prove or disprove each one. Every requirement here
is justified from the workload model, the assignment brief, or an explicit client-facing assumption,
and every one is checked against our own measurements in Step 6. The brief is blunt about the 
consequence: *"a recommendation that contradicts your stated requirements ... fails regardless of which model it picks."*

**Owner: Part 4 — Si Pei.**

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

---

## The requirements

Columns are fixed. The *How it will be measured* column names the script and output that produce each number.

| ID | Metric | Threshold | Percentile | Load condition | Justification | How it will be measured (script + output) |
|---|---|---|---|---|---|---|
| R1 | `POST /tickets` end-to-end response time | ≤ 10 s | p95 | `load_post_tickets`: 1 req/min, 600 s, 3 runs, each candidate model | Lowest runnable rate is 1 req/min, about 42× the modelled peak of 0.024 tickets/min, so it is tested as a headroom margin. An agent waiting at the screen should get a routing answer within 10 s. Each run's p95 rests on about 10 samples (30 across three runs), so it is indicative only. | `analysis/summarise_load.py --runs results/runs` → latency tables in `analysis/output/load/`; cross-check with `analysis/reconcile.py` |
| R2 | Errors and backlog at sustained load | ≥ 95% of tickets sent are classified successfully (≤ 5% errors), and each run finishes within 660 s (no backlog) | n/a | `load_post_tickets`: 12 req/min (720 tickets/hour offered), 600 s, 3 runs, each candidate model | 12 req/min is the capacity test, about 500× the modelled peak. Arrivals are random (Poisson), so the number of tickets sent varies by about ±10% around 120 per run and a fixed tickets/hour cut-off would fail a perfect system in many runs. Instead the service must classify what it receives and finish within 60 s of the last arrival, which fails if a queue builds up. Achieved tickets/hour is reported alongside. | `analysis/summarise_load.py --runs results/runs` → `error_rate_pct`, `span_s` and `ok_throughput_per_hour` in `analysis/output/load/load_per_run.csv` (all three runs must pass) |
| R3 | Overall classification accuracy on the golden set | ≥ 90% | n/a | `POST /tickets`; golden set measured serially, not under load, each candidate model. Measured in a single serial pass of the golden set (once per model). | About 1,496 tickets/year (workload model) at 90% means at most about 150 misrouted tickets/year, each costing repeated handling. `UNPARSEABLE` counts as incorrect. Achievable accuracy is also bounded by labeller agreement (kappa). | `analysis/accuracy.py --results results/accuracy --golden golden/golden_set.csv` → `analysis/output/accuracy/` |
| R4 | Per-category classification accuracy on the golden set | ≥ 80% for every category | n/a | `POST /tickets`; golden set measured serially, not under load, each candidate model. Measured in a single serial pass of the golden set (once per model). | Stops a strong overall figure hiding a failing category. One floor is used because the client has not said any category matters more. With 200 tickets across seven categories, per-category counts range from 19 to 41 (golden/golden_set.csv), so per-category accuracy is a coarse fraction, especially for the smallest categories. `UNPARSEABLE` counts as incorrect. At about 1,496 tickets/year (workload model), a category that is systematically misrouted sends a steady stream of tickets to the wrong team; the 80% floor caps that at one in five. | `analysis/accuracy.py --results results/accuracy --golden golden/golden_set.csv` → per-category table and confusion matrix |
| R5 | `GET /search` response time under mixed load | ≤ 2 s | p95 | `mixed_load`: 1 ticket req/min + 1 search req/min, 600 s, 3 runs, each candidate model; store starts empty and grows to about 10 tickets | Search should stay responsive while classification runs. Lowest runnable search rate is 1/min (modelled: 0.167/min). With about 10 stored tickets a `LIKE` scan is trivial, so this mainly tests contention with Ollama, not scan cost. | `analysis/summarise_load.py --runs results/runs` → the `GET /search` sampler rows of `analysis/output/load/load_per_run_by_label.csv` (one p95 per run; all three must be ≤ 2 s) |

Each load requirement (R1, R2, R5) is judged on the worst of the three runs (highest per-run p95, error rate and span; not the mean). The mean and spread are reported alongside.

---

## Notes on each row — what makes it testable

### R1 — response time for `POST /tickets`

* **What the number must be.** A latency, with its unit, that an agent waiting on a triage result
  would accept. Derive it from usability rather than from what the hardware happens to manage:
  deciding the threshold from a measurement you have already seen is circular, and the brief asks
  for requirements set *before* the benchmarks.
* **Percentile.** Required. Our analysis reports p50, p95 and p99 for every run, so the
  requirement may bind any of them; say which, and say it in the same words the analysis output
  uses. 
  Percentile: p95. The requirement uses p95 because the client needs most requests to remain responsive while allowing a small number of slower requests caused by transient system or model-inference variation. p95 is less dominated by individual extreme outliers than p99 and is therefore the chosen percentile for the latency requirement.
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
  `UNPARSEABLE` responses count as incorrect classifications for both overall and per-category accuracy. A response that cannot be mapped to one of the seven required categories therefore contributes to the error count rather than being treated as a correct or excluded result.

### R4 — per-category accuracy

* **What the number must be.** A floor that every category must clear, or a floor per category if
  some matter more to the client than others. A high overall accuracy can hide a category the
  model never gets right, which is exactly the failure a routing system cannot afford — the brief
  asks for per-category accuracy for this reason.
* **Percentile.** Not applicable; write `n/a`.
* **Load condition.** As R3: measured serially on the golden set.
* **Justification.** Say which categories the client cannot afford to misroute and why. If you set
  one floor for all seven, justify that too.
* **Watch out.** The golden set holds 200 tickets across seven categories, with per-category counts from 19 to 41, so 
   some categories will have few examples and their accuracy will be a coarse fraction. Acknowledge that
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

* [x] Every `TODO` in the table above is replaced by a real decision.
* [x] Every threshold has a unit.
* [x] Every requirement that is measured across many requests names a percentile; the ones that
      are not say `n/a` rather than being left blank.
* [x] Every requirement names its load condition: arrival rate, plan and candidate model — or
      states explicitly that it is measured serially.
* [x] If `workload_model.md` implies a peak, at least one requirement holds *at the peak*, and the
      arrival-rate list contains a rate at or above that peak.
* [x] Every justification points at a specific figure in `workload_model.md`.
* [x] Every row's *How it will be measured* column names a script that exists and an output we
      will actually produce. Walk the list with Part 1 — Yeo Kai Yuan.
* [x] The error-rate ceiling for R2 is stated.
* [x] The treatment of `UNPARSEABLE` in R3 and R4 is stated.
* [x] The cost position below is written.
* [x] `workload_model.md` and this file agree with each other.
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

**Position: a misrouted ticket costs the client more than a slow triage.** A misrouted complaint is read, bounced and re-routed, so an agent's handling time is spent twice and the customer's complaint reaches the right team late. A slow triage still produces the correct routing decision and needs no rework, provided it stays within the 10 s p95 requirement.

This is reflected in the requirements: R3 (≥ 90%) and R4 (≥ 80% per category) are strict, while R1 allows 10 s at p95 rather than a millisecond-level target. When candidates trade accuracy against latency, correct routing takes priority.

**What would change this position:** if the measured p95 latency of a model that meets R3 and R4 exceeds the 10 s R1 threshold, or if a model cannot sustain the 12 req/min capacity test in R2 without a growing queue, responsiveness would need more weight against accuracy.

**Order of concession if no candidate meets every requirement:** R5 is relaxed first, then R2's throughput target, then the R1 latency threshold. R3 and R4 are relaxed last, because accuracy is what the position says matters most.

