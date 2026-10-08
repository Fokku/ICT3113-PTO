# Test environment (Slide 7)

**What this document is for.** It is the test-environment description the brief demands in Step 5, and the
source Slide 7 ("Test Environment") is built from. Every hardware and software figure below is copied from a
capture file in [`environment/`](environment/) written by `scripts/capture_env.sh`, from a command whose output
is quoted with the time it was run, or from a run's `metadata.json`. Nothing is from memory.

**Owner:** Part 5 — Koh Tong Wei. The machines changed on 8 October 2026 (see [`run-log.md`](run-log.md)); this
version was written by Part 1 — Yeo Kai Yuan, whose two machines replaced the original pair, from the captures of
those machines.

**The setup in one paragraph.** Two machines on one home LAN. **Machine 1**, the service host `omarchy`, is
Yeo Kai Yuan's desktop: it runs the triage service and Ollama, both in Docker Engine natively on Linux, CPU only.
**Machine 2**, the load generator `kais-macbook-pro`, is Yeo Kai Yuan's MacBook Pro: it runs JMeter,
`scripts/run_accuracy.py` and `scripts/run_campaign.sh`, and no service or model. The first pair of machines
(`tw` and `kthgoat`) became unavailable before any reported run; their captures are kept in
[`environment/superseded/`](environment/superseded/) and no reported number comes from them.

**The brief's exact demands:** *"describe your test environment: the machines running the service, Ollama, and
the load generator; their CPU, memory, and operating system; the network between them; and any factors that
could make your measurements unrepresentative. Indicate how results from your test environment scale to the
client's deployment."* And: *"The load generator and the system under test must run on separate machines."*

---

## 1. The captures

| File | Machine | Declared role | Captured (UTC) |
|---|---|---|---|
| [`environment/omarchy-Service.txt`](environment/omarchy-Service.txt) | `omarchy` | `service` | 2026-10-08 11:41 |
| [`environment/omarchy-Ollama.txt`](environment/omarchy-Ollama.txt) | `omarchy` | `ollama` | 2026-10-08 11:41 |
| [`environment/kais-macbook-pro-Loadgen.txt`](environment/kais-macbook-pro-Loadgen.txt) | `kais-macbook-pro` (macOS reports `Kais-MacBook-Pro-2.local`) | `loadgen` | 2026-10-08 11:49 |

The capture script names its file after the host name; the files were renamed with the role suffix, as the
superseded `tw-Service.txt` / `tw-Ollama.txt` pair was. No file declares `Declared role: all`.

---

## 2. The machines

| Role | Hostname | CPU | Cores / threads | RAM | OS and kernel | Docker | Ollama | JMeter | Capture |
|---|---|---|---|---|---|---|---|---|---|
| Triage service (`POST /tickets`, `GET /search`, `GET /stats`) | `omarchy` | AMD Ryzen 9 5900X (Zen 3, x86_64; AVX2 and FMA, no AVX-512); max 4.95 GHz; 64 MiB L3 | 12 / 24 | 31.3 GiB (swap 15.6 GiB, 0 B used) | Arch Linux, kernel 7.2.3-arch1-3 | Docker Engine 29.7.2, native (no VM); Compose 5.5.1 | — | not installed | `omarchy-Service.txt` |
| Ollama model backend (CPU only) | `omarchy` (same machine) | same | same | same | same | same | **0.34.3** (`ollama/ollama` container) | not installed | `omarchy-Ollama.txt` |
| Load generator (JMeter, accuracy driver) | `kais-macbook-pro` | Apple M3 Pro (arm64) | 11 cores (no SMT) | 18.0 GiB | macOS 15.1.1 (24B91), Darwin 24.1.0 | installed but **not running** during reported runs (Docker Desktop quit) | none | **5.6.3**, on OpenJDK 21.0.12.1 (set in JMeter's `bin/setenv.sh`) | `kais-macbook-pro-Loadgen.txt` |

The load generator's capture prints `java (used by JMeter): 23.0.1`, because it reports the `java` on the
shell's `PATH`. JMeter itself runs on OpenJDK 21: its `bin/setenv.sh` sets `JAVA_HOME=/opt/homebrew/opt/openjdk@21`
(`java -version` there: `openjdk version "21.0.12.1"`). That matters — see the JDK factor in section 5.

**CPU only.** The service host has an NVIDIA GeForce GTX 1660 (`lspci`: `TU116 [GeForce GTX 1660]`), and it is
deliberately **not** passed to the container: `docker inspect ict3113-ollama` shows `DeviceRequests: null`, there
is no GPU device in [`../docker-compose.yml`](../docker-compose.yml), and the `ollama/ollama` container has no
NVIDIA runtime. Ollama therefore runs on the CPU, as the client's hardware would.

### 2.1 Software configuration in force

Confirmed on 8 October 2026 against `GET /health` and `docker exec ict3113-ollama env` on the service host, and
recorded again in every run's `metadata.json`:

| Setting | Value in force | Why it is on the slide |
|---|---|---|
| `UVICORN_WORKERS` | `1` | One worker, one event loop, one writer to SQLite and to the log. The process model is part of the baseline. |
| `SERVICE_THREADPOOL_SIZE` | `40` | The thread pool blocking SQLite calls are handed to. Set explicitly so it is visible. |
| `NUM_CTX` | `4096` | Ollama's default (2048) would silently truncate our longest prompts (~612 approximate tokens, `../workload/output/ticket_length_stats.md`) less often than you might think, but 4096 removes the question. |
| `OLLAMA_TIMEOUT_S` | `120` | The service's own model-call timeout. A `502` with `error: "ollama_timeout"` is this limit being hit. |
| seed / temperature | `42` / `0` | Re-running the accuracy test on the same model gives the same answers. |
| `OLLAMA_NUM_PARALLEL` | `0` in the container's environment — Ollama's "use the default" sentinel, documented as **1** request at a time per model, the rest queued (`OLLAMA_MAX_QUEUE`, default 512) | **Not tuned.** The prediction record puts the bottleneck here; tuning it is Assignment 2. |
| `OLLAMA_MAX_LOADED_MODELS` | `0` (same sentinel; Ollama's default) | The harness serves one model per run. |
| `OLLAMA_KEEP_ALIVE` | unset — Ollama's default of 5 minutes | Every measured window is preceded by a warm-up request, so no measured request pays the model load. |
| Container CPU / memory limits | none (`NanoCpus 0`, `Memory 0`) | The baseline gets the whole machine. See section 5. |
| Model pins | the four digests in [`../models/models.yaml`](../models/models.yaml), checked against `/health` before every configuration by `scripts/run_campaign.sh` | Slide 5 and every run's `metadata.json` carry the same digest. |

---

## 3. The network between the machines

| Property | Value | How it was established |
|---|---|---|
| Link, service host | Wired Gigabit Ethernet: `enp38s0`, 1000 Mb/s, full duplex | `/sys/class/net/enp38s0/speed` and `duplex` |
| Link, load generator | Wi-Fi 802.11ac (5 GHz, channel 40, 80 MHz), transmit rate 866 Mb/s, signal −40 dBm / noise −92 dBm | `system_profiler SPAirPortDataType`; `networksetup -listallhardwareports` (`en0` is the Wi-Fi port) |
| Path | Both on the home router `192.168.50.1`; no VPN, proxy or tunnel on the measured path | `route -n get default` on the MacBook |
| Addresses | service host `192.168.50.130/24`; load generator `192.168.50.35/24` — same subnet | section 7 of both capture files |
| Measured round trip, load generator → service host | 20 packets, 0% loss; min / avg / max / stddev = **2.218 / 3.515 / 6.797 / 1.638 ms** | `ping -c 20 -i 0.5 192.168.50.130` on the MacBook, 2026-10-08T11:51:30Z |
| Measured HTTP cost of `GET /health` | TCP connect **3.0–4.0 ms**; complete response **14.8–19.8 ms** (5 requests) | `curl -w 'connect=%{time_connect}s total=%{time_total}s'`, same time |
| Name resolution | none: JMeter and the accuracy driver are given the IP address `192.168.50.130` (`TARGET_HOST`) | the campaign environment; `service_url` in every `metadata.json` |
| Control channel (not measured traffic) | SSH from the MacBook to the service host over the Tailscale address `100.85.101.39`, used only for `docker compose`, `scripts/reset.sh` and `rsync` of `logs/service`, between measured windows | `SERVICE_SSH=omarchy` in `scripts/run_campaign.sh`; the service host's firewall (`ufw`) admits SSH only on the tailnet |

**What this means for our numbers.** The worst round trip measured (6.8 ms) is under 0.1% of R1's 10 s
`POST /tickets` threshold and about 0.3% of R5's 2 s `GET /search` threshold. The network is not a material share
of any latency we report, and the service log's own timings (`total_latency_ms`) exclude it entirely;
`analysis/reconcile.py` checks that JMeter's `elapsed` and the service's `total_latency_ms` agree within its
threshold for every sample.

---

## 4. CONFIRMATION: the load generator ran on a separate machine

> **Confirmation.** Apache JMeter and `scripts/run_accuracy.py` ran on `kais-macbook-pro` (Apple M3 Pro MacBook
> Pro). The system under test — the triage service container and the Ollama container — ran on `omarchy`
> (Ryzen 9 5900X desktop). No JMeter process, triage service or model ran on the other machine during a
> reported run: JMeter is not installed on `omarchy`, and on the MacBook the containers left from the
> afternoon rehearsals were stopped and Docker Desktop was quit before the campaign.

| Evidence | Where | What it shows |
|---|---|---|
| Two capture files, two host names, three roles | `environment/` | `omarchy-*` declare `service` and `ollama`, with `jmeter binary : not installed`; `kais-macbook-pro-Loadgen.txt` declares `loadgen`, with JMeter 5.6.3 |
| The address every request was sent to | `service_url` in each `../results/runs/*/metadata.json` and `../results/accuracy/*/metadata.json` | `http://192.168.50.130:8000` — never a loopback address |
| The machine JMeter ran on | `load_generator_host_info.hostname` in the same files | the MacBook, a different host name from `omarchy` |
| Same code on both machines | `scripts/run_load_test.sh` refuses a real run when `git rev-parse HEAD` differs between the two checkouts | every run's `git_commit` is the frozen commit or later |

The per-run check over every directory cited on the slides is recorded in section 4.1 once the campaign is
complete.

---

## 5. Factors that could make our measurements unrepresentative

| Factor | Does it apply? | How we know | Direction of bias | Mitigation |
|---|---|---|---|---|
| **Other processes on the service host** | Yes: `omarchy` is a personal desktop with a Wayland session, and the operator's terminal session (including the AI coding assistant used to drive the campaign and write documents) ran on it throughout. Other desktop use during the overnight campaign was not controlled | `run-log.md` | Adds variance and occasional tail latency to CPU-bound model calls; hurts p95/p99 more than p50 | The assistant's work during the campaign was text editing; no builds, model runs or other containers were started on `omarchy` while it ran. Run-to-run spread is reported, so any interference shows |
| **Wi-Fi on the load generator** | Yes | section 3 | Inflates JMeter's client-side tail by milliseconds, at most a few tenths of a percent of any threshold; the service log's timings are unaffected | None needed at this scale; the network share is reported per run by `analysis/reconcile.py` |
| **Desktop CPU, not a server** | Yes | section 2: 12 Zen 3 cores, two DDR4 memory channels (the AM4 platform), boosting to 4.95 GHz | Single-request latency on our desktop is likely **better** than on a commodity server core at a lower clock; capacity per host is likely **worse** than a many-core server with more memory channels — see section 6 | Stated, not corrected |
| **CPU frequency governor** | Set to `performance` on `omarchy` (power profile `performance`); the MacBook was on AC power, lid open, `caffeinate` held | `/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor`; `pmset -g batt`; `ioreg` clamshell state | A power-saving governor would slow every model call; this one does not | None needed |
| **Thermal behaviour** | Possible on a long CPU-bound campaign, even on a desktop | the campaign runs ~12 h of near-continuous inference for the larger models | Later runs of a three-run set slightly slower than the first; shows as run-to-run spread | Three runs per configuration, spread reported; models interleaved by phase, not run back to back |
| **No container limits** | Yes, by design | `docker inspect`: `NanoCpus 0`, `Memory 0` | The baseline gets the whole machine, so our capacity is an **upper bound** for the same container under a cgroup limit | Stated |
| **Ollama warm-up** | Handled | one `X-Warmup: 1` request per measured run, logged to `warmup.jsonl`, excluded from analysis | Our numbers describe a warm model — optimistic for a client whose model is evicted after `OLLAMA_KEEP_ALIVE` (5 min) of idleness, which at the modelled ~4 tickets per day would happen before most tickets | Stated; the cold-start cost is visible in `load_duration` of each warm-up line |
| **SQLite, one file, one writer, growing table** | By design | `../service/db.py`; `scripts/reset.sh --yes` empties the database before every run | `GET /search` gets slower as the table grows; our runs hold at most the tickets of one run, far fewer than a year of client data | Reset before every run; stated |
| **JDK on the load generator** | Handled | JMeter 5.6.3 needs Java 17 or 21; on newer JDKs its Groovy pre-processors can fail silently and drop samples | A silent shortfall would understate the offered rate and flatter the service | JMeter pinned to OpenJDK 21 in `bin/setenv.sh`; `analysis/reconcile.py` checks every sample has a log line |
| **Clock skew** | Small | `omarchy`: NTP synchronised (`timedatectl`); MacBook offset **+0.27 s** against `time.apple.com` (`sntp`, 2026-10-08) | Skew does not change latency (both sides measure durations on their own clock); it only shifts the log slice | The harness widens the service-log slice by 5 s at each end |
| **Swap** | No | 31.3 GiB RAM against the largest candidate's 4.7 GB of weights; `free -h`: swap 0 B used | — | — |
| **VM or Docker Desktop on the measured path** | No | Docker Engine runs natively on Arch Linux on `omarchy`; Docker Desktop on the MacBook was quit and runs nothing we measure | — | — |

---

## 6. How results scale to the client's deployment

1. **What is the same.** CPU-only inference; the same Ollama version (0.34.3) and the same pinned model digests,
   all four at Q4_K_M; the same prompt (hash `sha256:681131c48bdc15a1`, in every log line); `NUM_CTX=4096`; one
   uvicorn worker; synchronous classification; Ollama's default concurrency of one request at a time per model.
   The client would run exactly this container image against exactly these weights.

2. **What is different.**

   | Axis that decides CPU inference speed | Our service host | A commodity 2-socket CPU server (assumption) |
   |---|---|---|
   | Cores per model evaluation | 12 physical (Ollama's default: one thread per physical core) | 16–64 physical per socket |
   | Clock | up to 4.95 GHz boost | typically 2.0–3.5 GHz all-core |
   | Memory channels | 2 × DDR4 | 8–12 × DDR4/DDR5 per socket |
   | Vector extensions | AVX2, FMA (no AVX-512) | AVX2 everywhere; AVX-512 on most current Xeon and EPYC parts |

3. **Which way it pushes our numbers.** *Prefill* (evaluating the ticket, which the prediction record expects
   to dominate service time) is compute-bound: per request it scales with cores × clock × vector width, so a
   server socket with 2–4× our cores and AVX-512 would likely evaluate a ticket **faster** than our desktop,
   even at a lower clock. *Decode* (the few reply tokens) is memory-bandwidth-bound, and a server's 4–6× memory
   bandwidth makes it faster too. Our single-request latencies are therefore more likely **pessimistic** than
   optimistic for a dedicated modern server, and **optimistic** for a small or shared virtual machine with a
   handful of vCPUs. We do not average the two: the direction depends on what "commodity" means for this
   client, which is why item 5 exists.

4. **What scales linearly and what does not.** With `OLLAMA_NUM_PARALLEL` at its default, one model evaluates
   one ticket at a time, so a host's capacity is 60 / S tickets per minute, where S is the service time we
   measure. Capacity therefore scales with **hosts** (or with parallel slots, if the cores allow it — an
   Assignment 2 question), and it scales with per-request speed. Single-request latency does not improve by
   adding hosts. R1 (latency at 1/min) depends only on S; R2 (12/min without backlog) depends on S being under
   5 s; R3/R4 (accuracy) do not depend on hardware at all — the same digest, prompt, seed and temperature give
   the same answers on any CPU — so the accuracy results transfer exactly.

5. **What must be re-measured before promising the client anything.** On one of the client's own servers:
   `docs/playbooks/load-test.md` for the recommended model at R1's and R2's rates (three runs each), and one
   `docs/playbooks/stress-test.md` ramp for it. Accuracy does not need repeating unless the model, digest or
   prompt changes.

6. **The limits of this extrapolation.** It assumes the client's ticket-length distribution matches our 1,000
   rows (`../workload/workload_model.md`), that they run one model per host with nothing else on it, and that
   their volume stays near the modelled peak. Our environment supports claims about **which model is faster and
   by how much relative to the others**, about **where the bottleneck is**, and about **accuracy in absolute
   terms**. It does not support a promise about absolute latency or capacity on the client's hardware; those
   need the runs in item 5.
