# Run log — ICT3113 Assignment 1 (Team 10)

**Owner:** Part 5 (Koh Tong Wei).
**Status:** rehearsals, plus one accuracy attempt on `tw` that predates the prediction record and is therefore
excluded (moved to `../results/excluded/`, see its entry below). Every reported run is made on the new test
environment after the re-cut freeze.

## Rules
1. One dated entry per configuration (one model x one plan x one rate), written straight after its runs.
2. Never delete an entry. A discarded or aborted configuration keeps its entry, with the reason; the re-run gets a new entry.
3. Dev-mode runs go under *Rehearsals* and are never quoted as evidence.
4. Every figure is copied from a screenshot, `metadata.json`, a capture file or `analysis/output/`. Square brackets mean **not yet filled or not yet confirmed**: replace them or leave them visible.
5. Times are UTC, with Singapore time (UTC+8) in brackets.

## Environment as rehearsed

| | Machine 1 | Machine 2 |
|---|---|---|
| Host | `tw` | `kthgoat` |
| Role | triage service + Ollama | JMeter load generator, run scripts |
| Wi-Fi address | 192.168.50.73 | 192.168.50.15 (`ipconfig`: Wi-Fi 192.168.50.15/24, gateway 192.168.50.1; Ethernet adapter "Media disconnected") |
| Layer | WSL2 / Docker Desktop on Windows | WSL2 (Ubuntu 26.04.1) on Windows |
| Capture | `environment/tw-Service.txt`, `environment/tw-Ollama.txt` | `environment/kthgoat-Loadgen.txt` (captured 2026-10-07T17:30:56Z: JMeter 5.6.3, Java 21.0.12.1) |

## Rehearsals (dev mode — not evidence)

### 2026-10-07 17:12–17:15 UTC (2026-10-08 01:12–01:15 SGT) — network and reachability checks, machine 2 to machine 1
- Evidence: screenshots of the terminal on `kthgoat` (WSL) and `tw`; [file names/location of the saved screenshots].
- Results:

  | Check | Command (run on `kthgoat` unless stated) | Result |
  |---|---|---|
  | Packet loss and round trip | `ping -c 20 192.168.50.73` | 20 sent, 20 received, **0% loss**; rtt min/avg/max/mdev = **4.039 / 50.953 / 187.839 / 47.456 ms** (worst sample `icmp_seq=16`, 188 ms) |
  | HTTP cost of `/health` | `curl -s -o /dev/null -w 'connect=%{time_connect}s total=%{time_total}s\n' http://192.168.50.73:8000/health` | connect = 0.005635 s, total = 0.039474 s (one sample) |
  | Service health from machine 2 | `curl -s http://192.168.50.73:8000/health` | `status: ok`, `ollama_reachable: true`, `model_tag: llama3.2:1b`, **`model_digest: null`**, `num_ctx: 4096`, `seed: 42`, `prompt_hash: sha256:681131c48bdc15a1`, `ollama_timeout_s: 120.0`, `uvicorn_workers: 1`, `threadpool_size: 40` |
  | Clocks | `date -u; ssh tongw@192.168.50.73 'date -u'` | both **Wed Oct 7 17:14:49 UTC 2026** (agree to the second) |

- 1. Who and when: [name]; 17:12:35 to 17:14:49 UTC.
- 2. Other activity on each machine: [what else was open on `tw` and `kthgoat`].
- 3. Physical setup: both on Wi-Fi (same subnet, same gateway). [mains or battery, power mode, on each laptop]. The ping ran from inside WSL on `kthgoat`, so it includes WSL2's virtual network layer.
- 4. Done by hand: SSH from `kthgoat` to `tw` as `tongw` returned without a password prompt in the screenshot [confirm key-based login].
- 5. Accepted oddities: wide Wi-Fi jitter (min 4 ms, max 188 ms, mdev 47 ms), reported on Slide 7. `/health` showed `model_digest: null`, meaning the model was not yet confirmed as pulled (see attempt 2 below).
- 6. Wall-clock: about 2 minutes.
- 7. Verdict: **rehearsal** (network measurements for Slide 7, repeat if the network changes).

### 2026-10-07 17:32 UTC (2026-10-08 01:32 SGT) — load_post_tickets — llama3.2:1b — 60 / min, 60 s — dev, 1 run — attempt 1, ABORTED
- Run directory: `results/dev/runs/20261007T173203Z_llama3.2-1b_load_post_tickets_60pm_run1` [check what it contains; likely no `results.jtl`].
- Command: `scripts/run_load_test.sh --plan load_post_tickets --model llama3.2:1b --rate 60 --duration 60 --runs 1 --host 192.168.50.73 --dev --yes`
- What the script reported: service `http://192.168.50.73:8000`, JMeter `/home/user/apache-jmeter-5.6.3/bin/jmeter` (5.6.3), input `data/dev/synthetic_tickets.csv`, service log `logs/service` (the local repo folder), freeze gate bypassed (`--dev`).
- Outcome: stopped at **step [2/6] reset and switch model**: `The command 'docker' could not be found in this WSL 2 distro.` No warm-up and no JMeter run took place.
- 1. Who and when: [name]; started 17:32:03 UTC.
- 2. Other activity: [..]
- 3. Physical setup: [Wi-Fi; mains or battery]
- 4. Done by hand afterwards: Docker became usable from WSL (a later `docker version` shows client 29.8.2 and server Docker Desktop 4.79.0, engine 29.5.3). [Confirm what was changed, e.g. Docker Desktop WSL integration switched on.]
- 5. Accepted oddities: none; the run was abandoned.
- 6. Wall-clock: [seconds].
- 7. Verdict: **rehearsal, aborted**.

### 2026-10-07 17:37 UTC (2026-10-08 01:37 SGT) — load_post_tickets — llama3.2:1b — 60 / min, 60 s — dev, 1 run — attempt 2, ABORTED
- Run directory: `results/dev/runs/20261007T173713Z_llama3.2-1b_load_post_tickets_60pm_run1`
- Same command as attempt 1. This time the script printed `Service log : /home/user/tw-logs` [state how machine 1's log folder is made visible there: sshfs / NFS / other].
- Outcome: step [2/6] **succeeded**: it stopped and removed the triage container, removed and recreated volume `ict3113-triage_triage_db`, restarted triage, waited until healthy, started the Ollama container, and `/health` reported model `llama3.2:1b`, Ollama reachable. It then **failed at step [3/6] (warm-up)**:
  `FAIL: the warm-up POST returned HTTP 502 ... {"detail":"model backend did not classify the ticket","error":"ollama_http_error","request_id":"warmup-fbca83d2-..."}`
  The script stops here on purpose, so that the model-load cost does not land on the first measured sample. No JMeter measurement took place.
- Likely cause (**not yet confirmed**): `llama3.2:1b` is not present in the Ollama container's model volume (`/health` earlier showed `model_digest: null`). Check with `docker exec ict3113-ollama ollama list`.
- 1. Who and when: [name]; started 17:37:13 UTC.
- 2. Other activity: [..]
- 3. Physical setup: [..]
- 4. Done by hand: [model pull, if done].
- 5. Accepted oddities: none; the run was abandoned.
- 6. Wall-clock: [seconds].
- 7. Verdict: **rehearsal, aborted**.

## Setup changes made during the rehearsal (not runs)
- **Java:** `sudo update-alternatives --config java` listed `java-25-openjdk-amd64` as the automatic default (priority 2511) and `java-21-openjdk-amd64` as a manual choice (priority 2111). In that screenshot the two lines typed at the selection prompt (`java --version`, `scripts/capture_env.sh --role loadgen`) were not valid selections, so nothing changed there; the choice that selects Java 21 is `1`. The later capture shows `openjdk version "21.0.12.1"`. [Confirm when Java 21 was selected.]
- **Docker in WSL:** see attempt 1 and 2.

## Playbook defects found (fix in `docs/playbooks/`)
1. On Windows with WSL, `docker` is not available inside the WSL distro until Docker Desktop's WSL integration is on. `run_load_test.sh` fails at step [2/6] without it. State this as a prerequisite in `load-test.md`.
2. After installing a second JDK, Java 25 stayed the automatic default. Add `update-alternatives --config java` (and `java -version` before every session) to the load-generator setup.
3. A warm-up HTTP 502 `ollama_http_error` is the first sign that the model has not been pulled. Add to the abort table: run `docker exec ict3113-ollama ollama list` and pull the model before retrying.

## Open items before the first real run (on `tw`/`kthgoat`; superseded on 8 October 2026, see below)
- [ ] **Which machine's Docker engine does `kthgoat`'s `docker` talk to?** A later `docker version` shows `Context: default` and a Docker Desktop server. If `DOCKER_HOST` is empty, that engine is `kthgoat`'s own, and the reset in attempt 2 restarted containers on the load generator, not on `tw`. Check `echo $DOCKER_HOST` and `docker ps` on `kthgoat`. If `ict3113-*` containers are running there, stop them (`docker compose --profile local-ollama down`) before any run.
- [ ] Pull the model on machine 1 and rerun the dev load test to the end. Expect `results.jtl`, `metadata.json` and `service.jsonl` in the run folder.
- [ ] In that run's `metadata.json`: `service_url` is `http://192.168.50.73:8000`, `load_generator_host_info.hostname` is `kthgoat`.
- [ ] Freeze gate passes (`python scripts/freeze_gate.py`) and the tag `golden-freeze` exists.

## 8 October 2026 — what changed before any reported run

These entries record decisions and rehearsals, not measurements. Times are UTC (SGT in brackets).

### Morning (before ~07:30 UTC): the freeze was found to be empty
- The `golden-freeze` tag created at 04:28 UTC (12:28 SGT) on `ef5a1b2` passed `scripts/freeze_gate.py`, but the
  prediction record in that commit was the unfilled template. The gate checks that the file is committed, not
  that it is filled in.
- The `llama3.2:1b` accuracy attempt on `tw` (05:25 UTC, entry below) was therefore made before any prediction
  existed. It is **excluded**: moved to `../results/excluded/accuracy/` and explained in
  `../results/excluded/EXCLUDED.md`. It is repeated after the re-cut freeze.

### The test environment changed
- `tw` and `kthgoat` became unavailable. The campaign moves to a new service host (Yeo Kai Yuan's Ryzen desktop at home:
  triage service and Ollama, CPU only, in Docker) and a new load generator (Yeo Kai Yuan's Apple M3 Pro MacBook,
  JMeter 5.6.3 on OpenJDK 21). Their captures are in `environment/`; the old ones moved to
  `environment/superseded/`.
- The harness gained a remote mode (`SERVICE_SSH`): compose and `reset.sh` run in the service host's checkout over
  SSH, and its `logs/service` is mirrored with `rsync`. This replaces the `DOCKER_HOST` + sshfs arrangement
  above, which needed the same absolute repository path on both machines.

### 08:39–09:11 UTC (16:39–17:11 SGT) — five dev rehearsals of the whole campaign on the MacBook — dev, not evidence
- What: `scripts/run_campaign.sh --dev --models llama3.2:1b` with short durations, the service and Ollama in Docker on
  the same MacBook (co-hosted, which is exactly why none of it is evidence), synthetic tickets only, output under
  the gitignored `results/dev/`.
- Defects found and fixed before any real run (commit "Harness: remote service host over SSH…"):
  1. `run_load_test.sh` did not pass `-q jmeter/user.properties`.
  2. JMeter 5.6.3 writes the sample-variable header names in double quotes; the `.jtl` column check failed every run
     (also found independently on `tw`, see "Playbook defects" above).
  3. `analysis/common.read_jtl` typed `source_row` as float whenever a cell was blank (every `GET /search` sample), so
     every `mixed_load` run failed reconciliation with "source_row disagreements".
  4. Three comment lines at the top of `data/search_terms.txt` were sent as search queries.
  5. JMeter idled ~60 s after each run before exiting (`jmeterengine.force.system.exit=true` now).
  6. A variable-name clash: the campaign's address variable was called `SERVICE_HOST`, which `docker-compose.yml`
     uses for uvicorn's bind address, so the container listened on its own loopback. Renamed `TARGET_HOST`.
- Decision recorded the same day: the steady-state plans end with a **150 s drain** (`pause(drain_s)`), passed by
  `run_load_test.sh` to every plan. Without it JMeter interrupted every request still in flight at the end of the
  window and recorded it as a failure (46 of 80 samples in an overload rehearsal; 0 with the drain).
- Verdict: **rehearsal**. The final rehearsal ran accuracy, load, mixed and stress end to end with exit 0, and every
  run reconciled with its service log.

### 11:30–11:50 UTC (19:30–19:50 SGT) — the freeze re-cut, and the environment every reported run uses
- **Local work merged.** The service host's uncommitted work of 2 October (the Q4_K_M 1B pin with real digests in
  `../models/models.yaml`, and freeze-gate condition 6) was merged onto the 8 October history; where the two
  disagreed, the 2 October decisions stand (commit `e09e772`). The 1B candidate is `llama3.2:1b-instruct-q4_K_M`.
- **Prediction record finished and frozen.** The hardware-dependent entries were filled from the service host's
  capture (no model had answered a request on it since the 2 October smoke test), the sign-off table records that
  no teammate responded before the freeze, and `golden-freeze` was moved with `git tag -f` to commit
  `41d6ce2c2aa8c9e03c9d1e2abe2e23096aba9fba` and force-pushed. `python scripts/freeze_gate.py --json`:
  `{"ok": true, "freeze_commit": "41d6ce2c2aa8c9e03c9d1e2abe2e23096aba9fba", "golden_rows": 200,
  "golden_sha": "12100cc67565be773c9aebccc1e072114bf1b708", "prediction_sha": "c1d1da3f0e2db2487d8f38a231affc6ddee0e608"}`.
- **Machines.** Service host `omarchy` (Yeo Kai Yuan's desktop: Ryzen 9 5900X, 31.3 GiB, Arch Linux, Docker
  Engine 29.7.2, Ollama 0.34.3 in the `ollama/ollama` container, CPU only; wired Ethernet, 192.168.50.130).
  Load generator `kais-macbook-pro` (Yeo Kai Yuan's MacBook Pro, Apple M3 Pro, 18 GiB, macOS 15.1.1, JMeter
  5.6.3 on OpenJDK 21 via `bin/setenv.sh`; Wi-Fi, 192.168.50.35, same subnet). Captures:
  `environment/omarchy-Service.txt`, `environment/omarchy-Ollama.txt`, `environment/kais-macbook-pro-Loadgen.txt`.
- **Harness wiring.** The campaign runs on the MacBook with `SERVICE_SSH=omarchy` (SSH over the tailnet address
  100.85.101.39, control only: compose, `reset.sh`, `rsync` of `logs/service`) and `TARGET_HOST=192.168.50.130`
  (every measured request goes over the LAN, not the tailnet). The service host's `ufw` blocks LAN SSH;
  Docker-published ports 8000 and 11434 are reachable on the LAN.
- **Done by hand.** On the MacBook: the triage and Ollama containers left over from the afternoon rehearsals were
  stopped and Docker Desktop was quit, so the load generator runs no model; mains power, `caffeinate`
  held by the campaign script. On the service host: `docker compose build triage` from the frozen commit.

### 11:49–12:15 UTC (19:49–20:15 SGT) — three rehearsals of the campaign on the new machines — dev, not evidence
- What: `scripts/run_campaign.sh --dev --models llama3.2:1b-instruct-q4_K_M` on the MacBook, remote mode against
  `omarchy`, synthetic tickets only, 45 s windows at 30/min (and a mixed test at 1 then 20/min), output under the
  gitignored `results/dev/`. These were the first requests any model answered on the service host since the freeze.
- Rehearsal 1 (started with `nohup … &` over an SSH session that then closed): the accuracy driver (Python) worked;
  **every JMeter sample failed** with `java.net.NoRouteToHostException: No route to host`, and no service log line
  fell in the measured window. Rehearsal 2, same launch: the same failure.
- Diagnosis: macOS 15 Local Network privacy. A `java` process started inside a live SSH session reached
  `192.168.50.130:8000`; the same program started with `nohup` and left running after the session closed got
  `No route to host`. JMeter run by hand inside a live session posted 8 of 8 tickets with HTTP 200.
- Fix: the campaign is launched from the service host as
  `setsid nohup systemd-inhibit … ssh -o ServerAliveInterval=30 mac '… scripts/run_campaign.sh'`, so the MacBook
  side stays inside a live SSH session for the whole run (and the service host cannot suspend). Recorded as a
  load-generator gotcha in `playbooks/load-test.md` section 2.3.
- Rehearsal 3 (launched that way): accuracy skipped (done), load 22/22 HTTP 200, mixed 15 + 15 HTTP 200; both runs
  `analysis/reconcile.py` **PASS** (every sample joined to its log line). `scripts/run_analysis.sh --results
  results/dev` produced every output type the deck reads.
- Verdict: **rehearsal**.

## Real runs

### Campaign `20261008T121603Z` — the reported runs (started 2026-10-08 12:16:03 UTC, 20:16 SGT)
- Command, from the service host (the MacBook side runs inside the SSH session, see the rehearsal entry above):
  `STRESS_MODELS="llama3.2:1b-instruct-q4_K_M llama3.2:3b granite4:3b qwen2.5:7b" scripts/run_campaign.sh` with
  `SERVICE_SSH=omarchy SERVICE_REPO=claude/ICT3113-PTO TARGET_HOST=192.168.50.130`, defaults otherwise: rates 1, 4
  and 12 per minute, 600 s, 3 runs; mixed 1 + 1 per minute; stress ramp 1–21 per minute in 120 s steps.
- Code and freeze: both checkouts at `41d6ce2` (the re-cut `golden-freeze` commit); `freeze_gate.py` passes.
- Who: started by the AI coding assistant at Yeo Kai Yuan's instruction; unattended overnight.
- The per-configuration record (run directories, wall-clock, reconciliation) is in the section
  "Campaign record" below, generated from each run's `metadata.json` and the campaign log
  `../results/campaign/campaign_20261008T121603Z.log`.

### After the campaign — 9 October 2026 (UTC; SGT is +8 h)
- **00:16 Campaign complete**, exit 0: every configuration complete, none excluded
  (`../results/campaign/campaign_20261008T121603Z.log`).
- **00:17–01:03 Steeper ramps**, run by the follow-up script exactly as `playbooks/stress-test.md` decided in advance:
  the models whose 1–21/min ramp crossed neither criterion (`llama3.2:1b-instruct-q4_K_M`, `llama3.2:3b`,
  `granite4:3b`, decided by `analysis/stress_summary.py` on each run) got one 10–60/min ramp each
  (`RAMP_START_PER_MIN=10 RAMP_STEP_PER_MIN=10`, `--duration 870`). All three exit 0, all reconcile.
- **Analysis defect found and fixed: stress steps were cut from the first sample.** The first analysis counted
  each 120 s step from the first sample's timestamp. With random arrivals the first sample comes a random delay
  after the schedule starts (1.9–67.5 s in our seven ramps), so every boundary shifted and late arrivals of the
  last step fell outside the window: the per-step counts did not match the schedule (for example 6 samples in a
  1/min step), and `qwen2.5:7b`'s limit read as 17/min. `analysis/stress_summary.py --origin jmeter-log` now cuts
  steps from the instant JMeter started the schedule (the `OpenModelThreadGroup: Starting` line of `jmeter.log`,
  converted to UTC); the counts now match the schedule exactly (2, 10, 18, 26, 34, 42 arrivals) and the limit is
  **21/min**. The reported figures are the corrected ones; the first pass decided only which models got the
  steeper ramp, and the corrected pass gives the same answer (no step above 6 s p95 for those three).
- **The per-request service overhead, located.** The service log shows a median 172–197 ms per `POST /tickets`
  spent in our handler outside the model call. Timed directly in the triage container after the campaign
  (`docker exec -i ict3113-triage python -`, 30 calls of `service.db.insert_ticket` on a scratch database in the
  same `/data` volume, deleted afterwards): **median 191.6 ms** (min 158.3, p95 391.7); opening the connection
  alone 0.14 ms; `journal_mode=delete`, `synchronous=2` (FULL). The volume is on btrfs over LUKS. The overhead is
  the commit's fsyncs. An Assignment 2 candidate (WAL, or `synchronous=NORMAL`), not changed here.
- **Separate-machine check over every run:** all 55 run directories and 4 accuracy runs are `mode: real`,
  `service_url: http://192.168.50.130:8000`, `load_generator_host_info.hostname: Kais-MacBook-Pro-2.local`,
  `freeze_commit` and `git_commit` `41d6ce2`, `model_digest` recorded.
- **`git_dirty: true` in every run's metadata** means untracked evidence (the run directories themselves and the
  mirrored `logs/service/` files) was present in the MacBook's checkout; no tracked file was modified.

### 2026-10-08 05:25:11–05:42:22 UTC (2026-10-08 13:25:11–13:42:22 SGT) — accuracy — llama3.2:1b — EXCLUDED (predates the prediction record)

- Run directory: [llama3.2-1b_20261008T052511Z](../results/excluded/accuracy/llama3.2-1b_20261008T052511Z/) (moved there from `results/accuracy/` on 8 October 2026).
- Who ran it: [operator not recorded]. Driver hostname: `tw`; service URL: `http://localhost:8000`.
- Wall-clock duration: **17 min 11.175 s**, calculated from `metadata.json` start/end timestamps. This is scheduling information, not a latency benchmark.
- Database reset beforehand: [not recorded]. Other activity, physical setup and manual changes: [not recorded].
- Freeze gate: **PASS**, 200 golden rows; tag `golden-freeze`, commit `ef5a1b21f5030966047a2bb438082ab80a893f8c`.
- Configuration: prompt hash `sha256:681131c48bdc15a1`; context `4096`; seed `42`; recorded git commit `a21b38f26f849ff1626e92e354df10cef66a39ab`; `git_dirty: true`; `model_digest: null`.
- Response coverage: **200 unique golden row numbers, 200 HTTP 200 responses**, with no response error slugs. There were **3 UNPARSEABLE predictions (1.5%)**, counted as incorrect.
- Service-log check: all **200 response request IDs** have matching log lines. The captured file contains **201 lines** because it also includes request `8a3cbf49-c190-4a8c-b6ae-9d6d57854bb4`, source row `10028`, timestamp `2026-10-08T05:25:08.637Z`. This precedes the run start by 2.551 s and falls inside the driver's default five-second slicing margin. It is excluded from the response-based scores below; its originating activity is [not confirmed]. The original evidence is preserved.

#### Provisional accuracy results

These figures were calculated by joining this run's `responses.csv` to `golden/golden_set.csv` on `row_number`, counting exact category matches. They are response-based calculations; the formal analysis tables and confusion-matrix chart have not yet been generated for this entry.

| Golden category | Correct / total | Recall | R4: ≥ 80% |
|---|---:|---:|---|
| Bank account or service | 29 / 40 | 72.50% | Fail |
| Consumer loan | 3 / 23 | 13.04% | Fail |
| Credit card | 1 / 27 | 3.70% | Fail |
| Credit reporting | 36 / 41 | 87.80% | Pass |
| Debt collection | 0 / 23 | 0.00% | Fail |
| Money transfer or service | 0 / 19 | 0.00% | Fail |
| Mortgage | 1 / 27 | 3.70% | Fail |

**Overall: 70 / 200 = 35.00%; 130 incorrect classifications, including 3 UNPARSEABLE. R3 (≥ 90%) fails. R4 fails because six of seven categories are below 80% recall.**

Predicted-category counts: Bank account or service 85; Consumer loan 10; Credit card 1; Credit reporting 100; Debt collection 0; Money transfer or service 0; Mortgage 1; UNPARSEABLE 3. The model never predicted Debt collection or Money transfer or service in this attempt.

- Verdict: **excluded, not evidence.** Decisive reason: it was made before any prediction had been written (the `golden-freeze` tag then in force froze an empty prediction-record template), so it cannot appear on a slide whatever its quality. It also had a dirty working tree and no recorded model digest. See `../results/excluded/EXCLUDED.md` and `../predictions/prediction_record.md` §0.
- Next steps: establish the model pin using the pinning script, run from a committed clean state, and repeat the entire golden set. Preserve this attempt. Generate formal accuracy tables and confusion matrices for the replacement run; do not retrofit a digest or change this attempt's metadata.
- Other attempts: `results/excluded/accuracy/llama3.2-1b_20261008T052403Z/` contains only `responses.csv`; no metadata, freeze verdict or service-log snapshot is available in that directory. It is not used for the scores above.

### Entry template (copy for each configuration)
```
### <YYYY-MM-DD> <UTC> (<SGT>) — <plan> — <model tag> — <rate> / min, <duration> s — runs 1–3
- Run directories: results/runs/<run1>, <run2>, <run3>
- 1. Who ran it, and when:
- 2. What else was happening on each machine:
- 3. Physical setup (cable or Wi-Fi; mains or battery; power mode; lid open):
- 4. Anything done by hand that the script did not do:
- 5. Anything that looked wrong and was accepted, and why:
- 6. Wall-clock for the whole configuration:
- 7. Verdict, in these words: "reportable" or "rehearsal":
- Checks: service_url, load_generator_host_info.hostname, reconcile.py result for each run
```

## Campaign record (generated by `scripts/campaign_record.py` from the run directories)

One row per configuration. Every run is real mode, frozen at the commit in its `freeze.json`, posted to
`service_url` from the host in `load_generator_host_info.hostname`; reconciliation is `analysis/reconcile.py`
via `scripts/run_analysis.sh`. Verdict for every row: **reportable** unless the row says otherwise.

| Model | Plan | Rate | Runs | Started (UTC) | Wall-clock | Load generator → service | Reconciliation |
|---|---|---|---|---|---|---|---|
| `llama3.2:1b-instruct-q4_K_M` | `load_post_tickets` | 1/min | 3 | 2026-10-08 12:43 | 39 min (last run ends 2026-10-08 13:21) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `llama3.2:1b-instruct-q4_K_M` | `load_post_tickets` | 4/min | 3 | 2026-10-08 13:22 | 39 min (last run ends 2026-10-08 14:00) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `llama3.2:1b-instruct-q4_K_M` | `load_post_tickets` | 12/min | 3 | 2026-10-08 14:01 | 39 min (last run ends 2026-10-08 14:39) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `llama3.2:3b` | `load_post_tickets` | 1/min | 3 | 2026-10-08 14:40 | 39 min (last run ends 2026-10-08 15:19) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `llama3.2:3b` | `load_post_tickets` | 4/min | 3 | 2026-10-08 15:19 | 39 min (last run ends 2026-10-08 15:58) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `llama3.2:3b` | `load_post_tickets` | 12/min | 3 | 2026-10-08 15:58 | 39 min (last run ends 2026-10-08 16:37) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `granite4:3b` | `load_post_tickets` | 1/min | 3 | 2026-10-08 16:39 | 39 min (last run ends 2026-10-08 17:17) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `granite4:3b` | `load_post_tickets` | 4/min | 3 | 2026-10-08 17:18 | 39 min (last run ends 2026-10-08 17:57) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `granite4:3b` | `load_post_tickets` | 12/min | 3 | 2026-10-08 17:57 | 39 min (last run ends 2026-10-08 18:37) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `qwen2.5:7b` | `load_post_tickets` | 1/min | 3 | 2026-10-08 18:38 | 40 min (last run ends 2026-10-08 19:18) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `qwen2.5:7b` | `load_post_tickets` | 4/min | 3 | 2026-10-08 19:18 | 39 min (last run ends 2026-10-08 19:57) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `qwen2.5:7b` | `load_post_tickets` | 12/min | 3 | 2026-10-08 19:58 | 39 min (last run ends 2026-10-08 20:36) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `llama3.2:1b-instruct-q4_K_M` | `mixed_load` | 1/min | 3 | 2026-10-08 20:37 | 39 min (last run ends 2026-10-08 21:16) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `llama3.2:3b` | `mixed_load` | 1/min | 3 | 2026-10-08 21:16 | 39 min (last run ends 2026-10-08 21:55) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `granite4:3b` | `mixed_load` | 1/min | 3 | 2026-10-08 21:56 | 39 min (last run ends 2026-10-08 22:35) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `qwen2.5:7b` | `mixed_load` | 1/min | 3 | 2026-10-08 22:36 | 39 min (last run ends 2026-10-08 23:15) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `llama3.2:1b-instruct-q4_K_M` | `stress_ramp` | ramp from 1/min | 1 | 2026-10-08 23:15 | 15 min (last run ends 2026-10-08 23:30) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `llama3.2:3b` | `stress_ramp` | ramp from 1/min | 1 | 2026-10-08 23:31 | 15 min (last run ends 2026-10-08 23:45) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `granite4:3b` | `stress_ramp` | ramp from 1/min | 1 | 2026-10-08 23:46 | 15 min (last run ends 2026-10-09 00:00) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `qwen2.5:7b` | `stress_ramp` | ramp from 1/min | 1 | 2026-10-09 00:01 | 15 min (last run ends 2026-10-09 00:16) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `llama3.2:1b-instruct-q4_K_M` | `stress_ramp` | ramp from 10/min | 1 | 2026-10-09 00:17 | 15 min (last run ends 2026-10-09 00:32) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `llama3.2:3b` | `stress_ramp` | ramp from 10/min | 1 | 2026-10-09 00:33 | 15 min (last run ends 2026-10-09 00:47) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |
| `granite4:3b` | `stress_ramp` | ramp from 10/min | 1 | 2026-10-09 00:48 | 15 min (last run ends 2026-10-09 01:02) | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 | PASS |

Run directories, per configuration:

- `llama3.2:1b-instruct-q4_K_M` `load_post_tickets` 1/min: `20261008T124213Z_llama3.2-1b-instruct-q4_K_M_load_post_tickets_1pm_run1`, `20261008T124213Z_llama3.2-1b-instruct-q4_K_M_load_post_tickets_1pm_run2`, `20261008T124213Z_llama3.2-1b-instruct-q4_K_M_load_post_tickets_1pm_run3`
- `llama3.2:1b-instruct-q4_K_M` `load_post_tickets` 4/min: `20261008T132139Z_llama3.2-1b-instruct-q4_K_M_load_post_tickets_4pm_run1`, `20261008T132139Z_llama3.2-1b-instruct-q4_K_M_load_post_tickets_4pm_run2`, `20261008T132139Z_llama3.2-1b-instruct-q4_K_M_load_post_tickets_4pm_run3`
- `llama3.2:1b-instruct-q4_K_M` `load_post_tickets` 12/min: `20261008T140042Z_llama3.2-1b-instruct-q4_K_M_load_post_tickets_12pm_run1`, `20261008T140042Z_llama3.2-1b-instruct-q4_K_M_load_post_tickets_12pm_run2`, `20261008T140042Z_llama3.2-1b-instruct-q4_K_M_load_post_tickets_12pm_run3`
- `llama3.2:3b` `load_post_tickets` 1/min: `20261008T143947Z_llama3.2-3b_load_post_tickets_1pm_run1`, `20261008T143947Z_llama3.2-3b_load_post_tickets_1pm_run2`, `20261008T143947Z_llama3.2-3b_load_post_tickets_1pm_run3`
- `llama3.2:3b` `load_post_tickets` 4/min: `20261008T151917Z_llama3.2-3b_load_post_tickets_4pm_run1`, `20261008T151917Z_llama3.2-3b_load_post_tickets_4pm_run2`, `20261008T151917Z_llama3.2-3b_load_post_tickets_4pm_run3`
- `llama3.2:3b` `load_post_tickets` 12/min: `20261008T155827Z_llama3.2-3b_load_post_tickets_12pm_run1`, `20261008T155827Z_llama3.2-3b_load_post_tickets_12pm_run2`, `20261008T155827Z_llama3.2-3b_load_post_tickets_12pm_run3`
- `granite4:3b` `load_post_tickets` 1/min: `20261008T163758Z_granite4-3b_load_post_tickets_1pm_run1`, `20261008T163758Z_granite4-3b_load_post_tickets_1pm_run2`, `20261008T163758Z_granite4-3b_load_post_tickets_1pm_run3`
- `granite4:3b` `load_post_tickets` 4/min: `20261008T171755Z_granite4-3b_load_post_tickets_4pm_run1`, `20261008T171755Z_granite4-3b_load_post_tickets_4pm_run2`, `20261008T171755Z_granite4-3b_load_post_tickets_4pm_run3`
- `granite4:3b` `load_post_tickets` 12/min: `20261008T175715Z_granite4-3b_load_post_tickets_12pm_run1`, `20261008T175715Z_granite4-3b_load_post_tickets_12pm_run2`, `20261008T175715Z_granite4-3b_load_post_tickets_12pm_run3`
- `qwen2.5:7b` `load_post_tickets` 1/min: `20261008T183710Z_qwen2.5-7b_load_post_tickets_1pm_run1`, `20261008T183710Z_qwen2.5-7b_load_post_tickets_1pm_run2`, `20261008T183710Z_qwen2.5-7b_load_post_tickets_1pm_run3`
- `qwen2.5:7b` `load_post_tickets` 4/min: `20261008T191813Z_qwen2.5-7b_load_post_tickets_4pm_run1`, `20261008T191813Z_qwen2.5-7b_load_post_tickets_4pm_run2`, `20261008T191813Z_qwen2.5-7b_load_post_tickets_4pm_run3`
- `qwen2.5:7b` `load_post_tickets` 12/min: `20261008T195733Z_qwen2.5-7b_load_post_tickets_12pm_run1`, `20261008T195733Z_qwen2.5-7b_load_post_tickets_12pm_run2`, `20261008T195733Z_qwen2.5-7b_load_post_tickets_12pm_run3`
- `llama3.2:1b-instruct-q4_K_M` `mixed_load` 1/min: `20261008T203649Z_llama3.2-1b-instruct-q4_K_M_mixed_load_1pm_run1`, `20261008T203649Z_llama3.2-1b-instruct-q4_K_M_mixed_load_1pm_run2`, `20261008T203649Z_llama3.2-1b-instruct-q4_K_M_mixed_load_1pm_run3`
- `llama3.2:3b` `mixed_load` 1/min: `20261008T211609Z_llama3.2-3b_mixed_load_1pm_run1`, `20261008T211609Z_llama3.2-3b_mixed_load_1pm_run2`, `20261008T211609Z_llama3.2-3b_mixed_load_1pm_run3`
- `granite4:3b` `mixed_load` 1/min: `20261008T215538Z_granite4-3b_mixed_load_1pm_run1`, `20261008T215538Z_granite4-3b_mixed_load_1pm_run2`, `20261008T215538Z_granite4-3b_mixed_load_1pm_run3`
- `qwen2.5:7b` `mixed_load` 1/min: `20261008T223511Z_qwen2.5-7b_mixed_load_1pm_run1`, `20261008T223511Z_qwen2.5-7b_mixed_load_1pm_run2`, `20261008T223511Z_qwen2.5-7b_mixed_load_1pm_run3`
- `llama3.2:1b-instruct-q4_K_M` `stress_ramp` ramp from 1/min: `20261008T231508Z_llama3.2-1b-instruct-q4_K_M_stress_ramp_ramp_run1`
- `llama3.2:3b` `stress_ramp` ramp from 1/min: `20261008T233015Z_llama3.2-3b_stress_ramp_ramp_run1`
- `granite4:3b` `stress_ramp` ramp from 1/min: `20261008T234535Z_granite4-3b_stress_ramp_ramp_run1`
- `qwen2.5:7b` `stress_ramp` ramp from 1/min: `20261009T000050Z_qwen2.5-7b_stress_ramp_ramp_run1`
- `llama3.2:1b-instruct-q4_K_M` `stress_ramp` ramp from 10/min: `20261009T001705Z_llama3.2-1b-instruct-q4_K_M_stress_ramp_ramp_run1`
- `llama3.2:3b` `stress_ramp` ramp from 10/min: `20261009T003216Z_llama3.2-3b_stress_ramp_ramp_run1`
- `granite4:3b` `stress_ramp` ramp from 10/min: `20261009T004737Z_granite4-3b_stress_ramp_ramp_run1`

Accuracy runs (one serial pass of the 200 golden tickets per model):

| Model | Run directory | Started (UTC) | Wall-clock | Posted | Load generator → service |
|---|---|---|---|---|---|
| `granite4:3b` | `granite4-3b_20261008T122430Z` | 2026-10-08 12:24 | 357 s | 200 | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 |
| `llama3.2:1b-instruct-q4_K_M` | `llama3.2-1b-instruct-q4_K_M_20261008T121612Z` | 2026-10-08 12:16 | 143 s | 200 | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 |
| `llama3.2:3b` | `llama3.2-3b_20261008T121848Z` | 2026-10-08 12:18 | 330 s | 200 | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 |
| `qwen2.5:7b` | `qwen2.5-7b_20261008T123045Z` | 2026-10-08 12:30 | 685 s | 200 | Kais-MacBook-Pro-2.local → http://192.168.50.130:8000 |
