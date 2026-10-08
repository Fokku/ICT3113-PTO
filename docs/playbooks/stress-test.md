# Playbook — stress test (stepped open-loop ramp, to find a limit)

**What this document is for.** It is the procedure for the one stress test the brief requires in Step 5:
*"Design and execute one test that determines a limit of the system under test, for at least one candidate
model."* It is also the **authoritative record of the ramp's step boundaries**, because
`analysis/stress_summary.py` has to be *told* where the steps fall — that coupling is not enforced in code.

**Owner:** Part 5 — Koh Tong Wei.

**What "done" looks like.** One completed stress run directory under `../../results/runs/`, reconciling
cleanly with the service log; a per-step table under `../../analysis/output/stress/` that names the first step
at which the system breached the limit; and a one-sentence statement of the limit with the criterion that
defines it.

**Feeds:** Slide 8 (Playbook) and Slide 9 (the stress test and the limit it found).

**Related playbooks:** `load-test.md` — its preconditions (sections 2.1 to 2.4) and its open-loop
configuration (section 3) apply here in full and are **not** repeated. Read it first. This document covers
only what is different about the ramp.

**Conventions used in every command below.** Every command is run **from the repository root**, and `python`
means the repository's own virtual environment — `.venv/bin/python`, or activate it first with
`source .venv/bin/activate`. Anything in `<angle brackets>` is for you to substitute; every number in a
command is the team's decided value, with its source named next to it.

---

## 1. The limit this test looks for

The brief allows any meaningful limit. **Ours is: the highest ticket arrival rate at which the baseline still
answers within the response-time requirement and without an unacceptable error rate.** The last step that
still met both criteria is the answer; the first step that breached either one is the limit.

Two criteria, both set by Part 4 rather than by this playbook:

| Criterion | Value | Source |
|---|---|---|
| p95 response-time limit | **10 000 ms** | `../../workload/requirements.md`, requirement **R1**. Passed to the analysis as `--p95-limit-ms 10000` |
| Error-rate limit | **5%** | `../../workload/requirements.md`, requirement **R2** (≤ 5% errors). Passed as `--error-rate-limit 0.05` |

`analysis/stress_summary.py` also reports an **unbounded-growth signal**: whether the p95 rises monotonically
across the last few steps (`--monotonic-steps`, default 3). That is the "latency grows without bound" version
of a limit, and it can fire even where the p95 has not yet crossed the requirement. Report whichever criterion
actually fired, and say which one it was.

### 1.1 Why a staircase rather than a smooth ramp

A smooth linear ramp never gives the service a steady state at any particular rate, so a p95 computed over the
ramp belongs to no rate you could quote to a client. Flat steps mean each step yields its own p50/p95/p99,
throughput and error rate, and the limit is then simply "the last step that still met the requirement".

### 1.2 Why it must be open-loop, and why that matters more here than anywhere else

On a stress test the closed-loop failure is fatal, not merely inconvenient. With a fixed pool of N threads the
offered rate is `N / response_time`, so the harder the service struggles the less work it is sent: measured
throughput converges on the service's own service rate **by construction**, the queue in front of Ollama never
grows, and the plan can never find a limit because it never exceeds one. A closed-loop "stress test" reports
that the system coped with everything you offered it, because you only ever offered it what it could cope with.

`stress_ramp.jmx` uses a single **Open Model Thread Group**. The schedule string, and the six literal steps, are
in section 3. See `load-test.md` section 3 for the full open-loop argument that Slide 8 needs.

### 1.3 What the baseline does not have, and why we are not adding it

There is **no concurrency limit anywhere in the service**: in-flight model calls are bounded only by Ollama's
own parallelism and its internal queue, and the service applies no backpressure. That is the behaviour this
test exists to measure and record, not to fix.

A2 candidate: a bulkhead or semaphore around the model call, and backpressure — a `429`, or a queue with a
bounded wait — instead of unbounded queueing. The plan records the same candidate in its own
`TestPlan.comments`, because this is the test that exposes it. Do not implement any of it before the
baseline has been measured: the whole point of Slide 9 is that there is something left to optimise.

---

## 2. THE STEP BOUNDARIES (this is the authoritative copy)

`analysis/stress_summary.py` cannot infer the schedule from the results file — the offered rate is a property
of the JMeter plan, not of the `.jtl` — so it must be told. These are the boundaries **we run**, chosen by Part 4
in `../../workload/workload_model.md` ("Stress ramp"): `RAMP_START_PER_MIN=1`, `RAMP_STEP_PER_MIN=4`,
`RAMP_STEPS=6`, `RAMP_STEP_DURATION_S=120`, and the harness's drain of `DRAIN_S` = 150 s (passed as
`ramp_drain_s`; it was the plan default of one step duration, 120 s, until 8 October 2026 — see section 2.2):

| Step | Offered rate | Window (seconds from test start) | Expected arrivals |
|---|---|---|---|
| 1 | 1 / min | 0 – 120 | 2 |
| 2 | 5 / min | 120 – 240 | 10 |
| 3 | 9 / min | 240 – 360 | 18 |
| 4 | 13 / min | 360 – 480 | 26 |
| 5 | 17 / min | 480 – 600 | 34 |
| 6 | 21 / min | 600 – 720 | 42 |
| drain | no new arrivals | 720 – 870 | 0 |
| | | **total** | **132 tickets** |

Total wall-clock per run: `6 × 120 s + 150 s` = **870 s (14.5 minutes)**. JMeter always honours a pause in full,
so the thread group lasts the whole 870 s even if every request has already finished. The top step (21/min) is
above the highest steady-state load rate (12/min), so the ramp brackets requirement R2.

Arrivals are a **Poisson** process (`random_arrivals`), so the per-step counts vary around those figures. That
is the arrival process, not a fault.

> **The same table exists in three places:** here, in `../../jmeter/README.md` section 3, and in the
> `TestPlan.comments` of `../../jmeter/stress_ramp.jmx`. Change one and you must change all three. This copy
> is the one the analysis command in section 6 is written against.

### 2.1 Where the rates came from, and the pre-registered contingency

The staircase is Part 4's (8 October 2026; it replaced the plan's placeholder default of 30–180/min). Its top
step only finds a limit for a model whose capacity is below about 21 tickets per minute — a service time above
about 3 s per ticket. The prediction record expects that of `qwen2.5:7b` and not necessarily of the faster
models. So, decided **before** any stress run and recorded here so that it is not a choice made after seeing
results: **if this ramp finds no limit for a model, one second, steeper arithmetic ramp is run for that model —
`RAMP_START_PER_MIN=10`, `RAMP_STEP_PER_MIN=10`, 6 steps of 120 s (10, 20, 30, 40, 50, 60 per minute),
`--duration 870`, `--offered-rates 10,20,30,40,50,60`.** Both runs are reported. If neither finds a limit, Slide 9
says "no limit below 60 tickets/minute" for that model.

### 2.2 Why there is a drain pause

**Its length, decided 8 October 2026 before any real run: 150 s**, passed by `scripts/run_load_test.sh` as
`ramp_drain_s` (its `DRAIN_S`). The service gives up on a model call after `OLLAMA_TIMEOUT_S` = 120 s, so a
drain longer than that guarantees every request still in flight at the end of step 6 either completes or
receives the service's own 502 before JMeter stops. A drain equal to the timeout (the old 120 s) left a race
at the very end of the ramp. The steady-state plans got the same drain for the same reason; see
`../../jmeter/README.md`, "The drain on the steady-state plans".

An Open Model Thread Group interrupts its threads as soon as the schedule ends, and an interrupted in-flight
request is recorded as a **failed** sample. At the top step a CPU-only model call can easily still be running
when the last step ends, so without a drain the plan would manufacture a burst of errors at the end that look
exactly like the limit we are hunting for. The drain admits no new arrivals and lets the outstanding requests
finish, so they are recorded as the latencies they really were.

Because no arrival occurs during the drain, the drain window contributes no sample **start** times, so the
analysis normally sees six steps and not seven. See section 6.1 if it reports seven.

---

## 3. The open-loop configuration (for Slide 8)

One Open Model Thread Group, whose schedule concatenates the six steps literally — JMeter cannot loop a
schedule string, and the `${__groovy(...)}` loop trick was rejected on purpose because it hides the actual
rates from anyone reading the plan. The shape, with the property expressions reduced to their meaning:

```
rate(<step 1 rate>/min) random_arrivals(<step duration> sec) rate(<step 1 rate>/min)
rate(<step 2 rate>/min) random_arrivals(<step duration> sec) rate(<step 2 rate>/min)
...
rate(<step 6 rate>/min) random_arrivals(<step duration> sec) rate(<step 6 rate>/min)
pause(<drain> sec)
```

The literal string, as it appears in the plan for step 1, is:

```
rate(${__P(ramp_rate_1,${__groovy((props['ramp_start_per_min'] ?: '30').toInteger())})}/min) random_arrivals(${__P(ramp_step_duration_s,120)} sec) rate(${__P(ramp_rate_1,${__groovy((props['ramp_start_per_min'] ?: '30').toInteger())})}/min)
```

### 3.1 Every property the plan takes

| Property | Default | Meaning |
|---|---|---|
| `ramp_start_per_min` | `30` | Rate of step 1, when `ramp_rate_1` is not given |
| `ramp_step_per_min` | `30` | Increment between steps, when `ramp_rate_<k>` is not given |
| `ramp_rate_1` … `ramp_rate_6` | `ramp_start_per_min + (k-1) × ramp_step_per_min` | One step's rate, in tickets per minute. Each step has its own property so a single step can be raised without editing the schedule |
| `ramp_step_duration_s` | `120` | How long each step holds its rate |
| `ramp_drain_s` | same as `ramp_step_duration_s` | The trailing pause |
| `ramp_steps` | `6` | **Recorded, not obeyed.** The schedule contains six steps written out literally. This property exists so the value the operator intended appears in `jmeter.log`; changing it does not change the schedule. To add a seventh step, add one line to the schedule string and update all three copies of the boundary table |
| `random_seed` | `0` | Open-model arrival seed. `0` means a fresh arrival pattern per run |
| plus the properties shared with the other plans | | `host`, `port`, `input_csv`, `connect_timeout_ms` (10000), `response_timeout_ms` (180000) — see `../../jmeter/README.md` section 3 |

`response_timeout_ms` deserves attention here specifically: at **180 s** it is deliberately longer than the
service's own `OLLAMA_TIMEOUT_S` of 120 s, so that a slow request is recorded as the service's real latency
rather than as a load-generator timeout. On this plan that number is part of the definition of "failure" —
**record the value you used** with the result.

### 3.2 What `scripts/run_load_test.sh` can and cannot set

This matters, because it decides what staircase you can actually run through the sanctioned harness.

| Property | Reachable through `run_load_test.sh`? | How |
|---|---|---|
| `ramp_start_per_min` | yes | `--rate N` (or the `RAMP_START_PER_MIN` environment variable, which wins) |
| `ramp_step_per_min` | yes | `RAMP_STEP_PER_MIN=<n>` in the environment |
| `ramp_step_duration_s` | yes | `RAMP_STEP_DURATION_S=<n>` in the environment |
| `ramp_steps` | yes (recorded only) | `RAMP_STEPS=<n>` in the environment |
| `ramp_rate_1` … `ramp_rate_6` | **no** | Not passed by the script. Only an *arithmetic* staircase is reachable through the harness |
| `ramp_drain_s` | **no** | Not passed by the script; the plan's default (one step duration) applies |

So: **choose an arithmetic staircase** — `start + k × step` — and the harness runs it, produces the run
directory, the freeze verdict and the metadata, and the result is evidence. A hand-tuned staircase (raising
only the top step, say) can only be run by invoking JMeter directly, which produces no `metadata.json` and no
`freeze.json` and is therefore a diagnostic, not evidence.

Part 4's rates (1, 5, 9, 13, 17, 21) are an arithmetic progression, so the harness runs them as they are.

---

## 4. How many runs

The brief asks for *"One stress test"*, so one run satisfies it. But the limit this test reports is a single
observation, and a Poisson arrival pattern differs between runs (`random_seed=0`).

**Decision: once per candidate model, for all four candidates.** One run satisfies the brief; running the ramp
for every candidate (14 minutes each) shows how the limit moves with model size, which is the trade-off the
engagement is about. The limit each run found is reported per model, never averaged. The run for the model we
recommend is the one Slide 9 leads with; the others give the comparison. `scripts/run_campaign.sh` runs them
last, after every model's accuracy, load and mixed tests, so that if time runs short what is lost is
comparison, not a requirement.

---

## 5. Procedure

Sections 2.1 to 2.4 of `load-test.md` are preconditions here too: the freeze gate, the separate machines, the
`SERVICE_SSH` remote-mode plumbing, JMeter 5.6+, Java 17 or 21, the pinned model digest, synchronised
clocks, an empty database, a clean working tree, and the `.jtl` column pinning in its section 3.4. Do not skip
them because this is "just the stress test" — a stress run is the one most likely to be invalidated by a
saturated load generator.

**1. Confirm the freeze gate (load generator).**

```bash
python scripts/freeze_gate.py --json
```

**2. Confirm the service and the model (load generator).**

```bash
curl -s http://<service-host>:8000/health | python -m json.tool
```

Check `status`, `model_tag`, `model_digest` against the pin, `ollama_reachable`, `ollama_base_url` and
`num_ctx`.

**3. Run the ramp (load generator).**

```bash
export SERVICE_SSH=<user>@<service-host>                  # see load-test.md section 2.3
export RUN_NOTES="stress ramp 1/5/9/13/17/21 per min, 120 s steps, 150 s drain; operator <name>"

# The staircase. These must match the boundary table in section 2.
export RAMP_START_PER_MIN=1
export RAMP_STEP_PER_MIN=4
export RAMP_STEP_DURATION_S=120
export RAMP_STEPS=6                                       # recorded in jmeter.log; the schedule is six steps

scripts/run_load_test.sh \
    --plan stress_ramp \
    --model <ollama-tag> \
    --rate 1 \
    --duration 870 \
    --runs 1 \
    --host <service-host> \
    --port 8000 \
    --yes
```

Two things about the flags that will otherwise confuse you:

* **`--rate` is step 1's rate, not the whole ramp's rate.** The run directory is named `…_ramp_run<k>` rather
  than `…_<rate>pm_run<k>`, precisely because the rate changes during the run and cannot be labelled with one
  number.
* **`--duration` does not control the ramp.** The script passes it as `-Jduration_s`, which `stress_ramp.jmx`
  does not use: the schedule's length comes from `ramp_step_duration_s` and `ramp_drain_s`. It is required by
  the CLI and it is recorded in `metadata.json` as `duration_s`, so set it to the **true total wall-clock** of
  the ramp, or the run's own metadata will misdescribe it.

`--yes` skips the confirmation prompt. Read what you are agreeing to: each run calls `scripts/reset.sh --yes`,
which **destroys every ticket stored in the service's database**. That is deliberate — `GET /search` is a
full-table scan, so each run must start empty.

**4. Confirm the resolved rates before you trust the run (load generator).** This is the cheapest check in
this playbook and it catches a mistyped property:

```bash
grep -i "schedule" results/runs/<run-dir>/jmeter.log
```

JMeter prints a `Starting OpenModelThreadGroup … with schedule …` line with **all six resolved step rates**.
If they are not the rates in section 2's table, the run measured a different staircase from the one you are
about to report.

**5. Reconcile (load generator).**

```bash
python analysis/reconcile.py --run-dir results/runs/<run-dir>
```

Exit 0 or the run is not evidence. Note that at the top steps the client-minus-server latency disagreement
grows for real reasons (queueing happens inside the service, and both sides see it), so if this fails at a
high step, read the report before assuming a clock problem.

**6. Summarise the steps (load generator).** This is the command that produces the limit:

```bash
python analysis/stress_summary.py \
    --run-dir results/runs/<run-dir> \
    --step-seconds 120 \
    --offered-rates 1,5,9,13,17,21 \
    --p95-limit-ms 10000 \
    --error-rate-limit 0.05
```

Equivalently, for an arithmetic staircase, `--ramp-start-per-min` with `--ramp-step-per-min` instead of
`--offered-rates`. Give one or the other, not both — the explicit list wins and the script warns.

Omit `--p95-limit-ms` and only the error-rate criterion is assessed; omit the offered rates altogether and the
offered-versus-achieved saturation signal cannot be assessed at all and the offered column reads `n/a`. Both
degradations are stated in the report, which is why they are safe but not acceptable: supply the numbers.

Writes the per-step table, the chart and the report into `analysis/output/stress/`.

**7. Diagnose where the time went (load generator).**

```bash
python analysis/bottleneck_hints.py --run-dir results/runs/<run-dir>
```

Breaks the latency down from the service log's own timings and Ollama's reported durations: service overhead,
the queue/transport residual, model load, prompt evaluation and generation, plus token throughput and a
`num_ctx` truncation check. On a stress run this is the evidence behind the sentence "the bottleneck is X" on
Slide 9 — but the queue term is a **residual**, not a measured quantity. Read the module docstring before
quoting it.

**8. Commit the run directory and the regenerated `analysis/output/stress/`.**

---

## 6. What to observe while it runs

| Watch | Where | What is fine, and what is not |
|---|---|---|
| The rising sample count per step | the script's stdout (kept as `jmeter_stdout.txt`); the summariser prints every 30 s | Should rise step by step roughly in proportion to the offered rates. If it stops rising while the offered rate does, that **is** the saturation you came to find — do not stop the run, let the ramp finish |
| Errors appearing | same | Expected at the top steps: that is the limit. `502` from the service (a model error or `ollama_timeout`) and `Non HTTP response code: …` from the load generator's own 180 s read timeout mean different things — split by `responseCode` before interpreting |
| **Load generator CPU** | `top` on the load generator, continuously | The single most important thing to watch on this test. The top steps offer the highest rate of the whole campaign, so this is where JMeter is most likely to run out of CPU and start recording its own delay as service latency. See the abort criterion in section 7 |
| Service host CPU and memory | `top` / `free -h` on the service host | Ollama should dominate. If the machine starts swapping, latency becomes disk latency and the limit you find is a memory limit wearing a throughput limit's clothes — which is a legitimate finding, but only if you say so |
| The service still answering at all | `curl -s http://<service-host>:8000/health` from a third shell | `/health` is not written to the request log, so this is free. A `degraded` status or an unreachable Ollama part-way through the ramp changes the meaning of every step after it |
| Wall clock | your watch | The run lasts `6 × step + drain`. If it ends early, the plan did not run to completion and the top steps are missing |

### 6.1 If `stress_summary.py` reports seven steps

`--step-seconds` slices equal windows from the first measured sample, and the number of windows is
`ceil(span / step_seconds)`. Normally the drain contributes no arrivals, so the span ends inside step 6 and you
get six windows. If a boundary effect gives you seven, the script will say
`--offered-rates has 6 value(s) but the data covers 7 step(s)`. Append a trailing `0` for the drain window:

```
--offered-rates 30,60,90,120,150,180,0
```

An offered rate of `0` makes the tracking ratio `n/a` for that window rather than inventing one, and
`--min-step-fraction` (default 0.5) drops a window covered by less than half its nominal duration as a
fragment, with a warning. **Read the warnings the report prints.** A step reported as empty, or a step dropped
as partial, means the boundaries do not match the schedule — fix the boundaries, not the report.

---

## 7. Abort and retry: what makes a stress run invalid

Everything in `load-test.md` section 8 applies. These are the ones specific to the ramp:

| Abort criterion | How you detect it | Why it voids the run |
|---|---|---|
| **The load generator saturated its own CPU** | `top` during the top steps; afterwards, an achieved rate well below the offered rate at a step where the **service reported no errors**, or scheduler warnings in `jmeter.log` | The "limit" you found would be the load generator's limit, not the system's. This is the most likely way to get a plausible-looking wrong answer out of this test |
| **The resolved step rates in `jmeter.log` are not the rates you intended** | step 4 of section 5 | The run measured a different staircase from the one being reported |
| **`--step-seconds` does not equal the `ramp_step_duration_s` that was actually used** | compare `RUN_NOTES` / your run log against the analysis command | Every per-step figure is sliced at the wrong place. Nothing in the code catches this: it is the one coupling in this test that is documentation only |
| **The ramp did not run to completion** | the run ended before `6 × step + drain`; or the top steps have far fewer samples than expected | You have no top step, so you have no limit — only a lower bound |
| **A step reported as containing no samples at all** | a warning from `stress_summary.py` | Either the boundaries are wrong or the generator stopped sending. Both void the per-step table |
| **Ollama restarted, was reloaded, or evicted the model mid-ramp** | `load_duration` in `service.jsonl` becoming non-trivial again part-way through; `docker logs` on the Ollama host | A model reload in the middle of a ramp puts a load cost into a measured step, and the step it lands in will look like the limit |
| **The service host started swapping** | `free -h` during the run; `Total swap` in the machine's capture file | The limit found is a memory limit. It is reportable as such, but not as a throughput limit — and the two have very different implications for the client's server sizing |
| **The database was not empty at the start** | `GET /stats` before the measured window | `GET /search` is a full-table scan. Not relevant to this plan's own samples (it posts only), but it changes the service's overall load profile |
| **You stopped the run because it "looked bad"** | honesty | A ramp that produces errors at the top is the test working. Let it finish and let the drain do its job; an interrupted ramp manufactures failures that are indistinguishable from real ones |

**Retry rule.** Re-run the whole ramp. A ramp assembled from the good steps of two different runs is not a
measurement of anything.

---

## 8. Record this in the run log

Everything in `load-test.md` section 7, plus these, which are specific to the stress test and which no script
can capture:

1. **The staircase you actually ran** — the six rates and the step duration — in the same words as the boundary
   table in section 2. This is the number the analysis has to be told, so it must be written down by a human
   before it is typed into `stress_summary.py`.
2. **The `response_timeout_ms` in force** on the load generator (default 180000), because on this test it is
   part of the definition of a failed sample.
3. **Which criterion fired** — the p95 limit, the error-rate limit, or the monotonic-growth signal — and at
   which step. One sentence, in the form "the limit is `<rate>` tickets per minute, defined as the highest step
   at which `<criterion>` still held".
4. **What you saw on each machine at the top steps**: load generator CPU, service host CPU, memory and swap.
   This is what turns "it fell over" into a diagnosed bottleneck.
5. **Whether the ramp ran to completion**, including the drain.
6. **Your verdict**: reportable, or a rehearsal.

The short version goes into `metadata.json` via `RUN_NOTES`. Put the staircase in it — it is the one fact a
future reader cannot recover from the run directory alone:

```bash
export RUN_NOTES="stress ramp 1/5/9/13/17/21 per min, 120 s steps, 150 s drain; operator <name>"
```

---

## 9. Common failures and what they mean

`load-test.md` section 9 covers the shared ones (JMeter not found, `/health` timeouts, missing `.jtl` columns,
clock skew, silent Groovy failures). These are specific to the ramp:

| Symptom | Almost always means | Do this |
|---|---|---|
| `stress_summary.py`: `--offered-rates has N value(s) but the data covers M step(s)` | The slicing produced a different number of windows from the rates you supplied — usually the drain boundary effect | Section 6.1. Do not pad the list with a guessed rate; use `0` for a drain window |
| `stress_summary.py`: "Step N contains no samples at all" | The boundaries do not match the schedule, or the generator stopped sending | Check `--step-seconds` against `ramp_step_duration_s`, then check `jmeter.log` for the resolved schedule |
| `stress_summary.py`: "No usable steps: every window was empty or partial" | `--step-seconds` is wildly wrong, or the run produced almost no samples | Recheck both against section 2's table. A run with almost no samples is a failed run, not a slicing problem |
| `stress_summary.py` warns that no offered rate was supplied | `--offered-rates` and the `--ramp-*` pair were both omitted | Supply them. Without them the offered column is `n/a` and the saturation signal cannot be assessed, which loses half the point of the test |
| Every step's p95 is roughly the same, and no step breaches anything | The whole staircase sits below the service's capacity | The test found no limit because it never approached one. Raise the rates — this is why the staircase must bracket the throughput requirement rather than sit under it |
| Step 1 is already breaching the p95 limit | The requirement is tighter than the baseline can meet even unloaded, or the model was cold | Check `warmup.jsonl` exists and `load_duration` in `service.jsonl` is trivial for the measured samples. If the baseline genuinely misses R1 at the lowest step, that is a finding for Slide 9 and Slide 11, stated plainly |
| The achieved rate tracks the offered rate perfectly right to the top step, with no errors | Either the service really does cope (possible, and a fine result), or the generator is the thing setting the pace | Check the load generator's CPU and `jmeter.log`. `--tracking-tolerance` (default 0.05) is the jitter allowance the report uses; it is not a service-level threshold |
| Errors only in the last few seconds of the run | The drain did not happen, or was too short for the slowest in-flight request | Confirm `pause(...)` ran — the run should last `6 × step + drain`. Raise the drain with `-Jramp_drain_s` (which means running JMeter by hand; see section 3.2) |
| `reconcile.py` fails only on a high-step run | Real queueing inside the service widens the client-minus-server latency difference, and clock skew adds to it | Read the reconcile report before assuming a clock problem. Do not raise `--latency-threshold-ms` to make a run pass; if the difference is genuinely the network, measure the round-trip and record it in `../test-environment.md` section 3 |
