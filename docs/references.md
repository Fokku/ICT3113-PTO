# References and acknowledgements — pre-seeded list for Slide 12

**What this document is for.** It is the reference list Slide 12 ("References and Acknowledgements") is built
from, pre-seeded with every source this repository already uses: the dataset, the tools, and every candidate
model with its licence. It also separates what a licence **requires** us to state from what is merely good
practice, because the brief warns that *"Failing to comply with a licence may be an infringement of
copyright."*

**Owner:** Part 5 — Koh Tong Wei.

**What "done" looks like.** Every source cited anywhere in the deck appears here exactly once, in one
consistent style; the Consumer Complaint Database, Ollama and a licence for every candidate model are all
present; every to-do marker below is resolved; the numbering has been re-run in one pass so it is contiguous; and
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
  after it. The numbers below were settled on 8 October 2026: contiguous, [1]–[30], in document order. Why
  they were not reordered is recorded at the end of section 7.
* Organisation as author where there is no personal author. That is the normal case here.
* A version number wherever a version exists and we know it. Software without a version is not a citation you
  can reproduce.
* An accessed date on every URL. Where a committed document in this repository already establishes the date a
  page was read, that date is used and the document is named. Where it does not, the date is the day the page
  was actually read for this list (8 October 2026 for every page checked while it was compiled) — **never an
  invented one.**

**Why IEEE stands.** The brief asks only for "properly formatted references for all sources used" (Slide 12)
and names no citation style: checked against `assignment-brief.md` on 8 October 2026. No module or lab-group
instruction requiring a different style (APA, Harvard) is recorded in this repository. If one turns up, convert
the whole list rather than mixing two; the content does not change, only the layout does.

---

## 2. A note on versions

The version that belongs in a reference is the version we actually ran, and that is a captured fact, not a
recollection. Every version number below was filled in on 8 October 2026 from these places and nowhere else,
and the entry or the note under it says which:

| Tool | Where the real version is recorded |
|---|---|
| Apache JMeter | `environment/<loadgen-hostname>.txt`, section 6, label `jmeter version`. Also every run's `metadata.json`, key `jmeter_version` |
| Java (JMeter's runtime) | `environment/<loadgen-hostname>.txt`, section 6, label `java (used by JMeter)` — **except** on `kais-macbook-pro`, where that label reads the `java` on the shell's `PATH` (23.0.1). JMeter itself runs on OpenJDK 21.0.12.1, set in its `bin/setenv.sh`: `test-environment.md`, section 2 |
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
[Accessed: 28 September 2026].

*Accessed date from `../workload/workload_model.md`, "Sources", entry 1, where Part 4 read this page.*

*This is the reference the brief names explicitly, and it is not optional: "The Consumer Complaint Database is
published by a US government agency; acknowledge the source in your final document." The brief gives the
address as `www.consumerfinance.gov/data-research/consumer-complaints/`; the entry above adds the scheme.*

**[2]** ICT3113 course teaching team, "ICT3113 Assignment 1 ticket extract (`ict3113_tickets.csv`)," course
extract from [1], released on xSiTe, Week 1.

*The brief prescribes no citation form for the extract (checked 8 October 2026). It describes it as "a course
extract from the Consumer Complaint Database published by the US Consumer Financial Protection Bureau",
"released on xSiTe in Week 1 as a single numbered CSV", and asks only that the CFPB source be acknowledged.
The extract keeps its own entry rather than being folded into [1], because it is the thing we actually used and
section 9.2 acknowledges it by number. It has no public URL; the brief names xSiTe as where it was released.*

*What the deck must say about the data, from the brief: the narratives are "real consumer complaint
narratives, published with consumer consent and with personal information removed at source"; our team uses
rows 10000–10999 of the extract (team 10), and every labelled ticket and every test request comes from those
1,000 rows.*

**What the CFPB asks of a re-user (checked 8 October 2026).** Nothing beyond a requested citation:

* The database page [1] states: "All complaint data we publish is freely available for anyone to use, analyze,
  and build on." The same page warns that the database "is not a statistical sample of consumers' experiences
  in the marketplace". Neither that page nor "How we share complaint data",
  <https://www.consumerfinance.gov/complaint/data-use/>, states a licence or a citation format.
* The CFPB's "Website Privacy Policy and Legal Notices",
  <https://www.consumerfinance.gov/privacy/website-privacy-policy/>, under "Copyright and trademark", states:
  "Information created by the CFPB is in the public domain and you may reproduce, publish, or otherwise use it
  without the Bureau's permission. Please consider appropriate citation to the Bureau as the source." So a
  citation is **requested, not required**. [Accessed: 8 October 2026].
* The same notice adds that "Copyrighted materials created by entities outside of the Bureau also may appear on
  this website". The narratives are written by consumers, not created by the CFPB, and the notice does not say
  which side of that line they fall on. We record this rather than resolve it by assertion. The brief requires
  the acknowledgement regardless, and [1] gives it.

---

## 4. Load generator

**[3]** Apache Software Foundation, "Apache JMeter," version 5.6.3. [Online]. Available:
<https://jmeter.apache.org/>. [Accessed: 8 October 2026].

*Version from `environment/kais-macbook-pro-Loadgen.txt`, section 6 (`jmeter version : 5.6.3`), the load
generator for every reported run. JMeter ran on OpenJDK 21.0.12.1, set in its `bin/setenv.sh`. The capture's
`java (used by JMeter)` line shows 23.0.1 only because it reads the `java` on the shell's `PATH`; see
`test-environment.md`, section 2.*

**[4]** Apache Software Foundation, "Apache JMeter user manual: component reference." [Online]. Available:
<https://jmeter.apache.org/usermanual/component_reference.html#Open_Model_Thread_Group>.
[Accessed: 8 October 2026].

*Cite [4] wherever the deck relies on the **Open Model Thread Group** and its `rate(...) random_arrivals(...)`
schedule — which is Slide 8, because the brief requires the open-loop configuration to be shown. The anchor
`#Open_Model_Thread_Group` is the `id` of that section's heading in the page's HTML, confirmed on 8 October
2026. The section documents the `rate(1/sec) random_arrivals(2 min) rate(3/sec)` schedule syntax, and opens
with "This thread group is experimental, and it might change in the future releases."*

**Licence:** Apache License 2.0 [23]. Verified on 8 October 2026 from the licence file in JMeter's source
repository, <https://github.com/apache/jmeter/blob/master/LICENSE> ("Apache License, Version 2.0, January
2004"). The "License" link on <https://jmeter.apache.org/> points to the ASF's licence page,
<https://www.apache.org/licenses/>. We do not redistribute JMeter, so nothing beyond a correct citation is
owed — see section 8.

---

## 5. Model backend, container platform and service stack

**[5]** Ollama, "Ollama," version 0.34.3. [Online]. Available: <https://ollama.com/>.
[Accessed: 8 October 2026].

*Version from `environment/omarchy-Ollama.txt`, section 5 (`ollama /api/version : {"version":"0.34.3"}`). That
is the service host every reported run was measured on, where Ollama runs in the `ollama/ollama` container.
`../models/models.yaml` records the same version, `ollama_version: "0.34.3"`, against every pinned digest.*

**[6]** Ollama, "LICENSE" (MIT License, "Copyright (c) Ollama"). [Online]. Available:
<https://github.com/ollama/ollama/blob/main/LICENSE>. [Accessed: 23 September 2026].

*Source for [6]: `../models/candidates.md`, "Licences and attribution", section 5, which records this licence
and URL as read on 23 September 2026. The brief names Ollama explicitly as a source that must be referenced.*

**[7]** Ollama, "Ollama model library." [Online]. Available: <https://ollama.com/library>.
[Accessed: 23 September 2026].

*Every factual claim in `../models/candidates.md` about a model's parameter count, default quantisation and
download size was read from this library on that date. Cite it as the source of the Slide 5 table.*

**[8]** Docker Inc., "Docker Engine," version 29.7.2. [Online]. Available: <https://www.docker.com/>.
[Accessed: 8 October 2026].

**[9]** Docker Inc., "Docker Compose," version 5.5.1. [Online]. Available: <https://docs.docker.com/compose/>.
[Accessed: 8 October 2026].

*Versions from `environment/omarchy-Service.txt`, section 4: `docker` (client) 29.7.2, `docker server` 29.7.2,
`docker compose` 5.5.1. These are the service host's, which is where both containers ran.*

*The brief requires the repository to be "sufficient to rebuild and run it with docker compose", so Compose is
a cited tool and not an implementation detail.*

**Licences of [8] and [9], verified 8 October 2026.**

* **Docker Engine:** Apache License 2.0 [23]. <https://docs.docker.com/engine/> states, under "Licensing":
  "Apache License, Version 2.0. See LICENSE for the full license", linking to the Moby project's
  <https://github.com/moby/moby/blob/master/LICENSE>. The `docker` CLI is likewise Apache-2.0:
  <https://github.com/docker/cli/blob/master/LICENSE>.
* **Docker Compose:** Apache License 2.0 [23], <https://github.com/docker/compose/blob/main/LICENSE>.
* **Docker Desktop** is a different licence: Docker's own subscription terms,
  <https://docs.docker.com/subscription-billing/desktop-license/> (reached from
  `docs.docker.com/subscription/desktop-license/`, which now redirects there). That page lists "Personal use"
  and "Education" among the uses for which Docker Desktop is free.

**Which machine had which** (section 4 of each capture file). The service host, `omarchy`, runs Docker Engine
natively on Arch Linux, with no Docker Desktop and no VM (`environment/omarchy-Service.txt`;
`test-environment.md`, section 2). The load generator, `kais-macbook-pro`, **has Docker Desktop installed**
(`environment/kais-macbook-pro-Loadgen.txt`: Docker 27.5.1, Compose `v2.32.4-desktop.1`, daemon not reachable
at capture). It was used there for rehearsals, but was quit before the reported runs and ran nothing measured
(`run-log.md`). Docker Desktop was also on both superseded rehearsal machines, neither of which took part in a
reported run: `tw` ran the service under Docker Desktop on Windows, and `kthgoat`'s `docker version` showed a
Docker Desktop server (`run-log.md`, "Environment as rehearsed" and "Open items"). All of that use was for this
coursework. That it falls under the free "Education" or "Personal use" categories is our reading of Docker's
page, not something Docker has confirmed. See section 8.

**[10]** S. Ramírez, "FastAPI," version 0.142.4. [Online]. Available: <https://fastapi.tiangolo.com/>.
[Accessed: 8 October 2026].

**[11]** Encode OSS Ltd., "Uvicorn," version 0.54.0. [Online]. Available: <https://uvicorn.dev/>.
[Accessed: 8 October 2026].

*Uvicorn's address changed. The previously listed `https://www.uvicorn.org/` did not resolve (DNS failure) on
8 October 2026. `https://uvicorn.dev/` is the "Homepage" in Uvicorn 0.54.0's own PyPI metadata, and it
answered.*

**[12]** D. R. Hipp and the SQLite developers, "SQLite," version 3.46.1. [Online]. Available: <https://www.sqlite.org/>.
[Accessed: 8 October 2026].

*The service uses Python's standard-library `sqlite3` module, so SQLite is used as bundled with the container's
Python rather than installed separately. Say so in one clause on the slide: it is why there is no SQLite entry
in `../requirements.txt`. SQLite's copyright page, <https://www.sqlite.org/copyright.html> [Accessed: 8 October
2026], states that "All of the code and documentation in SQLite has been dedicated to the public domain by the
authors" and that "Anyone is free to copy, modify, publish, use, compile, sell, or distribute the original
SQLite code ... for any purpose, commercial or non-commercial, and by any means." It asks for **nothing**: no
notice and no attribution. The only thing it offers is an optional, paid "Warranty of Title" from Hwaci, for
organisations that need legal assurance of the public-domain dedication.*

**[13]** Python Software Foundation, "Python," version 3.11.17. [Online]. Available: <https://www.python.org/>.
[Accessed: 8 October 2026].

*Versions of [10]–[13] were read on 8 October 2026 from the running service container on the service host,
`ict3113-triage` (image `ict3113/triage:baseline`, image ID `sha256:2cfd2718faa4…`). The commands were
`docker exec ict3113-triage pip freeze` (`fastapi==0.142.4`, `uvicorn==0.54.0`),
`docker exec ict3113-triage python --version` (`Python 3.11.17`) and
`docker exec ict3113-triage python -c "import sqlite3; print(sqlite3.sqlite_version)"` (`3.46.1`).
`../requirements.txt` declares floors only (`fastapi>=0.115`, `uvicorn[standard]>=0.30`), so these are the
versions in the image that was measured, not versions a fresh rebuild is guaranteed to reproduce.*

*Licences of [10], [11] and [13], verified 8 October 2026. FastAPI: MIT License, "Copyright (c) 2018 Sebastián
Ramírez", <https://github.com/fastapi/fastapi/blob/master/LICENSE>; PyPI gives `MIT` as the licence expression
for 0.142.4. Uvicorn: BSD 3-Clause, "Copyright © 2017-present, Encode OSS Ltd",
<https://github.com/Kludex/uvicorn/blob/main/LICENSE.md>; PyPI gives `BSD-3-Clause` for 0.54.0. Python: the
"PSF LICENSE AGREEMENT FOR PYTHON 3.11.17", <https://docs.python.org/3.11/license.html>, which names exactly
the patch version we ran.*

### 5.1 Secondary dependencies — include only if the deck cites them

Twelve slides is not much room, so cite these only where a slide actually rests on them; otherwise leave them
in the repository's `requirements.txt` and `requirements-dev.txt`, which are committed and are themselves
evidence.

**Checked against the deck as drafted in `../slides/build_deck.js` on 8 October 2026.** No slide names httpx,
Pydantic, pandas or Matplotlib. One slide does show something drawn by one of them: Slide 3 carries the
ticket-length histogram `../workload/output/length_histogram.png`, cropped, not redrawn. The PNG's own
`Software` metadata reads `Matplotlib version3.11.2, https://matplotlib.org/`. Matplotlib is therefore promoted,
with version and licence, to entry **[30]**. That entry sits at the end of section 7 so that the list stays
contiguous in document order, which is the order Slide 12 prints it in. httpx, Pydantic and pandas are not
promoted: the deck cites none of them, and the numbers they help produce are cited on each slide by the
committed file they came from.

---

## 6. Candidate models and their licences

The four candidates, their licences and their URLs are carried across **exactly** from `../models/candidates.md`
and `../models/models.yaml`, which record where each fact was read and on what date. Slide 5 reports the tag
and digest; this section reports the licence.

> **The shortlist is confirmed.** Yeo Kai Yuan confirmed the four candidates on 2 October 2026 and settled
> the quantisation question by pinning the 4-bit 1B build, `llama3.2:1b-instruct-q4_K_M`, in place of the bare
> `llama3.2:1b` tag (which Ollama ships at Q8_0). All four candidates now share Q4_K_M quantisation, so the
> within-family comparison on Slide 5 varies size alone. `../models/candidates.md` remains the authority for
> every licence claim below: if anything here no longer matches that file, change **this** file, and do not
> let the two diverge silently.

> **The digests are pinned.** All four `pinned:` blocks in `../models/models.yaml` were written by
> `../scripts/pull_and_pin_models.sh` on 2 October 2026 (`pulled_at` 11:56:37Z for the 1B, 11:57:31Z for the
> other three). Each records `ollama_version: "0.34.3"`, the version the measured service host reports
> (`environment/omarchy-Ollama.txt`). Slide 5 must report the digests from that file, not the short web digests
> in `../models/candidates.md`, which are cross-checks only. The cross-check holds for the one candidate whose
> tag changed: the short digest in [14], `22bc6b92eb01`, is the first twelve hex digits of the pinned
> `sha256:22bc6b92eb0160c4…` digest.

### 6.1 Meta Llama 3.2 1B Instruct and 3B Instruct — `llama3.2:1b-instruct-q4_K_M`, `llama3.2:3b`

**[14]** Ollama, "llama3.2:1b-instruct-q4_K_M" (Meta Llama 3.2 1B Instruct; 1.24B parameters; quantisation
Q4_K_M; 808 MB; short digest 22bc6b92eb01). [Online]. Available:
<https://ollama.com/library/llama3.2:1b-instruct-q4_K_M>. [Accessed: 2 October 2026].

*This is an explicit quantisation tag, not the family's default 1B tag: the bare `llama3.2:1b` is Q8_0. The full
list of builds is on the tags page, <https://ollama.com/library/llama3.2/tags> [Accessed: 2 October 2026].*

**[15]** Ollama, "llama3.2:3b" (Meta Llama 3.2 3B Instruct; 3.21B parameters; default quantisation Q4_K_M).
[Online]. Available: <https://ollama.com/library/llama3.2:3b>. [Accessed: 23 September 2026].

**[16]** Meta Platforms, Inc., "LLAMA 3.2 COMMUNITY LICENSE AGREEMENT," 25 September 2024. [Online].
Available: <https://github.com/meta-llama/llama-models/blob/main/models/llama3_2/LICENSE>.
[Accessed: 23 September 2026].

**[17]** Meta Platforms, Inc., "Llama 3.2 licence text as shipped by Ollama." [Online]. Available:
<https://ollama.com/library/llama3.2:3b/blobs/fcc5a6bec9da>. [Accessed: 23 September 2026].

**[18]** Meta Platforms, Inc., "Llama 3.2 Acceptable Use Policy," incorporated by reference into [16].
[Online]. Available: <https://ollama.com/library/llama3.2:3b/blobs/a70ff7e570d9>. [Accessed: 8 October 2026].

*Reached from the Ollama model page [15], which ships the policy as the second "license" layer of
`llama3.2:3b`, beside the licence text [17]. The same text is in Meta's own repository at
<https://github.com/meta-llama/llama-models/blob/main/models/llama3_2/USE_POLICY.md> [Accessed: 8 October
2026]. **Could not verify** the address the policy itself gives for its most recent copy,
`https://www.llama.com/llama3_2/use-policy`. On 8 October 2026 it redirected (301) to `developer.meta.com`,
then (302) to `dev.meta.ai`, which answered HTTP 404, so the policy is not readable at that address. That is
why [18] cites the copies above.*

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

*Covers `granite4:3b` [19] and `qwen2.5:7b` [21], and also JMeter [3] and Docker Engine and Compose [8], [9],
whose Apache-2.0 licences were verified on 8 October 2026 (sections 4 and 5).*

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

The entries below are transcribed from the "Sources" list at the end of `../workload/workload_model.md`
(Part 4 — Toh Si Pei), with the accessed dates recorded there. Source 1 of that list is the Consumer Complaint
Database, already entry [1] above.

One source is our own, because the ticket-length distribution is measured rather than cited:

**[26]** This work, "Ticket length distribution of team 10's 1,000 rows," produced by
`python workload/scripts/ticket_length_stats.py --team-rows data/team_rows.csv`, output under
`../workload/output/`.

*Note on [26]: not an external source. It is cited as our own measurement so the slide distinguishes it from
the published figures around it.*

**[27]** US Consumer Financial Protection Bureau, "Consumer Response Annual Report: January 1 – December 31,
2025," March 2026. [Online]. Available:
<https://www.consumerfinance.gov/data-research/research-reports/2025-consumer-response-annual-report/>.
[Accessed: 28 September 2026].

*Published figures used: about 5,984,100 complaints sent to companies in 2025; "more than 4,000 companies";
about 5.1 million of 6.6 million complaints concerning three nationwide consumer reporting agencies.*

**[28]** CNA, "IN FOCUS: What happens when you contact a bank or telco customer care centre?," 2024. [Online].
Available:
<https://www.channelnewsasia.com/singapore/in-focus-what-happens-when-you-contact-bank-or-telco-customer-care-centre-4735346>.
[Accessed: 28 September 2026].

*Used only as an analogous proxy for agent activity pace (30–40 calls per officer per day, at one Singapore
bank). It does not measure searches against a ticket system.*

**[29]** W. Whitt, "What You Should Know About Queueing Models To Set Staffing Requirements in Service
Systems," Columbia University, 2007. [Online]. Available: <https://www.columbia.edu/~ww2040/shorter041907.pdf>.
[Accessed: 28 September 2026].

*Used only as evidence that a financial-services call centre has time-of-day variation in arrivals. It does
not support any particular peak multiplier.*

**Which workload figures are estimates rather than published.** Only the base complaint volume (5,984,100 per
year, [27]) is read directly from a source. The modelled firm's share (0.025%, an equal share across 4,000
companies), the derived volumes (1,496 tickets per year, 0.719 per opening hour), the search rate (5 searches
per agent per hour, so 0.167 per minute) and the peak factor (2×, giving 0.024 tickets per minute at peak) are
all estimates with stated methods in `../workload/workload_model.md`. Slide 3 must say so.

**Checked against the workload model and Slide 3 on 8 October 2026.**

* **Every workload source is here.** The "Sources" list at the end of `../workload/workload_model.md` has four
  entries. Its source 1 is [1], source 2 is [27], source 3 is [28] and source 4 is [29], each with the
  accessed date that file records (28 September 2026). The measured ticket-length distribution is [26].
* **Nothing on Slide 3 is missing, and nothing here is unused.** Slide 3, as drafted in
  `../slides/build_deck.js`, cites the annual report, CNA and Whitt, and shows the measured length
  distribution as a chart drawn with Matplotlib [30]. Every entry in this section appears on it.
* **Numbering.** The list is contiguous, [1]–[30], in document order. It was **not** reordered into strict
  first-citation order, because Slide 3 is the only slide that cites by number, and reordering would mean
  restructuring this document. **One mismatch must be fixed on the deck side:** Slide 3's draft writes its
  short forms with the workload model's own source numbers, "[2] CFPB 2025 Consumer Response Annual Report;
  [3] CNA (2024); [4] Whitt (2007)", in its source line and again in three of its cards. In this list, [2], [3] and
  [4] are the course extract and the two JMeter entries. On Slide 3 those short forms must read [27], [28] and
  [29], or Slide 3 and Slide 12 disagree.

One software entry closes the list. It belongs with Slide 3, because it drew the ticket-length chart of [26]
that the slide shows (see section 5.1):

**[30]** The Matplotlib Development Team, "Matplotlib," version 3.11.2. [Online]. Available:
<https://matplotlib.org/>. [Accessed: 8 October 2026].

*Version from the `Software` metadata of `../workload/output/length_histogram.png` ("Matplotlib version3.11.2,
https://matplotlib.org/"), i.e. the build that drew the committed chart. Licence: the Matplotlib License
Agreement, between the user and "the Matplotlib Development Team", which the project describes as "based on the
PSF license" (<https://matplotlib.org/stable/project/license.html>, accessed 8 October 2026; PyPI classifier
for 3.11.2: "Python Software Foundation License"). Its notice-retention clause applies to Matplotlib itself and
derivative versions of it, which we neither ship nor make. The project also asks that a scientific publication
Matplotlib contributed to cite J. D. Hunter, "Matplotlib: A 2D graphics environment," Computing in Science &
Engineering, vol. 9, no. 3, pp. 90–95, 2007 (<https://matplotlib.org/stable/project/citing.html>, accessed
8 October 2026).*


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
| CFPB Consumer Complaint Database [1] | Nothing, as a condition. The CFPB states that information it creates "is in the public domain", and asks re-users to "consider appropriate citation to the Bureau as the source"; the database page says the data "is freely available for anyone to use, analyze, and build on" (section 3, checked 8 October 2026). The **brief** requires the source to be acknowledged regardless of what the licence says, so the acknowledgement is mandatory for us either way | Naming the extract and our row range (10000–10999); stating that the narratives are published with consumer consent and with personal information removed at source. Both are honesty about provenance rather than licence compliance |
| Apache JMeter [3] | Nothing, as we neither modify nor redistribute it | A correct citation with the version we ran |
| Ollama [5], [6] | The MIT licence requires its copyright and permission notice to be included in copies or substantial portions of the software. We ship neither, so nothing is triggered | Crediting Ollama by name — which the brief requires of us anyway — and recording the exact version with the results |
| Docker [8], [9] | The service host uses Docker Engine natively on Arch Linux, not Docker Desktop. Docker Engine (Moby, and the `docker` CLI) and Docker Compose are both Apache-2.0 [23] (verified 8 October 2026, section 5); we neither modify nor redistribute them, so nothing is owed. **Separately:** the load generator, `kais-macbook-pro`, has Docker Desktop installed, which is under Docker's own subscription terms (<https://docs.docker.com/subscription-billing/desktop-license/>). It was quit for every reported run and ran nothing measured. Those terms list "Personal use" and "Education" among the free uses, which as we read them covers this coursework | A correct citation with the version |
| FastAPI [10], Uvicorn [11], SQLite [12], Python [13], Matplotlib [30] | FastAPI (MIT) and Uvicorn (BSD 3-Clause) require their copyright notice and licence text to be kept with copies or redistributions of the software. Python's PSF licence and Matplotlib's PSF-based licence require their licence and copyright notice to be retained in the software "alone or in any derivative version". SQLite is public domain and asks for nothing. The repository vendors none of them (the image is built from `../Dockerfile` by whoever runs `docker compose`), and a chart Matplotlib drew is not a copy of Matplotlib, so nothing is triggered | A correct citation with the version we ran |
| `granite4:3b` [19], `qwen2.5:7b` [21] — Apache-2.0 [23] | Section 4 of the licence binds a **redistributor**: retain copyright, patent, trademark and attribution notices; include a copy of the licence; carry forward any `NOTICE` file; and state significant changes. We redistribute neither model and modify neither, so what we owe in practice is a **correct citation** | Attributing the models to their publishers — the **IBM Granite Team** and the **Qwen Team, Alibaba Cloud**. IBM's model card asks for this explicitly. It costs nothing; do it |
| `llama3.2:1b-instruct-q4_K_M`, `llama3.2:3b` [14]–[18] — Llama 3.2 Community License [16] | On distributing the Llama Materials **or "a product or service that contains any of them"** (section 1.b): (1) provide a copy of the agreement to the recipient; (2) **prominently display "Built with Llama"** on a related website, user interface, blogpost, about page or product documentation; (3) retain, in a `NOTICE` text file distributed with the copies, the notice `Llama 3.2 is licensed under the Llama 3.2 Community License, Copyright © Meta Platforms, Inc. All Rights Reserved.`; (4) prefix the name of any *distributed* model created, trained or fine-tuned from the Materials with `Llama`; (5) comply with applicable law and the Acceptable Use Policy [18]. Clause 2 additionally requires a separate licence from Meta for a licensee with more than 700 million monthly active users in the month before the Llama 3.2 release date | Clause (4) plainly does not apply: we neither train nor distribute a derivative model. Whether (1)–(3) bind a public repository for a service that *calls* a Llama model is the genuinely unclear part — it turns on the phrase "a product or service that contains any of them", which is a lawyer's question and not ours. **The cheap precaution is to comply anyway**: a `NOTICE` file with the sentence above, and a "Built with Llama" line in the repository README. One file, and the question goes away |

**Decision: we comply.** Yeo Kai Yuan decided on 2 October 2026 to take the cheap precaution rather than argue
the ambiguity. The repository root carries a `NOTICE` file with the Llama 3.2 notice above, and the README's
"Licences and attribution" note carries the line "Built with Llama" and points at it.

**Slide 12 carries the "Built with Llama" line too**, because both Llama models are candidates. The clause names
"a related website, user interface, blogpost, about page or product documentation"; a submitted report is the
closest thing we have to product documentation, and the slide costs one line. See `../slides/outline.md`,
Slide 12.

---

## 9. Acknowledgements

### 9.1 AI tool use

The brief is explicit: *"AI coding tools are permitted and expected throughout. The build is a few hours' work
with an agent, and that is accepted. AI-generated code is typically correct but performance-naive, and an agent
will not label your test data, run your load tests, or make your recommendation. The assessment targets
measurement, interpretation, and judgement."*

So declaring it costs nothing and not declaring it looks worse than the truth. Write a short, specific
statement rather than a disclaimer.

**Statement.**

1. **Tools.** Anthropic's Claude, used through the Claude Code command-line agent. The 8 October 2026 session
   ran Claude Opus 5.5; the model versions of earlier sessions were not recorded.
2. **What it was used for.** Most of the code and much of the documentation: the triage service (`service/`)
   and its tests, the Docker and Compose files, the JMeter plans, the harness and freeze-gate scripts
   (`scripts/`), the analysis scripts (`analysis/`), the deck builder (`slides/`), and the templates and first
   drafts of the documents under `docs/`, `workload/` and `labelling/`. On 8 October it also merged the
   team's work, drafted the prediction record with Yeo Kai Yuan (disclosed in its §0, with the entries that
   are not blind), ran the benchmark campaign on our two machines, wrote the test-environment description from
   the capture files, verified the references in this file, and drafted the interpretation and recommendation
   text on Slides 9–11 from the analysis outputs, at Yeo Kai Yuan's direction.
3. **What it was not used for.** It assigned no golden-set label: both label sheets were written by the two
   named labellers, independently, and every disagreement was resolved by them in discussion
   (`../labelling/`). It supplied no measurement: every latency, throughput, error and accuracy figure comes
   from a JMeter `.jtl` file or a service log line produced by the system under test, through the analysis
   scripts. No model outside the four local candidates saw a ticket narrative.
4. **How the output was checked.** The test suites under `../tests/` and `../analysis/tests/` (run before every
   commit); `scripts/freeze_gate.py` before any reported run; `analysis/reconcile.py`, which joins every JMeter
   sample to its service log line; and the rule that every figure on a slide is read by
   `../slides/collect_deck_data.py` from a committed file rather than typed.
5. **Responsibility.** The submission, and every claim and number in it, is the team's responsibility.

**Form of the declaration.** The brief permits AI coding tools ("permitted and expected throughout") and
prescribes no declaration form or wording; we know of no module form that would replace this section.

### 9.2 Team and data

We thank the ICT3113 teaching team for preparing and releasing the ticket extract [2] from the US Consumer
Financial Protection Bureau's Consumer Complaint Database [1]. We are Team 10, and every labelled ticket and
every test request in this work comes from rows 10000–10999 of that extract. (Slide 1 carries the names and
student IDs; they are not duplicated here.)

### 9.3 Everything the deck rests on that is not a citation

No hardware was borrowed from outside the team. Both machines are Yeo Kai Yuan's own. The service host — the
triage service and Ollama, in Docker — is his desktop, `omarchy` (AMD Ryzen 9 5900X, Arch Linux, Docker Engine
native). The load generator is his laptop, `kais-macbook-pro`, a MacBook Pro (Apple M3 Pro), captured with
`scripts/capture_env.sh --role loadgen` on 8 October 2026 (`environment/kais-macbook-pro-Loadgen.txt`). Both
are personal machines, not lab or server hardware, which is part of describing the test environment honestly —
see `test-environment.md`.

---

## 10. Checklist before this goes on the slide

- [ ] Every to-do marker above is resolved or deliberately deleted, and none remains in the text that goes on
      the slide. (`../slides/collect_deck_data.py` refuses a final build while the literal word appears anywhere
      in this file, so do not write it in prose either.)
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
- [x] The Llama `NOTICE` / "Built with Llama" decision has been made and recorded either way (section 8: yes).
- [ ] Nothing cited on Slide 3 or Slide 7 is missing from this list, and nothing in this list is uncited.
- [ ] The AI-tool-use statement is written, specific, and names what the tools did **not** do.
