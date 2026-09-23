# Prediction record — Group 10

> ## STOP. READ THIS BEFORE YOU TYPE ANYTHING IN THIS FILE.
>
> 1. **This file cannot be edited after the `golden-freeze` tag.** Once the tag exists, the version of
>    this file inside the tagged commit *is* our prediction record, for good. See "How to freeze" at the
>    bottom.
> 2. **The commit history is the evidence.** The brief requires that the golden set and the prediction
>    record be committed to the repository *before the first benchmark run*, and states that the commit
>    history is our evidence that the labels and predictions predate the measurements. A prediction
>    written after a measurement is worth nothing, and a prediction record whose commit is newer than the
>    first `.jtl` file actively damages the submission.
> 3. **Marks are awarded for specificity and for the later account of where we were wrong — not for
>    being right.** The brief says so in plain words: *"Marks are awarded for specificity and for the
>    quality of your later account of where your predictions were wrong, not for being right. A vague
>    prediction that cannot fail earns nothing."* So a hedge earns nothing. Before you write any entry,
>    ask: *what result would prove this entry wrong?* If you cannot answer, the entry is not finished.
> 4. **Do not let anybody fill this in on the team's behalf.** These are the team's judgements. No tool,
>    no agent and no single member may supply them. Every cell marked `TODO(Whole team)` stays `TODO`
>    until the team has actually decided it.

---

## About this document

**What it is for.** The prediction record required by Step 4 of the brief. It states, before any model is
benchmarked, (a) where we expect the bottleneck to be and why, (b) for each candidate model the expected
golden-set accuracy and expected single-request latency, and (c) which categories we expect to be hardest
and why.

**Owner:** Part 4 — Teammate C holds the pen and chases the team for entries.
`TODO(Yeo Kai Yuan): replace "Teammate C" with the real name here and in the sign-off table.`
Every entry is a whole-team judgement, not the pen-holder's. Part 1 — Yeo Kai Yuan owns the freeze
(the commit, the tag, and the `scripts/freeze_gate.py` check).

**Done when.** Every `TODO(...)` below is replaced by a decision; every prediction names the result that
would falsify it; the sign-off table is complete with real names and real dates; the file is committed and
the `golden-freeze` tag points at that commit; and `python scripts/freeze_gate.py --json` prints
`"ok": true`. Until the gate passes, no benchmark run may be started against team rows.

**Conventions.** A path written `../like/this` is relative to this file (which lives in `predictions/`);
every command shown is run from the repository root.

**Which slide it feeds.** Slide 11, *Predictions, Recommendation and Defence* — "Your predictions against
your outcomes, and an account of where and why you were wrong." It is also a **submitted supporting file**
in its own right, alongside the golden set and the labelling material (see `../slides/outline.md`).

**Order of work.** Fill this in as a team in one sitting, after Part 2 and Part 3 have finished labelling
(so the edge cases are fresh) and after Part 4 has settled `../workload/requirements.md` (so the peak
arrival rate exists to predict against). **Each member writes their own figures down privately first, then
the team agrees the entry.** Otherwise the first figure spoken out loud becomes everybody's figure, the
disagreement column in the sign-off table comes out empty, and we lose the most interesting material on
Slide 11.

**Where the evidence will come from later.** Nothing in this file is measured. The fields that will be
compared against it after the freeze are fixed in advance: the service log schema in
`../service/log_schema.py`, the JMeter `.jtl` columns listed in `../analysis/common.py`, and the run
metadata in `results/runs/<run>/metadata.json`. Quoting those field names in a prediction is what makes it
checkable, so the tables below ask for them.

---

## Section 1 — Where we expect the bottleneck to be under load

The brief asks for *"Where you expect the bottleneck to be under load, and why."* An answer is complete
only when it has three parts:

* **the named component** — one component, chosen from the candidate list below (or a component not on the
  list, if the team can justify it);
* **the mechanism** — what saturates, what queues behind it, and why that shows up as latency or as errors
  rather than as something else;
* **the observation that would settle it** — the specific log field, `.jtl` column or metadata value whose
  behaviour would confirm the claim, *and* what that same evidence would look like if we were wrong.

### The candidate locations — choose from these and justify the choice

These are the places the bottleneck could plausibly be, given the baseline we have actually built (one
uvicorn worker, no concurrency limit in the service, a new `httpx` client and a new SQLite connection per
request, a full-table `LIKE` scan in `/search`, and Ollama on CPU only). **This table is a menu, not an
answer.** The "mechanism you would be claiming" column is deliberately terse: if the team picks a row, the
team writes the mechanism out properly in its own words in Section 1.1.

| # | Candidate location | Mechanism you would be claiming | Evidence that would confirm it | Evidence that would refute it |
|---|---|---|---|---|
| A | **Ollama's generation loop** (CPU token decoding for the chosen model) | Each request occupies a CPU-bound decode loop; the ceiling is tokens per second on this hardware, so the service rate is fixed and queueing is a consequence, not the cause | `model_latency_ms` tracks Ollama's own `total_duration` (ns) closely all run long; `eval_count` / `eval_duration` per request stays roughly constant while arrival rate rises | `model_latency_ms` drifts far above Ollama's `total_duration`, i.e. most of the time is spent *waiting*, not generating |
| B | **Ollama's request queue / parallelism admission** (`OLLAMA_NUM_PARALLEL`, recorded in `metadata.json`) | More requests are in flight than Ollama will decode at once — the service imposes no limit of its own — so requests sit in Ollama's queue before decoding starts | The gap between `model_latency_ms` and Ollama's own `total_duration` (converted from nanoseconds to milliseconds) grows through the run while `total_duration` itself stays flat | That gap stays flat as the arrival rate rises |
| C | **The service's single uvicorn worker** (`UVICORN_WORKERS=1`, in `/health` and `metadata.json`) | One event loop; any blocking or CPU work in the handler (JSON, SQLite, logging) delays every other request, so requests wait before the handler even starts | JMeter `elapsed` minus the service's `total_latency_ms` grows with load — time the request existed but was not being handled. `analysis/reconcile.py --latency-threshold-ms` is the check that surfaces this | That gap stays flat while `model_latency_ms` grows |
| D | **SQLite writes** (new connection per request, no WAL, no pooling) | Connection setup plus a durable insert per request, serialised by the database write lock, adds a growing non-model component to every POST | `total_latency_ms − model_latency_ms` grows as stored rows accumulate or as concurrency rises | That remainder stays small and flat all run long |
| E | **The `LIKE` scan in `GET /search`** (full-table scan, no index, no FTS) | Scan cost grows linearly with the number of stored tickets, so `/search` degrades as the run proceeds, independently of the model | In `mixed_load`, `total_latency_ms` on `/search` log lines rises over the run while the row count (from `GET /stats`) grows | `/search` latency stays flat while stored rows grow |
| F | **The load generator itself** (the JMeter host) | JMeter cannot maintain the scheduled open-model arrival rate — CPU, heap, GC — so part of the "latency" we measure is generator delay, not service delay | Achieved throughput below the configured `rate_per_min` while the service shows no errors; warnings in `jmeter.log`; JMeter's `Latency` / `Connect` columns; load-generator CPU in `docs/environment/` | Achieved arrival rate matches the configured schedule within run-to-run spread |
| G | **The network between load generator and service** (they are on separate machines, as the brief requires) | Per-request round-trip time or bandwidth adds a roughly constant amount to every sample | A consistent offset between JMeter `elapsed` and service `total_latency_ms` that does **not** grow with load, plus a non-trivial `Connect` time | The offset grows with load — that is queueing somewhere, not the network |

### 1.1 The team's prediction

`TODO(Whole team): name the ONE component you expect to bind first. Use the letter and the name from the`
`table above (or name a component not on the list and say why it is not there).`

`TODO(Whole team): write the mechanism in your own words — what saturates, what queues behind it, and at`
`roughly what point in the workload from ../workload/requirements.md you expect it to start binding.`
`"Ollama is slow" is not a mechanism.`

`TODO(Whole team): state the observation that would CONFIRM it, naming the exact field(s) — a key from`
`../service/log_schema.py, a column from the .jtl, or a value from metadata.json.`

`TODO(Whole team): state the observation that would REFUTE it. If you cannot name one, the prediction is`
`not specific enough to earn marks — rewrite it until you can.`

`TODO(Whole team): name the second most likely location and say why you ranked it below the first. If the`
`primary prediction turns out wrong, Slide 11 is much stronger if we recorded the runner-up here.`

`TODO(Whole team): if you expect the bottleneck to MOVE between models or between plans (load_post_tickets,`
`mixed_load, stress_ramp), say where and under which plan. A prediction that holds for every configuration`
`is usually a prediction that says nothing.`

---

## Section 2 — Per-candidate-model predictions

The brief asks, *"For each candidate model: expected classification accuracy on your golden set, and
expected single-request latency on your hardware."* One row per candidate model, three to five rows in
total (the brief's limits). Every cell is a team decision.

**Model column.** The rows below are pre-filled from `../models/models.yaml` as that file stood when this
template was generated: `llama3.2:1b`, `llama3.2:3b`, `granite4:3b` and `qwen2.5:7b`, smallest first. That
file described itself as a **proposal** — the shortlist was still awaiting confirmation and every `pinned:`
digest was still `null` — so **check every tag against `../models/models.yaml` before you sign this
document**. If a candidate has been dropped, or a named substitute promoted in its place, correct the row
here; the brief allows three to five candidates, so add or delete rows as the final shortlist requires.

The tag must match `../models/models.yaml` **character for character**: the same string goes into
`MODEL_TAG`, into the run directory names under `results/`, and into each `metadata.json`. If the tag here
differs even in punctuation, the prediction cannot be joined to the measurement on Slide 11.

| Model (exact Ollama tag) | Expected overall accuracy (%) | Expected hardest category | Expected single-request latency (p50, ms) | Expected p95 at the modelled peak rate | Confidence (low/med/high) | Reasoning |
|---|---|---|---|---|---|---|
| `llama3.2:1b` | `TODO(Whole team)` | `TODO(Whole team)` | `TODO(Whole team)` | `TODO(Whole team)` | `TODO(Whole team)` | `TODO(Whole team)` |
| `llama3.2:3b` | `TODO(Whole team)` | `TODO(Whole team)` | `TODO(Whole team)` | `TODO(Whole team)` | `TODO(Whole team)` | `TODO(Whole team)` |
| `granite4:3b` | `TODO(Whole team)` | `TODO(Whole team)` | `TODO(Whole team)` | `TODO(Whole team)` | `TODO(Whole team)` | `TODO(Whole team)` |
| `qwen2.5:7b` | `TODO(Whole team)` | `TODO(Whole team)` | `TODO(Whole team)` | `TODO(Whole team)` | `TODO(Whole team)` | `TODO(Whole team)` |
| `TODO(Whole team)`: a fifth candidate, only if one is promoted — otherwise delete this row | `TODO(Whole team)` | `TODO(Whole team)` | `TODO(Whole team)` | `TODO(Whole team)` | `TODO(Whole team)` | `TODO(Whole team)` |

### How to fill the cells so they can be checked later

* **Expected overall accuracy (%)** — against `../golden/golden_set.csv` only. Not against the raw
  `raw_label` column in `../data/team_rows.csv`: those labels are noisy, which is the whole reason the
  golden set exists.
* **Expected hardest category** — one of the seven canonical names, spelled exactly as in
  `../service/categories.py`. This is the per-model version of Section 3; the two must not contradict each
  other.
* **Expected single-request latency (p50, ms)** — one request at a time, no competing load, on the service
  host described in `../docs/environment/`. This is the figure a warm, unloaded `POST /tickets` produces;
  say whether you mean it warm (the model already resident, `load_duration` small) or cold, because the two
  differ and only one of them is what we will measure.
* **Expected p95 at the modelled peak rate** — a p95 with no load condition attached is untestable. Name
  the arrival rate you are predicting against and where it comes from, e.g. "at the peak arrival rate
  stated in `../workload/requirements.md`, section `TODO(Part 4 — Teammate C): section reference`".
* **Confidence** — `low`, `med` or `high`. Low confidence is respectable and useful; it is the entries
  marked `high` that later turn out wrong which make the best Slide 11 material.
* **Reasoning** — one clause is enough, but it must be a *reason*: parameter count, quantisation, CPU
  tokens per second, prompt length at `NUM_CTX`, the model's instruction-following behaviour on short
  answers. "It is bigger" is not a reason; "it is bigger, so decoding the same reply costs more CPU
  seconds" is.

### Ranges are allowed. Wide ranges are not.

A range is acceptable, but it must be narrow enough to be **wrong**. The test is not the width in the
abstract: it is whether you can name, in advance, an outcome that falls outside it.

*Unacceptably vague — earns nothing (no real figures are used here; N and M stand for whatever you might
write):*

> "Accuracy will be between N% and M%", where the band is so wide that every candidate we might plausibly
> pick falls inside it.
> "p50 latency will be under M ms", with M set so high that failing is inconceivable.
> "The larger model will be slower and more accurate." — true of almost any pair of models, so it cannot fail.

*Acceptably specific — can be shown wrong:*

> "Accuracy N% (we would accept N% to M%, a band of a few points); hardest category `<canonical name>`;
> p50 latency N ms warm and single-request on the service host in `../docs/environment/`; p95 no worse than
> M ms at the peak arrival rate in `../workload/requirements.md`. We would call this row wrong if the
> measured overall accuracy fell outside N–M%, or if the measured p95 exceeded M ms at that rate."

Apply the test to every row before signing: **name the result that would make this row wrong.** If there is
no such result, the row is not finished.

---

## Section 3 — Which categories we expect to be hardest, and why

The brief asks for *"Which categories you expect to be hardest to classify, and why."* The seven canonical
categories, in the canonical order used for every confusion-matrix axis (source of truth:
`../service/categories.py`):

1. Credit reporting
2. Debt collection
3. Mortgage
4. Credit card
5. Bank account or service
6. Consumer loan
7. Money transfer or service

`TODO(Whole team): list the categories you expect to be hardest, hardest first, and for each one give the`
`mechanism — is it a confusable pair, a thin slice of the data, or a genuine overlap in the definitions?`

`TODO(Whole team): predict the DIRECTION of the error, not just the category. "Category X will be hard" is`
`a weak prediction; "tickets whose true label is X will most often be predicted as Y, because ..." is a`
`prediction a confusion matrix can refute. Use the canonical spellings above so it lines up with the`
`matrix produced for Slide 10.`

`TODO(Whole team): predict where UNPARSEABLE replies will land. Which category's tickets do you expect to`
`produce the most unmappable model output, and why? The normaliser rules are listed in the module`
`docstring of ../service/categories.py — we do no semantic remapping, so a model that answers with a`
`category name we do not use scores as wrong, and that is deliberate.`

### Tie it to what the labelling work already showed us

Parts 2 and 3 have just labelled the golden set independently, so we already have hard evidence about which
categories humans confuse — and human confusion is the best prior we have for model confusion. Do not
predict in the abstract when we have this:

* `../labelling/protocol.md` — the category definitions and the edge-case rules, **including the revisions**.
  A rule that had to be added mid-labelling marks a real ambiguity.
* `../labelling/resolutions.csv` — every disagreement and how it was resolved. Which pairs of categories
  turn up repeatedly?
* `../labelling/labeller_A.csv` and `../labelling/labeller_B.csv` — the independent label sheets.
* The inter-annotator agreement statistic produced by `python labelling/scripts/agreement.py` into
  `../labelling/`.

`TODO(Part 2 — Teammate A) and TODO(Part 3 — Teammate B): name the specific edge cases and resolutions`
`that support the team's prediction above — cite the protocol rule or the resolution row, not a general`
`impression. This is also the material Slide 6 needs, so write it once and use it twice.`

### Tie it to the per-category accuracy requirement

The brief requires *"A classification accuracy requirement, overall and per category"*. That per-category
floor lives in `../workload/requirements.md`.

`TODO(Whole team): for each category you have named as hard, say whether you expect it to meet the`
`per-category accuracy requirement in ../workload/requirements.md, for which candidate models, and at`
`what cost to the client if it does not (a misrouted ticket is staff time). Slide 11 must state plainly`
`any requirement that no candidate meets, so predicting it here — before measuring — is worth real marks.`

---

## Sign-off

Every member signs. The fourth column is the important one: **where you did not agree with the entry the
team wrote above, record what you personally would have predicted instead.** A team-average prediction
hides the disagreement, and the disagreement is the interesting part — "three of us predicted the
bottleneck at B and two at C, and the measurement showed ..." is a far better Slide 11 than a single
consensus line. Leaving this column empty because the team agreed on everything is possible but unusual;
if that is genuinely the case, write "agreed with the team entry" rather than leaving it blank, so the
marker can see it was considered.

| Member | Part | Date signed (YYYY-MM-DD) | Where I disagreed with the team entry, and what I would have predicted instead |
|---|---|---|---|
| Yeo Kai Yuan | Part 1 — service, instrumentation, benchmark harness | `TODO(Yeo Kai Yuan): date` | `TODO(Yeo Kai Yuan): your own prediction where it differed, or "agreed with the team entry"` |
| Teammate A `TODO(Yeo Kai Yuan): replace with real name` | Part 2 — labelling protocol, independent labelling | `TODO(Part 2 — Teammate A): date` | `TODO(Part 2 — Teammate A): your own prediction where it differed, or "agreed with the team entry"` |
| Teammate B `TODO(Yeo Kai Yuan): replace with real name` | Part 3 — independent labelling, agreement, accuracy results | `TODO(Part 3 — Teammate B): date` | `TODO(Part 3 — Teammate B): your own prediction where it differed, or "agreed with the team entry"` |
| Teammate C `TODO(Yeo Kai Yuan): replace with real name` | Part 4 — workload model and requirements | `TODO(Part 4 — Teammate C): date` | `TODO(Part 4 — Teammate C): your own prediction where it differed, or "agreed with the team entry"` |
| Teammate D `TODO(Yeo Kai Yuan): replace with real name` | Part 5 — test environment, playbooks, references | `TODO(Part 5 — Teammate D): date` | `TODO(Part 5 — Teammate D): your own prediction where it differed, or "agreed with the team entry"` |

---

## How to freeze

Run these from the repository root, in this order. They are the same commands as README section 9; if the
two ever disagree, `scripts/freeze_gate.py` is the authority, because it is the thing the benchmark scripts
actually consult.

```bash
# 0. Sanity check: the gate must currently FAIL. Expect "ok": false and exit code 3.
#    It tells you on stderr exactly which condition is not yet met.
python scripts/freeze_gate.py --json || echo "not frozen yet — as expected at this point"

# 1. Both files go in ONE commit: the golden set and this prediction record.
#    Nothing else belongs in this commit; it is the commit the marker will look at.
git add golden/golden_set.csv predictions/prediction_record.md
git commit -m "Freeze golden test set and prediction record before first benchmark run"

# 2. Tag that commit. The tag name is fixed — the gate looks for exactly "golden-freeze".
git tag -a golden-freeze -m "Golden set and prediction record frozen (Assignment 1, Step 4)"

# 3. Prove the freeze. Exit code 0 and "ok": true is the green light for Step 5.
python scripts/freeze_gate.py --json

# 4. Prove both files are in the tagged tree, not merely in the working directory.
git cat-file -e golden-freeze:predictions/prediction_record.md && echo "prediction record is in the tagged tree"
git cat-file -e golden-freeze:golden/golden_set.csv && echo "golden set is in the tagged tree"

# 5. Push the commit and the tag, so the dated history is visible to the marker.
git push --follow-tags
```

**After the tag exists, this file is closed.** Do not amend the commit, do not move the tag, and do not
rewrite an entry — all three destroy the only evidence we have that the predictions predate the
measurements. If something genuinely must be corrected (a tag copied wrongly from
`../models/models.yaml`, say), leave the original text exactly as it stands, add a new dated appendix
section below this footer in a **new** commit saying what was wrong and what it should have read, and treat
the tagged version as the prediction of record when writing Slide 11.
