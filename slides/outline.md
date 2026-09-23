# Slide outline — Group10.pptx

## About this document

**What it is for.** The build plan for the submitted deck. It lists all twelve slides in the order the brief
prescribes and, for each one, the content the brief explicitly requires, who owns it, which files and
generated artefacts supply the content, and what "done" looks like. Work slide by slide from this file; the
checklists are the marking scheme restated, so an unticked box is a lost mark.

**Owner:** Part 1 — Yeo Kai Yuan assembles the deck and owns Slides 1, 2, 5 and 9. Every other slide has a
named owner below, and the owner — not the assembler — writes the content.
`TODO(Yeo Kai Yuan): replace "Teammate A/B/C/D" with real names throughout this file once the team is registered.`

**Done when.** Every checkbox below is ticked against the actual deck; every number on every slide names the
file it came from (see *Traceability rule* at the end); the deck is exactly twelve slides or fewer; and the
supporting files listed below are in the same submission.

**What it feeds.** `Group10.pptx` and the supporting-file bundle submitted with it.

**Conventions.** Every path in this file is relative to the repository root, and every command shown is run
from the repository root with the project virtual environment active.

---

## Submission constraints — settle these before building a single slide

* **Maximum twelve slides.** The brief: *"One PowerPoint file, maximum 12 slides, plus the supporting files
  listed below."* There are twelve required slide headings, so there is **no spare slide**: no agenda slide,
  no closing slide, and no splitting a required slide across two. If a slide overflows, move detail into the
  repository and cite the path on the slide.
* **File name `Group10.pptx`.** The brief: *"File name format: GroupNum.pptx, e.g. Group01.pptx."* We are
  team 10 (our dataset slice is rows 10000–10999), so the submitted file is `Group10.pptx` — two digits, no
  spaces, no version suffix.
* **Deadline 2359 Friday 9 October 2026 (Week 6), via xSiTe.** *"Late submissions will be penalised at 15%
  per day. No submissions will be accepted more than four days after the due date."*
* **Supporting files, submitted alongside the deck.** The brief: *"Supporting files, in the same submission:
  the golden test set (final labels for the 150 to 200 tickets, identified by row number); the prediction
  record (the three items listed in Step 4); and the labelling protocol with its revisions, the independent
  label sheets, and the agreement statistic."*

| Supporting file required by the brief | What we submit | Owner |
|---|---|---|
| The golden test set — final labels, identified by row number | `golden/golden_set.csv` (keeps the `row_number` column, so each label is traceable to the course CSV row) | Parts 2 and 3 — Teammates A and B |
| The prediction record — the three items listed in Step 4 | `predictions/prediction_record.md`, **as frozen at the `golden-freeze` tag** (`git show golden-freeze:predictions/prediction_record.md`) | Part 4 — Teammate C holds the pen; whole team signs |
| The labelling protocol **with its revisions** | `labelling/protocol.md` (the revision history is part of the document) | Part 2 — Teammate A |
| The independent label sheets | `labelling/labeller_A.csv` and `labelling/labeller_B.csv` | Parts 2 and 3 — Teammates A and B |
| The agreement statistic | The output written into `labelling/` by `python labelling/scripts/agreement.py --a labelling/labeller_A.csv --b labelling/labeller_B.csv` | Part 3 — Teammate B |

* **Repository evidence, not submitted but examined.** *"The golden test set and the prediction record must
  also be committed to your repository before your first benchmark run. The commit history is your evidence
  that your labels and predictions predate your measurements. Keep your raw JMeter .jtl files and service
  logs in the repository as well; you will not submit them, but every number in your document must
  reconcile with them, and you may be asked to produce and explain them."* The freeze is enforced by
  `python scripts/freeze_gate.py`, and each run directory keeps its `freeze.json` as proof it ran after the
  freeze.

### Ownership map

| Slide | Title | Part | Owner |
|---|---|---|---|
| 1 | Cover Page | Part 1 | Yeo Kai Yuan |
| 2 | Service Architecture | Part 1 | Yeo Kai Yuan |
| 3 | Workload Model | Part 4 | Teammate C |
| 4 | Performance and Accuracy Requirements | Part 4 | Teammate C |
| 5 | Candidate Models | Part 1 | Yeo Kai Yuan |
| 6 | Golden Test Set | Parts 2 and 3 | Teammates A and B |
| 7 | Test Environment | Part 5 | Teammate D |
| 8 | Playbook (Testing Procedure) | Part 5 | Teammate D |
| 9 | Load and Stress Test Results | Part 1 | Yeo Kai Yuan |
| 10 | Accuracy Results | Part 3 | Teammate B |
| 11 | Predictions, Recommendation and Defence | Whole team | Whole team (`TODO(Yeo Kai Yuan): nominate who assembles this slide from the five contributions`) |
| 12 | References and Acknowledgements | Part 5 | Teammate D |

**A note on artefact filenames.** Where a slide's content comes from an analysis script, this outline names
the **script and its output directory**, because the exact table and chart filenames are fixed by the
scripts themselves. Run the command, then cite on the slide the filename it actually wrote — never a
filename you assumed.

---

## Slide 1 — Cover Page

**Owner:** Part 1 — Yeo Kai Yuan.

**The brief requires (verbatim):**

- [ ] "Group number, names, and student IDs."
- [ ] "Project title (concise and descriptive)."
- [ ] "Link to your team's GitHub repository, containing the service source code, sufficient to rebuild and run it with docker compose."

**Sources:**

* Group number: **10** (the registered team number that selects our dataset slice, rows 10000–10999).
* `TODO(Yeo Kai Yuan): names and student IDs of all five members, spelled as registered on xSiTe.`
* `TODO(Whole team): project title — concise and descriptive, naming the system, not the assignment.`
* `TODO(Yeo Kai Yuan): the GitHub repository URL.`
* `README.md` and `docker-compose.yml` (plus `.env.example`) are what make the "sufficient to rebuild and
  run it with docker compose" claim true — the link is only as good as those files.

**Done when:** all three bullets are on the slide; the repository link has been opened by someone who is not
signed in to our GitHub account, so we know a marker can reach it; and a clean clone of that repository
starts with the `docker compose` command given in `README.md`.

---

## Slide 2 — Service Architecture

**Owner:** Part 1 — Yeo Kai Yuan.

**The brief requires (verbatim):**

- [ ] "Diagram of the components: triage service, Ollama backend, storage, load generator."
- [ ] "The three endpoints and what each does."
- [ ] "Confirmation that the baseline is synchronous, with no caching or queuing."

**Also required by the brief body (Steps 2 and 5):**

- [ ] The service exposes "at minimum: POST /tickets, ... GET /search, ... and GET /stats" — describe each in the terms the brief uses (classify and store and return the category; return stored tickets matching a text query; return counts of stored tickets by category).
- [ ] "The service starts empty. Tickets enter the system only through POST /tickets; there is no bulk import" — and "The dataset CSV is never loaded into the service directly." Say this on the slide: it explains why the load generator is in the architecture diagram at all.
- [ ] The load generator sits on a **separate machine** (detailed on Slide 7, but the diagram must show the boundary).

**Sources:**

* The `service/` package: the FastAPI application and its endpoints, `service/prompt.py` (the one fixed
  prompt template and its `PROMPT_HASH`), `service/categories.py` (the seven categories and the reply
  normaliser), `service/log_schema.py` (the per-request log line).
  `TODO(Part 1 — Yeo Kai Yuan): cite the exact module path of the FastAPI application — the module uvicorn is pointed at in docker-compose.yml.`
* `docker-compose.yml` — shows the two containers, the named volume holding the SQLite file (`DB_PATH`), and
  the bind mount for `logs/service/`, which is the "storage" and "instrumentation" of the diagram.
* `.env.example` — the configuration actually in force: `MODEL_TAG`, `NUM_CTX`, `OLLAMA_TIMEOUT_S`,
  `UVICORN_WORKERS=1`.
* `GET /health` output — a live, quotable confirmation of `uvicorn_workers`, `num_ctx`, `prompt_hash`,
  `model_tag` and `model_digest`.
* The `A2 candidate:` comments in `service/` — the in-code evidence that the absence of caching, queuing,
  connection reuse and batching is deliberate rather than accidental. The brief asks for confirmation; these
  comments are what we point at if asked.
* `README.md` architecture section.

**Done when:** the diagram names all four components the brief lists plus the log sink, and marks the
machine boundary between load generator and system under test; each of the three endpoints has a one-line
description; and the synchronous, no-caching, no-queuing confirmation is written as a sentence on the slide
rather than left to be inferred from the diagram.

---

## Slide 3 — Workload Model

**Owner:** Part 4 — Teammate C.

**The brief requires (verbatim):**

- [ ] "Estimated ticket volumes, search rates, and peak versus non-peak periods."
- [ ] "Expected distribution of ticket lengths."
- [ ] "Cite the source of every figure; state clearly which figures are estimates and how you estimated them (see Slide 12)."

**Also required by the brief body (Step 3):**

- [ ] The model must be **quantitative** and must estimate "the number of tickets the client receives in a relevant period; the rate of agent-side searches; peak and non-peak periods, if they exist; and the expected distribution of ticket lengths."
- [ ] "Use publicly available figures relevant to a financial services complaints desk as much as possible, for example published complaint volume statistics, and cite the source for each figure."
- [ ] "If no figure is available, make the best estimate you can and outline how you estimated it."

**Sources:**

* `workload/requirements.md` — the workload model and the requirements it justifies.
  `TODO(Part 4 — Teammate C): if the workload model is a separate document from the requirements, name its path here.`
* `workload/output/` — written by
  `python workload/scripts/ticket_length_stats.py --team-rows data/team_rows.csv --out-dir workload/output`.
  The ticket-length distribution is **measured from our own 1000 team rows**, so it is evidence rather than
  an estimate; say so on the slide, and cite the generated file.
* `data/team_rows.csv` — the 1000 rows the whole engagement uses (`row_number,narrative,raw_label`).
* Published complaint-volume statistics chosen by Part 4, each cited on this slide in short form and in full
  on Slide 12.

**Done when:** every figure on the slide carries either a citation or an explicit "estimated — method" note;
the ticket-length distribution shown is the chart generated into `workload/output/`, not a redrawn
impression of it; peak versus non-peak is stated explicitly, and if the model finds no peak, that
conclusion is stated and justified rather than omitted.

---

## Slide 4 — Performance and Accuracy Requirements

**Owner:** Part 4 — Teammate C.

**The brief requires (verbatim):**

- [ ] "The response time, throughput, and accuracy requirements, each as a testable statement: a number, a percentile where relevant, and the load condition under which it must hold."
- [ ] "Justify each requirement from your workload model and other relevant considerations."

**Also required by the brief body (Step 4):**

- [ ] "At least one response time requirement, for example the latency of POST /tickets, or of GET /search under mixed load."
- [ ] "At least one throughput requirement, for example tickets classified per hour at sustained load."
- [ ] "A classification accuracy requirement, overall and per category, to be measured on your golden test set." (Per category, not only overall.)
- [ ] "If your model implies peak periods, your requirements must cater for the peak."
- [ ] Justification may draw on "usability, the staffing cost of misrouted tickets, and capacity" as well as the workload model.

**Sources:**

* `workload/requirements.md` — the authoritative wording of each requirement. The slide quotes it; it does
  not restate it differently.
* Slide 3's workload model — each requirement must point at the figure it derives from.
* The analysis flags that consume these numbers, so that the deck and the scripts cannot drift apart:
  `python analysis/stress_summary.py --p95-limit-ms <the requirement> --error-rate-limit <the requirement>`
  and `python analysis/reconcile.py --latency-threshold-ms <the requirement>`. Whatever number appears on
  this slide is the number passed to those flags.
* `golden/golden_set.csv` — the accuracy requirement is defined against this set, not against the noisy
  `raw_label` column.

**Done when:** each requirement reads as a single sentence containing a number, a percentile where relevant,
and the load condition; the accuracy requirement has both an overall and a per-category floor; the peak from
Slide 3 is covered; each requirement has a one-line justification that traces to Slide 3 or to a stated
cost consideration; and the same numbers appear in `workload/requirements.md` and in the analysis
invocations on Slide 8.

---

## Slide 5 — Candidate Models

**Owner:** Part 1 — Yeo Kai Yuan.

**The brief requires (verbatim):**

- [ ] "Your three to five candidate models, each pinned by Ollama tag and digest."
- [ ] "The size classes they span and the justification for the candidate set."

**Also required by the brief body (System Under Test, Step 4):**

- [ ] "select three to five candidate models from the Ollama library, spanning at least two parameter size classes, and justify the candidate set in your report."
- [ ] "Pin each candidate by its exact Ollama tag and digest, and report the same pins with your results."
- [ ] "GPU inference is not permitted, in keeping with the client constraint" — the candidates are chosen for CPU-only inference.
- [ ] The candidate set must make the trade-off visible: "Smaller models are faster on CPU and wrong more often; larger models are more accurate, slower, and sustain less throughput. Your candidates should make that trade-off visible rather than avoid it."

**Sources:**

* `models/models.yaml` — one entry per candidate: exact Ollama tag, pinned digest, size class, licence and
  the reason it is in the set. This file is the single source of truth for the tags used everywhere else, and
  the `pinned:` block is written only by the pull script, never by hand — a hand-typed digest is not evidence
  that anything was pulled.
* `models/candidates.md` — the written justification of the candidate set (size classes, licences, the
  trade-off each candidate is in the set to expose, and the named substitutes). The slide is built from this
  and from `models/models.yaml` together; they must not disagree.
* `scripts/pull_and_pin_models.sh --models-file models/models.yaml` — its output records the digest actually
  served, which is what must be reported.
* `results/runs/<run>/metadata.json` and `results/accuracy/<model>_<stamp>/metadata.json` — `model_tag` and
  `model_digest` fields, showing the same pins alongside the results ("report the same pins with your
  results").
* `GET /health` — `model_tag`, `model_digest` of the running service.
* Model licences, carried through to Slide 12.

**Done when:** the slide shows three to five models with tag and digest that match `models/models.yaml` and
the `metadata.json` of the reported runs character for character; at least two parameter size classes are
identified; and the justification says what each candidate is in the set *to test*, not merely that it is
popular.

---

## Slide 6 — Golden Test Set

**Owner:** Parts 2 and 3 — Teammates A and B (Teammate A: protocol and revisions; Teammate B: agreement
statistic and resolutions).

**The brief requires (verbatim):**

- [ ] "Summary of the labelling protocol and its revisions."
- [ ] "The inter-annotator agreement statistic."
- [ ] "Number of disagreements and how they were resolved, with one or two examples."

**Also required by the brief body (Step 1):**

- [ ] "a golden test set of 150 to 200 tickets drawn from your team's rows."
- [ ] "Write a labelling protocol first: a definition of each category, with rules for the edge cases you expect (tickets that fit two categories, tickets that fit none, ambiguous narratives)."
- [ ] "At least two team members label every ticket independently, following the protocol and without conferring."
- [ ] "Compute and report an inter-annotator agreement statistic."
- [ ] "Resolve every disagreement by discussion, record each resolution, and update the protocol where a disagreement revealed a gap in it."
- [ ] The freeze: "it is committed to your repository before your first benchmark run, and the commit history is your evidence."
- [ ] "Disagreements are expected and are evidence of care, not error. A golden set with implausibly perfect agreement and no recorded resolutions will be examined closely." — so report the disagreements, do not minimise them.

**Sources:**

* `labelling/protocol.md` — category definitions, edge-case rules, **and the revision history**; also
  records the sampling seed (3113, the course code).
* `python labelling/scripts/sample_golden_candidates.py --team-rows data/team_rows.csv --n <count> --seed 3113 --out-dir labelling`
  — how the candidate tickets were drawn, which is part of the rigour of the construction.
* `labelling/labeller_A.csv`, `labelling/labeller_B.csv` — the independent label sheets.
* `python labelling/scripts/agreement.py --a labelling/labeller_A.csv --b labelling/labeller_B.csv --out-dir labelling`
  — the agreement statistic; name the statistic used and quote the value from the file it wrote.
* `labelling/resolutions.csv` — every disagreement and its resolution; the disagreement count on the slide
  is the row count of this file.
* `golden/golden_set.csv` — built by
  `python labelling/scripts/build_golden_set.py --a labelling/labeller_A.csv --b labelling/labeller_B.csv --resolutions labelling/resolutions.csv --out golden/golden_set.csv`.
* The `golden-freeze` tag and its commit date — the freeze evidence
  (`python scripts/freeze_gate.py --json` prints the freeze commit).

**Done when:** the slide names the agreement statistic used and gives its value from the generated file; the
ticket count is within the brief's 150 to 200; the disagreement count matches `labelling/resolutions.csv`;
one or two real resolutions are quoted (row number, the two labels, the agreed label, the reason); the
protocol revisions are summarised as what changed and why; and the freeze commit and tag date are shown.

---

## Slide 7 — Test Environment

**Owner:** Part 5 — Teammate D.

**The brief requires (verbatim):**

- [ ] "Hardware and software of each machine: service, Ollama, load generator."
- [ ] "Confirmation that the load generator ran on a separate machine."
- [ ] "How results scale to the client's deployment; assumptions and limitations."

**Also required by the brief body (Step 5, System Under Test):**

- [ ] "describe your test environment: the machines running the service, Ollama, and the load generator; their CPU, memory, and operating system; the network between them; and any factors that could make your measurements unrepresentative."
- [ ] "The load generator and the system under test must run on separate machines. A co-hosted load generator steals CPU from the service and produces latency numbers that are fiction."
- [ ] Ollama runs "on CPU only" — "GPU inference is not permitted ... report your hardware in the test environment description."
- [ ] The client's own hardware is "commodity CPU servers with no GPUs" — the scaling argument is made against that.

**Sources:**

* `docs/environment/` — written by
  `scripts/capture_env.sh --role all --out-dir docs/environment` (run it with `--role service`,
  `--role ollama` and `--role loadgen` on the respective machines). Copy CPU, memory and OS onto the slide
  from these captured files rather than from memory.
* `results/runs/<run>/metadata.json` — `service_host_info`, `load_generator_host_info`, `jmeter_version`,
  `ollama_num_parallel`, `ollama_max_loaded_models`: the per-run record that the environment on the slide is
  the environment the numbers came from.
* `docker-compose.yml` and `.env.example` — the software configuration in force (`NUM_CTX`,
  `UVICORN_WORKERS`, `SERVICE_THREADPOOL_SIZE`, `OLLAMA_TIMEOUT_S`).
* `GET /health` — confirms which Ollama the service was actually talking to (`ollama_base_url`).

**Done when:** each of the three roles has CPU, memory and OS on the slide, taken from `docs/environment/`;
the separate-machine claim is explicit and names the two hosts; the network between them is described
(link type and measured round-trip, captured as part of the environment evidence); and at least two named
limitations are given with the direction in which each biases our numbers, together with a stated
assumption about how the results carry over to commodity CPU servers.

---

## Slide 8 — Playbook (Testing Procedure)

**Owner:** Part 5 — Teammate D.

**The brief requires (verbatim):**

- [ ] "Step-by-step outline of how each test was conducted, including the open-loop JMeter configuration."
- [ ] "Include diagrams or flowcharts where useful."

**Also required by the brief body (Step 5):**

- [ ] "Each test playbook must be described in sufficient detail that a competent software tester could carry it out without seeking or inventing further information from your team."
- [ ] "Traffic must be generated open-loop, at controlled arrival rates: use the Open Model Thread Group or the Precise Throughput Timer. Closed-loop traffic self-throttles when the server slows down and hides queue buildup. Results from closed-loop tests will not be accepted as evidence against throughput or latency requirements."
- [ ] "JMeter plays the role of the client's complaint intake: it draws ticket narratives from your team's rows (for example with a CSV Data Set Config) and posts each one to POST /tickets."
- [ ] "Three runs per configuration." (Stated here as procedure; the results are on Slide 9.)
- [ ] "Keep the raw JMeter result files (.jtl) from every run in your repository; they must reconcile with your service logs."
- [ ] All three kinds of test are covered: load tests, accuracy tests ("Send every golden-set ticket through POST /tickets for each candidate model"), and "One stress test."

**Sources:**

* `docs/playbooks/` — the written playbooks, one per test. `docs/playbooks/stress-test.md` additionally
  records the **step boundaries** of the ramp, which `analysis/stress_summary.py --step-seconds` needs.
* `jmeter/load_post_tickets.jmx`, `jmeter/mixed_load.jmx`, `jmeter/stress_ramp.jmx` — the plans themselves.
  Each carries a `TestPlan.comments` block explaining why no closed-loop thread group is used; the Open
  Model Thread Group schedule string is the quotable evidence of open-loop generation.
* Exact invocations to reproduce a run, which belong on the slide verbatim:
  `scripts/run_load_test.sh --plan load_post_tickets --model <tag> --rate <per_min> --duration <seconds> --runs 3`
  and `python scripts/run_accuracy.py --model <tag> --golden golden/golden_set.csv`.
* `python scripts/freeze_gate.py --json` — the first step of every playbook: no run against team rows starts
  before the gate passes, and its output is kept as `freeze.json` in the run directory.
* `results/runs/<run>/` layout — `metadata.json`, `freeze.json`, `results.jtl`, `jmeter.log`,
  `service.jsonl`, `warmup.jsonl`: what a tester is expected to have produced when the run finishes.

**Done when:** the slide gives the open-model arrival-rate configuration (the schedule string) and the exact
commands; a flowchart shows freeze gate to warm-up to run to log collection to analysis; the three-runs rule
and the warm-up exclusion are stated; and a tester outside the team could execute one load run, the accuracy
run and the stress run from this slide plus `docs/playbooks/` with no further questions.

---

## Slide 9 — Load and Stress Test Results

**Owner:** Part 1 — Yeo Kai Yuan.

**The brief requires (verbatim):**

- [ ] "p50, p95, and p99 latency, achieved throughput, and error rate at each tested arrival rate, per candidate model, across three runs."
- [ ] "The stress test and the limit it found."
- [ ] "Short interpretation, including the diagnosed bottleneck."

**Also required by the brief body (Step 5):**

- [ ] "Three runs per configuration. Report means and the spread across runs. A single run is not a measurement."
- [ ] "Design and execute one test that determines a limit of the system under test, for at least one candidate model" — state which limit was chosen and the criterion that defines it.
- [ ] "Include the results of every test when applied to the unmodified baseline."
- [ ] "Note any instance where the system does not meet your requirements; you do not need to correct the root cause at this stage. Diagnose it and note that it exists."
- [ ] Results must be open-loop, and must reconcile with the service logs.

**Sources:**

* `results/runs/<stamp>_<model>_<plan>_<rate>_run<k>/` — `results.jtl` (the raw JMeter samples),
  `metadata.json` (model, plan, rate, run index, freeze commit), `service.jsonl` (the service's own view),
  `warmup.jsonl` (excluded from every figure).
* `analysis/output/load/` — written by `python analysis/summarise_load.py --runs results/runs`: the
  per-configuration percentile, throughput and error-rate tables, with mean and spread across the three runs.
* `analysis/output/stress/` — written by
  `python analysis/stress_summary.py --run-dir results/runs/<stress run> --step-seconds <from docs/playbooks/stress-test.md>`:
  the per-step table that identifies the limit.
* `analysis/output/bottleneck/` — written by
  `python analysis/bottleneck_hints.py --run-dir results/runs/<run>`: the decomposition of total latency into
  model time and the rest, which is the evidence behind the diagnosed bottleneck.
* `analysis/output/reconcile/` — written by
  `python analysis/reconcile.py --run-dir results/runs/<run>`: the proof that the `.jtl` samples and the
  service log lines are the same requests, joined on `request_id`. Cite it on the slide in one line; it is
  what makes every other number on the slide defensible.
* `workload/requirements.md` — the requirement each figure is judged against.

**Done when:** the table covers every tested arrival rate for every candidate model, with p50, p95, p99,
achieved throughput and error rate, each as the mean across the three runs plus the spread; the stress limit
is stated as a value with the condition that defines it; the bottleneck is named and supported by a specific
log field or `.jtl` column rather than asserted; every requirement the baseline misses is flagged here (not
quietly left to Slide 11); and each figure names its source file.

---

## Slide 10 — Accuracy Results

**Owner:** Part 3 — Teammate B.

**The brief requires (verbatim):**

- [ ] "Overall and per-category accuracy on the golden set, per candidate model."
- [ ] "Confusion matrix highlights: where each model goes wrong."

**Also required by the brief body (Step 5):**

- [ ] "Send every golden-set ticket through POST /tickets for each candidate model, and report overall and per-category accuracy against your golden labels, with a confusion matrix." — every ticket, every candidate.
- [ ] Accuracy is measured against the golden labels, not the raw dataset labels ("those labels are noisy").

**Sources:**

* `results/accuracy/<model>_<stamp>/responses.csv` — `row_number,request_id,http_status,predicted_category,error`,
  produced by `python scripts/run_accuracy.py --model <tag> --golden golden/golden_set.csv`, plus that run's
  `metadata.json` and `freeze.json`.
* `golden/golden_set.csv` — the labels accuracy is measured against.
* `analysis/output/accuracy/` — written by
  `python analysis/accuracy.py --results results/accuracy --golden golden/golden_set.csv`: the overall and
  per-category accuracy tables and the confusion-matrix chart for each candidate. The matrix axes follow the
  canonical category order in `service/categories.py`, so the axis order is the same on every chart.
* `service/categories.py` — the seven canonical names and `UNPARSEABLE`. Replies that could not be mapped are
  counted as `UNPARSEABLE`, never silently re-read as the nearest category; the slide must show them.

**Done when:** overall accuracy and a per-category breakdown appear for every candidate model; the confusion
matrix (or its highlighted cells) is on the slide with axes in canonical order; the `UNPARSEABLE` count is
reported per model and explained in one line; the per-category floor from Slide 4 is shown as met or missed
per category; and every figure names the file in `analysis/output/accuracy/` it came from.

---

## Slide 11 — Predictions, Recommendation and Defence

**Owner:** Whole team. Each part brings its own line: predictions (whole team), requirements (Part 4),
latency and throughput evidence (Part 1), accuracy evidence (Part 3).
`TODO(Yeo Kai Yuan): nominate who assembles this slide from the five contributions.`

**The brief requires (verbatim):**

- [ ] "Your predictions against your outcomes, and an account of where and why you were wrong."
- [ ] "The recommended model, defended against your stated requirements."
- [ ] "Any requirement no candidate meets, stated plainly."

**Also required by the brief body (Steps 4 and 6):**

- [ ] "Marks are awarded for specificity and for the quality of your later account of where your predictions were wrong, not for being right." — the account of the misses is the marked content; do not bury it.
- [ ] "Given the client's constraints, recommend which of your candidate models the client should deploy."
- [ ] "your recommendation must follow from your own measurements and hold against your own requirements."
- [ ] "A recommendation that contradicts your stated requirements, or rests on numbers that do not appear in your logs, fails regardless of which model it picks."
- [ ] "A finding that no candidate meets all of your requirements, measured carefully and argued clearly, is a strong result" — so state such a finding plainly rather than softening it.
- [ ] The client scenario's constraints frame the recommendation: no public model API, CPU-only commodity hardware, and the client has not told us whether a misrouted ticket or a slow triage costs more — our requirements take that position.

**Sources:**

* `predictions/prediction_record.md` **as frozen**: quote
  `git show golden-freeze:predictions/prediction_record.md`, not the working copy, so what we compare against
  is provably the pre-measurement text.
* `results/runs/*/freeze.json` and `results/accuracy/*/freeze.json` — each carries the freeze commit, proving
  every reported run happened after the freeze.
* `analysis/output/load/`, `analysis/output/stress/`, `analysis/output/bottleneck/` (Slide 9) and
  `analysis/output/accuracy/` (Slide 10) — the outcomes the predictions are placed against.
* `workload/requirements.md` — the requirements the recommendation is defended against, quoted in the same
  words as Slide 4.
* The sign-off table in `predictions/prediction_record.md` — where members predicted differently, that
  disagreement is usable material here.

**Done when:** every prediction in the frozen record is paired with the measured outcome and a one-line
account of why the gap exists (a mechanism, not "we underestimated"); exactly one recommended model is
named and defended requirement by requirement; every requirement that no candidate meets is stated plainly
with the evidence; and no number on the slide fails the traceability rule below.

---

## Slide 12 — References and Acknowledgements

**Owner:** Part 5 — Teammate D.

**The brief requires (verbatim):**

- [ ] "Properly formatted references for all sources used, including the Consumer Complaint Database, Ollama, and the licences of your candidate models."

**Also required by the brief body (Slide 3, Notes on Copyright and Plagiarism):**

- [ ] Slide 3 defers here: "Cite the source of every figure; state clearly which figures are estimates and how you estimated them (see Slide 12)." Every workload source cited in short form on Slide 3 appears here in full.
- [ ] "The Consumer Complaint Database is published by a US government agency; acknowledge the source in your final document." The brief gives the original database as www.consumerfinance.gov/data-research/consumer-complaints/, and notes the narratives are "published with consumer consent and with personal information removed at source".
- [ ] "Ollama and your candidate models each carry their own licences; place any acknowledgements they require in your final document. Failing to comply with a licence may be an infringement of copyright."

**Sources:**

* `docs/references.md` — the reference list the slide is built from.
  `TODO(Part 5 — Teammate D): confirm this path if the references live in a different file.`
* `docs/assignment-brief.md` — the Consumer Complaint Database attribution and URL as the brief states them.
* `models/models.yaml` and `models/candidates.md` — the candidate tags, the licence recorded for each
  (`licence` and `licence_url`), and the citations behind every factual claim made about a model.
* Apache JMeter, Ollama, and any library or published statistic used by Part 4 on Slide 3.

**Done when:** every source cited anywhere in the deck appears here in one consistent citation style; the
Consumer Complaint Database, Ollama and a licence for each candidate model are all present; and nothing
cited on Slide 3 or Slide 7 is missing from the list.

---

## Traceability rule

**Every number on a slide names the file it came from.** This is not house style; it is how the brief marks
us. *"Every number in your final document must reconcile with them; a number that cannot be traced to a log
entry is treated as unsupported, and you may be asked to produce and explain your logs."* And, more
sharply: *"Fabricated or irreconcilable measurement numbers are treated as an academic integrity matter, not
a marking deduction."*

How we satisfy it:

1. **Cite in place.** Each figure, table and quoted value carries its source as small text, for example
   `source: analysis/output/load/<filename>` or `source: results/runs/<run dir>/results.jtl`. The run
   directory name itself encodes model, plan, arrival rate and run index, so the citation is unambiguous.
2. **Only committed, regenerated artefacts.** Every reported number comes from `analysis/output/`, which is
   committed and is reproducible by re-running the command that wrote it. If a number on a slide cannot be
   reproduced by running the documented command, it does not go on the slide.
3. **Never from `results/dev/`.** Dev-mode runs use synthetic tickets, are gitignored, and print
   `*** DEV MODE — synthetic tickets only. Results are NOT evidence. ***`. No dev-mode figure reaches a
   slide, a supporting file, or a sentence of interpretation.
4. **Reconciliation is shown once.** `analysis/reconcile.py` joins the JMeter samples to the service log
   lines on `request_id`; cite it on Slide 9 so the marker can see the `.jtl` files and the service logs are
   the same requests.
5. **If it cannot be traced, delete it.** A missing number costs at most the marks for that point. An
   untraceable one is treated as unsupported, and a fabricated one is an academic integrity matter.
