# Test environment — template for Slide 7

**What this document is for.** It is the written test-environment description the brief demands in Step 5,
and it is the source Slide 7 ("Test Environment") is built from. It is deliberately a **template**: the
structure, the evidence pointers and the questions are here, and every figure is a


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
| Triage service (`POST /tickets`, `GET /search`, `GET /stats`) | tw | Intel(R) Core(TM) Ultra 7 155H | 11 / 22 | 15.3 GiB | Ubuntu 24.04.1 LTS (WSL2), 5.15.167.4 | 29.5.3 | 0.35.0 | n/a | `environment/tw-Service.txt` |
| Ollama model backend (CPU only) | tw | Intel(R) Core(TM) Ultra 7 155H | 11/22 | 15.3 GiB | Ubuntu 24.04.1 LTS (WSL2), 5.15.167.4 | 29.5.3 | 0.35.0 | n/a | `environment/tw-Ollama.txt` |
| Load generator (JMeter, `scripts/run_accuracy.py`) | kthgoat | Intel(R) Core(TM) i5-14400F | 8 / 16 | 15.5 GiB | Ubuntu 26.04.1 LTS on WSL2, kernel 6.18.40.1-microsoft-standard-WSL2, x86_64 | client 29.8.2, Compose v5.5.1 (command-line client only) | none running | 5.6.3 on Java 21.0.12.1 | `environment/kthgoat-Loadgen.txt` |

If the service and Ollama share one machine, keep both rows and put the same hostname and the same capture
file in each: the roles are still distinct even when the hardware is not, and Slide 7 has to speak about both.
The load generator row must always name a **different** hostname from the service row — see section 4.

`TODO(Part 5 — Koh Tong Wei): add a row for any other machine that took part, and delete the "Ollama version"
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
| `OLLAMA_MAX_LOADED_MODELS` | `0` (same sentinel) | Same reason. One model is served at a time. A2 candidate: `OLLAMA_MAX_LOADED_MODELS > 1`, to avoid a model reload when two candidates are exercised in one session. |\
| `OLLAMA_KEEP_ALIVE` | unset (`environment/tw-Ollama.txt`, section 5) | Ollama's default idle timeout decides when a loaded model is evicted |
| Container CPU and memory limits | none | The containers get everything the WSL2 guest has |
| GPU | none, anywhere | There is no `deploy.resources.reservations.devices` block and no GPU runtime in `../docker-compose.yml`. The client's constraint is CPU-only commodity hardware. |
| Container CPU/memory limits | none set | The baseline gets the whole machine. Constraining it would be tuning — but see the container-limit factor in section 5, because *not* limiting it has consequences too. A2 candidate: pin the containers to a stated core count so the measured configuration matches a sized client server. |

`TODO(Part 5 — Koh Tong Wei): confirm each of these against the .env actually used on the service host —
'docker compose config' on that host prints the values in force — and correct the table if any differs from
the committed default. GET /health reports num_ctx, uvicorn_workers, threadpool_size, prompt_hash and
ollama_base_url directly, which is the quickest check.`

---

## 3. The network between the machines

The brief asks for this explicitly, and it is the part nobody captures automatically: the capture script
records each machine's IPv4 addresses (section 7 of the file) and nothing else about the link.

| Property | Value |
|---|---|
| Link type and router | **[TO FILL: Wi-Fi or cable for each machine, and the router they share]** |
| Topology | Both machines are on one private local network. `tw` is at `192.168.50.73`. All 20 ping replies carried `ttl=127`, which is Windows' default of 128 less the single WSL2 hop on `kthgoat`, so no router sits between the two hosts |
| Measured round-trip time, load generator to service host | min / avg / max / mdev = **4.039 / 50.953 / 187.839 / 47.456 ms**; 20 packets sent, 20 received, 0% loss (`ping -c 20 192.168.50.73` on `kthgoat`) |
| Measured HTTP time to the service | connect 0.005635 s, total 0.039474 s for one `GET /health` (single sample) |
| Name resolution | None. JMeter is given the IP address (`--host 192.168.50.73`), so no DNS lookup happens inside a measured sample |
| Path into the service | JMeter posts to `tw`'s Windows address; Docker Desktop forwards port 8000 into the service container |
| When measured | 7 October 2026, about 17:12 UTC (01:12 on 8 October, Singapore time) |

**What this means for our numbers.** The link is uneven. The mean round trip (51 ms) is more than twelve times
the minimum (4 ms), and the slowest packet took 188 ms. Against requirement R1 (`POST /tickets` p95 ≤ 10 s,
`../workload/requirements.md`) this is small: 188 ms is under 2% of the threshold. Against R5 (`GET /search`
p95 ≤ 2 s) it is not negligible: 188 ms is about 9% of the threshold, and a search over a near-empty table is
itself fast, so network jitter can be a visible share of the search latency JMeter records. The effect is on
JMeter's client-side figures only. The service log's own timings do not include the network.

---

```bash
# 20 packets is enough to see jitter as well as the mean.
ping -c 20 <service-host>

# The HTTP path, which is what actually matters: TCP connect and the time to a
# complete /health response. /health is deliberately not written to the JSONL
# request log, so this probe does not contaminate the evidence.
curl -s -o /dev/null -w 'connect=%{time_connect}s  total=%{time_total}s\n' \
    http://<service-host>:8000/health
```
---

## 4. CONFIRMATION: the load generator ran on a separate machine

The brief requires this confirmation, and it explains why: *"A co-hosted load generator steals CPU from the
service and produces latency numbers that are fiction."* State it as a claim, then point at the evidence.

> **Confirmation.** The load generator (Apache JMeter, and `scripts/run_accuracy.py`) ran on
> `WX_Laptop`. The system under test — the triage service container
> and the Ollama backend — ran on `tw`
> `tw`. No JMeter process ran on any
> machine hosting the service or Ollama during a reported run.

The evidence, all of it already in the repository:

| Evidence | Where to look | What it must show |
|---|---|---|
| Two distinct capture files | `environment/` | Two different hostnames: `kthgoat.txt` with `Declared role: loadgen`, and `tw-Service.txt` / `tw-Ollama.txt` with `service` and `ollama`. No file declares `Declared role: all` |
| JMeter and Java only on the load generator | `environment/kthgoat.txt` section 6; both `tw` files | `kthgoat.txt`: JMeter 5.6 or newer and Java 17 or 21. The `tw` files: `jmeter binary : not installed` |
| No service or model backend on the load generator | `docker ps` on machine 2; `environment/kthgoat.txt` section 5 | No `ict3113-*` containers. `ollama /api/version : not reachable at http://localhost:11434` |
| Service healthy on machine 1 | `docker compose ps` and `curl.exe -s http://127.0.0.1:8000/health` on machine 1 | `ict3113-triage` Up (healthy), `ict3113-ollama` Up. `"status":"ok"` and `"ollama_reachable":true`. `model_digest` is **not** `null` once the model is pulled (`docker exec ict3113-ollama ollama list`) |
| Machine 1 reachable from machine 2 | `curl.exe -s -m 5 http://192.168.50.73:8000/health` and `ping -n 20 192.168.50.73` on machine 2 | JSON from `/health`. Ping packets sent, received and lost, with min/avg/max, date and time. If ping is blocked, record the `curl` timing range instead |
| Smoke test across the network | `bash scripts/smoke_test.sh --host 192.168.50.73 --count 3` on machine 2 | Passes: 3 of 3 tickets posted, 3 of 3 complete log lines |
| Live service log visible from machine 2 | `ls -l "$SERVICE_LOG_DIR"` and `wc -l "$SERVICE_LOG_DIR"/*.jsonl`, run twice during a smoke test | Line count **grows**. A stale copy is not acceptable |
| The address JMeter actually posted to | `../results/runs/<run>/metadata.json`, key `service_url` | `http://192.168.50.73:8000`. **Not** `127.0.0.1`, `localhost` or `0.0.0.0` |
| The machine JMeter actually ran on | `../results/runs/<run>/metadata.json`, key `load_generator_host_info.hostname` | `kthgoat`, **different** from the service host (`tw`) |
| The backend the service actually used | `../results/runs/<run>/metadata.json`, key `service_host_info.ollama_base_url` (also `GET /health`) | The Ollama host we claim, not a stale default |
| Same code and clock on both machines | `git rev-parse HEAD` and `date -u` on each | Identical commit hash. Clocks agree within a second or two |
| Freeze gate before any real run | `python scripts/freeze_gate.py` | Passes: golden set and prediction record committed, tag `golden-freeze` present. Until then only `--dev` runs are allowed |

`scripts/run_load_test.sh` warns when `--host` is a loopback address. If any run directory you intend to cite has a loopback `service_url`, that run is not evidence for a latency or throughput claim.

---

* **Two machines, two hostnames.** `environment/kthgoat.txt` declares `loadgen` (Intel Core i5-14400F, 15.5 GiB);
  `environment/tw-Service.txt` and `environment/tw-Ollama.txt` declare `service` and `ollama` (Intel Core Ultra 7 155H,
  15.3 GiB). No file declares `all`.
* **Still to confirm on `kthgoat`.** The capture screenshot showed Docker, JMeter and Java as not installed.
  **[TO FILL: re-run `bash scripts/capture_env.sh --role loadgen` after installing Java 21 and JMeter 5.6.3, then
  confirm section 6 shows both with version numbers.]**
* **Network.** Machine 1 `192.168.50.73`, machine 2 `192.168.50.15`, both on Wi-Fi through `192.168.50.1`.
  **[TO FILL: ping summary (packets lost, min/avg/max), the `curl` timing range, and the date and time measured.]**
* **Per-run record.** **[TO FILL after the reported runs: confirm that every cited run's `metadata.json` has
  `service_url` = `http://192.168.50.73:8000` and `load_generator_host_info.hostname` = `kthgoat`.]**

## 5. Factors that could make our measurements unrepresentative

The brief asks for "any factors that could make your measurements unrepresentative", and a list of generic
risks earns nothing. Fill in only the ones that **actually apply to our setup**, say how you know each one
applies, and say which way it biases the numbers. A factor with no stated direction is not yet an analysis.


| Factor | Does it apply to us? | How we know | Direction of bias | Mitigation actually applied, or "none — accepted" |
|---|---|---|---|---|
| **Thermal throttling** on a laptop or small-form-factor machine | Yes for `tw`. It is a mobile part and runs the CPU-only model | `tw`'s CPU is a Core Ultra 7 155H. `CPU max MHz : unknown` in `environment/tw-Service.txt` because the WSL2 guest does not expose clock speed, so we could not watch the clock during a run | Later runs of a three-run set are slower than the first, which inflates the spread. Against us | **[TO FILL: whether `tw` was on mains power and in a high-performance power mode during the runs]** |
| **Other processes** on the service or Ollama host | **[TO FILL: yes or no]** | **[TO FILL: what else was open on `tw` during the runs, for example VS Code, a browser, Docker Desktop's window]** | Adds latency and variance. Hurts the p95 and p99 more than the p50. Against us | **[TO FILL: what you closed, or "none — accepted"]** |
| **Wi-Fi jitter** between the load generator and the service | Yes. Both laptops are on Wi-Fi through `192.168.50.1` (`192.168.50.15` and `192.168.50.73`) | Section 3 ping over 20 packets: min / avg / max = 4.0 / 51.0 / 187.8 ms, mdev 47.5 ms **[CONFIRM: copy from your saved ping output, with the date and time measured]** | Inflates the tail. A p99 can be a radio retransmission instead of the service. Against us | Each run is reconciled against the service log before any figure is quoted. A run that fails is discarded, not reported |
| **A shared machine** (a guest sharing a physical CPU) | Yes. Both machines are WSL2 guests on Windows | `Virtualisation : Microsoft` in `environment/tw-Service.txt` and `environment/tw-Ollama.txt`. **[CONFIRM the same line in `environment/kthgoat.txt`]** | Unpredictable in both directions. The guest's CPUs are scheduled by Windows alongside every Windows process, which weakens run-to-run comparability | None — accepted and stated. Three runs per configuration show the spread |
| **The WSL2 guest's resource allocation** | Yes for `tw` | The guest sees 22 logical CPUs, 15.3 GiB RAM and 4.0 GiB swap (`environment/tw-Service.txt`, sections 2 and 3), not the whole physical machine | Memory pressure starts earlier than on the same hardware running Linux directly. Against us for the larger models | None. The WSL2 defaults were left alone, consistent with not tuning the baseline |
| **Container CPU limits** | Not applied — stated for completeness | `../docker-compose.yml` sets no `cpus`, `cpuset` or `mem_limit` on either service, deliberately: limiting them would be tuning | The baseline gets the whole machine, so our numbers are an **upper bound** on what the client would see if they limited the same container | None — accepted, and the consequence is stated |
| **Ollama cold start** (first-request model load) | Handled, but state it | `scripts/run_load_test.sh` sends one `X-Warmup: 1` request before every measured window and writes its log line to `warmup.jsonl`, outside `service.jsonl`. `OLLAMA_KEEP_ALIVE : unset (Ollama default)` in section 5 of `environment/tw-Ollama.txt` | Our numbers describe a **warm** service. That is optimistic relative to a client whose model is evicted between quiet periods and reloaded on the next ticket | Warm-up request, excluded from analysis. The cold-start cost stays visible as `load_duration` in the service log |
| **A single SQLite file, one writer** | Applies by design | `DB_PATH=/data/triage.db`, a new connection per request, no WAL, no pooling (`../service/db.py`) | `GET /search` is a full-table scan, so its cost grows with stored tickets. The store holds about 10 tickets at the end of a mixed run (R5: 1 ticket/min for 600 s) and about 120 at the end of the R2 run (12 tickets/min for 600 s). A client store holding a year of tickets is larger. Optimistic for search latency | `scripts/reset.sh --yes` wipes the database volume before every measured run, so each run starts empty. **[CONFIRM the end-of-run counts with `GET /stats` on one real run]** |
| **JDK version on the load generator** | **[TO FILL: yes or no]** | `java (used by JMeter)` in section 6 of `environment/kthgoat.txt`: **[TO FILL: the version number the final capture shows, which must be 17 or 21]**. JMeter 5.6.3 needs Java 17 or 21 (`../jmeter/README.md` section 7) | On a much newer JDK the plans' Groovy pre-processors fail silently and samples go missing. That understates the offered rate, which flatters the service | **[TO FILL: what was installed and when it was re-captured before the reported runs]** |
| **Clock skew between machines** | Yes, in principle. Each WSL2 guest takes its clock from its Windows host | The service log's `ts` and JMeter's `timeStamp` come from two clocks. `analysis/reconcile.py` fails a run whose client-minus-server latency p99 exceeds 250 ms by default, and `SLICE_MARGIN_S` widens the log slice by 5 s at each end | Skew does not change the service's real latency, but can void a run by making it unreconcilable | **[TO FILL: whether Windows time sync was running on both laptops, and the source it reported]** |
| **Swap** on the Ollama host | Present but not expected to bite | `Total RAM : 15.3 GiB`, `Total swap : 4.0 GiB` (`environment/tw-Ollama.txt`, section 3). The largest candidate, `qwen2.5:7b`, is about a 4.7 GB download (`../README.md` section 3.2) | If a model did not fit, latency would become disk latency: catastrophic and non-linear, visible as a step change in `eval_duration` rather than an error | **[TO FILL: how you confirmed only one model was loaded at a time, for example `docker exec ict3113-ollama ollama ps` between candidates]** |
| **Battery or power profile** on a laptop | **[TO FILL: yes or no]** | Whether any machine ran on battery or a power-saving mode during a run | A power-saving mode lowers the clock and makes every CPU-bound model call slower. Against us | **[TO FILL: "both on mains, high-performance mode", or what was true]** |

No VPN or proxy sat between the machines: JMeter posts directly to a private address on the local network.

---

## 6. How results scale to the client's deployment

The brief requires this, and it requires the reasoning, not a reassurance. The client's hardware is
*"commodity CPU servers with no GPUs"*; ours is whatever section 2 says it is. The argument has to bridge
that gap explicitly, and it has to say where it stops working.

Answer these in order. Each is a paragraph or a short table, not a sentence.

1. **What is the same?**
   The client would inherit these exactly: CPU-only inference; the same Ollama version (0.35.0); the same model
   weights, identified by the tag and digest pinned in `../models/models.yaml` and recorded in every run's
   `metadata.json`; the same prompt, whose hash is in every log line; `NUM_CTX=4096`; one uvicorn worker; and synchronous classification with no caching, queuing or batching.


2. **What is different, and by how much?**
   | Axis | Ours | Assumed for the client | Assumption or fact |
   |---|---|---|---|
   | Processor class | Mobile Core Ultra 7 155H, hybrid cores, 22 logical CPUs visible to the guest | A server processor with uniform cores | Assumption |
   | Vector extensions | AVX2, AVX-VNNI, FMA, F16C; no AVX-512 | At least AVX2; AVX-512 on many server parts | Ours is fact (capture); theirs is an assumption |
   | Memory | 15.3 GiB given to the guest | More memory, and more memory channels | Assumption |
   | Execution environment | WSL2 guest under Windows, sharing the machine with a desktop session | Linux on a dedicated server | Assumption |
   | Sustained load | Laptop cooling | Server cooling, designed for continuous load | Assumption |
   | Network | A local link with a 4 to 188 ms round trip | A data-centre network between intake and service | Assumption |
   | Data store | Empty at the start of every run | A store that accumulates tickets | Fact about ours; theirs follows from the workload model |

3. **Which direction does the difference push our numbers?**
   Our position is that our latency and throughput figures are **pessimistic** for a dedicated commodity server
   of a recent generation. A virtualised laptop that shares its processor with a desktop, throttles under
   sustained load and has less memory bandwidth is slower per request and sustains a lower arrival rate than a
   dedicated server. A requirement we meet here should be met there; a requirement we narrowly miss here is not
   proof the client would miss it.

   Three things run the other way, and they are the ones to watch:

   * **Warm model.** We measure after a warm-up. A client whose tickets arrive further apart than Ollama's idle
   timeout pays the model-load cost on those tickets.
   * **Empty store.** Our search latency is measured over at most about 120 stored tickets. The client's store
   grows without limit, and `GET /search` scans all of it.
   * **Whole machine.** Our containers are unconstrained. A client who limits the container gets less.

4. **What scales linearly and what does not?**
   * **Throughput at a fixed latency (R2)** depends on how many model evaluations the hardware sustains at once.
   It scales roughly linearly with additional hosts behind a load balancer, and it improves with more cores
   per host only if Ollama is allowed to use them, which is a setting we did not tune.
   * **Single-request latency (R1)** does not scale that way. One ticket is one model evaluation, bound by
   per-core speed and memory bandwidth. Adding hosts does not shorten it. If the recommended model misses R1
   on the client's hardware, the remedy is a smaller model or a faster processor, not more servers.
   * **Accuracy (R3, R4)** is independent of hardware. With the same weights, prompt, seed and temperature, the
   classifications are the same on any machine, so our accuracy results carry over directly.
   * **Search under mixed load (R5)** depends on contention with model inference and on the size of the store.
   Our result covers the first and not the second.

5. **What would you have to re-measure before promising the client anything?**
   Before promising the client a latency or throughput figure, repeat these on their own servers, for the
   recommended model only:

   1. `playbooks/load-test.md` at the R1 and R2 arrival rates, three runs each.
   2. The mixed test in `playbooks/load-test.md` section 10, against a store pre-filled to a realistic size, to
      test R5 properly.
   3. `playbooks/accuracy-test.md` once, as a check that the pinned digest reproduces our accuracy.

6. **The limits of this extrapolation, stated plainly.**
   The argument rests on three assumptions: that the client's tickets resemble ours in length (ours are rows
   10000 to 10999 of the course extract, up to 1,999 characters); that they run one model per host, as we do; and
   that the classifier does not share its server with other work. If any of these is false, our figures do not
   transfer.

   Stated plainly: our environment supports claims about **which model is faster and which is more accurate**,
   and about **accuracy in absolute terms**. It does not support a promise about absolute latency or capacity on
   the client's hardware. Those need the re-measurement in section 5.5.
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
