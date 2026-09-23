# Playbook — load test (`POST /tickets`, and the mixed `POST` + `GET /search` test)

**What this document is for.** It is the procedure for the load tests the brief requires in Step 5. It is
written to the brief's standard: *"Each test playbook must be described in sufficient detail that a competent
software tester could carry it out without seeking or inventing further information from your team."* If you
have to ask us a question to follow it, that question is a defect in this document — fix the document.

**Owner:** Part 5 — Teammate D.
`TODO(Yeo Kai Yuan): replace "Teammate D" with the real name.`

**What "done" looks like.** Three completed run directories per configuration under `../../results/runs/`,
each reconciling cleanly with the service log, and one summary table under `../../analysis/output/load/`.

**Feeds:** Slide 8 (Playbook) and Slide 9 (Load and Stress Test Results).

**Related playbooks:** `accuracy-test.md` (classification accuracy against the golden set) and
`stress-test.md` (the stepped ramp that finds the limit). All three share the preconditions in section 2.

**Conventions used in every command below.** Every command is run **from the repository root**, and `python`
means the repository's own virtual environment — `.venv/bin/python`, or activate it first with
`source .venv/bin/activate`. `<service-host>` is the hostname or IP address of the machine running the triage
service; prefer an IP address, or add the name to `/etc/hosts` on the load generator, so that a DNS lookup
never lands inside a measured sample. Anything in `<angle brackets>` is for you to substitute; anything marked
`TODO(...)` is a value this team has not yet decided, and the marker names who owns the decision.

---

## 1. What this test measures, and what it does not

| | |
|---|---|
| **Measures** | End-to-end response time of `POST /tickets` (p50, p95, p99), achieved throughput, and error rate, at a **fixed open-loop arrival rate**, for one pinned model. In the mixed variant, the same for `GET /search` while tickets are arriving. |
| **Does not measure** | Classification accuracy. A `200` carrying `category: "UNPARSEABLE"` is a **success** here: the request was served, and whether the answer is usable is an accuracy question. Accuracy is `accuracy-test.md`'s job, and there is deliberately no assertion on the returned category in any plan. |
| **The unit of measurement** | Three runs of the same configuration. A single run is not a measurement — the brief says so, and `scripts/run_load_test.sh` defaults to `--runs 3` for that reason. |
| **Plan used** | `../../jmeter/load_post_tickets.jmx` for the steady-state test; `../../jmeter/mixed_load.jmx` for the mixed test (section 10). |

### 1.1 The numbers you need before you start, and where they come from

These are **not** in this playbook, because they are not Part 5's to choose:

| What | Where it lives |
|---|---|
| The arrival rate(s) to test, in tickets per minute | `TODO(Part 4 — Teammate C)`: `../../workload/requirements.md`, requirement **R2** (throughput) and the load condition attached to **R1**. Test at least the rate named in the load condition, plus one below it and one above it, so the table on Slide 9 shows a trend rather than a point. |
| The measured duration per run, in seconds | `TODO(Part 4 — Teammate C)`: long enough that the expected sample count (`rate_per_min / 60 × duration_s`) gives a meaningful p95 and p99. Record the choice in `../../workload/requirements.md` next to R1 so every run uses the same one. |
| The agent search rate, for the mixed test | `TODO(Part 4 — Teammate C)`: `../../workload/requirements.md`, requirement **R5**. The default in `mixed_load.jmx` is deliberately the same number as the ticket rate so that it is visibly a placeholder and not a measured agent-to-ticket ratio. |
| The p50/p95/p99 thresholds each result is judged against | `TODO(Part 4 — Teammate C)`: `../../workload/requirements.md`, R1 and R5. This playbook produces the numbers; it does not decide whether they pass. |
| Which models to test | `../../models/candidates.md` and `../../models/models.yaml`. Use the exact tag, never `latest`. |

Do not invent any of these. A run at a made-up rate is a run nobody can defend on Slide 9.

---

## 2. Preconditions

Work through these in order. Every one of them has cost somebody a wasted run.

### 2.1 The freeze gate must pass

No run against the team's real rows may start until the golden set and the prediction record are committed and
tagged. Check it yourself before you touch anything else:

```bash
python scripts/freeze_gate.py --json
```

* Exit **0** and `"ok": true` — proceed.
* Exit **3** — stop. The gate prints exactly which condition failed and the command that fixes it. Do not
  work around it, and do not pass `--dev` and then report the result: `--dev` runs on 28 hand-written
  synthetic tickets, writes only under `results/dev/` (which is gitignored), and prints
  `*** DEV MODE — synthetic tickets only. Results are NOT evidence. ***`. It exists for rehearsing this
  procedure, not for producing evidence.

`scripts/run_load_test.sh` runs the gate itself and copies its verdict into every run directory as
`freeze.json`. Running it by hand first just saves you the container restarts.

### 2.2 The machines, and which step runs where

| Role | What runs there | Steps in section 4 |
|---|---|---|
| **Service host** | the `triage` container (and the `ollama` container, if Ollama is local) | 3 (model pull/pin), and everything `run_load_test.sh` does remotely |
| **Ollama host** | the Ollama server, CPU only | 3 |
| **Load generator** | `scripts/run_load_test.sh`, which runs JMeter — and the analysis scripts afterwards | 4, 5, 6, 7 |

**The load generator must be a different machine from the service.** The brief: *"A co-hosted load generator
steals CPU from the service and produces latency numbers that are fiction."* `run_load_test.sh` prints a
warning if `--host` is a loopback address, and a run whose `metadata.json` has a loopback `service_url` is not
evidence.

### 2.3 The cross-machine plumbing `run_load_test.sh` needs

This is the fiddly part, and it is the one thing to rehearse in `--dev` mode before a real run.
`run_load_test.sh` runs JMeter locally, but it also resets the database, recreates the triage container and
reads the service's own log — so from the load generator it needs to reach the service host's Docker daemon
**and** read the service host's `logs/service` directory:

```bash
# On the load generator, before the run:

# 1. Point the Docker CLI at the service host's daemon. Requires key-based SSH.
export DOCKER_HOST=ssh://<user>@<service-host>

# 2. Tell the script where the service's JSONL log is readable from HERE.
#    It must be live-readable during the run: the script reads the warm-up log
#    line before JMeter starts and slices the measured window immediately after
#    JMeter finishes, so copying the files afterwards is too late.
export SERVICE_LOG_DIR=/path/to/a/live/mount/of/the/service/host/logs/service
```

Two traps, both real:

* With `DOCKER_HOST=ssh://…`, Compose resolves the bind mount `./logs/service` to an **absolute** path using
  the compose file's location *on the load generator*, and the Docker daemon then interprets that absolute
  path on the **service host**. So the repository must be checked out at the *same absolute path* on both
  machines, or the container will bind-mount a directory that does not exist on the service host and write its
  log nowhere you can find it.
* `SERVICE_LOG_DIR` must be a live view (sshfs, NFS, or the service host's own path if you are running the
  script there for a rehearsal), not a snapshot.

Verify the plumbing before you spend an hour on runs:

```bash
docker compose -f docker-compose.yml ps          # must list the containers on the service host
ls -l "$SERVICE_LOG_DIR"                          # must show the service's <UTC-date>.jsonl
```

`TODO(Part 5 — Teammate D): record which arrangement the team actually used — sshfs, NFS, or something else —
and the absolute repository path on both machines. The next person to run this needs the answer, not the
options.`

`TODO(Yeo Kai Yuan): confirm this arrangement during the rehearsal run. If neither sshfs nor NFS is workable
in our setup, scripts/run_load_test.sh needs an option for fetching the service log over SSH, and this section
must be rewritten to match whatever it grows.`

### 2.4 Everything else

| Precondition | How to check it | Why |
|---|---|---|
| JMeter **5.6+** on the load generator, on PATH or given with `--jmeter-home` | `jmeter --version` | The Open Model Thread Group only exists from 5.5; the plans will not open on 5.4 |
| **Java 17 or 21** on the load generator | `java -version` | JMeter 5.6.3 bundles Groovy 3.0.20. On a much newer JDK the plans' Groovy pre-processors fail *silently*: no error in `jmeter.log`, JMeter still exits 0, and samples simply go missing. See `../../jmeter/README.md` section 7 |
| The model is pulled and **pinned** | `grep -A4 'tag: "<tag>"' models/models.yaml` shows a non-null `digest` | The digest is the only thing tying a number to a specific set of weights. Pull with `scripts/pull_and_pin_models.sh --model <tag>` on the Ollama host |
| Both machines' clocks are in sync | `date -u` on each, and NTP running | The `.jtl` timestamps and the service log's `ts` come from two clocks. `analysis/reconcile.py` fails a run whose client-minus-server latency p99 exceeds 250 ms |
| `curl` and `docker` on the load generator | `command -v curl docker` | The script uses both; it exits 2 if either is missing |
| The repository is committed | `git status --porcelain` is empty | `metadata.json` records `git_commit` and `git_dirty`. A run recorded as dirty cannot be reproduced |
| The database starts **empty** | `curl -s http://<service-host>:8000/stats` reports `"total": 0` after the reset | `GET /search` is a full-table `LIKE` scan, so leftover tickets change what is being measured. `run_load_test.sh` calls `scripts/reset.sh --yes` itself before every run |
| Nothing else is running on the service or Ollama host | `top`, or your judgement | Another process on a CPU-only inference host is the single easiest way to ruin a run |

---

## 3. The open-loop JMeter configuration (Slide 8 must show this)

The brief fixes the protocol: *"Traffic must be generated open-loop, at controlled arrival rates: use the Open
Model Thread Group or the Precise Throughput Timer. Closed-loop traffic self-throttles when the server slows
down and hides queue buildup. Results from closed-loop tests will not be accepted as evidence against
throughput or latency requirements."*

**Every thread group in every plan in `../../jmeter/` is an Open Model Thread Group.** There is no ordinary
Thread Group anywhere, and no loop controller.

### 3.1 The schedule string

`load_post_tickets.jmx`, thread group "Ticket intake" — copy this verbatim onto the slide:

```
rate(${__P(rate_per_min,60)}/min) random_arrivals(${__P(duration_s,300)} sec)
```

`mixed_load.jmx` carries two thread groups running concurrently
(`TestPlan.serialize_threadgroups` is `false`, which must stay false or the two streams stop overlapping):

```
Ticket intake :  rate(${__P(rate_per_min,60)}/min)        random_arrivals(${__P(duration_s,300)} sec)
Agent searches:  rate(${__P(search_rate_per_min,60)}/min) random_arrivals(${__P(duration_s,300)} sec)
```

`random_arrivals` is a **Poisson** process, not evenly spaced arrivals. Real complaint intake clumps, and
evenly spaced arrivals would understate the concurrency the service sees at a given mean rate. The practical
consequence: the sample count varies around `rate_per_min / 60 × duration_s` rather than hitting it exactly,
and that is the arrival process, not a fault.

`OpenModelThreadGroup.random_seed` is `${__P(random_seed,0)}`. Zero means a fresh arrival pattern per run, so
the spread across the three repeat runs includes arrival variability — which is the honest thing to report.

### 3.2 Why not closed-loop, in one paragraph for the slide

With a fixed pool of N threads in a loop, the offered rate is `N / response_time`. The moment the service
slows down the load generator slows down with it, so the test stops offering the rate you are claiming to have
tested; nothing ever queues, because nothing new arrives until something old has finished; and queue growth in
front of Ollama is precisely the failure mode this assignment asks us to find. Each `.jmx` repeats this
argument in its own `TestPlan.comments`, so it is visible to anyone who opens the plan in the GUI.

### 3.3 How a JMeter sample is tied to a service log line

Four elements, all of which must be present or the run cannot be reconciled and is therefore not evidence:

1. a **User Parameters** pre-processor sets `request_id` = `${__UUID()}` and `source_row` = `${row_number}`
   per iteration (`UserParameters.per_iteration` is deliberately **false** — see `../../jmeter/README.md`
   section 4 for the off-by-one bug that setting it true would cause);
2. the **HTTP Header Manager** sends them as `X-Request-ID` and `X-Source-Row`;
3. the **service** copies both into its JSONL log line and returns `request_id` in the response body;
4. **`sample_variables=request_id,source_row`** makes JMeter append those two columns to every CSV `.jtl` row.

`scripts/run_load_test.sh` supplies (4) as `-Jsample_variables=request_id,source_row` and then checks the
`.jtl` header for both columns, failing the run if either is missing.

The expected `.jtl` header, which `analysis/common.py` is built against:

```
timeStamp,elapsed,label,responseCode,responseMessage,threadName,dataType,success,failureMessage,bytes,sentBytes,grpThreads,allThreads,URL,Latency,IdleTime,Connect,"request_id","source_row"
```

### 3.4 One thing to fix on the load generator before the first real run

`../../jmeter/user.properties` pins the whole `.jtl` column set and the CSV format, so that the evidence chain
does not depend on a teammate's local JMeter installation. `scripts/run_load_test.sh` does **not** pass
`-q jmeter/user.properties`; it passes `-Jsample_variables=request_id,source_row` only and otherwise relies on
whatever `jmeter.properties` the load generator has installed. The script does check the resulting `.jtl`
header and fails the run if the file is not CSV or if either reconciliation column is missing — but that check
happens *after* the run, so a machine whose JMeter properties differ from ours costs you a whole configuration
before you find out.

Make the pinning unconditional once, per load generator, by appending our settings to the properties file
JMeter loads automatically:

```bash
cat jmeter/user.properties >> "$JMETER_HOME/bin/user.properties"
```

Then record in `../environment/` that you did it. When running a plan **by hand** (section 9), pass
`-q jmeter/user.properties` instead.

`TODO(Yeo Kai Yuan): decide whether scripts/run_load_test.sh should pass -q jmeter/user.properties itself. It
would remove this step and this footnote. Until it does, the step above is mandatory on every load generator.`

---

## 4. Procedure

Numbered, in order. Steps 1 to 3 are once per model; step 4 onwards is once per arrival rate.

**1. Confirm the freeze gate (load generator).**

```bash
python scripts/freeze_gate.py --json
```
Expect exit 0 and `"ok": true`. If it exits 3, stop and read section 2.1.

**2. Confirm the service is up, and which model and backend it is serving (load generator).**

```bash
curl -s http://<service-host>:8000/health | python -m json.tool
```
Read and check: `status` is `ok`; `model_tag` is the tag you intend to test; `model_digest` matches the pin in
`models/models.yaml`; `ollama_reachable` is `true`; `ollama_base_url` is the Ollama host you mean; `num_ctx` is
`4096`; `uvicorn_workers` is `1`. `/health` is deliberately **not** written to the JSONL request log, so
polling it does not contaminate the evidence.

**3. Confirm the model is pinned (Ollama host, once per model).**

```bash
scripts/pull_and_pin_models.sh --dry-run          # prints the plan; contacts nothing
scripts/pull_and_pin_models.sh --model <tag>      # pulls, then writes the digest into models/models.yaml
```
Commit `models/models.yaml`. If the script reports that a digest disagrees with an existing pin it **exits 4
and refuses to overwrite it** — that means the weights behind the tag changed, and every result already
gathered under the old digest is no longer comparable. Read its message before doing anything else.

**4. Run the three measured runs (load generator).** One command per configuration:

```bash
export DOCKER_HOST=ssh://<user>@<service-host>          # see section 2.3
export SERVICE_LOG_DIR=/path/to/service/logs/service    # see section 2.3
export RUN_NOTES="operator <name>; <anything a human noticed>"   # lands in metadata.json

scripts/run_load_test.sh \
    --plan load_post_tickets \
    --model <ollama-tag> \
    --rate <TODO(Part 4 — Teammate C): tickets per minute, from workload/requirements.md R2> \
    --duration <TODO(Part 4 — Teammate C): seconds per run> \
    --runs 3 \
    --host <service-host> \
    --port 8000 \
    --yes
```

`--yes` skips the confirmation prompt. Read what you are agreeing to first: **each run calls
`scripts/reset.sh --yes`, which destroys every ticket stored in the service's database.** That is deliberate —
every run must start empty — but it is destructive, and without `--yes` in a non-interactive shell the script
refuses to proceed (exit 2) rather than resetting unasked.

For each of the three runs the script does exactly this, and does not reorder it:

| | Step | What it is for |
|---|---|---|
| 1 | freeze gate | its JSON verdict is copied into the run directory as `freeze.json` |
| 2 | `scripts/reset.sh --yes`, then `docker compose up -d --force-recreate --no-deps triage` with `MODEL_TAG` set, then wait for `/health` to confirm that model and a reachable Ollama (up to `HEALTH_TIMEOUT_S`, default 240 s) | every run starts from an empty database and a known model |
| 3 | **one** warm-up `POST /tickets` from `data/dev/synthetic_tickets.csv` with `X-Warmup: 1`; its log line goes to `warmup.jsonl` | pays the one-off model-load cost before measurement, and keeps it out of the p99. A team row is never spent on a warm-up |
| 4 | JMeter, non-GUI, with `-Jsample_variables=request_id,source_row` and the `-J` properties from your flags | the measurement |
| 5 | copies the service log lines inside the measured window into `service.jsonl` (widened by `SLICE_MARGIN_S`, default 5 s, to absorb clock skew) | the run directory is self-contained |
| 6 | writes `metadata.json` | the run describes itself: model, digest, prompt hash, rate, freeze commit, git commit, JMeter version, both hosts |

**5. Repeat step 4 for each arrival rate**, and then for each candidate model. Nothing else changes between
configurations — same plan, same duration, same `--runs 3`.

**6. Reconcile every run before you quote a single number from it (load generator).** Once per run directory:

```bash
python analysis/reconcile.py --run-dir results/runs/<run-dir>
```

Exit 0 means the `.jtl` samples and the service log lines are the same requests, joined on `request_id`. A
non-zero exit means the run is **not** evidence — see section 8.

**7. Summarise (load generator).**

```bash
python analysis/summarise_load.py --runs results/runs --plan load_post_tickets
# or, for one model at a time:
python analysis/summarise_load.py --runs results/runs --plan load_post_tickets --model <ollama-tag>
```

Writes the per-run and per-configuration tables (p50/p95/p99, achieved throughput, error rate, sample count,
plus mean and spread across the three runs) and a latency-versus-arrival-rate chart into
`analysis/output/load/`. That directory is committed, because the slides cite it.

**8. Diagnose where the time went (load generator).** Once per configuration is enough:

```bash
python analysis/bottleneck_hints.py --run-dir results/runs/<run-dir>
```

Breaks a request down using only the service log's own timings and Ollama's reported durations: service
overhead, the queue/transport residual, model load, prompt evaluation and generation, plus a `num_ctx`
truncation check. The queue term is a **residual**, not a measured quantity — read the module docstring before
quoting it on a slide.

---

## 5. What to observe while it runs

Watch these; they are how you find out a run is worthless while it is still cheap to abandon.

| Watch | Where | What is fine, and what is not |
|---|---|---|
| JMeter's running summary | the script's stdout (kept as `jmeter_stdout.txt`) | The cumulative sample count should track `rate_per_min / 60 × elapsed_s`. A count drifting far below that means arrivals are being dropped — stop and check the JDK (section 2.4) |
| Error count in the summary | same | Any non-zero error count needs an explanation before the result is reported. Split by `responseCode` afterwards: a `502` is the service reporting a model error or timeout; a `Non HTTP response code: …` row is the load generator's own read timeout or a refused connection. They mean different things |
| **Load generator CPU** | `top` or `htop` on the load generator | This is the one that invalidates a run silently. If JMeter saturates the generator's own CPU, part of what you are recording as service latency is generator delay. See the abort criterion in section 8 |
| Service host CPU | `top` on the service host | Expect Ollama to dominate. If something else is competing, the run is not describing the baseline |
| The service log growing | `wc -l "$SERVICE_LOG_DIR"/*.jsonl` | It should grow at roughly the arrival rate. Flat means the service is not logging where you think it is, and step 5 of the run will find nothing to slice |

---

## 6. Expected artefacts, and where they land

One directory per run, under `results/runs/`, named
`<UTCSTAMP>_<model>_<plan>_<rate>_run<k>` — illustratively,
`20261006T031500Z_llama3.2-1b_load_post_tickets_60pm_run1` (an example of the *shape*; no such run exists). `<UTCSTAMP>` is `YYYYmmddTHHMMSSZ`; the model tag
is sanitised (`:` `/` and spaces become `-`); `<rate>` is `<rate_per_min>pm`.

| File | What it is | Must not be missing or empty |
|---|---|---|
| `metadata.json` | the run describing itself: model tag and digest, prompt hash, `num_ctx`, seed, rate, duration, run index, both hosts, JMeter version, git commit and dirty flag, freeze commit and tag | yes |
| `freeze.json` | the verbatim verdict of `scripts/freeze_gate.py --json` at run time | yes |
| `results.jtl` | the raw JMeter samples, CSV, with the `request_id` and `source_row` columns | yes |
| `jmeter.log` | JMeter's own log. Contains the resolved `Starting OpenModelThreadGroup … with schedule …` line, which is the cheapest proof your `-J` properties were picked up | yes |
| `jmeter_stdout.txt` | the running summary | yes |
| `service.jsonl` | the service's own log lines for the measured window — the independent second record every number is checked against | yes |
| `warmup.jsonl` | the warm-up request's log line, kept as evidence that the model-load cost was paid before measurement, and kept **out** of `service.jsonl` | yes |

Derived output, all regenerable and all committed:
`analysis/output/load/`, `analysis/output/reconcile/`, `analysis/output/bottleneck/`.

**Keep the raw files.** The brief: *"Keep the raw JMeter result files (.jtl) from every run in your
repository; they must reconcile with your service logs."* Commit each run directory.

---

## 7. Record this in the run log

The scripts capture everything machine-readable. They cannot capture what a person saw. After each
configuration, write down:

1. **Who ran it, and when** (local time as well as UTC — the UTC stamp is in the directory name, but "Tuesday
   evening" is what makes "the flatmate was streaming" a usable explanation later).
2. **What else was happening on each machine** — other processes, other people logged in, a laptop lid closed,
   a build running.
3. **The physical setup** — Wi-Fi or cable, machine on battery or mains, lid open, plugged into a dock.
4. **Anything you did by hand** that the script did not do: a container restarted, a model re-pulled, an SSH
   session dropped and reconnected, `SERVICE_LOG_DIR` remounted.
5. **Anything that looked wrong and that you decided to accept** — and why. This is the one nobody writes down
   and everybody needs in the last week.
6. **How long the configuration took wall-clock**, so the next person can plan.
7. **Your verdict**: is this configuration reportable, or is it a rehearsal? Say which, in those words.

The short version goes into the run's own `metadata.json`, which is the durable place, by exporting
`RUN_NOTES` before the run:

```bash
export RUN_NOTES="operator <name>; wired ethernet; service host otherwise idle; JDK 21"
```

`scripts/run_load_test.sh` copies it verbatim into `metadata.json`'s `notes` field, alongside its own notes.
`scripts/run_accuracy.py` honours the same variable.

`TODO(Part 5 — Teammate D): create a single run log for the longer narrative — one dated entry per
configuration, with the seven items above — and name it here so this playbook points at a real file. It is not
created by this playbook because Part 5 owns it; a markdown file under docs/ is enough, and it must be
committed, because it is the record that explains the numbers.`

---

## 8. Abort and retry: what makes a run invalid

If any of these is true, the run is **not evidence**. Do not report it, do not average it in, and do not
delete it quietly either — move it aside or note in the run log why it was discarded, then fix the cause and
re-run the whole configuration (all three runs, not just the bad one).

| Abort criterion | How you detect it | Why it voids the run |
|---|---|---|
| **The freeze gate did not pass** | exit 3, or `freeze.json` contains `"ok": false`, or `metadata.json` has `"mode": "dev"` | The labels and predictions must demonstrably predate the measurement. A dev-mode run used 28 synthetic tickets and is gitignored |
| **`analysis/reconcile.py` exits non-zero** | run step 6 | Unmatched samples, a duplicate `request_id`, an HTTP status or `source_row` disagreement, or a client-minus-server latency p99 above the threshold. Any of them means the `.jtl` and the service log are not describing the same requests, so no number in the run is traceable |
| **`/health` reported an unexpected model tag or digest** | step 2, and `metadata.json`'s `model_tag` / `model_digest` | The run measured a different set of weights from the one it is labelled with. `run_load_test.sh` waits for `/health` to confirm the tag and fails if it never does, so this normally shows up as a failed run rather than a wrong one |
| **The database was not empty at the start** | `GET /stats` reporting a non-zero `total` before the measured window | `GET /search` is a full-table scan, so the run is not comparable with one that started empty |
| **The load generator saturated its own CPU** | `top` on the load generator during the run; and afterwards, an achieved throughput below the configured rate while the service shows **no** errors, or warnings in `jmeter.log` about the scheduler falling behind | The latency you recorded includes generator delay. This is the failure mode the brief's separate-machine rule exists to prevent, and it does not announce itself. Reduce the rate per generator, or add a second generator, and re-run |
| **The sample count is far below `rate_per_min / 60 × duration_s`** | `results.jtl` line count, per sampler label | Arrivals were dropped. Most likely the JDK problem in section 2.4, which fails silently and still exits 0 |
| **`service.jsonl` is empty or much shorter than the `.jtl`** | the script warns; check the file | Either `SERVICE_LOG_DIR` is not the log the service is writing, or the two machines' clocks disagree by more than `SLICE_MARGIN_S` |
| **`results.jtl` has no `request_id` or `source_row` column** | the script warns; check the header against section 3.3 | Reconciliation is impossible. See section 3.4 |
| **`metadata.json`'s `service_url` is a loopback address** | `grep '"service_url"' results/runs/*/metadata.json` | The load generator was co-hosted with the service. The brief does not accept the resulting latency |
| **`metadata.json` reports `"git_dirty": true`** | the same file | The run cannot be reproduced from a committed state. Commit, then re-run |
| **The service returned `502`s you cannot explain** | `responseCode` in the `.jtl`; `error` in `service.jsonl` (`ollama_timeout`, `ollama_http_502`, `ollama_connect_error`) | A `502` is a legitimate *result* at a high arrival rate and belongs in the error rate. It is an abort only if it was caused by something outside the system under test — Ollama restarted, the model was evicted, the network dropped |
| **Anyone touched the machines during the run** | the run log | Including running `docker compose logs -f`, which is cheap, or a `docker pull`, which is not |

**Retry rule.** Re-run the whole configuration. Three runs exist to measure run-to-run spread; a set of three
where one was re-run under different conditions measures nothing, and the spread is the headline number on
Slide 9.

---

## 9. Common failures and what they mean

| Symptom | Almost always means | Do this |
|---|---|---|
| `run_load_test.sh: JMeter not found` (exit 2) | JMeter is not on PATH on the load generator | `--jmeter-home /path/to/apache-jmeter-5.6.3`, or put it on PATH |
| `run_load_test.sh: docker not found` (exit 2) | The script is being run somewhere with no Docker CLI | Run it on a machine with the CLI and set `DOCKER_HOST` (section 2.3) |
| `service log directory … does not exist` (exit 2) | `SERVICE_LOG_DIR` is unset or wrong | Section 2.3. The run directory must contain the service's own record, so the script refuses to start without it |
| `not an interactive terminal and --yes was not given` (exit 2) | You ran it from a script or a detached shell | Pass `--yes`, having understood that it resets the database |
| `/health did not report model <tag> within 240s` | The container could not start, or Ollama is unreachable, or the model is not pulled on that Ollama host | `docker compose logs triage`; check `ollama_base_url` in `/health`; pull the model. Raise `HEALTH_TIMEOUT_S` only if a slow pull is the genuine cause |
| `the warm-up POST returned HTTP 502` | Ollama cannot serve that tag: not pulled, out of memory, or the server is down | Pull the model on the Ollama host and check its memory. Measuring now would charge the first sample with the model-load cost |
| `the warm-up request produced no usable log line` | `SERVICE_LOG_DIR` is not the directory the service writes to | Section 2.3 |
| `results.jtl is empty. Nothing was measured.` | JMeter failed to start the plan (usually a bad `-J` property or an unresolvable `-Jhost`) | Read `jmeter_stdout.txt` and `jmeter.log`. `UnknownHostException` means `--host` was wrong; the plans' default host is a deliberately invalid name so a missing `-Jhost` fails loudly instead of quietly testing localhost |
| `results.jtl has no 'request_id' column` | The `.jtl` column set was not pinned on this machine | Section 3.4 |
| `no service log lines fall inside the measured window` | Clock skew between the machines, or the wrong log directory | Run NTP on both; raise `SLICE_MARGIN_S` only after you have checked the clocks, not instead |
| Sample count is roughly right but one whole sampler label is missing from the `.jtl` (mixed test) | The JDK problem: a Groovy pre-processor failed silently and killed its thread | `java -version` on the load generator; use Java 17 or 21. `../../jmeter/README.md` section 7 |
| `reconcile.py`: "unmatched samples" | Usually the log slice is too narrow, or `service.jsonl` came from the wrong machine; occasionally a duplicate `request_id` | Check the clocks and `SERVICE_LOG_DIR` first. Do **not** raise `--max-unmatched` to make it pass |
| `reconcile.py`: latency p99 disagreement above the threshold | The two clocks disagree, or the network round-trip is a large fraction of the response time | Check NTP; measure the round-trip (`../test-environment.md` section 3) and record it. A genuine network cost is a finding, not a threshold to relax |
| `summarise_load.py` exits non-zero: "no runs found" | `--runs` points at the wrong directory, or every run directory is misnamed | The directory name is parsed for model, plan, rate and run index. Do not rename run directories |
| Achieved throughput is below the configured rate, with no errors | The load generator could not keep up (its own CPU), or samples were dropped | Section 8, load-generator saturation |
| Every sample is a `200` but many carry `category: "UNPARSEABLE"` | Nothing is wrong with the load test | That is an accuracy observation. It belongs to `accuracy-test.md`, and it is deliberately not asserted on here |

---

## 10. The mixed test (`POST /tickets` + `GET /search`)

Same procedure, same preconditions, one plan and one extra flag. It exists for a requirement of the form
"`GET /search` stays under X ms at the p95 while tickets arrive at Y per minute" — requirement **R5** in
`../../workload/requirements.md`.

```bash
scripts/run_load_test.sh \
    --plan mixed_load \
    --model <ollama-tag> \
    --rate <TODO(Part 4 — Teammate C): ticket arrival rate, per minute> \
    --search-rate <TODO(Part 4 — Teammate C): agent search rate, per minute, from workload/requirements.md R5> \
    --duration <TODO(Part 4 — Teammate C): seconds per run> \
    --runs 3 \
    --host <service-host> --port 8000 --yes
```

What differs:

* **Two concurrent open-model thread groups**, both using the same `duration_s` so they start and stop
  together. The POST samples are labelled `POST /tickets` and the GET samples `GET /search`; the analysis
  groups by label, so do not rename a sampler.
* **Search terms** come from `data/search_terms.txt` via a second CSV Data Set Config, read with a **tab**
  delimiter and quoting **off**. `limit` on `GET /search` is the literal `50` and is not a property: it decides
  how much JSON the service must serialise, so changing it changes what a response-time requirement means.
  If a different page size is ever tested, add a second sampler with a different label rather than editing this
  one.
* **The first few searches of a run are not realistic queries.** The terms file carries a `#` comment header,
  JMeter's CSV Data Set Config has no concept of a comment, and the plan's filter can only substitute a term it
  has already seen — so with the file as committed, three searches at the very start of each run carry header
  text. They are real requests that cost a real full-table scan and match nothing, so they are not excluded;
  they are simply not realistic. Say so when reporting the `GET /search` p50.
* **A growing database.** `GET /search` scans the whole `tickets` table, and the table grows throughout the
  run as tickets arrive. So search latency is expected to rise within a single run. Record the final
  `GET /stats` total with the result: the search numbers only mean something against a stated table size.

Interpret `GET /search` and `POST /tickets` separately. In `analysis/output/load/` they appear as separate
rows, split by sampler label — the whole point of the mixed test is the interference between them, and a
figure that pools the two measures nothing.
