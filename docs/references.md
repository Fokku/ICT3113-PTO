# References and acknowledgements — pre-seeded list for Slide 12

**What this document is for.** It is the reference list Slide 12 ("References and Acknowledgements") is built
from, pre-seeded with every source this repository already uses: the dataset, the tools, and every candidate
model with its licence. It also separates what a licence **requires** us to state from what is merely good
practice, because the brief warns that *"Failing to comply with a licence may be an infringement of
copyright."*

**Owner:** Part 5 — Koh Tong Wei.

**What "done" looks like.** Every source cited anywhere in the deck appears here exactly once, in one
consistent style; the Consumer Complaint Database, Ollama and a licence for every candidate model are all
present; every `TODO` below is resolved; the numbering has been re-run in one pass so it is contiguous; and
the acknowledgements section states our use of AI coding tools.

**Feeds:** Slide 12 (References and Acknowledgements). Section 6 also feeds the licence line on Slide 5
(Candidate Models), and section 7's workload sources must agree with the short-form citations on Slide 3.

---

## 1. Citation style

**This list uses IEEE style.** State that on the slide. The pattern for the kind of source this assignment
uses — software, documentation and web-published datasets — is:

> `[n] Author or Organisation, "Title of the page or work," Version or edition (where it exists). [Online]. Available: URL. [Accessed: D Month YYYY].`

Rules we hold to, so that two people editing this file produce the same thing:

* Numbered in the order the sources are first cited in the deck. **Number the list in one pass, last**, after
  Part 4's workload sources have been added in section 7 — otherwise every insertion renumbers everything
  after it. The numbers below are provisional and are marked as such.
* Organisation as author where there is no personal author. That is the normal case here.
* A version number wherever a version exists and we know it. Software without a version is not a citation you
  can reproduce.
* An accessed date on every URL. Where a committed document in this repository already establishes the date a
  page was read, that date is used and the document is named. Where it does not, the date is a `TODO` for
  whoever compiles the final list — **do not invent one.**

`TODO(Part 5 — Koh Tong Wei): if the module or your lab group requires a different style (APA, Harvard), convert
the whole list rather than mixing two. The content does not change; only the layout does.`

---

## 2. A note on versions

Every version number below is a `TODO`, and deliberately so: the version that belongs in a reference is the
version we actually ran, and that is a captured fact, not a recollection. Get each one from these places and
nowhere else:

| Tool | Where the real version is recorded |
|---|---|
| Apache JMeter | `environment/<loadgen-hostname>.txt`, section 6, label `jmeter version`. Also every run's `metadata.json`, key `jmeter_version` |
| Java (JMeter's runtime) | `environment/<loadgen-hostname>.txt`, section 6, label `java (used by JMeter)` |
| Ollama | `environment/<ollama-hostname>.txt`, section 5, label `ollama /api/version`. Also written into `../models/models.yaml` next to each digest by `../scripts/pull_and_pin_models.sh` |
| Docker Engine and Compose | `environment/<hostname>.txt`, section 4, labels `docker`, `docker server`, `docker compose` |
| Python (in the container) | the image is `python:3.11-slim` — see `../Dockerfile`. For the exact patch version: `docker compose exec triage python --version` |
| FastAPI, uvicorn, httpx, pydantic | `docker compose exec triage pip freeze` on the service host. The declared floors are in `../requirements.txt` |
| SQLite | `docker compose exec triage python -c "import sqlite3; print(sqlite3.sqlite_version)"` — the service uses Python's standard-library `sqlite3`, so the SQLite version is the one bundled with the container's Python |
| pandas, matplotlib | `.venv/bin/pip freeze` on the machine that ran the analysis. Declared floors in `../requirements-dev.txt` |

---

## 3. Dataset

**[1]** US Consumer Financial Protection Bureau, "Consumer Complaint Database." [Online]. Available:
<https://www.consumerfinance.gov/data-research/consumer-complaints/>.
[Accessed: `TODO(Part 5 — Koh Tong Wei)`].

*This is the reference the brief names explicitly, and it is not optional: "The Consumer Complaint Database is
published by a US government agency; acknowledge the source in your final document." The brief gives the
address as `www.consumerfinance.gov/data-research/consumer-complaints/`; the entry above adds the scheme.*

**[2]** ICT3113 course teaching team, "ICT3113 Assignment 1 ticket extract (`ict3113_tickets.csv`)," course
extract from [1], released on xSiTe, Week 1. `TODO(Part 5 — Koh Tong Wei): confirm how the course wants the
extract itself cited, or fold it into the sentence describing [1] and delete this entry.`

*What the deck must say about the data, from the brief: the narratives are "real consumer complaint
narratives, published with consumer consent and with personal information removed at source"; our team uses
rows 10000–10999 of the extract (team 10), and every labelled ticket and every test request comes from those
1,000 rows.*

`TODO(Part 5 — Koh Tong Wei): check the CFPB's own terms-of-use or data-licence page and record here what, if
anything, it asks of a re-user beyond acknowledgement. The brief requires the acknowledgement regardless, so
this is about being right rather than about being safe.`

---

## 4. Load generator

**[3]** Apache Software Foundation, "Apache JMeter," version `TODO(Part 5 — Koh Tong Wei): from
environment/<loadgen>.txt`. [Online]. Available: <https://jmeter.apache.org/>.
[Accessed: `TODO(Part 5 — Koh Tong Wei)`].

**[4]** Apache Software Foundation, "Apache JMeter user manual: component reference." [Online]. Available:
<https://jmeter.apache.org/usermanual/component_reference.html>. [Accessed: `TODO(Part 5 — Koh Tong Wei)`].

*Cite [4] wherever the deck relies on the **Open Model Thread Group** and its `rate(...) random_arrivals(...)`
schedule — which is Slide 8, because the brief requires the open-loop configuration to be shown.*
`TODO(Part 5 — Koh Tong Wei): confirm the exact section anchor for the Open Model Thread Group on that page and
append it to the URL, or cite the page without an anchor. Do not guess the anchor.`

**Licence:** Apache License 2.0. `TODO(Part 5 — Koh Tong Wei): verify on jmeter.apache.org and record the URL of
the licence statement you verified it from.` We do not redistribute JMeter, so nothing beyond a correct
citation is owed — see section 8.

---

## 5. Model backend, container platform and service stack

**[5]** Ollama, "Ollama." [Online]. Available: <https://ollama.com/>. [Accessed: `TODO(Part 5 — Koh Tong Wei)`].
Version `TODO(Part 5 — Koh Tong Wei): from environment/<ollama-host>.txt, label "ollama /api/version"`.

**[6]** Ollama, "LICENSE" (MIT License, "Copyright (c) Ollama"). [Online]. Available:
<https://github.com/ollama/ollama/blob/main/LICENSE>. [Accessed: 23 September 2026].

*Source for [6]: `../models/candidates.md`, "Licences and attribution", section 5, which records this licence
and URL as read on 23 September 2026. The brief names Ollama explicitly as a source that must be referenced.*

**[7]** Ollama, "Ollama model library." [Online]. Available: <https://ollama.com/library>.
[Accessed: 23 September 2026].

*Every factual claim in `../models/candidates.md` about a model's parameter count, default quantisation and
download size was read from this library on that date. Cite it as the source of the Slide 5 table.*

**[8]** Docker Inc., "Docker Engine," version `TODO(Part 5 — Koh Tong Wei): from environment/<hostname>.txt,
labels "docker" and "docker server"`. [Online]. Available: <https://www.docker.com/>.
[Accessed: `TODO(Part 5 — Koh Tong Wei)`].

**[9]** Docker Inc., "Docker Compose," version `TODO(Part 5 — Koh Tong Wei): from environment/<hostname>.txt,
label "docker compose"`. [Online]. Available: <https://docs.docker.com/compose/>.
[Accessed: `TODO(Part 5 — Koh Tong Wei)`].

*The brief requires the repository to be "sufficient to rebuild and run it with docker compose", so Compose is
a cited tool and not an implementation detail.*

`TODO(Part 5 — Koh Tong Wei): verify the licences of [8] and [9] and record the URL you verified each from.
Docker Engine and Docker Compose are open-source projects with their own repository licences, while Docker
Desktop is distributed under Docker's own subscription terms — so if any team machine used Docker Desktop
rather than the engine alone, that is a different licence and it must be named. Check section 4 of each
capture file to see which was installed on which machine.`

**[10]** S. Ramírez, "FastAPI," version `TODO(Part 5 — Koh Tong Wei): from pip freeze in the container`.
[Online]. Available: <https://fastapi.tiangolo.com/>. [Accessed: `TODO(Part 5 — Koh Tong Wei)`].

**[11]** Encode OSS Ltd., "Uvicorn," version `TODO(Part 5 — Koh Tong Wei): from pip freeze in the container`.
[Online]. Available: <https://www.uvicorn.org/>. [Accessed: `TODO(Part 5 — Koh Tong Wei)`].

**[12]** SQLite Consortium, "SQLite," version `TODO(Part 5 — Koh Tong Wei): from
sqlite3.sqlite_version in the container`. [Online]. Available: <https://www.sqlite.org/>.
[Accessed: `TODO(Part 5 — Koh Tong Wei)`].

*The service uses Python's standard-library `sqlite3` module, so SQLite is used as bundled with the container's
Python rather than installed separately. Say so in one clause on the slide: it is why there is no SQLite entry
in `../requirements.txt`.* `TODO(Part 5 — Koh Tong Wei): SQLite's own copyright page states its public-domain
position; read <https://www.sqlite.org/copyright.html> and record here what, if anything, it asks for.`

**[13]** Python Software Foundation, "Python," version `TODO(Part 5 — Koh Tong Wei): 3.11.x, from
"docker compose exec triage python --version"`. [Online]. Available: <https://www.python.org/>.
[Accessed: `TODO(Part 5 — Koh Tong Wei)`].

### 5.1 Secondary dependencies — include only if the deck cites them

Twelve slides is not much room, so cite these only where a slide actually rests on them; otherwise leave them
in the repository's `requirements.txt` and `requirements-dev.txt`, which are committed and are themselves
evidence.

| Library | Used for | Home page |
|---|---|---|
| httpx | the service's HTTP call to Ollama (a fresh `AsyncClient` per request, naive on purpose) | <https://www.python-httpx.org/> |
| Pydantic | request-body validation in the service | <https://docs.pydantic.dev/> |
| pandas | every analysis script under `../analysis/` | <https://pandas.pydata.org/> |
| Matplotlib | the charts in `../analysis/output/` — cite it on any slide that shows one | <https://matplotlib.org/> |

`TODO(Part 5 — Koh Tong Wei): promote to a numbered entry, with version and licence, each library the deck
actually cites; delete the rest of this table.`

---

## 6. Candidate models and their licences

The four candidates, their licences and their URLs are carried across **exactly** from `../models/candidates.md`
and `../models/models.yaml`, which record where each fact was read and on what date. Slide 5 reports the tag
and digest; this section reports the licence.

> `TODO(Part 5 — Koh Tong Wei): verify against ../models/candidates.md` before submission. That file is the
> authority for every licence claim below, and it may have moved on — the shortlist itself is still marked
> **PROPOSAL** there pending Yeo Kai Yuan's confirmation, and the Q8_0 quantisation decision for
> `llama3.2:1b` is still open. If anything below no longer matches that file, change **this** file, and do not
> let the two diverge silently.

> `TODO(Part 5 — Koh Tong Wei): the digests are not pinned yet.` Every `pinned:` block in
> `../models/models.yaml` is null until `../scripts/pull_and_pin_models.sh` has run against the Ollama host we
> measure on. Slide 5 must report the digests from that file, not the short web digests in
> `../models/candidates.md`, which are cross-checks only.

### 6.1 Meta Llama 3.2 1B Instruct and 3B Instruct — `llama3.2:1b`, `llama3.2:3b`

**[14]** Ollama, "llama3.2:1b" (Meta Llama 3.2 1B Instruct; 1.24B parameters; default quantisation Q8_0).
[Online]. Available: <https://ollama.com/library/llama3.2:1b>. [Accessed: 23 September 2026].

**[15]** Ollama, "llama3.2:3b" (Meta Llama 3.2 3B Instruct; 3.21B parameters; default quantisation Q4_K_M).
[Online]. Available: <https://ollama.com/library/llama3.2:3b>. [Accessed: 23 September 2026].

**[16]** Meta Platforms, Inc., "LLAMA 3.2 COMMUNITY LICENSE AGREEMENT," 25 September 2024. [Online].
Available: <https://github.com/meta-llama/llama-models/blob/main/models/llama3_2/LICENSE>.
[Accessed: 23 September 2026].

**[17]** Meta Platforms, Inc., "Llama 3.2 licence text as shipped by Ollama." [Online]. Available:
<https://ollama.com/library/llama3.2:3b/blobs/fcc5a6bec9da>. [Accessed: 23 September 2026].

**[18]** Meta Platforms, Inc., "Llama 3.2 Acceptable Use Policy," incorporated by reference into [16].
[Online]. Available: `TODO(Part 5 — Koh Tong Wei): the policy is named on the Ollama model page [15]; record the
URL you actually reached it at.` [Accessed: `TODO(Part 5 — Koh Tong Wei)`].

* **Licence:** Llama 3.2 Community License — a **custom licence, not OSI-approved**, with an Acceptable Use
  Policy incorporated by reference.
* **Commercially usable:** yes, subject to conditions, including a separate-licence requirement for licensees
  with more than 700 million monthly active users (not our client).
* **Could not verify:** the canonical licence URL printed inside the licence text itself,
  `https://www.llama.com/llama3_2/license/`, redirected via `developer.meta.com` to a Meta developer **sign-in
  page** on 23 September 2026, so the text is not publicly readable at that address. That is why [16] and [17]
  are cited instead. **Say this in the reference list**: it is a verification note, not an omission.

### 6.2 IBM Granite 4.0 Micro — `granite4:3b`

**[19]** Ollama, "granite4:3b" (IBM Granite 4.0 Micro, dense build; 3.4B parameters; default quantisation
Q4_K_M). [Online]. Available: <https://ollama.com/library/granite4:3b>. [Accessed: 23 September 2026].

**[20]** IBM Granite Team, "granite-4.0-micro" (model card; licence `apache-2.0`). [Online]. Available:
<https://huggingface.co/ibm-granite/granite-4.0-micro>. [Accessed: 23 September 2026].

* **Licence:** Apache License 2.0 — see [23].
* **Attribution requested by the publisher:** IBM's model card asks that Granite be cited to the **Granite
  Team, IBM**. Requested, not licence-mandated; see section 8.
* Note for Slide 5: `granite4:3b` and `granite4:micro` resolve to the same digest. Report the explicit size
  tag, never `latest`.

### 6.3 Alibaba Qwen2.5 7B Instruct — `qwen2.5:7b`

**[21]** Ollama, "qwen2.5:7b" (Qwen2.5 7B Instruct; 7.62B parameters; default quantisation Q4_K_M). [Online].
Available: <https://ollama.com/library/qwen2.5:7b>. [Accessed: 23 September 2026].

**[22]** Qwen Team, Alibaba Cloud, "Qwen2.5-7B-Instruct" (model card; licence `apache-2.0`). [Online].
Available: <https://huggingface.co/Qwen/Qwen2.5-7B-Instruct>. [Accessed: 23 September 2026].

* **Licence:** Apache License 2.0 — see [23].
* **Attribution:** attribute the model to the **Qwen Team, Alibaba Cloud**.

### 6.4 The Apache License 2.0 itself

**[23]** Apache Software Foundation, "Apache License, Version 2.0," January 2004. [Online]. Available:
<https://www.apache.org/licenses/LICENSE-2.0>. [Accessed: 23 September 2026].

*Covers `granite4:3b` [19] and `qwen2.5:7b` [21], and — subject to the verification `TODO`s above — JMeter
[3] and Docker [8], [9].*

### 6.5 A licence finding worth a line on the slide

Within the Qwen2.5 family, **individual sizes carry different licences**. Ollama's own family page states that
all Qwen2.5 models except the 3B and 72B are Apache-2.0, while the 3B and 72B are under the Qwen licence; the
Qwen2.5-3B-Instruct card carries the identifier `qwen-research`, whose text restricts use to
**non-commercial purposes only** and requires a separate licence for commercial use.

**[24]** Ollama, "qwen2.5" (family page, stating the per-size licence split). [Online]. Available:
<https://ollama.com/library/qwen2.5>. [Accessed: 23 September 2026].

**[25]** Qwen Team, Alibaba Cloud, "Qwen2.5-3B-Instruct LICENSE" (Qwen Research License). [Online]. Available:
<https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/blob/main/LICENSE>. [Accessed: 23 September 2026].

*Why this is in the reference list and not only in the appendix: `qwen2.5:3b` would otherwise have been a
natural candidate, and it is disqualified for this client on licence grounds alone. Anyone who checks a licence
at the family level rather than per size ships a non-commercial model into a commercial deployment. The full
argument, and the other rejected candidates with their licence gaps (Gemma's Terms of Use, `phi4-mini`'s absent
licence statement), are in `../models/candidates.md`.*

### 6.6 Named substitutes (cite only if one was actually used)

Neither of these is a candidate. They exist so that a substitution made under time pressure is one we already
argued. **Cite them only if a substitution actually happened**, and if it did, move the model into section 6 as
a full entry and say why the substitution was made.

| Tag | Replaces slot | Licence recorded in `../models/models.yaml` | URL |
|---|---|---|---|
| `mistral:7b` | 7-8B | Apache License 2.0 — but Ollama's page states "Apache license" **without a version number**, which is why it is a substitute and not a candidate | <https://ollama.com/library/mistral> |
| `qwen2.5:1.5b` | sub-2B | Apache License 2.0 | <https://ollama.com/library/qwen2.5:1.5b> |

---

## 7. Workload model sources (Part 4)

Slide 3 defers to this slide: *"Cite the source of every figure; state clearly which figures are estimates and
how you estimated them (see Slide 12)."* So every published statistic behind the workload model belongs here in
full, and the short form on Slide 3 must match it.

`TODO(Part 4 — Toh Si Pei): list every published figure the workload model uses — complaint volumes, search
rates, peak and non-peak periods — as an IEEE entry in the style of section 1, and name which figures are
estimates rather than published. They are collected in ../workload/workload_model.md; this section is where
they become citations.`

`TODO(Part 5 — Koh Tong Wei): after Part 4 supplies them, check that no figure cited on Slide 3 is missing here
and that no entry here is unused. Then renumber the whole list in one pass.`

One source is already fixed, because our own ticket-length distribution is measured rather than cited:

**[26]** This work, "Ticket length distribution of team 10's 1,000 rows," produced by
`python workload/scripts/ticket_length_stats.py --team-rows data/team_rows.csv`, output under
`../workload/output/`. *Not an external source. Cite it as our own measurement so the slide distinguishes it
from the published figures around it.*

---

## 8. Attribution actually required by these licences

The brief is pointed about this: *"Ollama and your candidate models each carry their own licences; place any
acknowledgements they require in your final document. Failing to comply with a licence may be an infringement
of copyright."* So it is worth separating the two things students usually merge.

**The distinction that does the work.** Almost every clause below is triggered by **distribution** — handing
the software or the model weights to somebody else. We do not redistribute JMeter, Ollama, Docker, or any model
weights: the repository contains a service and a set of tags, and the weights are pulled from Ollama's library
by whoever runs it. Our client is likewise deploying internally on their own infrastructure, not redistributing
anything and not offering the model to third parties. Where that distinction leaves a genuine ambiguity, it is
said so rather than resolved by assertion.

| Source | What the licence **requires** of us | What is good practice but not required |
|---|---|---|
| CFPB Consumer Complaint Database [1] | `TODO(Part 5 — Koh Tong Wei): whatever the CFPB's own terms page asks for — check it.` The **brief** requires the source to be acknowledged regardless of what the licence says, so the acknowledgement is mandatory for us either way | Naming the extract and our row range (10000–10999); stating that the narratives are published with consumer consent and with personal information removed at source. Both are honesty about provenance rather than licence compliance |
| Apache JMeter [3] | Nothing, as we neither modify nor redistribute it | A correct citation with the version we ran |
| Ollama [5], [6] | The MIT licence requires its copyright and permission notice to be included in copies or substantial portions of the software. We ship neither, so nothing is triggered | Crediting Ollama by name — which the brief requires of us anyway — and recording the exact version with the results |
| Docker [8], [9] | `TODO(Part 5 — Koh Tong Wei): confirm, and note separately if any machine used Docker Desktop, which carries different terms` | A correct citation with the version |
| `granite4:3b` [19], `qwen2.5:7b` [21] — Apache-2.0 [23] | Section 4 of the licence binds a **redistributor**: retain copyright, patent, trademark and attribution notices; include a copy of the licence; carry forward any `NOTICE` file; and state significant changes. We redistribute neither model and modify neither, so what we owe in practice is a **correct citation** | Attributing the models to their publishers — the **IBM Granite Team** and the **Qwen Team, Alibaba Cloud**. IBM's model card asks for this explicitly. It costs nothing; do it |
| `llama3.2:1b`, `llama3.2:3b` [14]–[18] — Llama 3.2 Community License [16] | On distributing the Llama Materials **or "a product or service that contains any of them"** (section 1.b): (1) provide a copy of the agreement to the recipient; (2) **prominently display "Built with Llama"** on a related website, user interface, blogpost, about page or product documentation; (3) retain, in a `NOTICE` text file distributed with the copies, the notice `Llama 3.2 is licensed under the Llama 3.2 Community License, Copyright © Meta Platforms, Inc. All Rights Reserved.`; (4) prefix the name of any *distributed* model created, trained or fine-tuned from the Materials with `Llama`; (5) comply with applicable law and the Acceptable Use Policy [18]. Clause 2 additionally requires a separate licence from Meta for a licensee with more than 700 million monthly active users in the month before the Llama 3.2 release date | Clause (4) plainly does not apply: we neither train nor distribute a derivative model. Whether (1)–(3) bind a public repository for a service that *calls* a Llama model is the genuinely unclear part — it turns on the phrase "a product or service that contains any of them", which is a lawyer's question and not ours. **The cheap precaution is to comply anyway**: a `NOTICE` file with the sentence above, and a "Built with Llama" line in the repository README. One file, and the question goes away |

`TODO(Yeo Kai Yuan): decide whether to add the NOTICE file and the "Built with Llama" line to the repository
root. ../models/candidates.md records this as an open decision (item 3 of its confirmation block) and
recommends doing it. If the answer is yes, ask the owner of the repository root to add them — this file must not
add them, and neither must candidates.md. If the answer is no, record the reason here in one sentence, because
"we thought about it and decided not to" is a defensible position and silence is not.`

`TODO(Part 5 — Koh Tong Wei): if the Llama models are still candidates at submission, put the "Built with Llama"
attribution on Slide 12 itself. The clause names "a related website, user interface, blogpost, about page or
product documentation"; a submitted report is the closest thing we have to product documentation, and the
slide costs one line.`

---

## 9. Acknowledgements

### 9.1 AI tool use

The brief is explicit: *"AI coding tools are permitted and expected throughout. The build is a few hours' work
with an agent, and that is accepted. AI-generated code is typically correct but performance-naive, and an agent
will not label your test data, run your load tests, or make your recommendation. The assessment targets
measurement, interpretation, and judgement."*

So declaring it costs nothing and not declaring it looks worse than the truth. Write a short, specific
statement rather than a disclaimer.

`TODO(Part 5 — Koh Tong Wei): write the AI-tool-use statement. Be specific enough to be checkable, and cover
these five things:`

1. **Which tools**, by name and — where it is knowable — version or model.
2. **What they were used for.** Name the parts: the service implementation, the JMeter plans, the analysis
   scripts, the harness scripts, the document templates. Be honest about the proportion.
3. **What they were *not* used for**, which is the part that earns marks. The brief lists the work an agent
   cannot do for us: labelling the golden test set, running the tests, interpreting the results, and making the
   recommendation. If a human labelled every golden ticket and two humans labelled them independently, say so —
   `../labelling/protocol.md` and the agreement statistic are the evidence.
4. **How the output was checked.** Tests under `../tests/` and `../analysis/tests/`, review before commit,
   and the fact that every reported number is traceable to a `.jtl` or a service log line rather than to
   anything a model said.
5. **Who is responsible for the submission.** Us. That sentence belongs in the statement.

`TODO(Yeo Kai Yuan): check whether the module or the University requires the declaration in a particular form
or place (a specific appendix, a declaration form, a set wording). If it does, that form wins over this
section.`

### 9.2 Team and data

`TODO(Part 5 — Koh Tong Wei): acknowledge the course teaching team for the dataset extract, and state the team
number (10) and the row range used (10000–10999). Slide 1 carries the names and student IDs; do not duplicate
them here.`

### 9.3 Everything the deck rests on that is not a citation

`TODO(Part 5 — Koh Tong Wei): if any hardware was borrowed, or any machine belongs to someone outside the team,
say so here. It costs a line and it is part of describing the test environment honestly — see
../test-environment.md.`

---

## 10. Checklist before this goes on the slide

- [ ] Every `TODO` above is resolved or deliberately deleted, and no `TODO` marker remains in the text that
      goes on the slide.
- [ ] The style is stated on the slide, and every entry follows it.
- [ ] The list is numbered contiguously, in first-citation order, renumbered in **one pass** after Part 4's
      workload sources were added.
- [ ] Every version number is a real captured version, from the table in section 2.
- [ ] Every accessed date is a date somebody actually accessed the page.
- [ ] The Consumer Complaint Database, Ollama, and a licence for **every** candidate model still in the set are
      all present.
- [ ] Section 6 has been checked against `../models/candidates.md` and `../models/models.yaml`, and the two do
      not disagree.
- [ ] Every candidate that was dropped from the set has been removed from section 6, and every substitute that
      was promoted into the set has been added.
- [ ] The Llama `NOTICE` / "Built with Llama" decision has been made and recorded either way.
- [ ] Nothing cited on Slide 3 or Slide 7 is missing from this list, and nothing in this list is uncited.
- [ ] The AI-tool-use statement is written, specific, and names what the tools did **not** do.
