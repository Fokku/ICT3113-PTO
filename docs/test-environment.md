# Test environment — template for Slide 7

**What this document is for.** It is the written test-environment description the brief demands in Step 5,
and it is the source Slide 7 ("Test Environment") is built from. It is deliberately a **template**: the
structure, the evidence pointers and the questions are here, and every figure is a
`TODO(Part 5 — Teammate D)` that must be filled from a committed capture file rather than from memory.

**Owner:** Part 5 — Teammate D.
`TODO(Yeo Kai Yuan): replace "Teammate D" with the real name.`

**What "done" looks like.**

1. Every cell of the machine table in section 2 holds a value copied from a file in `environment/`, and the
   "captured file" column names that file.
2. Section 3 describes the network with a **measured** round-trip time, not an assumed one.
3. Section 4 states the separate-machine confirmation as a sentence, and the three named pieces of evidence
   for it all check out.
4. Section 5 lists at least the factors that actually apply to our setup, each with the **direction** in
   which it biases our numbers.
5. Section 6 makes the scaling argument to the client's commodity CPU servers, with its assumptions named.
6. No figure anywhere in this document is one nobody can point at a file for.

**Feeds:** Slide 7 (Test Environment). Sections 3 and 5 also supply the "assumptions and limitations" line
that Slide 11 needs when a requirement is missed for an environmental reason rather than a system one.

**The brief's exact demands, for checking against:** *"describe your test environment: the machines running
the service, Ollama, and the load generator; their CPU, memory, and operating system; the network between
them; and any factors that could make your measurements unrepresentative. Indicate how results from your test
environment scale to the client's deployment."* And: *"The load generator and the system under test must run
on separate machines."*

---

## 1. Produce the captures first

Nothing below can be filled in until the capture script has been run on every machine and its output
committed. That is one command per machine, run **on** that machine:

```bash
# On the machine running the triage service container:
scripts/capture_env.sh --role service

# On the machine running Ollama:
scripts/capture_env.sh --role ollama

# On the machine running JMeter and scripts/run_accuracy.py:
scripts/capture_env.sh --role loadgen
```

Each writes `docs/environment/<hostname>.txt`. See `environment/README.md` for how to commit them, what to do
if two machines share a hostname, and when to re-capture. Do not hand-edit a capture file: it is regenerated
in place, and this document is where the narrative belongs.

---

## 2. The machines

One row per machine. Every value is copied from the capture file named in the last column; the mapping from
column to the exact label inside the capture file is in section 2.1, so no guessing is needed.

| Role | Hostname | CPU model | Cores / threads | RAM | OS and kernel | Docker version | Ollama version | JMeter version | Captured file |
|---|---|---|---|---|---|---|---|---|---|
| Triage service (`POST /tickets`, `GET /search`, `GET /stats`) | TODO(Part 5 — Teammate D) | TODO(Part 5 — Teammate D) | TODO(Part 5 — Teammate D) | TODO(Part 5 — Teammate D) | TODO(Part 5 — Teammate D) | TODO(Part 5 — Teammate D) | n/a unless this host also runs Ollama | n/a | `environment/<hostname>.txt` |
| Ollama model backend (CPU only) | TODO(Part 5 — Teammate D) | TODO(Part 5 — Teammate D) | TODO(Part 5 — Teammate D) | TODO(Part 5 — Teammate D) | TODO(Part 5 — Teammate D) | TODO(Part 5 — Teammate D) | TODO(Part 5 — Teammate D) | n/a | `environment/<hostname>.txt` |
| Load generator (JMeter, `scripts/run_accuracy.py`) | TODO(Part 5 — Teammate D) | TODO(Part 5 — Teammate D) | TODO(Part 5 — Teammate D) | TODO(Part 5 — Teammate D) | TODO(Part 5 — Teammate D) | TODO(Part 5 — Teammate D) | n/a | TODO(Part 5 — Teammate D) | `environment/<hostname>.txt` |

If the service and Ollama share one machine, keep both rows and put the same hostname and the same capture
file in each: the roles are still distinct even when the hardware is not, and Slide 7 has to speak about both.
The load generator row must always name a **different** hostname from the service row — see section 4.

`TODO(Part 5 — Teammate D): add a row for any other machine that took part, and delete the "Ollama version"
and "JMeter version" cells marked n/a only if that role genuinely never ran on that host.`

### 2.1 Where each column comes from inside a capture file

`scripts/capture_env.sh` writes labelled `label : value` lines under eight numbered sections. Copy from these
exact labels so that two people filling the table in get the same answer.

| Table column | Capture file section | Label(s) to copy |
|---|---|---|
| CPU model | 2. CPU | `Model name` (Linux, from `lscpu`; macOS, from `machdep.cpu.brand_string`) |
| Cores / threads | 2. CPU | `Cores per socket` × `Sockets` physical, `Logical CPUs` total, `Threads per core` for SMT. On macOS: `Physical cores` and `Logical cores` |
| RAM | 3. Memory and storage | `Total RAM` (and note `Total swap` in section 5 if it is non-zero — see the swap factor) |
| OS and kernel | 1. Operating system | `Distribution` (or `macOS version`) plus `uname -r (kernel)` and `uname -m (arch)` |
| Docker version | 4. Software versions | `docker`, `docker server` and `docker compose` |
| Ollama version | 5. Model backend (Ollama) | `ollama /api/version` for the server actually serving us, or `ollama CLI` if the backend is not containerised |
| JMeter version | 6. Load generator (JMeter) | `jmeter version`, **and** `java (used by JMeter)` — record the JDK too, see the JDK factor in section 5 |
| Hostname | header block | `Host` |

### 2.2 Software configuration in force

These are not measurements; they are the committed configuration the baseline was measured under, and they
belong on the slide because they change what the numbers mean. The values below are the defaults in
`../.env.example` and `../docker-compose.yml`.

| Setting | Committed default | Why it is on the slide |
|---|---|---|
| `UVICORN_WORKERS` | `1` | One worker, one event loop, one writer to SQLite and to the log. The process model is part of the baseline. |
| `SERVICE_THREADPOOL_SIZE` | `40` | The anyio worker-thread pool that blocking SQLite calls are handed to. Set explicitly so it is visible rather than an invisible library default. |
| `NUM_CTX` | `4096` | Ollama's own default is 2048 and it truncates silently; our team rows reach 1,999 characters. A truncated prompt would look like a model error, not a configuration error. |
| `OLLAMA_TIMEOUT_S` | `120` | The service's own model-call timeout. A `502` with `error: "ollama_timeout"` is this limit being hit. |
| `OLLAMA_SEED` / temperature | `42` / `0` (fixed in code) | Re-running the accuracy test on the same model and prompt gives the same answers. |
| `OLLAMA_NUM_PARALLEL` | `0` (Ollama's "decide for me" sentinel) | **Not tuned.** Concurrency is where we expect the bottleneck; tuning it is Assignment 2. A2 candidate: raise `OLLAMA_NUM_PARALLEL` and re-measure the latency / throughput trade-off on the same plans. |
| `OLLAMA_MAX_LOADED_MODELS` | `0` (same sentinel) | Same reason. One model is served at a time. A2 candidate: `OLLAMA_MAX_LOADED_MODELS > 1`, to avoid a model reload when two candidates are exercised in one session. |
| GPU | none, anywhere | There is no `deploy.resources.reservations.devices` block and no GPU runtime in `../docker-compose.yml`. The client's constraint is CPU-only commodity hardware. |
| Container CPU/memory limits | none set | The baseline gets the whole machine. Constraining it would be tuning — but see the container-limit factor in section 5, because *not* limiting it has consequences too. A2 candidate: pin the containers to a stated core count so the measured configuration matches a sized client server. |

`TODO(Part 5 — Teammate D): confirm each of these against the .env actually used on the service host —
'docker compose config' on that host prints the values in force — and correct the table if any differs from
the committed default. GET /health reports num_ctx, uvicorn_workers, threadpool_size, prompt_hash and
ollama_base_url directly, which is the quickest check.`

---

## 3. The network between the machines

The brief asks for this explicitly, and it is the part nobody captures automatically: the capture script
records each machine's IPv4 addresses (section 7 of the file) and nothing else about the link.

| Property | Value | How to establish it |
|---|---|---|
| Link type | TODO(Part 5 — Teammate D) | Wired Ethernet, or Wi-Fi, or both (say which machine is on which) |
| Nominal link speed | TODO(Part 5 — Teammate D) | `ethtool <iface> \| grep Speed` on Linux, or the router/switch port speed. State it as nominal, not achieved |
| Switch, router or direct | TODO(Part 5 — Teammate D) | Named switch or home router, or a direct cable. Say whether other traffic shares it |
| Same subnet? | TODO(Part 5 — Teammate D) | Compare the `IPv4 address` lines in section 7 of the two capture files |
| **Measured** round-trip time, service host to load generator | TODO(Part 5 — Teammate D) | Measure it — see below. Give min/avg/max and the packet count |
| Measured HTTP connect time to the service | TODO(Part 5 — Teammate D) | Measure it — see below |
| Name resolution | TODO(Part 5 — Teammate D) | Whether `-Jhost` was an IP address or a name, and whether the name was in `/etc/hosts`. See `../jmeter/user.properties` section 3: a DNS lookup inside a measured sample is load-generator latency wearing the service's clothes |

**Measure the round-trip time; do not guess it.** Run this **on the load generator**, against the service
host, before the first reported run, and paste the output into the table above:

```bash
# 20 packets is enough to see jitter as well as the mean.
ping -c 20 <service-host>

# The HTTP path, which is what actually matters: TCP connect and the time to a
# complete /health response. /health is deliberately not written to the JSONL
# request log, so this probe does not contaminate the evidence.
curl -s -o /dev/null -w 'connect=%{time_connect}s  total=%{time_total}s\n' \
    http://<service-host>:8000/health
```

Repeat the `curl` a handful of times and record the range. If the round-trip time is a material fraction of
the `POST /tickets` latency you later measure, say so in section 5 — it is a bias in our favour or against us
depending on which side of the requirement the number lands, and the honest move is to state the size of it.

`TODO(Part 5 — Teammate D): record the date and time the network measurements were taken. A Wi-Fi
measurement taken at 03:00 does not describe a run done at 15:00.`

---

## 4. CONFIRMATION: the load generator ran on a separate machine

The brief requires this confirmation, and it explains why: *"A co-hosted load generator steals CPU from the
service and produces latency numbers that are fiction."* State it as a claim, then point at the evidence.

> **Confirmation.** The load generator (Apache JMeter, and `scripts/run_accuracy.py`) ran on
> `TODO(Part 5 — Teammate D): load generator hostname`. The system under test — the triage service container
> and the Ollama backend — ran on `TODO(Part 5 — Teammate D): service hostname`
> `TODO(Part 5 — Teammate D): and the Ollama hostname if it is a third machine`. No JMeter process ran on any
> machine hosting the service or Ollama during a reported run.

The evidence, all of it already in the repository:

| Evidence | Where to look | What it must show |
|---|---|---|
| Two distinct capture files | `environment/` | Two files, two different hostnames, one declaring `Declared role: loadgen` and one declaring `Declared role: service`. Neither may declare `Declared role: all` |
| The address JMeter actually posted to | `../results/runs/<run>/metadata.json`, key `service_url` | An address on the service host. **Not** `http://127.0.0.1:...`, `http://localhost:...` or `http://0.0.0.0:...` |
| The machine JMeter actually ran on | `../results/runs/<run>/metadata.json`, key `load_generator_host_info.hostname` | The load generator's hostname, and **different** from the service host's |
| The backend the service actually used | `../results/runs/<run>/metadata.json`, key `service_host_info.ollama_base_url` (also `GET /health`) | The Ollama host we claim, not a stale default |

`scripts/run_load_test.sh` prints a warning when `--host` is `127.0.0.1`, `localhost`, `::1` or `0.0.0.0`,
precisely so that a co-hosted run cannot be produced by accident and then reported. If any run directory you
intend to cite has a loopback `service_url`, that run is not evidence for a latency or throughput claim — see
the abort criteria in the playbooks.

`TODO(Part 5 — Teammate D): check every run directory you intend to cite, not just one. The check is:
grep -h '"service_url"' ../results/runs/*/metadata.json | sort -u`

---

## 5. Factors that could make our measurements unrepresentative

The brief asks for "any factors that could make your measurements unrepresentative", and a list of generic
risks earns nothing. Fill in only the ones that **actually apply to our setup**, say how you know each one
applies, and say which way it biases the numbers. A factor with no stated direction is not yet an analysis.

| Factor | Does it apply to us? | How we know | Direction of bias | Mitigation actually applied, or "none — accepted" |
|---|---|---|---|---|
| **Thermal throttling** on a laptop or small-form-factor machine | TODO(Part 5 — Teammate D) | A sustained CPU-only load test heats the machine. Check the CPU model and `CPU max MHz` in the capture file, and watch the clock during a run (`watch -n5 "grep MHz /proc/cpuinfo \| head"` on Linux) | TODO — usually makes later runs of a three-run set slower than the first, which inflates the spread | TODO(Part 5 — Teammate D) |
| **Other processes** on the service or Ollama host | TODO(Part 5 — Teammate D) | What else was running: a browser, a desktop environment, another student's job, a backup | TODO — adds latency and variance; usually hurts the p95 and p99 more than the p50 | TODO(Part 5 — Teammate D) |
| **Wi-Fi jitter** between the load generator and the service | TODO(Part 5 — Teammate D) | Section 3: is either machine on Wi-Fi? Compare the `ping` min/avg/max spread | TODO — inflates the tail; a p99 can be a radio retransmission rather than the service | TODO(Part 5 — Teammate D) |
| **A shared machine** (lab PC, shared VM, another team's workload on the same host) | TODO(Part 5 — Teammate D) | `Virtualisation` / `Hypervisor vendor` in section 2 of the capture file tells you if it is a guest. A guest shares a physical CPU with neighbours we cannot see | TODO — unpredictable in both directions, and it breaks run-to-run comparability, which is the thing three runs are supposed to establish | TODO(Part 5 — Teammate D) |
| **Container CPU limits** | Not applied — stated for completeness | `../docker-compose.yml` sets no `cpus`, `cpuset` or `mem_limit` on either service, deliberately: limiting them would be tuning | The baseline gets the whole machine, so our numbers are an **upper bound** on what the client would see if they cgroup-limited the same container | None — accepted, and the consequence is stated |
| **Ollama cold start** (first-request model load) | Handled, but state it | `scripts/run_load_test.sh` sends one `X-Warmup: 1` request before every measured window and writes its log line to `warmup.jsonl`, outside `service.jsonl`. `load_duration` in the service log shows the model-load cost per request | Without the warm-up the first sample would carry the whole model-load cost and drag the p99. With it, our numbers describe a **warm** service — which is optimistic relative to a client whose model is evicted between quiet periods (`OLLAMA_KEEP_ALIVE`) | Warm-up request, excluded from analysis. `TODO(Part 5 — Teammate D): state the OLLAMA_KEEP_ALIVE value from section 5 of the Ollama host's capture file, because it decides whether a real deployment would ever go cold` |
| **A single SQLite file, one writer** | Applies by design | `DB_PATH=/data/triage.db`, a new `sqlite3` connection per request, no WAL, no pooling — see the A2 candidate comments in `../service/db.py` | Every `POST /tickets` writes to one file through one worker process, and `GET /search` is a full-table `LIKE` scan whose cost grows with the number of stored tickets. So a long run gets slower as it goes, and a run against a non-empty database is not comparable with one against an empty one | `scripts/reset.sh --yes` wipes the database volume before every measured run, so each run starts empty. `TODO(Part 5 — Teammate D): state how many tickets are in the database by the end of the longest run, since GET /search cost depends on it — GET /stats reports the total` |
| **JDK version on the load generator** | TODO(Part 5 — Teammate D) | `java (used by JMeter)` in section 6 of the load generator's capture file. JMeter 5.6.3 bundles Groovy 3.0.20 and needs Java 17 or 21; on a much newer JDK the plans' Groovy pre-processors fail *silently* and samples simply go missing — see `../jmeter/README.md` section 7 | TODO — a silent shortfall in samples understates the offered rate, which flatters the service | TODO(Part 5 — Teammate D) |
| **Clock skew between machines** | TODO(Part 5 — Teammate D) | The service log's `ts` and JMeter's `timeStamp` come from two different clocks. `analysis/reconcile.py` fails a run whose client-minus-server latency p99 exceeds `--latency-threshold-ms` (250 ms by default), so gross skew is caught, and `SLICE_MARGIN_S` widens the log slice by 5 s at each end to absorb the rest | TODO — skew does not change the service's real latency, but it can void a run by making it unreconcilable | Run NTP on both machines. `TODO(Part 5 — Teammate D): say whether NTP was running and name the source` |
| **Swap** on the Ollama host | TODO(Part 5 — Teammate D) | `Total swap` in section 3 of the capture. A 7-8B model at four bits plus the context is gigabytes; if it does not fit in RAM the machine swaps and latency becomes disk latency | TODO — catastrophic and non-linear, and it would show up as a step change in `eval_duration` rather than as an error | TODO(Part 5 — Teammate D) |
| **Battery or power profile** on a laptop | TODO(Part 5 — Teammate D) | Whether any machine ran on battery or a power-saving governor during a run | TODO — a power-saving governor lowers the clock and makes every CPU-bound model call slower | TODO(Part 5 — Teammate D) |

`TODO(Part 5 — Teammate D): delete the rows that genuinely do not apply, rather than leaving them marked
"no". A row that says "does not apply" and cannot say how you know is worse than no row.`

`TODO(Part 5 — Teammate D): add any factor specific to our setup that is not in this list. Two that catch
student setups and are not here: a VPN or corporate proxy between the two machines, and Docker Desktop on
macOS or Windows, which runs the containers inside a Linux VM with its own CPU and memory allocation — if
either applies, it belongs in this table with the VM's allocation quoted from the capture file.`

---

## 6. How results scale to the client's deployment

The brief requires this, and it requires the reasoning, not a reassurance. The client's hardware is
*"commodity CPU servers with no GPUs"*; ours is whatever section 2 says it is. The argument has to bridge
that gap explicitly, and it has to say where it stops working.

Answer these in order. Each is a paragraph or a short table, not a sentence.

1. **What is the same?**
   `TODO(Part 5 — Teammate D): name what carries over unchanged — CPU-only inference, the same Ollama version
   and the same pinned model digests from ../models/models.yaml, the same prompt (its hash is in every log
   line and in metadata.json), NUM_CTX=4096, one uvicorn worker, synchronous classification. These are the
   things the client would inherit exactly.`

2. **What is different, and by how much?**
   `TODO(Part 5 — Teammate D): compare our CPU to a commodity server CPU on the axes that actually decide
   CPU inference speed — physical core count, memory bandwidth (channels and speed), and the vector
   extensions listed in section 2 of the capture file (AVX2 and AVX-512 change llama.cpp's throughput
   materially). Give the comparison as a table with our figure and a stated assumption about theirs.`

3. **Which direction does the difference push our numbers?**
   `TODO(Part 5 — Teammate D): say, for each difference, whether our measurement is optimistic or
   pessimistic relative to the client. A server with more cores and more memory channels is faster per
   request and sustains a higher arrival rate; a shared virtual machine or a laptop is slower. Do not average
   the two into "roughly comparable".`

4. **What scales linearly and what does not?**
   `TODO(Part 5 — Teammate D): argue this rather than asserting it. Throughput at a fixed latency is roughly
   proportional to the number of concurrent model evaluations the hardware can sustain, so adding cores or
   machines helps it. Single-request latency is not: one ticket's classification is one model evaluation,
   largely memory-bandwidth bound, and more cores past a point do not shorten it. Which of our requirements
   depends on which is the whole point of this section — see ../workload/requirements.md.`

5. **What would you have to re-measure before promising the client anything?**
   `TODO(Part 5 — Teammate D): name the smallest set of runs that would have to be repeated on the client's
   own hardware to make our recommendation safe, and say which playbook produces them. "Re-run
   docs/playbooks/load-test.md at the arrival rate in R2 and docs/playbooks/accuracy-test.md for the
   recommended model" is a defensible answer; "it should be fine" is not.`

6. **The limits of this extrapolation, stated plainly.**
   `TODO(Part 5 — Teammate D): state the assumptions the scaling argument rests on and what breaks it. At
   minimum: that the client's ticket length distribution matches ours (../workload/workload_model.md), that
   they run one model per host as we do, and that they do not run the classifier on the same machine as
   anything else. A finding that our environment cannot support a claim about theirs is a legitimate finding;
   say it rather than hedging.`

---

## 7. Checklist before this goes on the slide

- [ ] A committed capture file exists for every machine named in section 2, and no two share a hostname.
- [ ] Every cell of the section 2 table is a value, not a `TODO`.
- [ ] The round-trip time in section 3 was measured, and the date and time it was measured are recorded.
- [ ] Section 4's confirmation names both hostnames, and `service_url` is a loopback address in **none** of
      the run directories being cited.
- [ ] Section 5 has at least two factors with a stated direction of bias, as Slide 7 requires.
- [ ] Section 6 answers all six questions, and question 3 takes a position rather than balancing.
- [ ] Nothing in this document contains a figure that cannot be traced to `environment/`,
      `../results/runs/<run>/metadata.json`, `../.env.example` or `../docker-compose.yml`.
