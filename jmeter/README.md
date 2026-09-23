# JMeter test plans

**What this document is for.** It explains the three JMeter plans in this
directory: what each one measures, every `-J` property they take and its default,
how a JMeter sample is tied back to a service log line, and why not one of them
uses a closed-loop thread group. Read it before running a test and before editing
a `.jmx`.

**Owner:** Part 1 — Yeo Kai Yuan (test harness).
`TODO(Yeo Kai Yuan): replace with real name` if the repository should carry a
different owner for this directory.

**Done looks like:** a teammate who has never opened JMeter can run any of the
three plans from `scripts/run_load_test.sh`, and can say what every number in the
resulting `.jtl` means and which service log line it came from.

**Feeds:** slide 8 (playbook / testing procedure) and slide 9 (load and stress
results).

Target version: **Apache JMeter 5.6.3**. The Open Model Thread Group is required
and only exists from 5.5 onwards, so 5.4 and earlier will not open these plans.

---

## 1. The three plans

| Plan | Thread groups | What it measures |
|---|---|---|
| `load_post_tickets.jmx` | one, POST `/tickets` | Steady state. Tickets arrive at a fixed rate for a fixed duration and nothing else touches the service. This is the plan behind the response-time and throughput requirements. |
| `mixed_load.jmx` | two, concurrent: POST `/tickets` and GET `/search` | Interference. Agents search while the classifier is busy. This is the plan behind a requirement of the form "GET /search stays under X ms at the p95 while tickets arrive at Y per minute". |
| `stress_ramp.jmx` | one, POST `/tickets`, six rising steps | A limit. The arrival rate climbs step by step until the baseline stops meeting the requirement, and the last step that still met it is the answer. |

All three post the same JSON body to the same endpoint with the same headers and
the same sampler label (`POST /tickets`), so results from different plans at the
same arrival rate are directly comparable. That is deliberate; do not rename a
sampler.

### What the plans deliberately do NOT contain

* No warm-up sampler. `scripts/run_load_test.sh` sends one warm-up request with
  `X-Warmup: 1` before the run, and its log line is kept in `warmup.jsonl`,
  separate from the measured samples. A warm-up inside the plan would land in the
  `.jtl` and drag the p99 up with the one-off model load cost.
* No think time, no cookie manager, no cache manager, no client-side retries.
* No assertion on the returned category. See section 5.
* Nothing that makes the service look faster than it is. The baseline is meant to
  be measured, not flattered; optimisation is Assignment 2.

---

## 2. Why every thread group is open-loop

Every thread group in this directory is an **Open Model Thread Group**, which is
an open-loop, arrival-rate model: JMeter works out in advance *when* each request
arrives and starts a thread for it, whether or not earlier requests have come
back. The rate you ask for is the rate the service is offered.

A closed-loop thread group — JMeter's ordinary Thread Group with N threads in a
loop — cannot be used here, and the reason is not stylistic:

1. **It self-throttles.** The offered rate is `N / response_time`. The moment the
   service slows down, the load generator slows down with it, so the test stops
   offering the rate you are claiming to have tested. A latency figure from such a
   run cannot honestly be attributed to any arrival rate.
2. **It hides queue build-up.** Nothing ever queues, because nothing new arrives
   until something old has finished. Queue growth in front of Ollama is precisely
   the failure mode this assignment asks us to find.
3. **It makes a stress test impossible.** A closed-loop stress test will always
   report that the system coped, because you only ever offered it what it could
   cope with. The measured throughput converges on the service's own service rate
   by construction.

The assignment brief settles it: *"Traffic must be generated open-loop, at
controlled arrival rates: use the Open Model Thread Group or the Precise
Throughput Timer... Results from closed-loop tests will not be accepted as
evidence against throughput or latency requirements."*

Each `.jmx` repeats this argument in its `TestPlan.comments`, so it is visible to
anyone who opens the plan in the GUI rather than reading this file.

`random_arrivals` is a Poisson process, not evenly spaced arrivals. Real complaint
intake clumps, and evenly spaced arrivals would understate the concurrency the
service sees at a given mean rate.

---

## 3. Properties

Everything is set with `${__P(name,default)}`, so every plan runs with no flags at
all and every value can be overridden on the command line. Relative file defaults
are relative to **this directory** (`jmeter/`), because that is how JMeter resolves
a relative CSV path — it resolves against the directory holding the `.jmx`.
`scripts/run_load_test.sh` passes absolute paths.

### Used by all three plans

| Property | Default | Meaning |
|---|---|---|
| `host` | `SET-JHOST-TO-THE-SERVICE-HOST` | Hostname or IP of the triage service. There is no sensible default: the brief requires the load generator to run on a **different machine** from the service, so the default is an invalid hostname that fails immediately with `UnknownHostException` rather than quietly measuring a co-hosted run. |
| `port` | `8000` | Service port (`SERVICE_PORT` in `.env`). |
| `input_csv` | `../data/dev/synthetic_tickets.csv` | Ticket source, columns `row_number,narrative,raw_label`. **Defaults to the synthetic dev tickets on purpose.** No team row may reach a model before the golden set and the prediction record are committed and tagged; `run_load_test.sh` only passes `data/team_rows.csv` once `scripts/freeze_gate.py` has passed. |
| `connect_timeout_ms` | `10000` | TCP connect timeout. |
| `response_timeout_ms` | `180000` | Read timeout, deliberately longer than the service's `OLLAMA_TIMEOUT_S` of 120 s. If JMeter gave up first we would record a load-generator timeout instead of the service's real latency. A sample that does hit 180 s is a genuine failure of the system under test to answer within three minutes. On the stress plan this number is part of the definition of "failure" — record the value you used. |
| `random_seed` | `0` | Open Model Thread Group seed. `0` means a fresh arrival pattern per run, so the spread across the three repeat runs includes arrival variability. A non-zero value repeats the same arrival pattern every run. |
| `jtl_out` | *(empty)* | Optional results path for the plan's own Simple Data Writer, for running a plan by hand or from the GUI without `-l`. Left empty it writes nothing. `run_load_test.sh` uses `-l` instead. |

### `load_post_tickets.jmx` and the POST stream of `mixed_load.jmx`

| Property | Default | Meaning |
|---|---|---|
| `rate_per_min` | `60` | Ticket arrival rate, tickets per minute. |
| `duration_s` | `300` | Length of the measured window, seconds. Both of `mixed_load.jmx`'s streams use this same property so they start and stop together. |

Expected samples per run is `rate_per_min / 60 * duration_s`. Because arrivals are
Poisson the actual count varies around that, and at a very low rate over a very
short window the expected count can be below one, in which case a run can
legitimately produce **zero** samples. That is the arrival process, not a broken
plan.

### `mixed_load.jmx` only

| Property | Default | Meaning |
|---|---|---|
| `search_rate_per_min` | `60` | Agent search rate, searches per minute. `TODO(Part 4 — Teammate C)`: this is a workload figure and Part 1 has not invented one. The default is deliberately the same number as `rate_per_min`'s default so that it is visibly a placeholder rather than a measured agent-to-ticket ratio. |
| `search_terms_file` | `../data/search_terms.txt` | The query strings. See section 6. |
| `search_random_seed` | `0` | Seed for the search stream, separate from `random_seed`. If you want reproducible arrival patterns, give the two streams **different** non-zero seeds: JMeter's documentation warns that two thread groups sharing one non-zero seed can fire their samples at the same instants, which would manufacture a collision no real workload has. |

`limit` on `GET /search` is the literal `50` and is not a property. It decides how
much JSON the service must serialise for a query that matches many tickets, so
changing it changes what a response-time requirement means. If a different page
size is ever tested, add a second sampler with a different label rather than
editing this one, so old and new results stay distinguishable in the `.jtl`.

### `stress_ramp.jmx` only

| Property | Default | Meaning |
|---|---|---|
| `ramp_step_duration_s` | `120` | How long each of the six steps holds its rate. |
| `ramp_drain_s` | *same as* `ramp_step_duration_s` | Trailing pause: no new arrivals, but requests already in flight are allowed to finish. See below. |
| `ramp_start_per_min` | `30` | Rate of step 1, when `ramp_rate_1` is not given. |
| `ramp_step_per_min` | `30` | Increment between steps, when `ramp_rate_<k>` is not given. |
| `ramp_rate_1` … `ramp_rate_6` | `ramp_start_per_min + (k-1) * ramp_step_per_min` | The rate of one step, in tickets per minute. Each step has its own property so a single step can be changed without editing the schedule. |
| `ramp_steps` | `6` | **Recorded, not obeyed.** The schedule contains six steps written out literally, because JMeter cannot loop a schedule string. This property exists so the value the operator intended appears in `jmeter.log` and can be stamped into `metadata.json`; changing it does not change the schedule. To add a seventh step, add one line to the schedule string and update this file and the playbook. |

So `-Jramp_start_per_min=12 -Jramp_step_per_min=12` gives 12/24/36/48/60/72 per
minute, while `-Jramp_rate_6=240` raises only the top step and leaves the rest
alone.

**The step boundaries.** With every property at its default:

| Step | Offered rate | Window (s from test start) | Expected arrivals |
|---|---|---|---|
| 1 | 30 / min | 0 – 120 | 60 |
| 2 | 60 / min | 120 – 240 | 120 |
| 3 | 90 / min | 240 – 360 | 180 |
| 4 | 120 / min | 360 – 480 | 240 |
| 5 | 150 / min | 480 – 600 | 300 |
| 6 | 180 / min | 600 – 720 | 360 |
| drain | no arrivals | 720 – 840 | 0 |
| | | **total** | **1,260 tickets** |

`analysis/stress_summary.py` has to be *told* where the boundaries are. Pass it
the same number you passed to JMeter:

```
python analysis/stress_summary.py --run-dir results/runs/<dir> --step-seconds 120
```

That coupling is not enforced in code, which is why it is written in three places:
here, in the plan's own comments, and in `docs/playbooks/stress-test.md`. Change
one and you must change all three.

**Why there is a drain pause.** An Open Model Thread Group interrupts its threads
as soon as the schedule ends, and an interrupted in-flight request is recorded as
a *failed* sample. At the top step a CPU-only model call can easily still be
running when the last step ends, so without a drain the plan would manufacture a
burst of errors at the end that look exactly like the limit we are hunting for.
The drain admits no new arrivals and lets the outstanding requests finish, so they
are recorded as the latencies they really were. Note that JMeter always honours a
pause in full, so the thread group lasts `6 × ramp_step_duration_s + ramp_drain_s`
seconds even if every request has already finished.

**The same artefact exists, unfixed, in the other two plans.** Their schedule
string is fixed by the build contract as
`rate(...) random_arrivals(... sec)` with no trailing pause, so the handful of
requests still in flight when the window closes are recorded as failures. At
60 tickets/min with a two-second service time that is on the order of two samples
in three hundred, well under a one-percent error rate, but it is a real floor on
the error rate a load run can report.
`TODO(Yeo Kai Yuan): decide whether to add pause(...) to the two steady-state
plans as well. It would deviate from the contract's literal schedule string, so it
needs a recorded decision, and the same decision must apply to every reported run.`

---

## 4. How a JMeter sample is tied to a service log line

Every number in the final document has to reconcile with a service log line. The
mechanism is four elements working together, and all four must be present:

1. **A User Parameters pre-processor** on the sampler sets two variables for the
   iteration:
   * `request_id` = `${__UUID()}` — a fresh UUID4 per request;
   * `source_row` = `${row_number}` — the course CSV row being posted (empty for
     `GET /search`, which has no row behind it).
2. **The HTTP Header Manager** sends them as `X-Request-ID` and `X-Source-Row`.
3. **The service** copies both into its JSONL log line (`request_id`,
   `source_row`) and returns `request_id` in the response body.
4. **`sample_variables=request_id,source_row`** in `jmeter/user.properties` makes
   JMeter append those two variables as extra columns on the end of every CSV
   `.jtl` row.

`analysis/reconcile.py` then joins the `.jtl` to `service.jsonl` on `request_id`
and fails the run if samples do not match up.

The resulting `.jtl` header, which `analysis/common.py` and
`analysis/tests/conftest.py` are both built against, is:

```
timeStamp,elapsed,label,responseCode,responseMessage,threadName,dataType,success,failureMessage,bytes,sentBytes,grpThreads,allThreads,URL,Latency,IdleTime,Connect,"request_id","source_row"
```

JMeter quotes the two sample-variable names in the header; `pandas.read_csv`
strips the quotes, so the parsed column names are plain `request_id` and
`source_row`.

### One subtlety worth knowing about: "Update Once Per Iteration" is off

`UserParameters.per_iteration` is **false** in all three plans, and that is not an
oversight. With it true, JMeter sets the values from an `iterationStart` listener,
and it notifies iteration listeners in *reverse* registration order — so the
User Parameters element can fire **before** the CSV Data Set Config has advanced
to the current row. `source_row` would then name the *previous* ticket. Every
reconciled row would be off by one and nothing in the `.jtl` would show it.

With it false the values are set from `process()`, i.e. as an ordinary
pre-processor immediately before the sampler runs, by which time this iteration's
CSV row is already bound. There is one sampler per iteration, so the values are
still per-iteration in effect — they are merely sequenced safely.

Verified: with this setting the `source_row` column walks the input CSV in order,
`request_id` is unique per sample, and the narrative in the request body is the
narrative belonging to the row named in `X-Source-Row`.

---

## 5. What is asserted, and what deliberately is not

Each sampler has one Response Assertion: **the response code equals 200.** That
is what turns a 502 from a model timeout, a 422 from a malformed body or a refused
connection into a failed sample, so the error rate in the `.jtl` is a real error
rate.

There is **no assertion on the returned category**, on purpose:

* It would be measuring classification accuracy client-side, in the middle of a
  timed load test, against whatever row the load generator happened to pick — and
  the raw dataset labels are noisy, which is the whole reason Part 2 builds a
  golden set. Accuracy is measured only by `scripts/run_accuracy.py` against
  `golden/golden_set.csv`, after the freeze gate passes.
* It would make a correct-but-slow service and a fast-but-wrong service produce
  the same error rate, which would make the load results unreadable.

A `200` carrying `category: "UNPARSEABLE"` therefore counts as a **success** here.
The request was served; the reply being unusable is an accuracy question, not a
performance one.

When reading a failed stress run, split the failures by `responseCode` before
interpreting them. A `502` is the service reporting a model error or timeout; a
`Non HTTP response code: ...` row is the load generator's own read timeout or a
refused connection. They mean different things, and the `502`s can be
cross-checked against the `error` slug in `logs/service/*.jsonl`.

---

## 6. The search terms file

`mixed_load.jmx` draws its query strings from `../data/search_terms.txt` through a
second CSV Data Set Config. The file is not really a CSV: the plan reads it with a
**tab** delimiter and quoting **off**, so the whole line is the term and a term may
contain commas, apostrophes and double quotes with no escaping.

### Why the search plan filters the terms file

The terms file is maintained by hand and carries `#` comment lines. JMeter's CSV
Data Set Config has no concept of a comment, so left alone it would hand those
lines to the sampler as though an agent had typed them. The plan deals with this in
two places:

* `ignoreFirstLine=true` skips exactly one line, and re-skips it on every recycle
  of the file. That covers line 1.
* A small JSR223 (Groovy) pre-processor replaces any other `#` line, blank line or
  `<EOF>` marker with one of the terms the run has already seen, and publishes the
  result as `search_q`, which is what the sampler actually sends.

It **substitutes** rather than skipping the sample, because skipping would drop an
arrival — and a fixed offered rate is the one property an open-loop test must
have. It invents nothing: the substitute always comes from the file.

Its one limitation, stated plainly: the pre-processor can only substitute a term it
has already seen, so `#` lines near the **top** of the file are queried for real
during the first pass of a run. That is why `data/search_terms.txt` keeps a short
TODO header at the top and puts its prose notes at the **bottom**, where they are
never queried. With the file as committed, three searches at the very start of a
run carry header text as their query. They are real requests that cost the service
a real full-table scan and match nothing, so they are not excluded from the
results; they are simply not realistic queries.

Two traps for whoever edits the plan:

* **Do not turn `quotedData` back on** for this data set. With quoting on and a
  comma delimiter, JMeter parses every line as CSV and a prose comment line
  containing a double quote raises `Cannot have quote-char in plain field`. That
  exception aborts the iteration, so the sample is never sent — silently dropping
  an arrival. This was observed, not theorised.
* **A blank line becomes `<EOF>`, not an empty string.** Splitting an empty line
  yields no fields at all, and `CSVDataSet` then sets every variable to
  `csvdataset.eofstring`. The filter treats `<EOF>` as a comment line for exactly
  this reason.

---

## 7. Groovy and the JDK version

**Run JMeter on a JDK that JMeter 5.6.3 supports — Java 17 or 21.** This is not a
preference. JMeter 5.6.3 bundles Groovy 3.0.20, whose compiler reads class files
with a bundled ASM that does not understand class-file versions from much newer
JDKs. On a too-new JDK, a Groovy script that names a Java type (`String`, `File`,
`ArrayList`, `Collections`, `ThreadLocalRandom`, or a closure coerced to
`java.util.function.Function`) fails to compile with

```
org.codehaus.groovy.GroovyBugError: BUG! exception in phase 'semantic analysis'
... Unsupported class file major version NN
```

and — this is the dangerous part — **the failure is silent from the outside.** The
pre-processor's failure kills the thread. No error appears in `jmeter.log`, no row
appears in the `.jtl`, and JMeter still exits 0. The only symptom is a sample count
far below `rate × duration`, or a whole sampler label missing from the results.
This was reproduced on JDK 26, where `mixed_load.jmx` produced every POST sample
and not one GET sample, with a clean log.

Two consequences, both already applied:

* The Groovy in these plans names **no Java type at all** and uses only JMeter's
  own script bindings (`vars`, `props`, `ctx`, `log`) plus Groovy's own classes
  (`groovy.json.JsonOutput`, and Groovy methods on dynamic values). Keep it that
  way — it is why the plans work on both old and new JDKs.
* **If a run's sample count is much lower than expected, or a label is missing
  from the `.jtl`, check the JDK first.** Run `java -version` on the load generator
  and record it in `docs/environment/`. It is a much likelier cause than anything
  in the service.

---

## 8. Running the plans

### Normal use

```
scripts/run_load_test.sh --plan load_post_tickets --model llama3.2:1b \
    --rate 60 --duration 300 --runs 3 --host <service-host> --port 8000
```

The script handles the freeze gate, the warm-up request, the run directory layout,
`metadata.json`, and slicing the service log for the run window. Use it for
anything that will be reported.

### By hand, for a smoke check

```
$JMETER_HOME/bin/jmeter -n -t jmeter/load_post_tickets.jmx \
    -l /tmp/check.jtl -j /tmp/check.log \
    -q jmeter/user.properties \
    -Jhost=127.0.0.1 -Jport=8000 -Jrate_per_min=60 -Jduration_s=30 \
    -Jinput_csv="$PWD/data/dev/synthetic_tickets.csv"
```

`-q jmeter/user.properties` is not optional. It carries `sample_variables` and the
`jmeter.save.saveservice.*` settings, and without it the `.jtl` has no `request_id`
or `source_row` columns and cannot be reconciled with the service log. That file
documents each setting; read it rather than memorising flags.

Write scratch results to `/tmp`, never into the repository. JMeter also drops a
`jmeter.log` in the current directory if `-j` is not given; `.gitignore` covers
both `jmeter.log` and `jmeter/*.log`, but pass `-j` anyway.

### Checking that a run is usable before you trust it

1. The `.jtl` header matches the line in section 4, including the two quoted
   sample-variable columns.
2. The row count is close to `rate_per_min / 60 * duration_s` — per label, for
   `mixed_load.jmx`. A large shortfall means arrivals were dropped; see section 7.
3. `jmeter.log` contains a `Starting OpenModelThreadGroup ... with schedule ...`
   line, and the rates in it are the rates you meant. This is the cheapest way to
   confirm your `-J` properties were picked up; for `stress_ramp.jmx` it prints all
   six resolved step rates.
4. `python analysis/reconcile.py --run-dir <dir>` exits 0.

---

## 9. Editing the plans

The `.jmx` files are hand-written rather than GUI-generated, so that a change shows
up as a readable diff instead of a reshuffled file. They do open and re-save
cleanly in the JMeter 5.6.3 GUI, and every element carries its reasoning in
`TestPlan.comments`, which the GUI shows in the element's comment box — so the
reasoning survives a GUI round-trip. If you do edit in the GUI, expect the file to
be reformatted and the XML comments between elements to be dropped; check the diff
before committing.

Things not to change without recording a decision somewhere a marker can find it:

* the sampler labels (`POST /tickets`, `GET /search`) — `analysis/` groups by them;
* the schedule strings of `load_post_tickets.jmx` and `mixed_load.jmx`, which are
  fixed by the build contract;
* `UserParameters.per_iteration` (section 4);
* `quotedData` on either CSV Data Set Config (sections 6 and 3);
* `TestPlan.serialize_threadgroups` in `mixed_load.jmx`, which must stay `false`
  or the two streams stop overlapping;
* anything that would make the load generator do less work than the configured
  rate, which is the one thing that invalidates every number in the run.
