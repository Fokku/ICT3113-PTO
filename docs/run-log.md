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

## Open items before the first real run
- [ ] **Which machine's Docker engine does `kthgoat`'s `docker` talk to?** A later `docker version` shows `Context: default` and a Docker Desktop server. If `DOCKER_HOST` is empty, that engine is `kthgoat`'s own, and the reset in attempt 2 restarted containers on the load generator, not on `tw`. Check `echo $DOCKER_HOST` and `docker ps` on `kthgoat`. If `ict3113-*` containers are running there, stop them (`docker compose --profile local-ollama down`) before any run.
- [ ] Pull the model on machine 1 and rerun the dev load test to the end. Expect `results.jtl`, `metadata.json` and `service.jsonl` in the run folder.
- [ ] In that run's `metadata.json`: `service_url` is `http://192.168.50.73:8000`, `load_generator_host_info.hostname` is `kthgoat`.
- [ ] Freeze gate passes (`python scripts/freeze_gate.py`) and the tag `golden-freeze` exists.

## Real runs

### 2026-10-08 05:25:11–05:42:22 UTC (2026-10-08 13:25:11–13:42:22 SGT) — accuracy — llama3.2:1b — completed, provisional

- Run directory: [llama3.2-1b_20261008T052511Z](../results/accuracy/llama3.2-1b_20261008T052511Z/).
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

- Verdict: **rehearsal / provisional diagnostic attempt; not reportable** under playbook section 9. Although recorded in real mode after the freeze, the run has a dirty working tree and no recorded model digest. A low score alone would not invalidate a run.
- Next steps: establish the model pin using the pinning script, run from a committed clean state, and repeat the entire golden set. Preserve this attempt. Generate formal accuracy tables and confusion matrices for the replacement run; do not retrofit a digest or change this attempt's metadata.
- Other attempts: `results/accuracy/llama3.2-1b_20261008T052403Z/` contains only `responses.csv`; no metadata, freeze verdict or service-log snapshot is available in that directory. It is not used for the scores above.

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
