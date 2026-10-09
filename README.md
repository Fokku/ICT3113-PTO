# ICT3113 Assignment 1 — Ticket Triage Service (Team 10)

**Module:** ICT3113 Performance Optimisation and Design.
**Assignment:** Assignment 1 — Performance Requirements and Testing (15% of the final mark).
**Team:** Team 10. Our dataset slice is rows 10000–10999 of the course CSV.
**Deliverable:** `Group10.pptx`, maximum 12 slides, plus the supporting files listed in
[`slides/outline.md`](slides/outline.md). Due **2359, Friday 9 October 2026**.
**Team members:** Yeo Kai Yuan (Part 1), Loh Wen Xuan (Part 2), Jolie Ngai Ning Li (Part 3), Toh Si Pei
(Part 4), Koh Tong Wei (Part 5).
**Repository:** <https://github.com/Fokku/ICT3113-PTO>
**Owner of this file and of the technical core:** Yeo Kai Yuan (Part 1).

| Part | Name | Student ID | What they own |
|---|---|---|---|
| 1 | Yeo Kai Yuan | 2403201 | the service, the scripts, the plans, the freeze gate, the candidate shortlist, the campaign |
| 2 | Loh Wen Xuan | ⟪ID⟫ | golden-set lead and labeller A: `labelling/protocol.md`, the agreement run, the golden set |
| 3 | Jolie Ngai Ning Li | ⟪ID⟫ | labeller B, co-resolution of disagreements, accuracy results |
| 4 | Toh Si Pei | ⟪ID⟫ | workload model and requirements |
| 5 | Koh Tong Wei | 2402162 | test environment, playbooks and the deck |

The three ⟪ID⟫ cells are filled from `slides/team.yaml`, which Slide 1 is built from.

**Licences and attribution.** Built with Llama. Two of our four candidate models, `llama3.2:1b-instruct-q4_K_M`
and `llama3.2:3b`, are Meta Llama 3.2 models under the Llama 3.2 Community License; the required notice is in
[`NOTICE`](NOTICE) at the repository root. The other two, `granite4:3b` and `qwen2.5:7b`, are under the
Apache License 2.0. Every licence and its obligations are set out in
[`docs/references.md`](docs/references.md) section 8.

## Results at a glance (campaign of 8–9 October 2026)

Every figure below is read from `analysis/output/`, produced by `scripts/run_analysis.sh` from the raw `.jtl` files
and service logs in `results/` and `logs/service/`; all 55 JMeter runs reconcile with the service log.
The deck is [`slides/Group10.pptx`](slides/Group10.pptx), rebuilt by `scripts/build_submission.sh`.

| Model | Accuracy (R3 ≥ 90%) | Lowest category recall (R4 ≥ 80%) | p95 at 1/min (R1 ≤ 10 s) | 12/min (R2) | Search p95 (R5 ≤ 2 s) | Stress limit |
|---|---|---|---|---|---|---|
| `llama3.2:1b-instruct-q4_K_M` | 26.0% | 0% | 0.96 s | 0% errors, done by 598 s | 17 ms | none up to 60/min |
| `llama3.2:3b` | 48.5% | 0% | 2.32 s | 0% errors, 587 s | 17 ms | 40/min |
| `granite4:3b` | 66.0% | 35% | 2.40 s | 0% errors, 598 s | 17 ms | 40/min |
| `qwen2.5:7b` | 74.0% | 57% | 5.52 s | 0% errors, 603 s | 140 ms | 21/min |

Every candidate meets R1, R2 and R5; none meets R3 or R4. The recommendation (Slide 11) is `qwen2.5:7b`, as a
route suggestion for an agent to confirm, not as an autonomous router. The bottleneck is Ollama's single request
slot; our own handler adds ~0.2 s per ticket in the SQLite commit. Predictions against outcomes:
[`predictions/outcomes.md`](predictions/outcomes.md). The run, in order: [`docs/run-log.md`](docs/run-log.md).

This README is written for a teammate opening a fresh clone who has never seen the repository. Follow it in
order and you will not have to ask anyone a question. Every script and file it names exists, and every
`--help` quoted here came from running that script. The JMeter commands were first transcribed from the plans;
on 8 October 2026 every plan was run end to end through `scripts/run_campaign.sh --dev` with JMeter 5.6.3 on
JDK 21, which is how the `-q jmeter/user.properties` gap described in [section 6.7](#67-running-a-plan-by-hand)
was found and closed.

Two documents sit alongside this one and are not repeated here:

* [`TODO.md`](TODO.md) — who is doing what, by when, with the internal deadlines.
* [`slides/outline.md`](slides/outline.md) — what goes on each of the twelve slides and which file supplies it.

---

## Table of contents

1. [What this is](#1-what-this-is) — the scenario, the system under test, the repository map, the hard rules,
   the worker and thread configuration
2. [**The freeze rule**](#2-the-freeze-rule) — read this before running anything
3. [Prerequisites](#3-prerequisites)
4. [Setup, step by step](#4-setup-step-by-step)
5. [The two-machine setup](#5-the-two-machine-setup)
6. [Running the tests](#6-running-the-tests)
7. [Analysis and reconciliation](#7-analysis-and-reconciliation)
8. [Where to start, per part](#8-where-to-start-per-part)
9. [How to do the freeze](#9-how-to-do-the-freeze)
10. [Troubleshooting](#10-troubleshooting)
11. [Service log format](#11-service-log-format)
12. [Changelog](#12-changelog)

---

## 1. What this is

### 1.1 The scenario and the system under test

Our client is a financial services company whose customer relations desk receives a steady stream of
complaint tickets. Today every ticket is read and routed by a human, and the client wants them classified
automatically into one of seven categories so they can be routed to the right team. The binding constraint
is that **no public model API may be used**: ticket narratives contain sensitive customer financial
information, so all inference must run on hardware the client controls, and that hardware is commodity CPU
servers with **no GPUs**. The engagement question is therefore not "which model is best" but "given these
constraints, what should the client deploy, and what service quality can we promise?"

The system under test has three parts:

| Part | What it is | Where it lives |
|---|---|---|
| **Ticket triage service** | A FastAPI web service in Docker. `POST /tickets` classifies one narrative by calling the model backend, stores it, and returns the category; `GET /search` returns stored tickets matching a text query; `GET /stats` returns counts by category. `GET /health` reports the configuration and whether the backend is reachable. | [`service/`](service/) |
| **Model backend** | Ollama, **CPU only**, serving one pinned model at a time. Four candidates across three size classes are proposed in [`models/candidates.md`](models/candidates.md) and pinned by digest in [`models/models.yaml`](models/models.yaml). | `ollama` container in [`docker-compose.yml`](docker-compose.yml) |
| **Load generator** | Apache JMeter, driving open-loop arrival rates from a **separate machine**, plus the accuracy driver. | [`jmeter/`](jmeter/), [`scripts/`](scripts/) |

The service starts empty. Tickets enter only through `POST /tickets`; the dataset CSV is never loaded into the
service directly. During testing the load generator plays the role of the client's complaint intake, drawing
narratives from our team's rows and posting them one at a time.

**What we are measuring.** Three things, and each is measured by a different test:

1. **Response time** of `POST /tickets` (p50, p95, p99) and of `GET /search` under mixed load, at controlled
   open-loop arrival rates — [`docs/playbooks/load-test.md`](docs/playbooks/load-test.md).
2. **Throughput and error rate** at each tested arrival rate, and the **limit** at which the baseline stops
   meeting the requirement — [`docs/playbooks/stress-test.md`](docs/playbooks/stress-test.md).
3. **Classification accuracy**, overall and per category, against our own frozen golden test set —
   [`docs/playbooks/accuracy-test.md`](docs/playbooks/accuracy-test.md).

The seven categories, in the canonical order used for every confusion-matrix axis, are defined once in
[`service/categories.py`](service/categories.py): Credit reporting, Debt collection, Mortgage, Credit card,
Bank account or service, Consumer loan, Money transfer or service. A model reply that cannot be mapped onto
exactly one of them is stored as `UNPARSEABLE`. The seven numbered normalisation rules, and the deliberate
decision not to perform any semantic remapping, are in that module's docstring. Do not write a second
normaliser.

### 1.2 Repository map

```
.
├── analysis/                derived tables and charts; every number that reaches Slides 9-11
│   ├── common.py            shared helpers: run-directory parsing, .jtl and log readers, percentiles
│   ├── output/              committed derived output, one subdirectory per topic (the slides cite it)
│   └── tests/               pytest suite for the analysis scripts, on synthetic fixtures only
├── data/                    the only ticket data in the repository
│   ├── team_rows.csv        our 1,000 rows (10000-10999): row_number,narrative,raw_label
│   ├── dev/                 28 hand-written synthetic tickets — the ONLY pre-freeze model input
│   └── search_terms.txt     query strings for the mixed-load GET /search stream
├── docs/                    the brief, the procedures, the environment write-up, the references
│   ├── assignment-brief.md  the brief itself, converted from the .docx
│   ├── playbooks/           step-by-step test procedures (Slide 8)
│   ├── environment/         one generated capture file per machine (Slide 7 evidence)
│   ├── test-environment.md  the Slide 7 template: machines, network, biases, scaling argument
│   └── references.md        pre-seeded reference list and licence obligations (Slide 12)
├── golden/                  golden_set.csv: the 200-row golden set built by Part 2 from the resolved sheets
├── jmeter/                  the three open-loop plans, plus the pinned .jtl column set
│   ├── load_post_tickets.jmx   steady state: POST /tickets at a fixed rate
│   ├── mixed_load.jmx          interference: POST /tickets and GET /search concurrently
│   ├── stress_ramp.jmx         a six-step rising staircase, to find a limit
│   ├── user.properties         sample_variables and the saveservice settings; pass with -q
│   └── README.md            what each plan measures, every -J property, and why never closed-loop
├── labelling/               Step 1: the golden test set (Parts 2 and 3)
│   ├── protocol.md          the labelling protocol and its revision log
│   ├── labeller_A.csv       independent label sheet A
│   ├── labeller_B.csv       independent label sheet B
│   ├── resolutions.md/.csv  how every disagreement was resolved
│   └── scripts/             sampler (seed 3113), Cohen's kappa, golden-set builder
├── logs/service/            the service's JSONL request log, bind-mounted out of the container
├── models/                  Step 4, first half: the candidate shortlist
│   ├── candidates.md        the argued shortlist, licences, and what was rejected and why
│   └── models.yaml          the machine-readable pin file; digests written by the pull script only
├── predictions/             prediction_record.md — frozen together with the golden set
├── results/                 raw evidence, committed
│   ├── runs/                one directory per load, mixed or stress run
│   ├── accuracy/            one directory per accuracy run, per model
│   └── dev/                 pre-freeze rehearsals. GITIGNORED. Never evidence
├── scripts/                 the operational surface
│   ├── freeze_gate.py       the single implementation of the freeze check
│   ├── run_load_test.sh     the sanctioned load/mixed/stress harness
│   ├── run_accuracy.py      posts every golden ticket once, for one model
│   ├── smoke_test.sh        the one permitted pre-freeze model exercise
│   ├── reset.sh             wipes the database volume so a run starts empty
│   ├── pull_and_pin_models.sh   pulls each candidate and writes its digest into models.yaml
│   ├── capture_env.sh       records one machine's hardware and software for Slide 7
│   └── extract_team_rows.py     already run; produced data/team_rows.csv
├── service/                 the baseline service
│   ├── main.py              the FastAPI app and the four routes
│   ├── config.py            every environment variable, resolved once, reported by /health
│   ├── categories.py        the seven categories and the reply normaliser (single source of truth)
│   ├── prompt.py            the one fixed prompt template and its PROMPT_HASH
│   ├── ollama_client.py     the per-request model call
│   ├── db.py                SQLite: a new connection per request, no WAL, no pooling
│   ├── log_schema.py        LOG_FIELDS: the 24 keys of every log line, in order
│   └── request_log.py       the JSONL writer: open, write, flush, close, per request
├── slides/outline.md        the slide-by-slide build plan for Group10.pptx
├── tests/                   pytest suite for the service and the scripts (no model is contacted)
├── workload/                Step 3 and the requirements half of Step 4 (Slides 3 and 4)
│   ├── workload_model.md    volumes, search rate, peak factor, ticket length distribution
│   ├── requirements.md      R1-R5: the testable requirements
│   └── scripts/             ticket length and truncation-risk statistics
├── docker-compose.yml       the two services; the `local-ollama` profile creates Ollama locally
├── Dockerfile               the service image (python:3.11-slim, non-root, one uvicorn worker)
├── .env.example             every configuration variable with its default and its rationale
├── requirements.txt         service runtime only (installed in the image)
├── requirements-dev.txt     host tooling: pytest, pandas, matplotlib, PyYAML
├── TODO.md                  the team's working agreement and the internal deadlines
├── NOTICE                   the Llama 3.2 Community License notice
└── ict3113_tickets.csv      the full course CSV. GITIGNORED — place it here yourself
```

### 1.3 The hard rules

Six rules govern every file in this repository. They override style, elegance and convenience, and
`jmeter/user.properties` and several other files point here for them.

1. **The baseline stays naive.** `POST /tickets` is synchronous: it does not return until the model has
   answered. No caching, no queuing, no batching, no response reuse, no connection pooling, no background
   workers, no retries for speed, no prompt shortening for speed. Where there was a naive choice and a clever
   one we took the naive one and left a comment of the form
   `# A2 candidate: <the optimisation we are deliberately not doing>` on the line above. Optimisation is
   Assignment 2; the baseline exists to be measured. Do not "improve" performance anywhere.
2. **No model sees a team row before the freeze.** See [section 2](#2-the-freeze-rule).
3. **We do not measure model performance at development time.** No latency and no accuracy figure appears in
   a smoke test, an example, or a docstring. The analysis scripts compute latency and accuracy — that is
   their job — and they are run against real evidence only after the freeze.
4. **Judgement work belongs to its owner.** The labels and the protocol (Parts 2 and 3), the workload figures
   and the requirements (Part 4) were written by their owners. The prediction record was drafted by Part 1 with
   an AI assistant under deadline pressure and circulated to the whole team before the freeze; its §0 says so,
   and says which entries were not blind. A placeholder is always visibly empty, never a plausible-looking
   made-up value.
5. **No number is ever fabricated.** Every figure that could be reported traces to a line in
   `logs/service/*.jsonl` or to a JMeter `.jtl`. The brief treats an irreconcilable number as an academic
   integrity matter, not a marking deduction.
6. **The freeze gate is enforced in code**, not in prose — [`scripts/freeze_gate.py`](scripts/freeze_gate.py).

### 1.4 Worker and thread configuration

This subsection exists because these four settings decide *where the bottleneck can land*, and a reader of
our results has to know them. All four are reported live by `GET /health` and written into every run's
`metadata.json`.

| Setting | Value | Why it is what it is |
|---|---|---|
| `UVICORN_WORKERS` | **1** (explicit, not a default) | One process, one event loop, one writer to the SQLite file and one appender to the JSONL log. The evidence therefore cannot interleave, and the process model is a stated part of the baseline. Set in `.env.example`, honoured by the container `CMD` and by `python -m service.main`. |
| Endpoint style | `async def`, with blocking SQLite handed to the framework's worker-thread pool via `run_in_threadpool` | Calling `sqlite3` straight from an `async def` handler would block the single event loop for the whole insert and serialise every request *inside our process*. That would move the bottleneck into the web tier as an artefact of a coding mistake rather than as a property of the design. The naivety Assignment 2 gets to fix is the connect-and-close per request in `service/db.py`, not loop blocking. |
| `SERVICE_THREADPOOL_SIZE` | **40** (the anyio framework default, set explicitly) | Set explicitly and logged so the value is visible rather than being an invisible library default that could change with a dependency upgrade. `service/main.py` sets `anyio.to_thread.current_default_thread_limiter().total_tokens` from it at start-up. |
| **Concurrency limit in the service** | **none** | There is no semaphore, no bulkhead and no queue in the service. Requests arrive as fast as the load generator sends them, and each one opens its own `httpx.AsyncClient` to Ollama. In-flight model calls are bounded only by Ollama's own parallelism and its internal queue. `# A2 candidate: a bulkhead / semaphore around the model call.` |
| `OLLAMA_NUM_PARALLEL`, `OLLAMA_MAX_LOADED_MODELS` | **`0`** — Ollama's own "decide for me" sentinel, stated explicitly in `docker-compose.yml` | Written out so the value appears in `docker compose config` and can be copied into `metadata.json`. Deliberately **not tuned**: concurrency is the knob most likely to move throughput on CPU, and turning it now would mean the baseline is already tuned and there is nothing left to show in Assignment 2. |

**Why this matters.** Because the service imposes no limit of its own and Ollama imposes both a parallelism
limit and a queue, we expect the bottleneck under load to land in **Ollama**, not in the web tier. That is a
prediction the stress test tests, not an assumption the design is built around — and it is recorded as a
prediction in [`predictions/prediction_record.md`](predictions/prediction_record.md) before any measurement,
where it can be proved wrong. `analysis/bottleneck_hints.py` breaks a request down into service overhead, a
queue/transport residual, model load, prompt evaluation and generation, which is how the prediction gets
checked.

---

## 2. THE FREEZE RULE

> ### Read this before you run anything at all
>
> **No model may see one of our team's rows until the golden set and the prediction record are committed and
> the commit is tagged `golden-freeze`.** That means no model touches
> [`data/team_rows.csv`](data/team_rows.csv) and no model touches `golden/golden_set.csv` before the tag
> exists.
>
> **Why, in plain terms.** Our accuracy figure is measured against labels we wrote ourselves, because the
> consumer-selected labels in the raw dataset are noisy. If we label — or revise a label, or revise a
> prediction — after seeing what a model said, our labels drift towards the model's answers and the accuracy
> measurement is quietly corrupted. It stops being a measurement of the model and becomes a measurement of
> our agreement with it. The brief is explicit: *"Labelling after you have seen model outputs drags your
> labels towards whatever the model says, and quietly corrupts the accuracy measurement."*
>
> **The commit history is our only evidence that this did not happen.** Not our word, not a note in a
> document: the dated commits and the tag. A prediction record whose commit is newer than the first `.jtl`
> actively damages the submission.
>
> **The rule is enforced in code, not by good intentions.**
> [`scripts/freeze_gate.py`](scripts/freeze_gate.py) is the single implementation, and it passes only when
> all four of these hold:
>
> 1. `golden/golden_set.csv` exists, is tracked by git, and has no uncommitted modifications;
> 2. `predictions/prediction_record.md` exists, is tracked, and has no uncommitted modifications;
> 3. the tag `golden-freeze` exists;
> 4. **both files are present in the tagged commit's tree** — that is, they were committed at or before the
>    tag.
>
> `scripts/run_load_test.sh` and `scripts/run_accuracy.py` both call the gate themselves and **copy its
> verbatim JSON verdict into every run directory as `freeze.json`**, and both stamp the `freeze_commit` into
> `metadata.json`. So each individual run carries its own proof that it happened after the freeze. Nothing
> can be back-dated.
>
> **Before the freeze, use `--dev`.** `scripts/run_load_test.sh --dev` and
> `.venv/bin/python scripts/run_accuracy.py --dev` bypass the gate on purpose, so the whole pipeline can be
> rehearsed.
> Dev mode reads only [`data/dev/synthetic_tickets.csv`](data/dev/synthetic_tickets.csv) (28 hand-written
> tickets, row numbers 900000–900027), writes only under the gitignored `results/dev/`, stamps
> `"mode": "dev"` and `"freeze_commit": null`, prints
> `*** DEV MODE — synthetic tickets only. Results are NOT evidence. ***`, and **refuses (exit 2)** if any
> argument names `data/team_rows.csv` or anything under `golden/`. Rehearse with it as much as you like.
> **Dev-mode output must never appear on a slide.**
>
> Check the gate at any time:
>
> ```bash
> .venv/bin/python scripts/freeze_gate.py            # human-readable; exit 0 pass, 3 blocked
> .venv/bin/python scripts/freeze_gate.py --json     # machine-readable, for the run scripts
> ```
>
> Before the freeze it exits **3** and prints the exact command that fixes each unmet condition. That is the
> expected and correct behaviour, not a fault. How to actually do the freeze is
> [section 9](#9-how-to-do-the-freeze).

---

## 3. Prerequisites

### 3.1 Software

| What | Version | Which machine | Check it with |
|---|---|---|---|
| Docker Engine and Docker Compose v2 | Compose v2 (`docker compose`, not `docker-compose`) | Service host; and the load generator needs the **CLI** so it can drive the service host's daemon over SSH ([section 5](#5-the-two-machine-setup)) | `docker version`, `docker compose version` |
| Python | **3.11 or newer** | Any machine running a script or a test | `python3 -V` |
| Java (JDK) | **17 or 21** | **Load generator only** | `java -version` |
| Apache JMeter | **5.6 or newer** | **Load generator only** | `jmeter --version` |
| `curl`, `git` | any recent | Both | `command -v curl git` |

Three of those deserve emphasis.

* **Java and JMeter belong on the LOAD GENERATOR machine, and only there.** Nothing in the service host's
  image or its dependency list needs Java, and installing JMeter on the service host invites somebody to run
  it there — which would invalidate every latency number ([section 5](#5-the-two-machine-setup)).
* **JMeter 5.6+ is not negotiable.** The Open Model Thread Group, which is how every plan generates open-loop
  traffic, only exists from 5.5 onwards. The plans will not open on 5.4.
* **Java 17 or 21, not something newer.** JMeter 5.6.3 bundles Groovy 3.0.20, whose compiler cannot read
  class files from much newer JDKs. On a too-new JDK the plans' Groovy pre-processors fail **silently**: no
  error in `jmeter.log`, JMeter still exits 0, and samples simply go missing. This was reproduced on JDK 26,
  where `mixed_load.jmx` produced every POST sample and not one GET sample with a clean log. See
  [`jmeter/README.md`](jmeter/README.md) section 7.

**Unverified on this machine.** Every `jmeter` and `java -version` command in this README is transcribed from
[`jmeter/README.md`](jmeter/README.md), the three `.jmx` plans and `scripts/run_load_test.sh`, because no
JMeter installation existed on the machine this file was written on. The first person to set up the load
generator should run them, confirm the version strings, and correct this README if anything differs.

The repository ships a virtual environment for host tooling. Use it explicitly rather than relying on
whatever `python` resolves to:

```bash
.venv/bin/python          # pandas, matplotlib, PyYAML, httpx, fastapi and the rest
.venv/bin/pytest
```

If `.venv` is absent on your machine, create it from the committed requirements:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt     # includes requirements.txt
```

The service container installs only `requirements.txt` (fastapi, uvicorn[standard], httpx, pydantic,
python-dotenv). Nothing in the image can run an analysis script, and nothing in the image can read the
dataset — see [`.dockerignore`](.dockerignore).

### 3.2 Hardware assumptions

The client's hardware is *"commodity CPU servers with no GPUs"*, so ours must be CPU-only too. There is no
`deploy.resources.reservations.devices` block, no `gpus:` key and no NVIDIA runtime anywhere in
[`docker-compose.yml`](docker-compose.yml), deliberately. **Do not add one** — a GPU measurement would not
describe the client's deployment and the brief does not permit it.

**Disk.** The four candidates' download sizes, as displayed on ollama.com (23 September 2026; 2 October 2026
for the 1B build) and cited in [`models/candidates.md`](models/candidates.md), are:

| Candidate | Quantisation | Approximate download |
|---|---|---|
| `llama3.2:1b-instruct-q4_K_M` | Q4_K_M | 808 MB |
| `llama3.2:3b` | Q4_K_M | 2.0 GB |
| `granite4:3b` | Q4_K_M | 2.1 GB |
| `qwen2.5:7b` | Q4_K_M | 4.7 GB |

That is roughly **10 GB** for the full set, held in the `ollama_models` named Docker volume, plus the image
layers and the SQLite volume. `scripts/reset.sh` never touches the model volume, precisely so a reset does
not force a multi-gigabyte re-pull. Those sizes are Ollama's rounded web display values and are **unverified
until `scripts/pull_and_pin_models.sh` has run** and written real byte counts into `models/models.yaml`.

**RAM.** The Ollama host must have enough free memory to hold the **largest candidate you intend to serve**
resident, together with its 4096-token context, without swapping. `qwen2.5:7b` is the largest of the four at
the 4.7 GB download above. If the machine swaps, latency becomes disk latency, which shows up as a step
change in `eval_duration` rather than as an error — and the limit your stress test then finds is a memory
limit wearing a throughput limit's clothes. Record `Total RAM` and `Total swap` from the machine's capture
file and read the swap row of [`docs/test-environment.md`](docs/test-environment.md) section 5 before you
report anything.

**Cores.** More physical cores and more memory channels raise the number of concurrent model evaluations the
host sustains, so they raise throughput; they do **not** shorten a single request by much, because one
ticket's classification is one memory-bandwidth-bound model evaluation. Which of our requirements depends on
which is the substance of the scaling argument in `docs/test-environment.md` section 6.

**No figure in this section is a measurement of our hardware.** The machines' real specifications are
captured by `scripts/capture_env.sh` into `docs/environment/` and written up on Slide 7.

---

## 4. Setup, step by step

Every command is run **from the repository root**.

**1. Clone the repository.**

```bash
git clone https://github.com/Fokku/ICT3113-PTO ICT3113-PTO
cd ICT3113-PTO
```

If you will run `scripts/run_load_test.sh` across two machines, clone it to the **same absolute path** on
both — see the bind-mount trap in [section 5.3](#53-the-cross-machine-plumbing).

**2. Place the course CSV in the repository root.**

Download `ict3113_tickets.csv` from xSiTe (50,000 rows; columns `row,source_label,narrative`) and put it at
the repository root. **It is gitignored and must never be committed** — it is large, and it is distributed
through xSiTe. Only our own 1,000-row slice is committed.

```bash
ls -l ict3113_tickets.csv
git check-ignore -v ict3113_tickets.csv     # confirms .gitignore covers it
```

**3. Create the environment file.**

```bash
cp .env.example .env
```

`.env` is gitignored; `.env.example` is committed and is the documented record of every knob the service has.
Every value in the example **is** the default, so an unedited copy changes nothing — that is deliberate, so a
diff against the example shows exactly what a run was configured with. What you may need to change:

| Variable | Change it when |
|---|---|
| `OLLAMA_BASE_URL` | Ollama is **not** in the same compose project. Use `http://<ollama-host>:11434` for another machine, or `http://localhost:11434` when running the service outside Docker. Inside compose, leave it as `http://ollama:11434`. |
| `MODEL_TAG` | You are serving a different candidate. One model per service run. `scripts/run_load_test.sh --model <tag>` sets it for you per run. |
| `MODEL_DIGEST` | You want to pin the digest explicitly. Left empty, the service asks Ollama's `/api/tags` at start-up which digest it is serving and logs what it found. An explicit value is never overwritten, so a mismatch shows up instead of being papered over. |
| `SERVICE_PORT` | Port 8000 is already in use on the service host. |

Leave `NUM_CTX=4096`, `OLLAMA_SEED=42`, `UVICORN_WORKERS=1` and `SERVICE_THREADPOOL_SIZE=40` alone unless the
team has recorded a decision to change them: each is deliberate and each is on Slide 7. The rationale for
every variable is a comment in `.env.example`.

**4. Extract the team rows (already done, and committed — verify rather than re-run).**

[`data/team_rows.csv`](data/team_rows.csv) is committed: 1,000 rows, columns `row_number,narrative,raw_label`.
To reproduce it from the course CSV, for **team 10**:

```bash
.venv/bin/python scripts/extract_team_rows.py --csv ict3113_tickets.csv --team 10
# writes data/team_rows.csv (rows 10000-10999)
```

```bash
wc -l data/team_rows.csv          # 1001 lines: a header plus 1,000 rows
```

No other rows may be labelled or sent as test traffic.

**5. Bring the stack up.**

```bash
# Everything on this machine: the service and Ollama, both in containers.
docker compose --profile local-ollama up -d --build

# Or: service here, Ollama on another machine.
OLLAMA_BASE_URL=http://<ollama-host>:11434 docker compose up -d --build triage
```

The `ollama` service sits behind the `local-ollama` profile, so it is simply not created unless that profile
is requested. There is deliberately no `depends_on`: the triage service must start, serve `/search` and
`/stats`, and report `"status": "degraded"` from `/health` when the backend is absent.

```bash
docker compose ps
docker compose logs triage | tail -20     # the start-up configuration line is here
```

If the container cannot append to the bind-mounted log directory, rebuild with your own UID and GID — the
`./logs/service` directory is owned by the host user and the container user has to match it:

```bash
docker compose build --build-arg APP_UID=$(id -u) --build-arg APP_GID=$(id -g) triage
docker compose up -d --force-recreate triage
```

**6. Pull and pin the models.**

Run this **on the machine whose Ollama will actually serve the benchmarks**. Check the plan first; the dry run
contacts nothing at all:

```bash
scripts/pull_and_pin_models.sh --dry-run

# Dockerised Ollama in our compose project (the usual case):
scripts/pull_and_pin_models.sh --ollama-url http://ollama:11434

# An Ollama on another host, reached over its published port:
scripts/pull_and_pin_models.sh --transport api --ollama-url http://<ollama-host>:11434

# One candidate only:
scripts/pull_and_pin_models.sh --model llama3.2:1b-instruct-q4_K_M
```

The script pulls each candidate listed in `models/models.yaml` and writes the **exact digest**, byte size,
pull timestamp and Ollama version back into that file. Commit `models/models.yaml`: those digests are what
Slide 5 reports and they are the only thing tying a latency or accuracy number to a specific set of weights.
If a later re-pull reports a digest that differs from an existing pin the script **exits 4 and refuses to
overwrite it**, because a changed digest means every result gathered under the old digest is no longer
comparable. Read its message before doing anything else; `--allow-repin` means re-running the affected
benchmarks.

**7. Check `/health`.**

```bash
curl -s http://127.0.0.1:8000/health | .venv/bin/python -m json.tool
```

Read and confirm: `status` is `ok`; `ollama_reachable` is `true`; `model_tag` is the tag you mean;
`model_digest` matches the pin in `models/models.yaml`; `ollama_base_url` is the backend you mean; `num_ctx`
is `4096`; `uvicorn_workers` is `1`; `threadpool_size` is `40`; `prompt_hash` is the value you will also see
in every log line and every `metadata.json`. `/health` is deliberately **not** written to the JSONL request
log, so polling it costs the evidence nothing.

**8. Smoke test against a synthetic ticket.**

This is the **one** model exercise permitted before the freeze, and its input is fixed to
`data/dev/synthetic_tickets.csv`. The script refuses (exit 2) to read `data/team_rows.csv` or anything under
`golden/`.

```bash
scripts/smoke_test.sh --count 3
# --host HOST, --port PORT, --count N (max 28) are the only options
```

Per posted ticket it asserts HTTP 200; that the returned category is one of the seven or `UNPARSEABLE`; that
the returned `request_id` is exactly the `X-Request-ID` that was sent; and that a log line with that
`request_id` exists and carries all 24 fields of `service/log_schema.py` with the values that line must have.
**It measures no latency and assesses no accuracy**, by design — see hard rule 3.

To do the same thing by hand, with a synthetic narrative (row 900015 of the dev file):

```bash
curl -sS -X POST http://127.0.0.1:8000/tickets \
  -H 'Content-Type: application/json' \
  -H "X-Request-ID: $(uuidgen)" \
  -H 'X-Source-Row: 900015' \
  --max-time 180 \
  -d '{"narrative": "After I was a victim of identity theft I placed an extended fraud alert on my file and supplied the police report. One of the agencies continued to release my file to new credit applicants without contacting me, and two more fraudulent accounts were opened before I noticed."}'
```

A good response is HTTP 200 with exactly this shape:

```json
{
  "id": 1,
  "category": "<one of the seven category names, or UNPARSEABLE>",
  "request_id": "<the X-Request-ID you sent, echoed back>"
}
```

`id` is the SQLite row id, so it is `1` on a freshly reset database and counts up from there. **There is no
latency field, and there is no latency figure in this document anywhere**: the first request also pays the
one-off model-load cost, so any time you observe here describes a cold model rather than the service, and
quoting it would be a fabricated measurement. Timings come only from `logs/service/*.jsonl` and from a `.jtl`,
after the freeze.

On a model failure the response is **HTTP 502 and nothing is stored**:

```json
{
  "detail": "model backend did not classify the ticket",
  "error": "<ollama_timeout | ollama_connect_error | ollama_http_error | ollama_bad_response>",
  "request_id": "<the X-Request-ID you sent>"
}
```

Storing a failed classification as `UNPARSEABLE` would be indistinguishable in `/stats` from a model that
answered with nonsense, and would corrupt the accuracy denominator — hence 502 and no row.

**9. Run the test suite.**

```bash
.venv/bin/pytest
```

No model is contacted: the model call is stubbed throughout. This exercises the log schema, the normaliser,
the endpoints, the freeze gate, the labelling scripts and every analysis script against synthetic fixtures.

---

## 5. The two-machine setup

### 5.1 The rule, and why it is not negotiable

**Machine 1 runs the triage service and Ollama. Machine 2 runs JMeter. Never the same machine.**

The brief states it and states the reason: *"The load generator and the system under test must run on separate
machines. A co-hosted load generator steals CPU from the service and produces latency numbers that are
fiction."* On a CPU-only inference host this is not a technicality. JMeter has to construct, send and time
every request, and every core it takes is a core the model is not using — so the latency you record is partly
your own load generator's delay, the effect grows precisely at the high arrival rates where the interesting
results live, and **it does not announce itself**. A run that looks clean can be entirely wrong.

`scripts/run_load_test.sh` prints a warning when `--host` is `127.0.0.1`, `localhost`, `::1` or `0.0.0.0`, so
a co-hosted run cannot be produced by accident and then reported. A run whose `metadata.json` has a loopback
`service_url` is **not evidence** for any latency or throughput claim.

One exception, stated so nobody misapplies the rule: the **accuracy** driver
(`scripts/run_accuracy.py`) measures no latency, so running it on the service host invalidates nothing. The
separate-machine rule exists to protect latency measurements. Run it wherever is convenient; it needs HTTP
access to the service and read access to the service's log directory.

### 5.2 Making machine 1 reachable, and pointing JMeter at it

The service already binds on all interfaces (`SERVICE_HOST=0.0.0.0`) and compose publishes
`${SERVICE_PORT}:${SERVICE_PORT}`, so no change is needed inside the container. What usually blocks machine 2
is the host firewall.

```bash
# On machine 1: confirm the port is actually published and listening.
docker compose ps
ss -tlnp | grep 8000            # Linux; on macOS: lsof -nP -iTCP:8000 -sTCP:LISTEN
```

Open the ports. Which ports depends on your topology:

| Port | Needed when |
|---|---|
| **8000/tcp** on machine 1 | always — JMeter and `curl` on machine 2 reach the service through it |
| **11434/tcp** on the Ollama host | only when Ollama is on a **different** machine from the service |
| **22/tcp** on machine 1 | when the load generator drives machine 1's Docker daemon over SSH ([section 5.3](#53-the-cross-machine-plumbing)) |

```bash
# Linux, ufw (Debian/Ubuntu). Restrict to the load generator's address, not the world.
sudo ufw allow from <loadgen-ip> to any port 8000 proto tcp
sudo ufw status verbose

# Linux, firewalld (Fedora/RHEL).
sudo firewall-cmd --permanent --add-rich-rule='rule family=ipv4 source address=<loadgen-ip>/32 port port=8000 protocol=tcp accept'
sudo firewall-cmd --reload
sudo firewall-cmd --list-all
```

On **macOS** the built-in application firewall is per-application, not per-port. Docker Desktop publishes the
port through its own helper process, so the prompt you must allow is for Docker, not for a port number:
System Settings → Network → Firewall → Options, and allow incoming connections for **Docker**. If Docker
Desktop is in use, also note that it runs the containers inside a Linux VM with its own CPU and memory
allocation — quote that allocation on Slide 7, because it is the hardware the service actually got
(`docs/test-environment.md` section 5 has a row for it).

**Point JMeter at machine 1** with `--host`, which the run script turns into `-Jhost`:

```bash
scripts/run_load_test.sh --plan load_post_tickets --model <tag> \
    --rate <per-min> --duration <seconds> --runs 3 \
    --host <machine-1-ip> --port 8000 --yes
```

**Prefer an IP address over a hostname**, or add machine 1 to `/etc/hosts` on machine 2. A DNS lookup inside
a measured sample is load-generator latency wearing the service's clothes, and the JVM resolver cache is a
`java.security` setting that cannot be fixed from `jmeter/user.properties`. Record which you did in
`docs/environment/`.

The plans' default `host` is the deliberately invalid string `SET-JHOST-TO-THE-SERVICE-HOST`, so a plan run
without `-Jhost` fails immediately with `UnknownHostException` rather than quietly measuring a co-hosted run.

### 5.3 The cross-machine plumbing

`scripts/run_load_test.sh` runs JMeter locally, but it also resets the database, recreates the triage
container with the right `MODEL_TAG`, and reads the service's own log. From machine 2 it therefore needs to run
commands on machine 1 **and** read machine 1's `logs/service`. We use **remote mode**, which needs nothing on
machine 2 except key-based SSH and `rsync`:

```bash
# On machine 2, before the run.
export SERVICE_SSH=<user>@<machine-1>      # key-based SSH (ours: OpenSSH over machine 1's Tailscale address)
export SERVICE_REPO=ICT3113-PTO            # machine 1's checkout, relative to its home directory
```

With `SERVICE_SSH` set, both drivers behave as follows:

* `docker compose` and `scripts/reset.sh` run **inside machine 1's own checkout** over SSH, so the bind mount
  `./logs/service` and the build context resolve on machine 1. (The older `DOCKER_HOST=ssh://…` approach
  resolves the bind mount against machine 2's path, which is why it is not used.)
* machine 1's `logs/service/` is mirrored into machine 2's `logs/service/` with `rsync` before every read
  (the warm-up line, and the measured window after JMeter finishes). Nothing is deleted on either side.
* `run_load_test.sh` refuses a real run if machine 1's checkout is not at the **same commit** as machine 2's,
  because `metadata.json` records machine 2's commit and the service must be running that code.

`scripts/run_campaign.sh` (section 6.0) uses the same two variables, plus `TARGET_HOST`, the address JMeter
sends to.

**If machine 2 is a Mac, keep the SSH session open for the whole run.** macOS 15's Local Network privacy blocks
a process that has left its login session from connecting to LAN addresses unless its app has "Local Network"
access, so a campaign started with `nohup … &` over an SSH session that then closes records every JMeter sample
as `NoRouteToHostException` (curl and Python are unaffected, which makes it confusing). Grant Java access in
System Settings → Privacy & Security → Local Network, or start the campaign from another machine with an SSH
session that stays open, as we did — see `docs/run-log.md`, 8 October, and `docs/playbooks/load-test.md` 2.3.
On a Linux machine 1 running `ufw`, note that Docker-published ports (8000, 11434) bypass `ufw` while SSH does
not, which is why our SSH went over the tailnet and the measured traffic over the LAN.

### 5.4 Verify reachability from machine 2 before a run

Do all four of these from machine 2, before spending an hour on runs.

```bash
# 1. The service answers, and reports the model and backend you expect.
curl -s http://<machine-1>:8000/health | .venv/bin/python -m json.tool

# 2. The SSH plumbing works: this must list machine 1's containers, from machine 1's checkout.
ssh "$SERVICE_SSH" 'cd ICT3113-PTO && docker compose ps && git rev-parse HEAD'
git rev-parse HEAD                        # must print the same commit

# 3. The service log can be mirrored here.
rsync -a "$SERVICE_SSH:ICT3113-PTO/logs/service/" logs/service/ && ls -l logs/service/

# 4. The network cost, measured rather than assumed. Record the output for Slide 7.
ping -c 20 <machine-1>
curl -s -o /dev/null -w 'connect=%{time_connect}s  total=%{time_total}s\n' \
    http://<machine-1>:8000/health
```

Also confirm, on machine 2, that JMeter and the JDK are what the plans need:

```bash
jmeter --version      # 5.6 or newer
java -version         # 17 or 21
```

And confirm both machines' clocks agree — `date -u` on each, with NTP running.
`analysis/reconcile.py` fails a run whose client-minus-server latency p99 exceeds 250 ms, so gross skew voids
a run.

### 5.5 How the two-machine fact is evidenced for Slide 7

The brief requires *"Confirmation that the load generator ran on a separate machine"*. Assert it as a
sentence in `docs/test-environment.md` section 4, then point at four pieces of evidence that are already in
the repository:

| Evidence | Where | What it must show |
|---|---|---|
| Two distinct capture files | `docs/environment/<hostname>.txt` | Two files, two different hostnames, one declaring `Declared role: loadgen` and one `Declared role: service`. Neither may declare `Declared role: all` |
| The address JMeter posted to | `results/runs/<run>/metadata.json`, key `service_url` | An address on machine 1. **Not** `127.0.0.1`, `localhost` or `0.0.0.0` |
| The machine JMeter ran on | same file, key `load_generator_host_info.hostname` | Machine 2's hostname, **different** from machine 1's |
| The backend the service used | same file, key `service_host_info.ollama_base_url` (also `GET /health`) | The Ollama host we claim, not a stale default |

Produce the capture files with one command per machine, **on** that machine, then commit them:

```bash
scripts/capture_env.sh --role service    # on machine 1 (the triage container)
scripts/capture_env.sh --role ollama     # on the Ollama host
scripts/capture_env.sh --role loadgen    # on machine 2 (JMeter)
```

Each writes `docs/environment/<hostname>.txt`. The script contacts nothing except a three-second probe of
`${OLLAMA_BASE_URL}/api/version`, runs no model and times nothing. `--role all` also exists but *declares
that one machine runs everything*, and the script writes a warning into the file saying so; do not use it to
mean "I could not decide". Check every run you intend to cite, not just one:

```bash
grep -h '"service_url"' results/runs/*/metadata.json | sort -u
```

---

## 6. Running the tests

Read the playbook for the test you are running before you run it. Each is written to the brief's standard —
*"sufficient detail that a competent software tester could carry it out without seeking or inventing further
information from your team"* — and each carries its own preconditions, abort criteria and failure table:

* [`docs/playbooks/load-test.md`](docs/playbooks/load-test.md) — the steady-state and mixed tests
* [`docs/playbooks/stress-test.md`](docs/playbooks/stress-test.md) — the stepped ramp, and the authoritative
  copy of the step boundaries
* [`docs/playbooks/accuracy-test.md`](docs/playbooks/accuracy-test.md) — the golden-set run, per model

**Every arrival rate, duration, search rate and threshold in the commands below comes from Part 4** — the
"Derived arrival rates for testing" section of [`workload/workload_model.md`](workload/workload_model.md) and
requirements R1–R5 in [`workload/requirements.md`](workload/requirements.md). Part 1 did not invent them:

| Test | Rates (per minute) | Duration per run | Runs | Requirement it tests |
|---|---|---|---|---|
| `load_post_tickets` | 1, 4, 12 | 600 s of arrivals + 150 s drain | 3 per rate, per model | R1 (p95 ≤ 10 s at 1/min), R2 (≤ 5% errors, no backlog at 12/min) |
| `mixed_load` | 1 ticket + 1 search | 600 s of arrivals + 150 s drain | 3 per model | R5 (`GET /search` p95 ≤ 2 s) |
| `stress_ramp` | 1, 5, 9, 13, 17, 21 (120 s steps) + 150 s drain | 870 s | 1 per model | the limit: first step breaching R1's 10 s p95 or a 5% error rate |
| accuracy | every golden ticket, once, serially | — | 1 per model | R3 (≥ 90% overall), R4 (≥ 80% per category) |

### 6.0 The whole campaign in one command

[`scripts/run_campaign.sh`](scripts/run_campaign.sh) runs every row of that table for every candidate in
`models/models.yaml`, by calling the two drivers below with exactly those parameters. It switches the service
to each model and checks that `/health` reports the digest pinned in `models/models.yaml` first. It logs every
command, exit status and duration to `results/campaign/campaign_<stamp>.log`, and it can be re-run safely: a
configuration with complete evidence for the current freeze is skipped, and a partial one is moved to
`results/excluded/` (with the reason appended to `results/excluded/EXCLUDED.md`) and run again in full.

```bash
export SERVICE_SSH=<user>@<machine-1> TARGET_HOST=<machine-1> JMETER_HOME=$HOME/tools/apache-jmeter-5.6.3
STRESS_MODELS="llama3.2:1b-instruct-q4_K_M llama3.2:3b granite4:3b qwen2.5:7b" scripts/run_campaign.sh
# rehearsal on synthetic tickets, no freeze needed, writes only under results/dev/:
DURATION_S=45 RUNS=1 RATES=30 scripts/run_campaign.sh --dev --models llama3.2:1b-instruct-q4_K_M
```

The sections below are the same steps, one at a time.

**`--runs 3` is the default and the brief's requirement**: *"Three runs per configuration. Report means and
the spread across runs. A single run is not a measurement."*

**`--yes` skips a destructive confirmation.** Each run calls `scripts/reset.sh --yes`, which **destroys every
ticket stored in the service's database**. That is deliberate — `GET /search` is a full-table scan, so every
run must start empty — but read what you are agreeing to. Without `--yes` in a non-interactive shell the
script refuses (exit 2) rather than resetting unasked.

### 6.1 Load test — steady state, `POST /tickets`

```bash
export SERVICE_SSH=<user>@<machine-1>                # section 5.3
export RUN_NOTES="operator <name>; service host otherwise idle; JDK 21"

for rate in 1 4 12; do
  scripts/run_load_test.sh \
      --plan load_post_tickets \
      --model <ollama-tag> \
      --rate "$rate" \
      --duration 600 \
      --runs 3 \
      --host <machine-1> --port 8000 --yes
done
```

### 6.2 Mixed load — `POST /tickets` and `GET /search` concurrently

Two Open Model Thread Groups in one plan, sharing `duration_s` so they start and stop together. This is the
plan behind a requirement of the form "`GET /search` stays under X ms at the p95 while tickets arrive at Y per
minute" (R5).

```bash
scripts/run_load_test.sh \
    --plan mixed_load \
    --model <ollama-tag> \
    --rate 1 \
    --search-rate 1 \
    --duration 600 \
    --runs 3 \
    --host <machine-1> --port 8000 --yes
```

Interpret the two sampler labels (`POST /tickets`, `GET /search`) **separately** — the interference between
them is the whole point, and a figure that pools the two measures nothing. `GET /search` latency is expected
to rise within a single run, because the table grows as tickets arrive; record the final `GET /stats` total
with the result.

### 6.3 Stress test — the stepped ramp

Six rising steps and a drain pause. `--rate` is **step 1's rate**, not the whole ramp's, and `--duration`
does **not** control the ramp: the schedule's length comes from `ramp_step_duration_s` and `ramp_drain_s`, so
set `--duration` to the true total wall-clock (`6 × step + drain`) or `metadata.json` will misdescribe the
run.

```bash
export RAMP_STEP_PER_MIN=4             # workload_model.md: 1, 5, 9, 13, 17, 21 per minute
export RAMP_STEP_DURATION_S=120
export RAMP_STEPS=6                    # recorded in jmeter.log; the schedule is six literal steps

scripts/run_load_test.sh \
    --plan stress_ramp \
    --model <ollama-tag> \
    --rate 1 \
    --duration 870 \
    --runs 1 \
    --host <machine-1> --port 8000 --yes
```

**The ramp is run once per candidate model** (four ramps of 14 minutes, about an hour). That is the team's
decision, recorded in [`docs/playbooks/stress-test.md`](docs/playbooks/stress-test.md) section 4: the ramp's
purpose is to locate each model's limit, and the brief's three-run rule applies to the load configurations
above. If time allows, the ramp is repeated for the recommended model.

Only an **arithmetic** staircase is reachable through the harness: `ramp_rate_1`…`ramp_rate_6` and
`ramp_drain_s` are not passed by the script. Confirm the resolved rates before trusting the run — this is the
cheapest check in the whole procedure:

```bash
grep -i "schedule" results/runs/<run-dir>/jmeter.log
```

The step boundaries live in **three** places that must agree: `docs/playbooks/stress-test.md` section 2 (the
authoritative copy), `jmeter/README.md` section 3, and the `TestPlan.comments` of `jmeter/stress_ramp.jmx`.
`analysis/stress_summary.py` has to be *told* the boundaries; nothing enforces the coupling in code.

### 6.4 Accuracy test — every golden ticket, per model

One run per candidate. Switch the service to that model first, then confirm it:

```bash
# Switch machine 1 to the model (from machine 2, in machine 1's checkout):
ssh "$SERVICE_SSH" 'cd ICT3113-PTO && docker compose up -d ollama && MODEL_TAG=<ollama-tag> docker compose up -d --force-recreate --no-deps triage'

# Confirm it, from the driver machine:
curl -s http://<machine-1>:8000/health | .venv/bin/python -m json.tool

export SERVICE_SSH=<user>@<machine-1>        # the driver mirrors machine 1's log before slicing it
export RUN_NOTES="operator <name>; candidate <tag>"

.venv/bin/python scripts/run_accuracy.py \
    --model <ollama-tag> \
    --host <machine-1> --port 8000 \
    --golden golden/golden_set.csv
```

The driver refuses to start if `/health` reports a different `model_tag` — that check is what prevents a
mislabelled accuracy run. It **never reads the golden labels**: it reads the golden set's row numbers only,
looks each narrative up in `data/team_rows.csv`, and posts it. That makes it structurally impossible for this
step to be nudged towards a better score. It computes **no** accuracy; scoring is
[section 7](#7-analysis-and-reconciliation).

There is no warm-up here, on purpose, because nothing is timed: `metadata.json` records
`"warmup_request_id": null`. So the first golden ticket of each run carries the model-load cost in the
service log. That changes no category, and it is another reason never to quote a latency from an accuracy
run.

### 6.5 Rehearsing before the freeze

Every one of the above becomes safe pre-freeze by adding `--dev`:

```bash
scripts/run_load_test.sh --plan load_post_tickets --model <tag> \
    --rate 60 --duration 60 --runs 1 --host <machine-1> --dev --yes

.venv/bin/python scripts/run_accuracy.py --model <tag> --host <machine-1> --dev
```

Dev mode forces the input to `data/dev/synthetic_tickets.csv`, writes only under `results/dev/`, stamps
`"mode": "dev"` and `"freeze_commit": null`, prints the dev banner, and exits 2 if any argument names real
team data. Rehearse the cross-machine plumbing here, not on a real run.

### 6.6 Where the outputs land

The layout is a contract. `analysis/common.py` parses these directory names for the model, plan, rate and run
index, so **do not rename a run directory**.

```
results/runs/<UTCSTAMP>_<model>_<plan>_<rate>_run<k>/
    metadata.json      the run describing itself (keys listed below)
    freeze.json        the verbatim output of scripts/freeze_gate.py --json at run time
    results.jtl        raw JMeter samples, CSV, with the request_id and source_row columns
    jmeter.log         JMeter's own log, including the resolved schedule line
    jmeter_stdout.txt  the running summariser output
    service.jsonl      the service's own log lines for the measured window
    warmup.jsonl       the warm-up request's log line, kept OUT of service.jsonl

results/accuracy/<model>_<UTCSTAMP>/
    metadata.json
    freeze.json
    responses.csv      row_number,request_id,http_status,predicted_category,error
    service.jsonl
    warmup.jsonl       only if warm-up-flagged lines happened to fall in the window

results/dev/...        the same shapes. GITIGNORED. Never evidence
```

* `<UTCSTAMP>` is `YYYYmmddTHHMMSSZ`.
* `<model>` is the Ollama tag sanitised: `:`, `/` and spaces become `-`.
* `<plan>` is the `.jmx` basename without its extension.
* `<rate>` is `<rate_per_min>pm` — for example `60pm` — or the literal `ramp` for the stress plan, whose rate
  changes during the run and so cannot be labelled with one number.

`metadata.json` holds exactly these keys: `run_id`, `mode`, `plan`, `plan_file`, `model_tag`, `model_digest`,
`rate_per_min`, `duration_s`, `run_index`, `runs_total`, `started_at_utc`, `ended_at_utc`, `git_commit`,
`git_dirty`, `freeze_commit`, `freeze_tag`, `prompt_hash`, `num_ctx`, `seed`, `input_csv`, `service_url`,
`service_host_info`, `load_generator_host_info`, `jmeter_version`, `ollama_num_parallel`,
`ollama_max_loaded_models`, `warmup_request_id`, `notes`.

**Commit every run directory.** The brief: *"Keep the raw JMeter result files (.jtl) from every run in your
repository; they must reconcile with your service logs."*

### 6.7 Running a plan by hand

For a diagnostic only. It produces no `metadata.json` and no `freeze.json`, so it is not evidence.

```bash
$JMETER_HOME/bin/jmeter -n -t jmeter/load_post_tickets.jmx \
    -l /tmp/check.jtl -j /tmp/check.log \
    -q jmeter/user.properties \
    -Jhost=<machine-1> -Jport=8000 -Jrate_per_min=60 -Jduration_s=30 \
    -Jinput_csv="$PWD/data/dev/synthetic_tickets.csv"
```

`-q jmeter/user.properties` is **not** optional by hand: it carries `sample_variables=request_id,source_row`
and the `jmeter.save.saveservice.*` settings, and without it the `.jtl` has no `request_id` or `source_row`
columns and cannot be reconciled with the service log. Write scratch results to `/tmp`, never into the
repository.

**Resolved 8 October 2026.** `scripts/run_load_test.sh` originally did not pass `-q jmeter/user.properties`
and relied on whatever JMeter properties the load generator had installed. It now passes it on every run, so
the `.jtl` column set and `httpclient4.retrycount=0` are fixed by the repository, not by the machine. The
script still checks the `.jtl` header after each run and fails a run whose reconciliation columns are
missing.

---

## 7. Analysis and reconciliation

Run these in this order after a set of runs, from the repository root. All of them are deterministic given
the same inputs, they run no model, and they invent nothing: every figure is derived from a `.jtl` written by
JMeter or a line written by the service. Each exits **non-zero** when its own sanity check fails; silence is
not an option.

`analysis/output/` **is committed**, because the slides cite it.

### Step 1 — reconcile. This is not optional.

```bash
.venv/bin/python analysis/reconcile.py --run-dir results/runs/<run-dir>
```

Once per run directory, before a single number from that run is quoted anywhere. It inner-joins the run's
`.jtl` to `service.jsonl` on `request_id` and refuses the run if the two do not agree: unmatched samples above
`--max-unmatched` (default 0), any duplicate `request_id`, any HTTP status or `source_row` disagreement, or a
client-minus-server latency p99 above `--latency-threshold-ms` (default 250).

**A number that does not reconcile cannot be reported.** The brief: *"a number that cannot be traced to a log
entry is treated as unsupported, and you may be asked to produce and explain your logs"*, and *"Fabricated or
irreconcilable measurement numbers are treated as an academic integrity matter, not a marking deduction."* A
non-zero exit means the run is not evidence. Fix the cause — clock skew, the wrong `SERVICE_LOG_DIR`, a log
slice that is too narrow — and re-run the whole configuration. **Do not raise `--max-unmatched` or
`--latency-threshold-ms` to make a run pass.**

Writes into `analysis/output/reconcile/`, per run: `<run_id>__report.md` (read this),
`<run_id>__checks.csv/.md`, `<run_id>__unmatched.*`, `<run_id>__mismatches.*`, `<run_id>__latency_diff.*`.
**Feeds:** the instrumentation claim on Slide 9, and the brief's "every number reconciles" requirement.

### Step 2 — summarise the load runs.

```bash
.venv/bin/python analysis/summarise_load.py --runs results/runs --plan load_post_tickets
.venv/bin/python analysis/summarise_load.py --runs results/runs --plan mixed_load
# narrow to one candidate at a time with --model <ollama-tag>
```

Writes into `analysis/output/load/`:

| Output | What it is for |
|---|---|
| `load_per_run.csv/.md` | one row per run: p50/p95/p99, achieved throughput, error rate, sample count |
| `load_per_run_by_label.csv/.md` | one row per (run, sampler label) — how a `mixed_load` run **must** be read, because POST and GET latencies must not be pooled |
| `load_per_config.csv/.md` | one row per (model, plan, rate, metric): the mean and the spread across the three repeat runs |
| `load_summary.md` | all of the above plus the metric definitions and any warnings, in one file a marker can read end to end |
| `latency_vs_rate_<model>.png` | one latency-versus-arrival-rate chart per candidate |

**Feeds:** Slide 9. The headline latency is JMeter's `elapsed` column — the client-observed round trip, which
is what a response-time requirement is about — reported alongside the service's own `total_latency_ms`.

### Step 3 — summarise the stress ramp.

```bash
.venv/bin/python analysis/stress_summary.py \
    --run-dir results/runs/<stress-run-dir> \
    --step-seconds 120 \
    --offered-rates 1,5,9,13,17,21 \
    --p95-limit-ms 10000 \
    --error-rate-limit 0.05 \
    --out-dir analysis/output/stress/<stress-run-dir>
```

Writes into `analysis/output/stress/`: `stress_steps.csv/.md` (per-step arrival rate, latency percentiles and
error rate), `stress_signals.csv/.md`, `stress_ramp.png`, `stress_report.md`. It names the **first step at
which the system breached a limit**, and reports an unbounded-growth signal separately (whether the p95 rises
monotonically across the last `--monotonic-steps`, default 3). Report whichever criterion actually fired, and
say which one it was. Read the warnings the report prints — a step reported as empty, or dropped as partial,
means the boundaries do not match the schedule. **Feeds:** Slide 9.

The output filenames are fixed, so **a second stress run overwrites the first** unless each has its own
`--out-dir`, as above. We run one ramp per candidate, so always pass it.

### Step 4 — diagnose where the time went.

```bash
.venv/bin/python analysis/bottleneck_hints.py --run-dir results/runs/<run-dir>
```

Once per configuration. Reads only `service.jsonl` and `metadata.json` — the question here is not what the
caller experienced but which stage inside one request consumed the time. Writes into
`analysis/output/bottleneck/`: `bottleneck_breakdown.csv/.md` (service overhead, queue/transport residual,
model load, prompt evaluation, generation), `bottleneck_tokens.csv/.md`, `bottleneck_per_request.csv`,
`ctx_truncation_suspects.csv`, `bottleneck_stacked.png`, `bottleneck_report.md`.

**The queue term is a residual, not a measured quantity.** Read the module docstring before quoting it on a
slide. **Feeds:** the diagnosed-bottleneck sentence on Slide 9, and the prediction post-mortem on Slide 11.

These filenames are fixed too, so a second run overwrites the first: pass
`--out-dir analysis/output/bottleneck/<run-dir-name>` when you need to keep more than one breakdown.

### Step 5 — score accuracy, once all candidates have been run.

```bash
.venv/bin/python analysis/accuracy.py --results results/accuracy --golden golden/golden_set.csv
```

Scores every accuracy run directory it finds, taking the predictions from `service.jsonl` (the evidence of
record) rather than from the convenience copy in `responses.csv`, and joining to the golden set on row number.

It writes **one subdirectory per accuracy run**, `analysis/output/accuracy/<model>_<UTCSTAMP>/`, each holding
`overall.csv/.md`, `per_category.csv/.md` (recall and precision), `confusion_matrix.csv/.md` and
`confusion_matrix.png` (axes in the canonical category order), `misclassified.csv` (every row the model got
wrong, with the first 200 characters of its narrative), `report.md`, plus `missing_rows.csv`,
`duplicates.csv`, `unmatched_responses.csv` and `errored_responses.csv` so nothing is smoothed over. At the
top level of `analysis/output/accuracy/` it writes `model_comparison.csv/.md` and `accuracy_report.md`, which
are the across-candidate view Slide 10 is built from.

Exit **1** means a sanity check failed — most often **incomplete coverage of the golden set**, which is
correct behaviour: an accuracy figure over part of the golden set is not the figure the requirement was
written against. The tables are written *before* the failure, so you can see what is missing. **Feeds:**
Slide 10, and `misclassified.csv` is the file the "where each model goes wrong" commentary is written from.

### Step 6 — commit.

The run directories under `results/`, and the regenerated `analysis/output/`. Both are cited by the slides.

---

## 8. Where to start, per part

Each block is the first three things to do. The full task list with deadlines is in [`TODO.md`](TODO.md); the
slide requirements are in [`slides/outline.md`](slides/outline.md).

### Part 1 — Yeo Kai Yuan (technical core; Slides 1, 2, 5, 9)

**Folder:** `service/`, `scripts/`, `jmeter/`, `analysis/`, `models/`.
**Documents:** [`models/candidates.md`](models/candidates.md), [`models/models.yaml`](models/models.yaml),
[`jmeter/README.md`](jmeter/README.md), this README.
**Scripts:** all of `scripts/` and `analysis/`.
**Slides:** 1 (cover), 2 (architecture), 5 (candidate models), 9 (load and stress results). Assembles the deck.

1. ~~Confirm the four-candidate shortlist and settle the Q8_0 quantisation question.~~ Done on 2 October
   2026 and recorded in `models/candidates.md`: the floor candidate is `llama3.2:1b-instruct-q4_K_M`, so all
   four candidates share Q4_K_M. Next, run `scripts/pull_and_pin_models.sh` on the service host and commit
   the digests.
2. Decide which two machines we use, stand the stack up on machine 1, confirm `/health`, and run
   `scripts/smoke_test.sh --count 5`. Rehearse the cross-machine plumbing of
   [section 5.3](#53-the-cross-machine-plumbing) with `--dev` before the freeze, not after.
3. ~~Replace every `Teammate A/B/C/D` placeholder with the real names.~~ Done. Still to do: collect the five
   student IDs and hand the list to Part 5 for Slide 1.

### Part 2 — Loh Wen Xuan (golden set lead, labeller 1; Slide 6)

**Folder:** [`labelling/`](labelling/), and `golden/` once the set is built.
**Documents:** [`labelling/README.md`](labelling/README.md) (read this first — it is two pages),
[`labelling/protocol.md`](labelling/protocol.md), [`labelling/resolutions.md`](labelling/resolutions.md).
**Scripts:** `labelling/scripts/sample_golden_candidates.py`, `agreement.py`, `build_golden_set.py`.
**Slide:** 6 (golden test set), with Jolie Ngai Ning Li.

**Part 2 sets the pace of the whole assignment**: the freeze gate cannot pass until the golden set is
finished, and nothing may be measured until the gate passes. No code is needed for any of it.

1. Read `labelling/README.md`, then fill in `labelling/protocol.md` **before labelling anything** — a
   definition of each of the seven categories in your own words, the boundary each draws against its nearest
   neighbour, and the edge-case rules (fits two categories, fits none, too vague to judge). Agree it with
   Jolie Ngai Ning Li and note the date.
2. Draw the sample and commit the **blank** sheets, so the history shows the sample predates the labelling:
   `.venv/bin/python labelling/scripts/sample_golden_candidates.py --n 200 --seed 3113`. The seed is the
   course code and is fixed so the sample is provably not cherry-picked.
3. Label every sampled ticket into `labelling/labeller_A.csv` without conferring, using the seven category
   names spelled exactly as in `service/categories.py`. Do **not** open
   `labelling/golden_candidates.csv` or `data/team_rows.csv` while labelling: both carry the noisy consumer
   `raw_label`, which is the noise the golden set exists to remove.

### Part 3 — Jolie Ngai Ning Li (labeller 2 and accuracy results; Slide 6 with A, Slide 10)


**Folder:** [`labelling/`](labelling/), then `analysis/output/accuracy/`.
**Documents:** `labelling/README.md`, `labelling/protocol.md`,
[`docs/playbooks/accuracy-test.md`](docs/playbooks/accuracy-test.md).
**Scripts:** `labelling/scripts/agreement.py`, `analysis/accuracy.py`.
**Slides:** 6 (with A), 10 (accuracy results).

1. Read `labelling/protocol.md` and agree it with Loh Wen Xuan **before** starting, then label every sampled
   ticket into `labelling/labeller_B.csv` without conferring and without looking at their sheet. The
   independence is the point: it is what makes the agreement statistic mean anything.
2. Compute the agreement statistic and keep its report as a submitted file:
   `.venv/bin/python labelling/scripts/agreement.py --a labelling/labeller_A.csv --b labelling/labeller_B.csv`
   redirected into `labelling/agreement_report.txt`. Then co-resolve every disagreement with Loh Wen Xuan and
   record the reasoning in `labelling/resolutions.csv`. Disagreements are evidence of care, not error.
3. After the benchmarks, read `analysis/output/accuracy/misclassified.csv` and the confusion matrices and
   write the "where each model goes wrong" commentary for Slide 10. An `UNPARSEABLE` prediction is a
   **result**, not a bug — how it counts towards accuracy is an open decision under R3.

### Part 4 — Toh Si Pei (workload model and requirements; Slides 3, 4)


**Folder:** [`workload/`](workload/), plus the pen on
[`predictions/prediction_record.md`](predictions/prediction_record.md).
**Documents:** [`workload/README.md`](workload/README.md) (read this first),
[`workload/workload_model.md`](workload/workload_model.md),
[`workload/requirements.md`](workload/requirements.md).
**Script:** `workload/scripts/ticket_length_stats.py`.
**Slides:** 3 (workload model), 4 (requirements).

**Part 1 cannot choose the arrival rates to test.** They come from here, and they are needed before the
freeze so the benchmark plan is ready the moment the gate opens.

1. Read `workload/README.md`, then get the one figure you do not have to estimate — the ticket length
   distribution — from our own data:
   `.venv/bin/python workload/scripts/ticket_length_stats.py --out-dir workload/output`. It runs no model, so
   it is safe at any time. Read its truncation-risk figure too: it says how many of our rows risk exceeding
   `NUM_CTX=4096` once the prompt is added.
2. Fill in `workload/workload_model.md`: ticket volume in a stated period, agent search rate, peak versus
   non-peak, and the length distribution. **Cite a source for every figure, or state the estimation method.**
   An uncited number is treated as unsupported; the estimation method is what is being marked.
3. Fill in `workload/requirements.md` — R1 response time, R2 throughput, R3 overall accuracy, R4 per-category
   accuracy, R5 `GET /search` under mixed load — each with a number, a percentile where relevant, the load
   condition under which it must hold, and the analysis script that will produce the number that tests it.
   Then **hand Part 1 the explicit list of arrival rates, the search rate and the run duration**, at the end
   of `workload_model.md`. Take a position on what costs the client more: a misrouted ticket or a slow triage.
   Slide 11's recommendation has to follow from it.

### Part 5 — Koh Tong Wei (environment, playbooks and deck; Slides 7, 8, 12)


**Folders:** [`docs/environment/`](docs/environment/), [`docs/playbooks/`](docs/playbooks/),
[`slides/`](slides/).
**Documents:** [`docs/test-environment.md`](docs/test-environment.md), the three playbooks,
[`docs/references.md`](docs/references.md), [`slides/outline.md`](slides/outline.md).
**Script:** `scripts/capture_env.sh`.
**Slides:** 7 (test environment), 8 (playbook), 12 (references); assembles the final deck with Part 1.

1. Run `scripts/capture_env.sh` on **every** machine, on that machine, with the right `--role`, and commit
   the files ([section 5.5](#55-how-the-two-machine-fact-is-evidenced-for-slide-7)). Nothing in
   `docs/test-environment.md` can be filled in until those exist, and no figure may be typed from memory.
2. Fill in `docs/test-environment.md`: the machine table (every cell copied from a named capture file), the
   **measured** round-trip time, the separate-machine confirmation with its four pieces of evidence, the
   factors that could make our measurements unrepresentative **with the direction each biases the numbers**,
   and the scaling argument to the client's commodity CPU servers. Its section 7 is a checklist; work to it.
3. Run one test yourself end to end in `--dev` mode, following
   [`docs/playbooks/load-test.md`](docs/playbooks/load-test.md) exactly as written. Wherever you had to ask
   somebody a question, that question is a defect in the playbook — fix the document. Then create the single
   committed **run log** the playbooks point at (one dated entry per configuration, with the seven items in
   `load-test.md` section 7) and name it in both playbooks.

### Whole team

The [prediction record](predictions/prediction_record.md) is a whole-team judgement and **no tool, no agent
and no single member may supply it**. Fill it in in one sitting, after the labelling is finished and after
`workload/requirements.md` is settled. Each member writes their own figures down privately first, then the
team agrees the entry — otherwise the first figure spoken aloud becomes everybody's figure and Slide 11 loses
its most interesting material. Marks come from specificity and from the later account of where we were wrong,
not from being right: before writing any entry, ask *what result would prove this wrong?* If you cannot
answer, the entry is not finished.

---

## 9. How to do the freeze

Run these from the repository root, in this order. If this section and
[`scripts/freeze_gate.py`](scripts/freeze_gate.py) ever disagree, **the script is the authority**, because it
is the thing the benchmark scripts actually consult.

Everything else must be committed **first**, in its own commits: the protocol, both label sheets,
`labelling/resolutions.csv`, the agreement report, `workload/workload_model.md`,
`workload/requirements.md` and `models/models.yaml` with a digest for every candidate.

```bash
# 0. Sanity check: the gate must currently FAIL. Expect "ok": false and exit code 3.
.venv/bin/python scripts/freeze_gate.py --json || echo "not frozen yet — as expected at this point"

# 1. Both files go in ONE commit, and nothing else belongs in it.
#    This is the commit the marker will look at.
git add golden/golden_set.csv predictions/prediction_record.md
git commit -m "Freeze golden test set and prediction record before first benchmark run"

# 2. Tag that commit. The tag name is fixed: the gate looks for exactly "golden-freeze".
git tag -a golden-freeze -m "Golden set and prediction record frozen (Assignment 1, Step 4)"

# 3. VERIFY. Exit code 0 and "ok": true is the green light for Step 5.
.venv/bin/python scripts/freeze_gate.py --json

# 4. Prove both files are in the TAGGED TREE, not merely in the working directory.
git cat-file -e golden-freeze:predictions/prediction_record.md && echo "prediction record is in the tagged tree"
git cat-file -e golden-freeze:golden/golden_set.csv && echo "golden set is in the tagged tree"

# 5. Push the commit AND the tag, so the dated history is not only on one laptop.
#    --follow-tags pushes the annotated tag along with the commit. Equivalently:
#      git push && git push origin golden-freeze
git push --follow-tags
```

On success the gate prints, and writes to stdout with `--json`, the freeze commit, the tag, the blob hash of
each file and the golden-set row count. Paste that JSON into the team channel: it is the moment of the
freeze. Every run directory created afterwards stores the same JSON verbatim as `freeze.json`.

> ### Do not move or delete the tag
>
> **After the tag exists, `golden/golden_set.csv` and `predictions/prediction_record.md` are closed.** Do not
> amend the commit, do not move the tag, do not delete and re-create it, and do not rewrite an entry. All of
> those destroy the only evidence we have that our labels and predictions predate our measurements, and a
> moved tag is worse than no tag: it looks like exactly the thing the rule exists to prevent.
>
> **If something genuinely must be corrected** — a model tag copied wrongly from `models/models.yaml`, say —
> then:
>
> 1. leave the original text exactly as it stands;
> 2. add a **new dated appendix** in a **new commit**, saying what was wrong and what it should have read;
> 3. if a second tag is needed, create a **new** tag (for example `golden-freeze-2`) rather than moving
>    `golden-freeze`, and **never rewrite history**;
> 4. treat the version at the original `golden-freeze` tag as the prediction of record when writing Slide 11,
>    and **say all of this on the slide**. An openly declared correction is defensible; a silently moved tag
>    is not.

---

## 10. Troubleshooting

Each playbook carries a fuller failure table for its own test. These are the ones that bite on a fresh clone.

### Ollama is not reachable

**From the service:** `GET /health` returns `"status": "degraded"` and `"ollama_reachable": false`, and every
`POST /tickets` returns 502 with `error: "ollama_connect_error"`. The service is working correctly — the
container is up, the backend is not, and that is the distinction `/health` exists to draw.

```bash
curl -s http://127.0.0.1:8000/health | .venv/bin/python -m json.tool   # check ollama_base_url
docker compose ps                                  # is the ollama container even created?
docker compose --profile local-ollama up -d ollama # it is only created with this profile
docker compose logs ollama | tail -30
```

The commonest causes, in order: the `local-ollama` profile was never requested, so no Ollama container
exists; `OLLAMA_BASE_URL` still says `http://ollama:11434` while Ollama is actually on another machine; or
the model named by `MODEL_TAG` was never pulled on *that* Ollama.

**From another machine:** check from the machine that needs it, not from the Ollama host.

```bash
curl -s http://<ollama-host>:11434/api/tags | head -c 400
```

If that hangs or is refused: the port is not published (`ports: 11434:11434` in the compose file), the
firewall is closed ([section 5.2](#52-making-machine-1-reachable-and-pointing-jmeter-at-it)), or Ollama is
bound to loopback only. Our compose file sets `OLLAMA_HOST=0.0.0.0:11434` inside the container for exactly
this reason; a hand-installed Ollama on the host may not.

### The first request is very slow

Expected, and it is not the service. The first request for a given model pays the **model-load** cost:
Ollama reads gigabytes of weights from disk into memory before it can evaluate anything. The service log
records that cost separately as `load_duration` (nanoseconds, Ollama's own figure), so you can see it rather
than infer it.

This is why `scripts/run_load_test.sh` sends **one warm-up `POST /tickets`** with the `X-Warmup: 1` header
before every measured window, from `data/dev/synthetic_tickets.csv`, and writes its log line to
`warmup.jsonl` — **outside** `service.jsonl`. Without it the first sample would carry the whole model-load
cost and drag the p99, and the reported latency would describe something no steady-state client ever
experiences. A team row is never spent on a warm-up.

Two consequences to state on Slide 7: our numbers describe a **warm** service, which is optimistic relative
to a client whose model is evicted between quiet periods (`OLLAMA_KEEP_ALIVE`); and the accuracy driver
deliberately sends no warm-up, because it times nothing, so the first golden ticket of each accuracy run
carries the load cost in the log. That changes no category, and it is another reason never to quote a latency
from an accuracy run.

If `load_duration` becomes non-trivial again **part-way through** a run, Ollama reloaded or evicted the model
mid-measurement. The step that lands in will look like the limit, and the run is not evidence.

### JMeter runs out of memory

Symptoms: `java.lang.OutOfMemoryError: Java heap space` in `jmeter.log`, or JMeter dying part-way through a
long or high-rate run. Raise the heap on the **load generator**:

```bash
# Per invocation, before starting JMeter:
export JVM_ARGS="-Xms1g -Xmx4g"

# Or edit the heap line in $JMETER_HOME/bin/jmeter (JMeter's own launcher sets it).
```

Then record the value you used in `docs/environment/`: the heap is part of the load generator's configuration
and it belongs on Slide 7. Two related points. We already keep the `.jtl` small — response bodies are **not**
saved (`jmeter.save.saveservice.response_data=false` in `jmeter/user.properties`), because a 300-second run
would otherwise write tens of megabytes of classification replies, and the reply is already in the service log
with its `request_id`. And **watch the load generator's own CPU** while a run is in flight: if JMeter
saturates it, part of what you record as service latency is generator delay, which is the silent failure mode
the separate-machine rule exists to prevent.

### `/stats` reports a non-zero total before a run

`GET /search` is a full-table `LIKE` scan, so leftover tickets change what is being measured and make the run
incomparable with one that started empty. The service must start empty for every measured run — the brief
says the service starts empty and tickets enter only through `POST /tickets`.

```bash
curl -s http://<machine-1>:8000/stats | .venv/bin/python -m json.tool   # expect "total": 0
scripts/reset.sh --yes                                                  # DESTROYS every stored ticket
```

`scripts/run_load_test.sh` calls `scripts/reset.sh --yes` itself before every run, so this normally only
bites when a plan is run by hand or after an accuracy run (which deliberately does **not** reset, because
accuracy does not depend on what is stored — but it leaves the golden tickets in the database). `reset.sh`
removes the `<project>_triage_db` volume only; it never touches the Ollama model volume and never touches
anything under `logs/`.

### The freeze gate blocks a real run

```
FREEZE GATE: BLOCKED -- 3 condition(s) not met.
```

Working as designed. The gate names each unmet condition and prints the exact command that fixes it. Do not
work around it. In particular, **do not pass `--dev` and then report the result**: dev mode runs on 28
hand-written synthetic tickets, writes only under the gitignored `results/dev/`, stamps `"mode": "dev"` and
`"freeze_commit": null`, and prints
`*** DEV MODE — synthetic tickets only. Results are NOT evidence. ***`. `--dev` exists for rehearsing the
procedure, never for producing evidence. The way past the gate is
[section 9](#9-how-to-do-the-freeze).

A run whose `freeze.json` contains `"ok": false`, or whose `metadata.json` has `"mode": "dev"`, is not
evidence.

### The model tag in `.env` does not match what is pulled

The failure looks like `/health did not report model <tag> within 240s`, or a warm-up returning 502, or a
start-up warning that no digest could be resolved. The diagnosis is always the same three checks:

```bash
curl -s http://<machine-1>:8000/health | .venv/bin/python -m json.tool     # what the service thinks
curl -s http://<ollama-host>:11434/api/tags | head -c 600                   # what Ollama actually has
grep -A4 'tag: "<tag>"' models/models.yaml                                  # what we pinned
```

Three distinct mismatches, with three different fixes:

* **`MODEL_TAG` names a model Ollama has not pulled.** Pull it on the Ollama host:
  `scripts/pull_and_pin_models.sh --model <tag>`. Raise `HEALTH_TIMEOUT_S` only if a genuinely slow pull is
  the cause, not to paper over this.
* **The container was never recreated after `MODEL_TAG` changed.** The service reads its configuration once,
  at start-up: `MODEL_TAG=<tag> docker compose up -d --force-recreate --no-deps triage`.
* **`MODEL_DIGEST` was pinned explicitly and disagrees with what Ollama serves.** This is the mismatch
  surfacing rather than being papered over, which is the point of the explicit pin. Either the weights behind
  the tag changed — in which case every result recorded under the old digest is no longer comparable — or the
  pin was typed by hand. Never type a digest by hand; only
  `scripts/pull_and_pin_models.sh` may write one.

Also check the start-up line in `docker compose logs triage`: it prints the whole resolved configuration,
including the digest the service resolved from `/api/tags`.

### Port already in use

```
Error response from daemon: ... address already in use
```

Something else on machine 1 holds port 8000.

```bash
ss -tlnp | grep 8000              # Linux
lsof -nP -iTCP:8000 -sTCP:LISTEN  # macOS
```

Either stop the other process, or change `SERVICE_PORT` in `.env` and pass the new port to everything that
talks to the service (`--port`, `-Jport`, the `curl` URLs, and the firewall rule). Compose publishes
`${SERVICE_PORT}:${SERVICE_PORT}`, so the published and internal ports move together. The same applies to
`OLLAMA_PORT` (11434) if another Ollama is already running — including a **host-installed** Ollama, which is
a common cause: a native `ollama serve` holding 11434 will block the container, and then it is ambiguous
which Ollama a request reached. Stop one of them.

### Log files are not appearing in `logs/service/`

The log directory is bind-mounted, `./logs/service` on the host to `${LOG_DIR}` (`/logs/service`) in the
container, because those files are the evidence every reported number must reconcile with. Three things go
wrong.

1. **Ownership.** A bind mount takes its ownership from the **host** directory, so the container's `triage`
   user must match it. The image is built with `APP_UID=1000`/`APP_GID=1000`; if `id -u` on the host says
   something else, the container cannot append and the writes fail silently from outside. Rebuild:
   ```bash
   docker compose build --build-arg APP_UID=$(id -u) --build-arg APP_GID=$(id -g) triage
   docker compose up -d --force-recreate triage
   docker compose logs triage | grep -i "failed to write a request log line"
   ```
   The service deliberately never 500s because it could not log; it logs the failure to stdout instead, so
   `docker compose logs triage` is where the evidence of the missing evidence is.
2. **You are looking on the wrong machine, or at the wrong path.** With `DOCKER_HOST=ssh://…`, Compose
   resolves `./logs/service` to an absolute path computed on **machine 2** and machine 1's daemon interprets
   it on **machine 1** — so the repository must sit at the same absolute path on both. This is the trap in
   [section 5.3](#53-the-cross-machine-plumbing), and its symptom is exactly "no log files".
3. **You are looking on the wrong date, or too early.** The filename is `<UTC-date>.jsonl`, chosen at
   **write** time, so a run crossing midnight UTC lands in two files, and nothing exists until the first
   logged request. Note also that `/health` is deliberately **not** logged, so polling it produces no lines:
   send a real request.
```bash
ls -l logs/service/                                     # <UTC-date>.jsonl
tail -1 logs/service/$(date -u +%F).jsonl | .venv/bin/python -m json.tool
```

### Other symptoms, and where they are documented

| Symptom | Where the answer is |
|---|---|
| Sample count far below `rate_per_min / 60 × duration_s`, or a whole sampler label missing from the `.jtl` | The JDK problem: a Groovy pre-processor failed silently. `jmeter/README.md` section 7, and `java -version` on the load generator |
| `results.jtl` has no `request_id` or `source_row` column | [Section 6.7](#67-running-a-plan-by-hand): the `.jtl` column set is not pinned on that machine |
| `reconcile.py`: unmatched samples, or a latency p99 disagreement | Clocks and `SERVICE_LOG_DIR` first. `docs/playbooks/load-test.md` section 9. Never raise the threshold to make it pass |
| `no service log lines fall inside the measured window` | Clock skew or the wrong log directory. Run NTP on both; raise `SLICE_MARGIN_S` only after checking the clocks |
| `stress_summary.py` reports seven steps instead of six | The drain boundary effect. `docs/playbooks/stress-test.md` section 6.1: append a trailing `0` to `--offered-rates` |
| `summarise_load.py`: "no runs found" | `--runs` points at the wrong directory, or a run directory was renamed. The name is parsed for model, plan, rate and run index |
| `accuracy.py`: incomplete coverage, or "no responses found" | `docs/playbooks/accuracy-test.md` section 10. Re-run the whole golden set for that model; never patch a partial run |
| Every sample is a 200 but many carry `category: "UNPARSEABLE"` | Nothing is wrong with the load test. That is an accuracy observation, deliberately not asserted on client-side |
| `not an interactive terminal and --yes was not given` (exit 2) | Pass `--yes`, having understood that each run destroys the stored tickets |
| `run_load_test.sh: JMeter not found` (exit 2) | `--jmeter-home /path/to/apache-jmeter-5.6.3`, or put `jmeter` on PATH on the load generator |

---

## 11. Service log format

One JSON object per request, appended to `logs/service/<UTC-date>.jsonl`. The date is taken at **write**
time, so a run crossing midnight UTC lands in two files; the run scripts copy the slice they need into the
run directory as `service.jsonl`.

This log is the assignment's primary evidence. The **only** way to produce a line is
`service.request_log.build_log_line()`, which refuses an unknown field, refuses a missing field, and returns
the fields in `LOG_FIELDS` order — so a handler that forgets a field fails at development time rather than
producing a log file the analysis rejects after a fifteen-minute load test. The authoritative field list is
[`service/log_schema.py`](service/log_schema.py); `LOG_SCHEMA_VERSION` is currently **1**.

`/tickets`, `/search` and `/stats` are all logged (`/search` and `/stats` appear in the mixed test, with every
model field `null`). **`/health` is deliberately not logged** — a container health check and possibly a load
test poll it, and those lines would swamp the run's evidence.

**Units.** Ollama's four duration fields are **nanoseconds**, copied through verbatim. Our own two latency
fields are **milliseconds**, measured with a monotonic clock and rounded to one decimal place. Mixing the two
is the easiest arithmetic error available here.

### The 24 fields, in order

| # | Field | Type | Meaning |
|---|---|---|---|
| 1 | `ts` | str | Write time: UTC, ISO-8601, **millisecond** precision, `Z` suffix. Truncated rather than rounded, so the stamp is never ahead of the event |
| 2 | `request_id` | str | From `X-Request-ID`, or a generated UUID4 if absent. **The join key** `analysis/reconcile.py` uses against the `.jtl` |
| 3 | `source_row` | str \| null | From `X-Source-Row`: the course CSV row being posted. A string, because a row number is an identifier, not a quantity |
| 4 | `warmup` | bool | `true` for the run script's warm-up request (`X-Warmup: 1`). Those lines go to `warmup.jsonl` and are excluded from analysis |
| 5 | `endpoint` | str | `/tickets`, `/search` or `/stats` (or the path, for an error line) |
| 6 | `method` | str | `POST` or `GET` |
| 7 | `status` | int | The HTTP status actually returned |
| 8 | `ticket_chars` | int \| null | `len(narrative)`; `null` off `/tickets` |
| 9 | `model_tag` | str \| null | The Ollama tag that served this request |
| 10 | `model_digest` | str \| null | The pinned digest, or the one resolved from `/api/tags` at start-up. What ties this line to a specific set of weights |
| 11 | `predicted_category` | str \| null | One of the seven, or `UNPARSEABLE`. `null` on a 502 — no classification happened |
| 12 | `raw_model_output` | str \| null | What the model actually said, sliced to 500 characters with nothing appended. When the category is `UNPARSEABLE` this is the only record of the reply |
| 13 | `prompt_hash` | str \| null | `sha256:` plus 16 hex characters, derived from the one prompt template. Accuracy is a property of model **and** prompt, so two runs with different hashes are not a comparison |
| 14 | `num_ctx` | int \| null | The context window we asked Ollama for. Logged per request so a truncation question can be answered after the fact |
| 15 | `seed` | int \| null | The fixed sampling seed (temperature is fixed at 0 in code) |
| 16 | `total_latency_ms` | float | **Ours, milliseconds.** Wall clock across the whole request handler, 1 dp |
| 17 | `model_latency_ms` | float \| null | **Ours, milliseconds.** Wall clock around the Ollama HTTP call, 1 dp |
| 18 | `total_duration` | int \| null | **Ollama's, nanoseconds.** Its own total for the generation |
| 19 | `load_duration` | int \| null | **Ollama's, nanoseconds.** Model load. Non-trivial here means the model was (re)loaded for this request |
| 20 | `prompt_eval_count` | int \| null | **Ollama's**, tokens in the prompt. Compare with `num_ctx` to detect silent truncation |
| 21 | `prompt_eval_duration` | int \| null | **Ollama's, nanoseconds.** Time spent evaluating the prompt |
| 22 | `eval_count` | int \| null | **Ollama's**, tokens generated |
| 23 | `eval_duration` | int \| null | **Ollama's, nanoseconds.** Time spent generating |
| 24 | `error` | str \| null | `null`, or one of `ollama_timeout`, `ollama_connect_error`, `ollama_http_error`, `ollama_bad_response`, `bad_request`, `internal_error` |

Fields **9–15 and 17–23** are `null` for `/search` and `/stats` lines, because no model was called;
`total_latency_ms` (16) is always present, on every logged endpoint. On a **502** the line still records
which model, prompt and context length failed, and `model_latency_ms` still records how long the failed call
took — only `predicted_category` (11), `raw_model_output` (12) and Ollama's own timings (18–23) are `null`,
with the reason in `error` (24). Fields 18–23 are also `null` whenever Ollama simply did not return them.

The writer is deliberately naive: one `open(..., "a")`, one `write`, one `flush`, one `close`, per request.
The explicit flush is what makes a line survive a container kill mid-run, which is exactly what a stress test
creates. `# A2 candidate: buffered / async logging instead of an open-write-close per request.`

**Adding a field is a breaking change for every run already recorded.** If one must be added: add it at the
**end** of `LOG_FIELDS`, bump `LOG_SCHEMA_VERSION`, and record it in
[section 12](#12-changelog) — runs recorded before and after cannot be pooled without care.

---

## 12. Changelog

Two identifiers pin what our measurements mean, and a change to either one splits the results into two
incomparable sets. Both are enforced by a failing test rather than by good intentions, and both must be
recorded here when they change.

| Date | What changed | Old value | New value | Consequence |
|---|---|---|---|---|
| 2026-09-23 | Initial baseline. `LOG_SCHEMA_VERSION = 1`; the prompt template pinned in `tests/test_prompt.py`. | — | — | Nothing measured yet. |
| 2026-10-08 | Reported campaign run. Neither identifier changed: every reported run has `prompt_hash` `sha256:681131c48bdc15a1` and schema version 1. | — | — | All 55 runs and 4 accuracy passes are poolable by model. |

**`LOG_SCHEMA_VERSION`** — [`service/log_schema.py`](service/log_schema.py). Bump it whenever `LOG_FIELDS`
changes, add the new field at the end, and say here which runs predate the change. Runs recorded under
different schema versions cannot be pooled without care.

**`PROMPT_HASH`** — derived from `PROMPT_TEMPLATE` in [`service/prompt.py`](service/prompt.py) and pinned in
`tests/test_prompt.py` as `PINNED_PROMPT_HASH`. Editing the template by a single character changes the hash
and fails that test. **That failing test is the point**: it forces the edit to be a deliberate, recorded act.
If the change is intended, update `PINNED_PROMPT_HASH`, record it here, and **do not pool results from before
and after** — accuracy is a property of the model *and* the prompt, and `prompt_hash` is in every log line
and every `metadata.json` so the split can always be seen.

Changes to `MODEL_TAG`, `MODEL_DIGEST`, `NUM_CTX` or `OLLAMA_SEED` do not need an entry here, because each
one is already recorded per request in the service log and per run in `metadata.json`. A **model digest**
change is handled elsewhere and more strictly: `scripts/pull_and_pin_models.sh` exits 4 and refuses to
overwrite an existing pin, because every result gathered under the old digest stops being comparable.
