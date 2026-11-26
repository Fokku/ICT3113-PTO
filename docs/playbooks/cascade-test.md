# Playbook — Assignment 2 speed test (every configuration, cascade included)

**What this document is for.** The Assignment 2 counterpart of `load-test.md`. It does **not** repeat what is
unchanged from Assignment 1 — the cross-machine plumbing, the `.jtl` column set, the open-loop reasoning —
read `load-test.md` sections 2.2–2.4 and 3 first and come back here only for what Assignment 2 changes: the
gate, the arrival rate, the fixed ticket list, and the two-model warm-up.

**Owner:** Part 5 — Koh Tong Wei.

**What "done" looks like.** One completed run directory per speed-tested configuration (every qualifying
single model, `qwen2.5:7b` alone, and the cascade at both settings), three runs each, under `results/runs/`,
with `gate.json` (not `freeze.json`) recording the A2 gate this run was measured under.

**Feeds:** Slide 3 (test environment and method), Slide 5 (speed results).

---

## 1. What changed from `load-test.md`

| | Assignment 1 | Assignment 2 |
|---|---|---|
| Gate checked before any run | `scripts/freeze_gate.py` (`golden-freeze`) | `scripts/a2_gate.py` (`a2-predictions-freeze`) — see `../../TODO_A2.md` "Definition of done" |
| Arrival rate | from `../../workload/workload_model.md` | derived from `qwen2.5:7b`'s own speed (S) — see `../a2/arrival-rate.md` |
| Ticket source | `data/team_rows.csv`, recycled via CSV Data Set Config | the **fixed** 100-ticket list in `../../workload/speed_test_rows_a2.txt`, sourced from `../../data/speed_test_tickets_a2.csv` (same `row_number,narrative,raw_label` shape), **same order for every configuration, recycle off** so no ticket repeats within a run |
| Models loaded before the run | one | **one** for a single-model configuration, **two** for the cascade — both must be confirmed resident (`ollama ps`) before the run starts |
| HTTP timeout / trailing pause | fixed per `load-test.md` | derived from S — see `../a2/arrival-rate.md` §3 |
| Software/digest/Ollama-settings check | recorded once for the campaign | recorded once, **then diffed before every configuration** (brief, Set-up) — see §2.4 |
| p99 reported | yes | **no** — brief: "the sample is too small" |
| Warm-up | one request | **three fixed tickets**, same three every run; for the cascade, at least one must reach the large model — see §4.2 |

## 2. Preconditions

### 2.1 The A2 gate must pass

```bash
python scripts/a2_gate.py --json
```

Exit 0 and `"ok": true` — proceed, and note `gate_commit`. Anything else — stop. No real Assignment 2 run may
happen before this passes (`../../TODO_A2.md`, "Definition of done").

### 2.2 Machines, plumbing, `.jtl` columns

Unchanged from Assignment 1 — follow `load-test.md` sections 2.2–2.4 and 3.4 exactly: load generator on a
separate machine, same SSH/`rsync` plumbing, same `jmeter/user.properties`.

### 2.3 The fixed workload ticket list

```bash
cat workload/speed_test_rows_a2.txt      # the 100 row numbers, with their band (typical/long)
```

JMeter's CSV Data Set Config for the Assignment 2 plan points at `data/speed_test_tickets_a2.csv` (not
`data/team_rows.csv`), in file order, the same for every configuration, with **recycle off**. A run must
never send the same ticket twice: the brief warns that Ollama caches prompts it has seen and a repeat comes
back much faster. 100 tickets covers this team's runs — with S ≈ 2.3 s the 5-minute minimum gives ~65
requests (rate × run length, random arrivals can run higher). Once S is measured, do the check in
`../a2/arrival-rate.md` §2: the safe upper bound (expected + 3 × √expected) must be ≤ 100. If not, regenerate
the list larger before the first run, not after.

### 2.4 Software versions, model digests, Ollama settings

Brief, Set-up: *"Before the first run, record your software versions, model digests and Ollama settings.
Check they are unchanged before each configuration."* Record once, before the first Assignment 2 run of any
kind (`docs/environment/`, or re-captured with `../../scripts/capture_env.sh` if anything changed since
Assignment 1), then diff against that record before starting **every** configuration — not just once for the
whole campaign. A silent Ollama version bump or digest drift between configurations would make the
comparison meaningless without anyone noticing.

## 3. Timeout and pause settings (set these before the first run)

From `../a2/arrival-rate.md` §3: HTTP sampler response timeout = `max(10×S, 5 min)`; Open Model Thread Group
trailing pause ≥ timeout + 1 minute (brief: the pause must outlast the timeout, or a slow request can be cut
off and lost — and those are the slow ones you most need). Recompute per model/configuration only if S
differs meaningfully (it shouldn't — S is derived once from `qwen2.5:7b` and held constant for every
configuration, per the brief).

## 4. Each run, step by step

This section is self-contained on purpose — it does **not** assume the equivalent steps exist in
`load-test.md`, because one of them (4.3/4.5 below) doesn't: Assignment 1 resets the database to empty and
checks `total: 0` (`load-test.md` §2.x, via `scripts/reset.sh --yes`); Assignment 2's brief instead asks for
a before/after delta on `GET /stats`, which also works for a cascade run where warm-up tickets get stored
too. Everything else below (restart, `.jtl` columns, cross-machine plumbing) is unchanged from
`load-test.md` sections 2.2–2.4 and 3.4 — follow those for anything not restated here.

### 4.1 Restart and confirm up

Restart the Ollama container; confirm with `GET /health` on the service, or `ollama ps` in the container. No
model is loaded yet. This also clears Ollama's prompt cache.

### 4.2 Warm-up

Brief: *"Send three fixed warm-up tickets, one at a time. The first one loads the model. Throw away all three
timings. Use the same three tickets every time."* **Three, not one** — Assignment 1's `run_load_test.sh` sends
a single warm-up request, so do not inherit its warm-up step unchanged.

- **The three warm-up tickets:** rows **900000, 900001 and 900002** of `../../data/dev/synthetic_tickets.csv`
  (the first three hand-written dev tickets), the same three for every run of every configuration.
  `../../scripts/run_load_test_a2.sh` sends them itself and records them as `warmup_rows` in each run's
  `metadata.json`. Pick them so they are **not** in `workload/speed_test_rows_a2.txt` and are not
  the three tickets S was measured on: Ollama's prompt cache would otherwise make the first measured
  requests artificially fast. For the cascade, at least one must reach the large model (see below), so the
  final choice depends on the escalation rule.
- **Single-model configuration:** the three warm-up tickets via `POST /tickets` with `X-Warmup: 1`, one at a
  time, all discarded from analysis.
- **Cascade configuration — both models must end up resident:**
  1. Send the three warm-up tickets one at a time. The small model sees all three.
  2. Make sure at least one of them reaches the large model — either a ticket the rule **will** escalate, or
     one sent directly to the large model.
  3. Run `ollama ps` in the container and confirm **both** tags are listed, before starting the measured run.
     The confirming `ollama ps` output is captured per run, by the runner, in
     `results/runs/<run>/ollama_ps_before.txt` (and `ollama_ps_after.txt`), next to the memory-check evidence
     in `../environment/a2-memory-check/` (`TODO_A2.md` §1.1). If none of the three warm-ups escalated, the
     runner sends one direct warm-up call to the large model (`large_model_warmup.json`) before checking.
  4. If either model is not listed, **stop — do not run.** See `TODO_A2.md` §1.1 for what to do if no pair
     fits.
- Either way: throw away all warm-up timings. Use the same fixed warm-up ticket(s) every time.

### 4.3 `GET /stats`, before

Call `GET /stats` on the triage service and note the `total`. (Unlike `load-test.md`'s empty-database start,
the cascade's warm-up tickets may already have been stored — that's expected; the delta in 4.5 is what
matters, not an absolute zero.)

### 4.4 Run JMeter

At the rate and duration from `../a2/arrival-rate.md` §2, against the fixed ticket list (§2.3), with the
timeout/pause settings from §3.

### 4.5 `GET /stats`, after

Call `GET /stats` again. The **increase** in `total` since §4.3 is the number of requests the service
completed and stored — this is the figure to check against what JMeter itself reports sent/completed, not a
number to take on faith from either side alone.

```bash
# From the load generator (the brief: a separate machine), with SERVICE_SSH pointing at the
# service host's checkout for compose/reset/log sync. The script performs 4.1-4.5 itself.
# Rate, run length, timeout and pause come from docs/a2/arrival_rate.json; the ticket list is
# workload/speed_test_rows_a2.txt; the A2 gate and the environment check run first.
SERVICE_SSH=omarchy SERVICE_REPO=claude/ICT3113-PTO JMETER_HOME=~/tools/apache-jmeter-5.6.3 \
  scripts/run_load_test_a2.sh --config <qwen2.5:7b|cascade-A|cascade-B> \
  [--small-model granite4:3b] --host <service host LAN address> --runs 3
# Every configuration in order (TODO_A2.md section 1.5):
#   scripts/run_a2_campaign.sh speed --small-model granite4:3b --host <service host> --singles ""
```

## 5. Report, per run

- Requests sent, completed, errored and **unfinished. A run with unfinished requests is reported as such,
  not thrown away** (brief, Step 4) — do not re-run and discard a messy result; report what happened and let
  the analysis note it.
- If requests sent exceeded the 100 tickets in the list, tickets repeated within the run and its latency is
  suspect (prompt cache). Report it as such, and regenerate a larger list before further runs.
- p50 for the run; mean and spread once all three runs of a configuration exist.
- Pooled p95 across the three runs, with the actual count stated (the brief's "about 90" assumes ~30 per
  run; ours will be higher if the 5-minute minimum applies). **No p99.**
- Achieved throughput and error rate.
- For the cascade: the escalation fraction from the service log, compared against the accuracy-test
  escalation fraction. Explain any gap above the "large gap" threshold fixed in
  `../../predictions/prediction_record_a2.md` §4.
- **No-queue check:** first-half vs second-half p50, and median `ollama_other_ms` (queue wait). If the run
  fails the threshold in `../../predictions/prediction_record_a2.md` §4, a queue built up and its p50
  reflects run length, not the configuration. Report it flagged as queued, and don't compare it on p50.
- For the cascade: confirm no measured request paid a model reload. Check that every request's
  `load_duration` in the service log is near zero. A large value means Ollama unloaded a model mid-run
  (`OLLAMA_KEEP_ALIVE`, default 5 min), which the brief calls "a loading result", not a cascade result. Flag
  that run rather than reporting it as-is (`TODO_A2.md` §1.1).

## 6. Re-run policy

A run may be re-run **only** for a documented validity failure:

- the A2 gate didn't pass, or `gate.json` is missing;
- for the cascade, both models weren't resident (`ollama ps`), or a measured request shows a reload
  (`load_duration`);
- the no-queue check failed;
- more requests were sent than the 100-ticket list holds;
- software versions, digests or Ollama settings changed (§2.4);
- an environment fault: a machine crashed, the network dropped, Ollama died.

**Never re-run because the result looks bad, slow, or surprising.** That turns "three runs" into "the best
three of six", and the brief treats the spread across runs as part of the result. Write the reason in
`../a2/run-log.md` before re-running. The invalid run is **kept** — its folder stays under `results/`, its
log entry stays, marked invalid with the reason — and the replacement is added beside it. Same "never delete
an entry" rule as Assignment 1's run log.

Unfinished requests are not a validity failure: they are reported, not re-run away (§5).

## 7. Definition of done — a run, and a configuration

**A run counts as evidence only when every box is true.** If one isn't, the run is invalid: apply §6.

- [ ] `gate.json` is in the run folder and shows `"ok": true`.
- [ ] Versions, digests and Ollama settings matched the record (§2.4).
- [ ] Three fixed warm-up tickets were sent and their timings discarded (§4.2).
- [ ] For the cascade: `ollama ps` listed both models before the run, and no measured request shows a
      reload (`load_duration` near zero).
- [ ] Requests sent ≤ 100, so no ticket repeated.
- [ ] The no-queue check passed (thresholds in `../../predictions/prediction_record_a2.md` §4).
- [ ] `python analysis/reconcile.py --run-dir <run>` exits 0 — the `.jtl` and the service log agree.
- [ ] Sent, completed, errored and unfinished counts are recorded, and the `GET /stats` delta (§4.5) is
      consistent with them.
- [ ] The run has an entry in `../a2/run-log.md`.

**A configuration is done when:** it has an accuracy result on the 101 test-set rows (reused for single
models only if the reuse check in `../a2/accuracy_limits.md` passes), and — if it is speed-tested — **three
valid runs**, each meeting the list above, all at the same rate, run length and ticket list.

## 8. Record this in the run log

In `../a2/run-log.md` — **not** `../run-log.md` (that one is Assignment 1's and is not touched again). Same
fields as `load-test.md` section 7, plus: which cascade setting (if any), and the escalation fraction read
from the run's service log.

## 9. Rehearsal

Per `TODO_A2.md` §5.2: run one complete A2 speed test from this playbook, with Yeo Kai Yuan watching but not
helping. Every point you had to ask about is a defect in this document — fix it here, not just in
conversation.
