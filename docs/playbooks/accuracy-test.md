# Playbook — accuracy test (every golden-set ticket, per candidate model)

**What this document is for.** It is the procedure for the accuracy test the brief requires in Step 5: *"Send
every golden-set ticket through POST /tickets for each candidate model, and report overall and per-category
accuracy against your golden labels, with a confusion matrix."* It is written so that a competent tester who
cannot ask us anything can carry it out.

**Owner:** Part 5 — Koh Tong Wei.

**What "done" looks like.** One completed run directory per candidate model under `../../results/accuracy/`,
each covering **every** row of the golden set, and one scored set of tables and confusion matrices under
`../../analysis/output/accuracy/`.

**Feeds:** Slide 8 (Playbook) and Slide 10 (Accuracy Results).

**Related playbooks:** `load-test.md` and `stress-test.md`. The preconditions overlap but are **not**
identical: this test needs no load generator machine and no JMeter, and it deliberately measures no timings.

**Conventions used in every command below.** Every command is run **from the repository root**, and `python`
means the repository's own virtual environment — `.venv/bin/python`, or activate it first with
`source .venv/bin/activate`. Anything in `<angle brackets>` is for you to substitute; anything marked
every threshold is the team's decided value, with its source named next to it.

---

## 1. What this test measures, and what it does not

| | |
|---|---|
| **Measures** | The category the baseline service assigns to each golden-set ticket, for one pinned model, recorded row by row. Scoring against the frozen labels — overall accuracy, per-category recall and precision, a confusion matrix, and a list of every misclassified row — is a **separate** step (section 6). |
| **Does not measure** | Latency. `scripts/run_accuracy.py` times nothing and reports nothing but counts. The service logs its own latencies as usual, and those are the load test's business. Do not quote a latency from an accuracy run: it was produced one request at a time, with no controlled arrival rate, and it is not comparable with anything on Slide 9. |
| **Determinism** | `temperature` is fixed at `0` in code and `OLLAMA_SEED` is `42`, so re-running the same model on the same golden set and the same prompt should give the same answers. If it does not, something changed — find out what before reporting either result. |
| **Separation of concerns worth knowing about** | The driver never reads the golden **labels**. It reads the golden set's first column (row numbers) only, looks each narrative up in `data/team_rows.csv`, and posts it. That makes it structurally impossible for this step to be nudged towards a better score. |

### 1.1 The numbers you need before you start, and where they come from

| What | Where it lives |
|---|---|
| The overall accuracy requirement | **≥ 90%** on the golden set, measured serially, not under load, once per model — `../../workload/requirements.md`, requirement **R3** (Part 4 — Toh Si Pei). |
| The per-category accuracy requirement | **≥ 80% for every category**, same conditions — `../../workload/requirements.md`, requirement **R4**. With 200 golden tickets across seven categories, some categories hold only a few tens of tickets, so each per-category figure is a coarse fraction. |
| How `UNPARSEABLE` counts towards accuracy | **As incorrect**, for both overall and per-category accuracy — decided in `../../workload/requirements.md` under R3, before any numbers were seen. A reply the parser could not map is a *wrong routing decision* in production, even though it is a different failure from a confident wrong category, so Slide 10 states the rule and reports the `UNPARSEABLE` count alongside. |
| Which models to test | `../../models/candidates.md` and `../../models/models.yaml`. Every candidate, one run each. Use the exact tag, never `latest`. |

This playbook produces the numbers; it does not decide whether they pass.

---

## 2. Preconditions

### 2.1 The freeze gate must pass

This is not a formality here — it is the whole point. The brief: *"Labelling after you have seen model outputs
drags your labels towards whatever the model says, and quietly corrupts the accuracy measurement."* The gate is
what proves our labels predate the measurement.

```bash
python scripts/freeze_gate.py --json
```

* Exit **0** and `"ok": true` — proceed. Note the `freeze_commit`; it is stamped into the run.
* Exit **3** — stop. The gate names the failing condition and the command that fixes it. The four conditions
  are: `golden/golden_set.csv` exists, is tracked and is unmodified; `predictions/prediction_record.md` exists,
  is tracked and is unmodified; the tag `golden-freeze` exists; and both files are present in the tagged
  commit's tree.

`--dev` bypasses the gate for rehearsal, but then runs on the 28 hand-written tickets in
`data/dev/synthetic_tickets.csv`, writes only under `results/dev/accuracy/` (gitignored), stamps
`"mode": "dev"` and `"freeze_commit": null`, prints
`*** DEV MODE — synthetic tickets only. Results are NOT evidence. ***`, and **refuses (exit 2)** if any
argument names `team_rows.csv`, `golden/` or `golden_set`. Rehearse with it; never report from it.

### 2.2 Which machine each step runs on

| Role | What runs there | Steps in section 5 |
|---|---|---|
| **Service host** | the `triage` container (and the `ollama` container, if Ollama is local) | 2 (model switch) |
| **Ollama host** | the Ollama server, CPU only | 1 (pull and pin) |
| **Driver machine** | `scripts/run_accuracy.py`, then the analysis | 3, 4, 5, 6, 7 |

The brief's separate-machine rule is about the **load generator**, because a co-hosted generator steals CPU and
corrupts *latency*. This test measures no latency, so running the driver on the service host does not
invalidate anything. Run it from the load generator anyway if that is convenient — the driver only needs HTTP
access to the service and read access to the service's log directory.

### 2.3 Everything else

| Precondition | How to check it | Why |
|---|---|---|
| The golden set is a committed, unmodified file whose first column is the course CSV row number | the freeze gate checks this; `head -3 golden/golden_set.csv` shows the shape | The driver reads only the first column. A duplicated row number is refused; a first column that is not a row number is refused |
| Every golden row number exists in `data/team_rows.csv` | the driver refuses with a list if any is missing | It resolves the narrative by row number. A golden row with no narrative cannot be tested |
| The service is serving the model you intend to test | `curl -s http://<service-host>:8000/health` | The driver refuses (`SystemExit`) if `/health` reports a different `model_tag`. This is how a mislabelled accuracy run is prevented |
| The model is pulled and **pinned** | a non-null `digest` under that tag in `models/models.yaml` | The digest is what ties the score to a specific set of weights, and it is what Slide 5 and Slide 10 report |
| The service log reaches the driver machine | with `SERVICE_SSH` set (remote mode, `load-test.md` section 2.3) the driver mirrors the service host's `logs/service` with `rsync` before slicing it; otherwise `SERVICE_LOG_DIR` must be a live view of it | The run directory must contain the service's own record of the same requests |
| Time budget | see below | This is the step people underestimate |

**Time budget.** One golden-set run is one sequential model call per golden ticket, 200 of them, on CPU.
Multiply by the number of candidates. Plan for it, run the largest candidate when nobody needs the machine,
and do not interrupt a run to save time — a partial `responses.csv` fails `analysis/accuracy.py`'s coverage
check, which is the correct behaviour.

The first completed candidate's observed wall-clock duration is recorded in the
[run log](../run-log.md), so the remaining candidates can be scheduled. This is scheduling information,
not a request-latency measurement. `scripts/run_campaign.sh` also records each step's duration on its `DONE`
line in `results/campaign/campaign_<stamp>.log`.

---

## 3. About the database, and whether to reset

`scripts/run_accuracy.py` does **not** reset the database, and does not need to: accuracy does not depend on
what is already stored. Two consequences matter anyway.

* **After an accuracy run, the database holds the golden tickets.** `GET /search` is a full-table `LIKE` scan,
  so a load test started against that database would not be measuring what it claims to. This is handled for
  you — `scripts/run_load_test.sh` calls `scripts/reset.sh --yes` before every measured run — but if you ever
  run a plan by hand, reset first.
* **A reset before the accuracy run makes `GET /stats` describe that run alone**, which is a convenient
  cross-check on the predicted-category counts. Optional; if you do it, say so in the run log.

```bash
# Optional, on the service host. DESTROYS every stored ticket.
scripts/reset.sh --yes
```

---

## 4. There is no warm-up, on purpose

`scripts/run_load_test.sh` sends a warm-up request because the first request pays the model-load cost and would
otherwise dominate the p99. This driver does not, because **nothing here is timed**: `metadata.json` records
`"warmup_request_id": null` for exactly that reason.

So the first golden ticket of each run carries the model-load cost in the service log. That is expected, it
changes no category, and it is another reason not to quote a latency from an accuracy run. If any warm-up-
flagged log lines do turn up in the window — for instance because somebody ran a load test at the same time —
the driver separates them into `warmup.jsonl` rather than letting them into `service.jsonl`.

---

## 5. Procedure

Repeat the whole of this section **once per candidate model**.

**1. Pull and pin the model (Ollama host, once per model).**

```bash
scripts/pull_and_pin_models.sh --dry-run            # prints the plan; contacts nothing
scripts/pull_and_pin_models.sh --model <ollama-tag> # pulls, then writes the digest into models/models.yaml
```

Commit `models/models.yaml`. If the script exits **4**, a digest disagrees with an existing pin: the weights
behind the tag changed, and every result already gathered under the old digest is no longer comparable with
anything measured afterwards. Read its message before doing anything else; `--allow-repin` means re-running
the affected benchmarks.

**2. Switch the service to that model (service host).** The service serves one model at a time, so switching
candidates means recreating the container with a different `MODEL_TAG`:

```bash
# On the service host, from the repository root.
MODEL_TAG=<ollama-tag> docker compose up -d --force-recreate --no-deps triage

# If Ollama runs locally in the compose project, make sure it is up too:
docker compose --profile local-ollama up -d ollama
```

**3. Confirm what the service is actually serving (driver machine).**

```bash
curl -s http://<service-host>:8000/health | python -m json.tool
```

Check: `status` is `ok`; `model_tag` is the tag you just set; `model_digest` matches the pin in
`models/models.yaml`; `ollama_reachable` is `true`; `ollama_base_url` is the Ollama host you mean; `num_ctx` is
`4096`; `prompt_hash` is the same value you will see in `metadata.json` and in every log line. `/health` is
deliberately not written to the JSONL request log, so polling it costs the evidence nothing.

**4. Confirm the freeze gate (driver machine).**

```bash
python scripts/freeze_gate.py --json
```

Expect exit 0. The driver runs it again itself and copies the verdict into the run directory as `freeze.json`.

**5. Run the driver (driver machine).**

```bash
export SERVICE_SSH=<user>@<service-host>   # remote mode: the driver mirrors the service host's log
export RUN_NOTES="operator <name>; <anything a human noticed>"

python scripts/run_accuracy.py \
    --model <ollama-tag> \
    --host <service-host> \
    --port 8000 \
    --golden golden/golden_set.csv
```

`--golden` defaults to `golden/golden_set.csv`, so it can be omitted; it is spelled out here because Slide 8
quotes this command and the golden set is the thing that makes it an accuracy test.

Optional environment variables: `ACCURACY_TIMEOUT_S` (default 300) is the per-request HTTP timeout — raise it
only for a genuinely slow candidate, and record that you did; `SLICE_MARGIN_S` (default 5) widens the
service-log slice at each end to absorb clock skew between the machines.

The driver prints, per row, as it goes, and at the end prints the HTTP status counts and the output directory.
It computes **no** accuracy: that is the next step, and the separation is deliberate.

**6. Score the run (driver machine).** Once, after all candidates have been run — it scores every run
directory it finds:

```bash
python analysis/accuracy.py --results results/accuracy --golden golden/golden_set.csv
```

Writes into `analysis/output/accuracy/`: overall accuracy per model, per-category recall and precision, a
confusion matrix as both CSV and a greyscale PNG (axes in the canonical category order), and
`misclassified.csv` listing every row the model got wrong with the first 200 characters of its narrative.
Useful flags: `--no-charts` writes tables only; `--narrative-chars N` changes how much narrative goes into
`misclassified.csv`.

Exit **0** means every run scored over the complete golden set. Exit **1** means a sanity check failed — the
golden set is missing or unusable, no responses were found, or a run does not cover the whole golden set. The
tables are written *before* the failure, so you can see what is missing.

**7. Commit the evidence.** The run directories under `results/accuracy/` and the regenerated
`analysis/output/accuracy/`. Both are cited by Slide 10.

---

## 6. What to observe while it runs

| Watch | Where | What is fine, and what is not |
|---|---|---|
| The per-row progress | the driver's stdout | Steady progress. A long stall on one row means a slow model call or a hung Ollama; the request will end in a timeout after `ACCURACY_TIMEOUT_S` |
| HTTP statuses | the driver's summary at the end | Every row should be `200`. Any non-`200` is recorded in `responses.csv` with its `error` and must be explained, not dropped |
| `UNPARSEABLE` in the predicted categories | `responses.csv` | Not a failure of the run. It means the model's reply could not be mapped to one of the seven categories by the documented rules in `service/categories.py`. It is a **result**, and how it counts towards accuracy is R3's open decision |
| Service host CPU | `top` on the service host | Ollama should dominate. Anything else competing makes the run take longer but does not change the categories |
| Nobody else using the service | your judgement | Another person posting tickets at the same time pollutes `GET /stats` and puts unrelated lines in the sliced log |

---

## 7. Expected artefacts, and where they land

One directory per model per attempt, at `results/accuracy/<model>_<UTCSTAMP>/` — illustratively,
`results/accuracy/llama3.2-1b_20261006T041200Z/` (an example of the *shape*; no such run exists). `<UTCSTAMP>` is `YYYYmmddTHHMMSSZ` and the model tag is
sanitised (`:` `/` and spaces become `-`).

| File | What it is | Must not be missing or empty |
|---|---|---|
| `metadata.json` | the run describing itself: `model_tag`, `model_digest`, `prompt_hash`, `num_ctx`, `seed`, `input_csv`, `service_url`, freeze commit and tag, git commit and dirty flag, `notes` | yes |
| `freeze.json` | the verbatim verdict of `scripts/freeze_gate.py --json` at run time | yes |
| `responses.csv` | one row per golden ticket: `row_number,request_id,http_status,predicted_category,error`. Written and flushed row by row, so a run that dies half way leaves usable partial evidence | yes |
| `service.jsonl` | the service's own log lines for the window — the independent second record of the same requests | yes |
| `warmup.jsonl` | present **only** if warm-up-flagged lines happened to fall in the window (they should not) | may be absent |

Derived output: `analysis/output/accuracy/` — committed, because Slide 10 cites it.

Note what is deliberately **not** in `responses.csv`: the golden label, and any score. The labels are joined in
only by `analysis/accuracy.py`, against the frozen file.

---

## 8. Record this in the run log

The scripts capture everything machine-readable. Write down what they cannot:

1. **Who ran it, when** (local time as well as UTC), and **which candidate**.
2. **How long the run took**, wall-clock, so the remaining candidates can be scheduled.
3. **Whether you reset the database first** (section 3), because it changes what `GET /stats` then describes.
4. **Anything done by hand**: a container recreated, a model re-pulled, `ACCURACY_TIMEOUT_S` raised and why, a
   run abandoned and restarted.
5. **Any non-`200` row**, with your explanation of it. `responses.csv` records the status and the error slug; it
   cannot record that Ollama had just been restarted.
6. **Anything that looked wrong and that you decided to accept**, and why.
7. **Your verdict**: is this run reportable, or was it a rehearsal? Say which, in those words.

The short version goes into the run's own `metadata.json` via `RUN_NOTES`, which the driver copies verbatim
into the `notes` field:

```bash
export RUN_NOTES="operator <name>; candidate <tag>; database reset first; service host otherwise idle"
```

The longer narrative belongs in the shared [run log](../run-log.md). Record unknown operator details as
unconfirmed rather than inferring them from the machine hostname.

---

## 9. Abort and retry: what makes a run invalid

If any of these is true, the run is **not evidence**. Fix the cause and re-run the whole golden set for that
model — never patch a partial run by re-posting the failed rows, because the second half would then have run
under different conditions from the first.

| Abort criterion | How you detect it | Why it voids the run |
|---|---|---|
| **The freeze gate did not pass** | exit 3, or `freeze.json` has `"ok": false`, or `metadata.json` has `"mode": "dev"` | The labels must demonstrably predate the measurement. A dev-mode run used 28 synthetic tickets and is gitignored |
| **`/health` reported an unexpected model tag** | the driver refuses to start, and says what `/health` reported | The run would be labelled with weights it did not use. This is the single most damaging error available here, and it is why the check exists |
| **`model_digest` in `metadata.json` does not match the pin** | compare with `models/models.yaml` | Same reason: the score would be attributed to the wrong set of weights |
| **`analysis/accuracy.py` exits 1 with incomplete coverage** | run step 6 | Some golden rows have no response. A score over a subset of the golden set is not the score the requirement is written against |
| **`responses.csv` has fewer rows than the golden set** | `wc -l` against the golden set | The run was interrupted. Re-run it whole |
| **Any non-`200` you cannot explain** | `responses.csv`'s `http_status` and `error`; cross-check the `error` slug in `service.jsonl` (`ollama_timeout`, `ollama_http_502`, `ollama_connect_error`) | A ticket the service could not classify has no predicted category, so it is neither right nor wrong — it is a hole in the coverage. A `502` caused by Ollama restarting mid-run voids the run; one caused by a genuinely over-long model call is a finding, and must be stated on Slide 10 rather than hidden |
| **The golden set was modified during or after the run** | `git status --porcelain golden/` | The frozen file is the measurement's reference. If it changed, the freeze is broken and the whole accuracy result has to be re-established |
| **`metadata.json` reports `"git_dirty": true`** | the same file | The run cannot be reproduced from a committed state |
| **The prompt changed** | `prompt_hash` differs between runs you intend to compare | Accuracy is a property of model **and** prompt. Two candidates compared under different prompt hashes are not a comparison |
| **Two runs of the same model disagree** | compare their `responses.csv` | With `temperature=0` and a fixed seed they should not. Something changed — the model digest, `num_ctx`, the prompt, or the Ollama version. Find it before reporting either run |

An `UNPARSEABLE` prediction is **not** an abort criterion. Nor is a low accuracy score: the brief is explicit
that *"A finding that no candidate meets all of your requirements, measured carefully and argued clearly, is a
strong result."*

---

## 10. Common failures and what they mean

| Symptom | Almost always means | Do this |
|---|---|---|
| `golden set not found: golden/golden_set.csv` | Part 2 has not finished, or the file is somewhere else | Build it with `python labelling/scripts/build_golden_set.py …`, commit it, tag the freeze. The freeze gate prints the exact command |
| `first column … is not a row number` | The golden set's columns are in the wrong order | The first column must be the course CSV row number. Fix the file that generates it, not this run |
| `lists N row number(s) more than once` | The golden set has duplicate rows | Each golden row must appear exactly once. Fix it upstream and re-freeze |
| `golden set names row numbers missing from data/team_rows.csv` | The golden set was built from a different extract, or a row number was typed by hand | The golden set must be a subset of our team's 1,000 rows |
| `/health reports model_tag=<other>` | The container was never recreated with the new `MODEL_TAG`, or it failed to restart | Step 2 of section 5, then `docker compose logs triage` |
| `ollama_reachable=false` in `/health` | Ollama is down, or `OLLAMA_BASE_URL` points at the wrong host | Every POST would return 502. Fix the backend before starting |
| `cannot reach …/health` | Wrong host or port, the container is not running, or a firewall | `curl` the URL by hand from the driver machine |
| Many rows time out | The candidate is too slow for `ACCURACY_TIMEOUT_S` (default 300 s), or the host is swapping | Check `Total swap` and RAM in the machine's capture file: a 7-8B model that does not fit in RAM turns latency into disk latency. Raise the timeout only if RAM is not the problem, and record that you raised it |
| `service log directory not found` | `SERVICE_LOG_DIR` is unset or wrong on the driver machine | Point it at a live view of the service's `logs/service` |
| `service.jsonl` has far fewer lines than `responses.csv` | Clock skew between driver and service host, or the wrong log directory | Run NTP on both; raise `SLICE_MARGIN_S` only after checking the clocks |
| `analysis/accuracy.py`: "no responses found" | `--results` points at the wrong directory, or every run directory is misnamed | Directory names are parsed for the model and stamp. Do not rename them |
| The confusion matrix PNG is missing | matplotlib could not write it, or `--no-charts` was passed | The CSV matrix is authoritative; the PNG is for the slide. Re-run without `--no-charts` |
| Accuracy differs from a previous run of the same model | `prompt_hash`, `model_digest`, `num_ctx` or the Ollama version changed | Compare those four fields in the two `metadata.json` files before concluding anything about the model |
| One category is never predicted at all | A real model behaviour, or a normalisation problem | Check `raw_model_output` in `service.jsonl` for those rows against the rules in `service/categories.py`'s module docstring. If the model is producing a name the normaliser rejects, that is a finding for Slide 10 and an A2 candidate, not a bug to fix mid-measurement |
