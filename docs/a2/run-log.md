# Run log — Assignment 2 (Team 10)

**Owner:** Part 5 — Koh Tong Wei. Same role, same rules as `../run-log.md` played for Assignment 1 — this is
a **separate file**, not an extension of that one, so an Assignment 1 entry is never mistaken for Assignment
2 evidence or vice versa.

**Status:** real runs started 2026-11-26, after `python ../../scripts/a2_gate.py` exited 0.

## Rules (same as Assignment 1's run log)

1. One dated entry per configuration (one model-or-cascade-setting × one test kind — accuracy or speed),
   written straight after its runs.
2. Never delete an entry. A discarded or aborted configuration keeps its entry, with the reason; the re-run
   gets a new entry.
3. Dev-mode runs go under *Rehearsals* and are never quoted as evidence.
4. Every figure is copied from `gate.json`, `metadata.json`, a service log, or `analysis/output/`. Square
   brackets mean **not yet filled or not yet confirmed**.
5. Times are UTC, with Singapore time (UTC+8) in brackets.
6. For a cascade entry, record the setting (A or B) and the escalation fraction from the service log
   alongside the usual latency figures.
7. Re-run only for a reason listed in `../playbooks/cascade-test.md` §6, and write the reason here **before**
   re-running. Never re-run because a result looks bad. The invalid run's entry stays, marked invalid.
8. Mark each run valid or invalid against the checklist in `../playbooks/cascade-test.md` §7.

## Environment

**Hardware unchanged from Assignment 1; some software moved on by patch or OS releases.** Captured again on
2026-11-26 with `../../scripts/capture_env.sh` into `../environment/a2/` (same file names as Assignment 1's
`../environment/`), and diffed against the Assignment 1 captures:

| | Assignment 1 (`../environment/`) | Assignment 2 (`../environment/a2/`) | Matters for the measurement? |
|---|---|---|---|
| Service + Ollama host `omarchy` | Ryzen 9 5900X, 31.3 GiB RAM, CPU only | **Same** | — |
| Ollama | 0.34.3, `OLLAMA_NUM_PARALLEL=0`, `OLLAMA_MAX_LOADED_MODELS=0`, four pinned digests | **Same** (checked by `../../scripts/a2_env_snapshot.py check` against `env_baseline.json` before every configuration) | This is what the brief requires to stay fixed |
| Service settings | prompt `sha256:681131c48bdc15a1`, `num_ctx` 4096, seed 42 | **Same** | — |
| Host OS / Docker on `omarchy` | kernel 7.2.3, Docker Engine 29.7.2, Compose 5.5.1, swap 15.6 GiB | kernel 7.2.8, Docker Engine 29.9.2, Compose 5.6.1, swap 31.2 GiB | Patch updates. Ollama runs the same image and version (0.34.3) inside its container; the model settings are unchanged |
| `omarchy` LAN address | 192.168.50.130 | 192.168.50.129 (DHCP) | No: same wired link and subnet |
| Load generator `kais-macbook-pro` | Apple M3 Pro, 18 GiB, macOS 15.1.1, JMeter 5.6.3 on OpenJDK 21 | Same machine and JMeter 5.6.3 on OpenJDK 21 (`bin/setenv.sh`), **macOS 27.2.1** | The load generator only times requests; an OS update does not change the service's latency |
| Load generator LAN address | 192.168.50.35 (Wi-Fi) | 192.168.50.199 (same subnet) | No |
| Separate machines | yes | **yes**: every measured request goes from the MacBook to `omarchy` over the LAN | Brief: "The load generator must run on a separate machine" |

Notes on the A2 load-generator capture: it was taken over a non-interactive SSH session, so its `python3`,
`git` and `docker` lines show the macOS system tools rather than the user's shell tools. The run scripts use
the repository's `.venv` and `~/tools/apache-jmeter-5.6.3` explicitly. Docker Desktop was not running
on the MacBook (the load generator runs no model).

## Gate

`python scripts/a2_gate.py --json`, 2026-11-26, before the first A2 run (and again by every run script, into
each run's `gate.json`):

```json
{
  "ok": true,
  "gate_commit": "c544a51e4db8a015331fc29c9eeb415d280836f5",
  "gate_tag": "a2-predictions-freeze",
  "prediction_sha": "d632ebb78e54a6a217d7e69a99c6a43807a8ca22",
  "escalation_rule_sha": "ac99c5237df16ca3c0908bd3eee074a6cb270634",
  "split_sha": "842dfac28556efd33100b9ef6d311b822c4f4b39"
}
```

## Rehearsals (dev mode — not evidence)

### 2026-11-19 — first exercise of the A2 scripts on `omarchy` — dev, not evidence
- What: `scripts/run_load_test_a2.sh --dev --config qwen2.5:7b --runs 2` (co-hosted on `omarchy`, which a
  real run may never be), synthetic tickets only, output under the gitignored `results/dev/runs/`; and
  `scripts/run_accuracy_a2.py --dev --config qwen2.5:7b` (`results/dev/accuracy_a2/`).
- Result: JMeter 5.6.3 accepted the decimal rate `rate(8.98/min)`; both runs reconciled (`analysis/reconcile.py`
  PASS) and `analysis/summarise_load_a2.py` read them; the accuracy driver posted 14/14 and joined every
  ticket to its log line in `routing.csv`. A cascade smoke test against the real models used throwaway rules,
  never saved.
- Verdict: **rehearsal**. Started by the AI coding assistant at Yeo Kai Yuan's instruction.

## Real runs (after the gate)

Every real run below was started by the AI coding assistant at Yeo Kai Yuan's instruction, from `omarchy`
over SSH to the MacBook, so the load generator ran inside a live SSH session (the macOS Local Network gotcha,
`../run-log.md`, Assignment 1 rehearsal entry), under `caffeinate`, with `omarchy` held awake by
`systemd-inhibit`. Measured requests went over the LAN to 192.168.50.129. The campaign logs are
`../../results/campaign/a2_accuracy_20261126T094123Z.log` and `../../results/campaign/a2_speed_*.log`.

Code: both checkouts at `9c4a7d5` for the accuracy runs (Settings A and B in `service/cascade.py`, rule-fidelity
check 78/99 and 59/99 MATCH) and `8ec94d8` for the speed runs (same service code; one campaign-script logging
fix). The triage image was rebuilt from that code on `omarchy` before the first run, and its `RULE_SETTINGS` were
printed from inside the image to confirm both settings. `git_dirty` is true in every run's metadata only because
earlier runs' output folders under `results/` were not yet committed.

### 2026-11-26 09:41–09:56 UTC (17:41–17:56 SGT) — accuracy, cascade Settings A and B, test rows
- What: `scripts/run_a2_campaign.sh accuracy --small-model granite4:3b --host 192.168.50.129`, which recreated
  `triage` in cascade mode at each setting (confirmed by `/health`) and ran
  `scripts/run_accuracy_a2.py --config cascade-A|cascade-B --rows test`: the 101 test-set rows, one at a time,
  each once. Single models were not re-run: their test-set accuracy is reused from Assignment 1 (brief, Step 4;
  `accuracy_limits.md` reuse check; scored by Part 3 in `../../analysis/output/accuracy_a2/report.md`).
- Run folders: `../../results/accuracy_a2/cascade-A_20261126T094140Z/` (09:41:40–09:50:20) and
  `../../results/accuracy_a2/cascade-B_20261126T095101Z/` (09:51:01–09:55:55). Each holds `gate.json`
  (`"ok": true`), `responses.csv`, `routing.csv`, `service.jsonl` and `metadata.json`.
- Counts: 101/101 HTTP 200 at each setting, **0 errors**, 0 tickets without a log line. Escalated (from the
  service log): **A 83/101 (82.2%)**, **B 65/101 (64.4%)**.
- Scored with `python -m analysis.cascade_accuracy_a2` (`../../analysis/output/accuracy_a2/cascade_report.md`):
  **Setting A 76/101 (75.25%)** and **Setting B 74/101 (73.27%)**. Both pass the overall limit (≥ 65/101) and all
  seven per-category limits. Setting B's Consumer loan is exactly at its limit (6/14, needs 6).
- Determinism cross-check (TODO_A2.md §3.1): `granite4:3b`'s answer inside the cascade equals its Assignment 1
  answer on **101/101** rows at both settings, and `qwen2.5:7b`'s answer on escalated rows equals its
  Assignment 1 answer on **83/83** (A) and **65/65** (B). This supports reusing the single-model figures.
- Note: the first escalated ticket after the restart paid `qwen2.5:7b`'s load. That is irrelevant to an accuracy
  run, which times nothing.
- Verdict: **valid**. Nothing re-run.

### Speed runs — common to every entry below
- Procedure: `scripts/run_load_test_a2.sh`, three runs per configuration, each run doing the brief's "Each run"
  steps itself: restart Ollama, reset the database and recreate `triage` in the configuration (confirmed by
  `/health`), three fixed warm-ups (rows 900000–900002 of `data/dev/synthetic_tickets.csv`), `ollama ps`
  residency check, `GET /stats`, JMeter `jmeter/speed_test_a2.jmx` at **8.98/min, random arrivals, 300 s, then
  a 360 s pause, 300 000 ms response timeout** (`../a2/arrival_rate.json`, S = 3.339 s), `GET /stats`, log
  slice. Same 100-ticket list in the same order (`../../workload/speed_test_rows_a2.txt`).
- Every run: `gate.json` ok, environment unchanged from `env_baseline.json`, 3 warm-ups sent, expected
  model(s) resident before the run, 44 sent / 44 completed / 0 errored / 0 unfinished (`/stats` 3 → 47, delta
  44 = completed), 44 distinct tickets (no repeats), largest measured `load_duration` 14 ms (no mid-run load),
  `analysis/reconcile.py` PASS. `ollama ps` after each run lists nothing: the 360 s pause outlasts Ollama's
  5-minute keep-alive, so the models unload after the last request. That is expected and is not a reload.
- Figures: `../../analysis/output/speed_a2/` (`python analysis/summarise_load_a2.py --accuracy-verdicts
  analysis/output/accuracy_a2/verdicts_a2.csv`), the frozen `prediction_record_a2.md` §4 rule. A labelled
  secondary reading (halves test only) is in `../../analysis/output/speed_a2_secondary/`, explained in
  `../../predictions/prediction_record_a2_appendix.md`.
- **No-queue check.** The frozen check flags six of the nine runs as queued, including two of the three
  `qwen2.5:7b` runs. The appendix gives the cause: random arrivals at about 50% utilisation, not a growing
  queue. No run was re-run. The flag comes from chance in the arrival pattern, and re-running until a run passes
  would cherry-pick (playbook §6).

### 2026-11-26 09:56–10:33 UTC (17:56–18:33 SGT) — speed, `qwen2.5:7b` alone (reference)
- Runs: `../../results/runs/20261126T095648Z_qwen2.5-7b_speed_a2_8.98pm_run{1,2,3}/` (09:58–10:09, 10:10–10:21,
  10:22–10:33 UTC). Code `8ec94d8`.
- p50 per run: **6121 / 6535 / 4505 ms**. Halves +12.9% / +187.0% / +19.1%. Median queue wait 1773 / 2305 / 11
  ms. Ollama busy 0.54 / 0.52 / 0.52. Throughput 0.157 / 0.153 / 0.150 req/s. Error rate 0%.
- Frozen §4: run 1 queued (queue wait), run 2 queued (halves and queue wait), run 3 valid.
- Verdict: three runs completed and kept; **one counts** under the frozen rule.

### 2026-11-26 10:33 UTC — cascade A stopped before measuring (no data)
- The first campaign (`../../results/campaign/a2_speed_20261126T095627Z.log`) stopped at cascade A's pre-flight
  check: "service host checkout is at 1587344 but this checkout is at 8ec94d8". The AI assistant had committed
  analysis-code changes on `omarchy` mid-campaign. **Nothing was measured**: the check runs before any restart or
  request. The service code was identical in both commits (`git diff 9c4a7d5 1587344 -- service/` is empty), so
  the triage image was unchanged. The MacBook was fast-forwarded to `1587344` and cascades A and B were relaunched
  (`../../results/campaign/a2_speed_cascades_20261126T103356Z.log`).
- Verdict: no run, nothing to keep. Recorded because it interrupted the campaign.

### 2026-11-26 10:34–11:11 UTC (18:34–19:11 SGT) — speed, cascade Setting A
- Runs: `../../results/runs/20261126T103412Z_cascade-A_speed_a2_8.98pm_run{1,2,3}/`. Code `1587344`. `ollama ps`
  listed `qwen2.5:7b` and `granite4:3b` before every run (`ollama_ps_before.txt`).
- p50 per run: **9611 / 7629 / 9250 ms**. Halves −56.7% / −41.1% / −3.9%. Median queue wait 934 / 49 / 2241
  ms. Ollama busy 0.92 / 0.94 / 1.02. Throughput 0.149 / 0.149 / 0.148 req/s. Error rate 0%.
- **Escalated under load: 33/44 in each run (99/132, 75.0%)**, against 83/101 (82.2%) in the accuracy test, a
  gap of −7.2 pp (under the 15 pp line). p50 of accepted tickets 2219 / 2287 / 4462 ms; of escalated tickets
  12183 / 9231 / 11111 ms.
- Frozen §4: run 1 queued (queue wait), run 2 valid, run 3 queued (queue wait).
- Verdict: three runs kept; one counts under the frozen rule. Slower than `qwen2.5:7b` on every reading.

### 2026-11-26 11:11–11:48 UTC (19:11–19:48 SGT) — speed, cascade Setting B
- Runs: `../../results/runs/20261126T111121Z_cascade-B_speed_a2_8.98pm_run{1,2,3}/`. Code `1587344`. Both models
  resident before every run.
- p50 per run: **5501 / 5569 / 5029 ms**. Halves +212.3% / +7.8% / +87.7%. Median queue wait 28 / 29 / 35 ms.
  Ollama busy 0.75 / 0.85 / 0.83. Throughput 0.147 / 0.157 / 0.158 req/s. Error rate 0%.
- **Escalated under load: 23/44 in each run (69/132, 52.3%)**, against 65/101 (64.4%) in the accuracy test, a
  gap of −12.1 pp (under the 15 pp line). p50 of accepted tickets 2363 / 3354 / 3328 ms; of escalated tickets
  7637 / 9006 / 7400 ms.
- Frozen §4: runs 1 and 3 queued (halves), run 2 valid.
- Verdict: three runs kept; one counts under the frozen rule. Not distinguishably faster than `qwen2.5:7b`: its
  per-run p50s sit inside `qwen2.5:7b`'s spread.
