# Candidate models — proposed shortlist

**What this document is for.** It proposes the three-to-five candidate models required by Step 4 of the
brief, records the evidence behind each choice (tag, parameter count, default quantisation, download size,
licence and the URL each fact came from), and records the candidates we looked at and rejected. Slide 5
("Candidate Models") and the model half of Slide 12 ("References and Acknowledgements") are built from this
file together with the digests in `models.yaml`.

**Owner:** Yeo Kai Yuan — the candidate shortlist and the pins.
The other two halves of Step 4 (the requirements and the prediction record) are owned elsewhere; see
`../workload/requirements.md` and `../predictions/prediction_record.md`.

**What "done" looks like.** Yeo Kai Yuan has struck out the confirmation marker below; every row of the
shortlist table has a digest in `models.yaml` written by `../scripts/pull_and_pin_models.sh`; and every
licence named here appears in `../docs/references.md`.

**Feeds:** Slide 5 (candidate models and size classes), Slide 12 (model licences and acknowledgements).

---

> ## Decisions — confirmed by Yeo Kai Yuan, 8 October 2026
>
> 1. **The set: confirmed as proposed.** Four candidates in three size classes (~1B, ~3B twice, ~7.6B):
>    `llama3.2:1b`, `llama3.2:3b`, `granite4:3b`, `qwen2.5:7b`. Four models times three arrival rates times
>    three runs, plus the mixed-load and accuracy tests, fits one overnight campaign on the service host.
> 2. **The 1B quantisation asymmetry: accepted and stated, not corrected.** We pin the default
>    `llama3.2:1b` build (**Q8_0**), not `llama3.2:1b-instruct-q4_K_M`. The default build is what a client
>    gets when they ask Ollama for "llama3.2:1b", so it is the honest thing to measure; the cost is that the
>    1B-versus-3B comparison varies bits per weight as well as parameter count. Slide 5 says so in one line,
>    and the effect is predicted in `../predictions/prediction_record.md`: the 1B model is heavier per
>    parameter than the others, which narrows its speed advantage.
> 3. **The Llama notice: added as a precaution.** `../NOTICE` carries the Llama 3.2 notice sentence, and the
>    README carries "Built with Llama". It costs one file and removes the question.
> 4. **Substitutions: none.** All four candidates serve on the service host; neither substitute was needed.
>    The pins are the digests that `../scripts/pull_and_pin_models.sh` wrote into `models.yaml`.

---

## Why this set, as a set

The client's constraint decides the shape of the set before any model is named: CPU only, on commodity
hardware, with no data leaving their infrastructure. That rules out most of the Ollama library. What is
left is roughly 0.3B to 8B at four-bit quantisation, and the engagement question is where inside that
band the client should sit. So the set is built to make the size trade-off *measurable*, and each member
is in it for one reason:

| Slot | Candidate | The question this member exists to answer |
|---|---|---|
| Floor | `llama3.2:1b` | How cheap can we go before instruction-following collapses? This is the fast end of the trade-off and the member most likely to fail the accuracy requirement. |
| Middle | `llama3.2:3b` | Same family, same tokeniser, same chat template, same licence as the floor — so the difference between these two rows is (almost) size alone. This is the controlled comparison in the set. |
| Middle, licence-clean | `granite4:3b` | What does a permissively-licensed alternative cost us in the *same* size class? If it matches `llama3.2:3b`, the client's licence problem disappears for free. |
| Ceiling | `qwen2.5:7b` | The largest model that is honestly servable on commodity CPU. It is in the set to be slow. If it is not materially more accurate than the 3B class, the recommendation writes itself. |

Two deliberate absences, both argued in "Considered and rejected" rather than passed over in silence:

* **No reasoning/"thinking" model.** The current Qwen3 and Qwen3.5 families are the obvious Apache-2.0
  choices by capability, and they are excluded on purpose. Qwen3 has "thinking capabilities enabled" by
  default and emits a `<think>...</think>` block before its answer
  ([model card](https://huggingface.co/Qwen/Qwen3-8B)). Our prompt template is fixed and does not disable
  it, `NUM_CTX` is 4096, and `service/categories.py` deliberately performs no semantic recovery — so those
  replies would mostly land in `UNPARSEABLE` while consuming the most CPU time of any candidate. A
  thinking model is a measurement of our prompt, not of the model.
* **Nothing above ~8B.** A 7-8B model at four bits on CPU is slow but feasible. 12B upwards is not a
  serious proposal for this client's hardware, so the shortlist does not pad itself with one. Saying so is
  the finding.

The set spans **three** size classes, which exceeds the brief's minimum of two. Two members sit in the
3-4B class on purpose: that is where we expect the client's decision actually to be made, and holding size
constant while varying vendor and licence is the more useful of the two comparisons available to us there.

---

## The shortlist

All figures in this table were read from ollama.com on **23 September 2026** and are cited below. Download
sizes are Ollama's own rounded display values; treat them as approximate until the pull script has written
real byte counts into `models.yaml`.

| Model | Ollama tag | Parameters | Default quantisation | Approx. download size | Licence | Where published (URL) | Why this candidate (one line) |
|---|---|---|---|---|---|---|---|
| Meta Llama 3.2 1B Instruct | `llama3.2:1b` | 1.24B | **Q8_0** | 1.3 GB | Llama 3.2 Community License (custom; not OSI-approved) | <https://ollama.com/library/llama3.2:1b> | The floor of the trade-off: the fastest thing we will serve, and the member most exposed to short-output disobedience. |
| Meta Llama 3.2 3B Instruct | `llama3.2:3b` | 3.21B | Q4_K_M | 2.0 GB | Llama 3.2 Community License (custom; not OSI-approved) | <https://ollama.com/library/llama3.2:3b> | Same family as the floor, one size class up, so the pair isolates the effect of size within a fixed prompt and template. |
| IBM Granite 4.0 Micro | `granite4:3b` | 3.4B | Q4_K_M | 2.1 GB | Apache License 2.0 | <https://ollama.com/library/granite4:3b> | The licence-clean comparator in the 3-4B class: tells the client what Apache-2.0 costs them, if anything. |
| Alibaba Qwen2.5 7B Instruct | `qwen2.5:7b` | 7.62B | Q4_K_M | 4.7 GB | Apache License 2.0 | <https://ollama.com/library/qwen2.5:7b> | The ceiling: the largest CPU-feasible candidate, instruction-tuned and with no thinking mode to disable. |

Sources for the table, per row:

* `llama3.2:1b` — parameters 1.24B, quantisation Q8_0, 1.3 GB, licence "LLAMA 3.2 COMMUNITY LICENSE
  AGREEMENT": <https://ollama.com/library/llama3.2:1b>
* `llama3.2:3b` — parameters 3.21B, quantisation Q4_K_M, 2.0 GB, same licence:
  <https://ollama.com/library/llama3.2:3b>
* `granite4:3b` — parameters 3.4B, quantisation Q4_K_M, 2.1 GB, licence "Apache License Version 2.0",
  and the note that this tag is the **dense** build (the `-h` tags are the hybrid Mamba-2 builds):
  <https://ollama.com/library/granite4:3b>; family page and 2 October 2025 release date:
  <https://ollama.com/library/granite4>
* `qwen2.5:7b` — parameters 7.62B, quantisation Q4_K_M, 4.7 GB, licence "Apache License Version 2.0":
  <https://ollama.com/library/qwen2.5:7b>; upstream card confirming 7.61B and apache-2.0:
  <https://huggingface.co/Qwen/Qwen2.5-7B-Instruct>

### Digests are not pinned yet

**No digest in this document is a pin.** The only digests that count are the ones
`../scripts/pull_and_pin_models.sh` writes into `models.yaml` after pulling against the Ollama host we
actually measure on, and those are what Slide 5 reports. Until that script has run, every download size
and every digest in this repository is unverified.

For cross-checking only, these are the short manifest digests displayed on ollama.com on 23 September
2026. If the script writes a digest whose first twelve characters differ from these, the library has moved
since we wrote this file — which is useful to know, but is not by itself a problem:

| Tag | Short digest observed on ollama.com, 23 Sep 2026 | Source |
|---|---|---|
| `llama3.2:1b` | `baf6a787fdff` | <https://ollama.com/library/llama3.2/tags> |
| `llama3.2:3b` | `a80c4f17acd5` | <https://ollama.com/library/llama3.2/tags> |
| `granite4:3b` | `89962fcc7523` | <https://ollama.com/library/granite4/tags> |
| `qwen2.5:7b` | `845dbda0ea48` | <https://ollama.com/library/qwen2.5:7b> |

Note for Slide 5: `granite4:3b` and `granite4:micro` resolve to the same digest, and `llama3.2:3b` and
`llama3.2:latest` resolve to the same digest
(<https://ollama.com/library/granite4/tags>, <https://ollama.com/library/llama3.2/tags>). Report the
explicit size tags, never `latest`, because `latest` is a moving target.

### The Q8_0 problem

This is the one place where the shortlist is not clean, and it should be stated on the slide rather than
hidden. Ollama's default build for `llama3.2:1b` is **Q8_0** (1.3 GB), while the default for
`llama3.2:3b` is **Q4_K_M** (2.0 GB) — both read from the pages cited above. So the 1B-versus-3B
comparison varies parameter count *and* bits per weight, and the 1B model is carrying roughly twice the
bytes per parameter that the 3B model is. On a CPU, where inference is memory-bandwidth bound, that
narrows the speed gap we are trying to expose.

There is a four-bit build of the 1B available: `llama3.2:1b-instruct-q4_K_M`, 808 MB, short digest
`22bc6b92eb01` (<https://ollama.com/library/llama3.2/tags>). Pinning that instead would hold quantisation
constant across the Llama pair at the cost of a less obvious tag on the slide.

**Decision (8 October 2026):** we keep the default `llama3.2:1b` (Q8_0) and state the asymmetry on Slide 5;
`MODEL_TAG` in `.env.example`, `models.yaml` and Slide 5 all name `llama3.2:1b`.

### What we are *not* writing here

The per-candidate expected accuracy on the golden set, the expected single-request latency on our
hardware, and the expected bottleneck all belong in `../predictions/prediction_record.md`, which is frozen
under the `golden-freeze` tag before the first benchmark run. They are deliberately absent from this file:
this document chooses candidates, it does not predict how they will perform, and it contains no accuracy or
latency figure of any kind.

---

## Licences and attribution

This section is written to be sufficient on its own to build `../docs/references.md` and Slide 12. For
each licence: what it is, where its text is, whether it is commercially usable by a financial services
company, and what attribution it *actually* requires — as distinct from what is merely polite.

**The client's position matters here.** They are a commercial financial services company deploying the
model on their own infrastructure for internal ticket routing. They are not redistributing model weights
and not offering the model to third parties. Most attribution clauses are written around *distribution*,
so whether they bite at all depends on that distinction. Where it is genuinely unclear we say so; it is
not our call to make.

### 1. Llama 3.2 Community License — `llama3.2:1b`, `llama3.2:3b`

* **Licence name:** LLAMA 3.2 COMMUNITY LICENSE AGREEMENT, dated 25 September 2024.
* **Text (canonical, accessible):**
  <https://github.com/meta-llama/llama-models/blob/main/models/llama3_2/LICENSE>
* **Text as shipped by Ollama:** <https://ollama.com/library/llama3.2:3b/blobs/fcc5a6bec9da>
* **Incorporated by reference:** the Llama 3.2 Acceptable Use Policy, named on the Ollama model page
  (<https://ollama.com/library/llama3.2:3b>).
* **Commercially usable?** Yes, subject to conditions, but **this is not an open-source licence** and it
  is not OSI-approved. For a compliance-bound client, "custom licence with an acceptable use policy
  attached" is a different procurement conversation from "Apache 2.0", and that difference is a finding of
  this engagement rather than a footnote.
* **Attribution the licence actually requires**, on distributing the Llama Materials or "a product or
  service that contains any of them" (section 1.b):
  1. provide a copy of the agreement to the recipient;
  2. **prominently display "Built with Llama"** on a related website, user interface, blogpost, about page
     or product documentation;
  3. retain, in a `NOTICE` text file distributed with the copies, the notice:
     `Llama 3.2 is licensed under the Llama 3.2 Community License, Copyright (c) Meta Platforms, Inc. All Rights Reserved.`
     (the copyright symbol is a literal `©` in the licence text);
  4. if the Materials are used to create, train or fine-tune a *distributed* AI model, prefix that model's
     name with `Llama`;
  5. comply with applicable law and the Acceptable Use Policy.
* **Commercial threshold (section 2):** if, on the Llama 3.2 release date, the licensee's products or
  services had more than **700 million monthly active users** in the preceding calendar month, a separate
  licence must be requested from Meta, which Meta may grant at its sole discretion. Our client is nowhere
  near that threshold, so this clause does not bind them — but it is the clause that makes the licence
  something other than a permissive one, and it is worth one line on the slide.
* **Does it bind *us*, for this assignment?** Unclear, honestly. We do not redistribute the weights: our
  repository contains a service and a tag, and the weights are pulled by the marker or by the client from
  Ollama. Clause 4 (the `Llama` name prefix) plainly does not apply, because we do not train or distribute
  a derivative model. Whether publishing a public GitHub repository for a service that calls a Llama model
  counts as making available "a product or service that contains any of them" is a lawyer's question.
  **Recommended precaution:** add a `NOTICE` file with the sentence above and a "Built with Llama" line to
  the README. It costs one file and removes the question.
  **Decision (8 October 2026): yes.** `../NOTICE` and a "Built with Llama" line in `../README.md` were
  added.
* **Could not verify:** the canonical licence URL printed in the licence text itself,
  <https://www.llama.com/llama3_2/license/>, redirected on 23 September 2026 through
  `developer.meta.com` to a Meta developer **login page**, so the licence text is not publicly readable
  at that address. Cite the GitHub copy and the Ollama licence blob instead, and say in the references
  that the llama.com address now requires sign-in.

### 2. Apache License 2.0 — `granite4:3b`, `qwen2.5:7b`

* **Licence name:** Apache License, Version 2.0, January 2004.
* **Text:** <https://www.apache.org/licenses/LICENSE-2.0>
* **As stated for each model:** "Apache License Version 2.0, January 2004" appears on both
  <https://ollama.com/library/granite4:3b> and <https://ollama.com/library/qwen2.5:7b>; and on the
  upstream cards <https://huggingface.co/ibm-granite/granite-4.0-micro> (licence `apache-2.0`) and
  <https://huggingface.co/Qwen/Qwen2.5-7B-Instruct> (licence `apache-2.0`).
* **Commercially usable?** Yes, unconditionally for our purposes. OSI-approved, patent grant included, no
  field-of-use restriction and no user-count threshold. For this client this is the cleanest answer
  available, and it is the reason two of the four candidates are Apache-2.0.
* **Attribution the licence actually requires** (section 4): on redistribution of the work or derivative
  works, retain copyright, patent, trademark and attribution notices; include a copy of the licence; carry
  forward any `NOTICE` file the original supplied; and state significant changes. Since we redistribute
  neither model, what we owe in practice is a correct citation. Attribute the models to their publishers:
  the **IBM Granite Team** for Granite 4.0 Micro, and the **Qwen Team, Alibaba Cloud** for Qwen2.5.
* **Requested (not licence-mandated) attribution:** IBM's model card asks that Granite be cited to the
  Granite Team, IBM (<https://huggingface.co/ibm-granite/granite-4.0-micro>). Cite it; it is free.
* **Could not verify:** nothing material. Note only that Ollama's `mistral` family page says "Apache
  license" without a version number (<https://ollama.com/library/mistral>), which is why that model is a
  substitute rather than a candidate — see the rejection list.

### 3. Qwen Research License — the trap we avoided (no candidate uses it)

This is a genuine commercial finding and belongs on Slide 12 or Slide 5, not in a footnote:
**within the Qwen2.5 family, individual sizes carry different licences.**

* Ollama's own family page states it plainly: "all models except the 3B and 72B are released under the
  Apache 2.0 license, while the 3B and 72B models are under the Qwen license"
  (<https://ollama.com/library/qwen2.5>).
* The 3B instruct card carries the licence identifier `qwen-research`
  (<https://huggingface.co/Qwen/Qwen2.5-3B-Instruct>).
* Its text restricts use to "**NON-COMMERCIAL PURPOSES ONLY**", and section 2(b) adds: "If you are
  commercially using the Materials, you shall request a license from us"
  (<https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/blob/main/LICENSE>).

`qwen2.5:3b` would otherwise have been a natural member of this shortlist: right size class, right
family, and it would have given us a within-family 1.5B/3B/7B ladder. It is **disqualified for this
client** on licence grounds alone. Anyone who picks candidates by benchmark score and download size, and
checks the licence at the family level rather than per size, ships a non-commercial model into a
commercial deployment. That is the lesson worth a line on the slide.

### 4. Gemma Terms of Use — why no Gemma candidate

* **Terms:** "Gemma Terms of Use", <https://ai.google.dev/gemma/terms>; Prohibited Use Policy
  incorporated by reference, <https://ai.google.dev/gemma/prohibited_use_policy>.
* Commercial use is not prohibited, but the terms are **not** an open-source licence. Distribution other
  than through a hosted service must be accompanied by a `NOTICE` text file containing the sentence
  "Gemma is provided under and subject to the Gemma Terms of Use found at ai.google.dev/gemma/terms", the
  use restrictions must be passed downstream **as enforceable contract terms**, and recipients must be
  given a copy of the agreement.
* For a regulated client, pass-through restriction obligations on an internally deployed model are an
  extra legal conversation. We get no measurement from Gemma that the four candidates do not already give
  us, so the set does not spend a slot on it. See the rejection list.

### 5. Ollama itself

* **Licence:** MIT License, "Copyright (c) Ollama" —
  <https://github.com/ollama/ollama/blob/main/LICENSE>.
* Slide 12 must credit Ollama; the brief names it explicitly. Record the exact Ollama version with the
  results — `../scripts/pull_and_pin_models.sh` writes it into `models.yaml` alongside each digest, and
  `scripts/capture_env.sh` records it for the environment description.

### 6. The dataset (for completeness; owned by whoever writes the references)

* Consumer Complaint Database, US Consumer Financial Protection Bureau:
  <https://www.consumerfinance.gov/data-research/consumer-complaints/>. A US government work; the brief
  requires it to be acknowledged. The course extract is derived from it.

---

## Considered and rejected

One line each, with the reason. This list is the evidence of the judgement the brief asks for; it is not
padding, and it is deliberately longer than the shortlist.

| Candidate | Rejected because |
|---|---|
| `qwen3:8b`, `qwen3:4b`, `qwen3:1.7b` | Apache-2.0 and otherwise the strongest available choices, but thinking mode is **on by default** and the model emits a `<think>...</think>` block before the answer (<https://huggingface.co/Qwen/Qwen3-8B>). Our prompt is fixed, does not set `think: false`, and `NUM_CTX` is 4096; `service/categories.py` performs no semantic recovery, so those replies would land in `UNPARSEABLE` while burning the most CPU of any candidate. |
| `qwen2.5:3b` | **Qwen Research License, non-commercial only** — disqualified by the client's constraint, even though it is the same family as a candidate we did take. See "the trap we avoided" above. |
| `qwen2.5:1.5b` | Apache-2.0 and a perfectly legitimate sub-2B option. Dropped only because the sub-2B slot is better spent on `llama3.2:1b`, which buys us a controlled within-family comparison against `llama3.2:3b` that this would not. Named substitute if the Llama licence is judged unacceptable. |
| `qwen3.5` (0.8b–9b) | Newest family on the library (<https://ollama.com/search?q=qwen>), 256K context, multimodal at 9B. Rejected as too new to pin confidently for a six-week assignment, and because we **could not verify its licence** from its Ollama page on 23 September 2026. |
| `qwen3.6`, `qwen3.8`, `qwen3-next:80b`, `qwen3:14b`/`30b`/`32b`/`235b` | Smallest published size is 27B or above (or a 14B+ dense build). Not CPU-feasible on commodity hardware. |
| `gemma3:1b`, `gemma3:4b` | Gemma Terms of Use: not OSI-approved, use restrictions must be passed downstream as enforceable terms, Prohibited Use Policy incorporated (<https://ai.google.dev/gemma/terms>). An extra compliance conversation for a measurement the existing four already give us. `gemma3:4b` is additionally multimodal (<https://ollama.com/library/gemma3>), which is dead weight for a text-only task. |
| `gemma4` (12b, 26b, 31b) | The current Gemma generation starts at **12B** (<https://ollama.com/search?q=gemma>). Too large for the client's hardware, so it cannot be a serious candidate however good it is. |
| `mistral:7b` | Apache-licensed and CPU-feasible, but it duplicates `qwen2.5:7b`'s role in the set, its instruct tuning is older (v0.3, 22 May 2024), and Ollama's page states "Apache license" without a version (<https://ollama.com/library/mistral>). **Named substitute** for the 7-8B slot if `qwen2.5:7b` will not serve. |
| `phi4-mini:3.8b` | A reasonable 3-4B option on paper, but its Ollama page states **no licence at all** (<https://ollama.com/library/phi4-mini>), so our licence claim would rest entirely on an off-Ollama source; and the 3-4B class is already represented twice. |
| `granite4:1b`, `granite4:350m` | Ollama ships these at **bf16**, not four bits — 3.3 GB and 708 MB respectively (<https://ollama.com/library/granite4/tags>) — so `granite4:1b` is a *larger* download than the 3B Q4_K_M build. Using either would mix quantisation with parameter count in exactly the way we are trying to avoid. |
| `granite4:3b-h`, `granite4:7b-a1b-h`, `granite4:32b-a9b-h` | The hybrid Mamba-2 builds. Ollama's own page says the dense `3b`/`1b`/`350m` tags exist "for users when mamba-2 support is not yet optimized" (<https://ollama.com/library/granite4:3b>), which makes the dense build the safer pin for a CPU-only measurement. The 32B mixture-of-experts build is out of scope on size regardless. |
| `llama3.2:latest`, `granite4:latest`, `qwen2.5:latest` | Moving tags. `latest` resolves to a specific size today (`llama3.2:latest` = the 3B digest; `granite4:latest` = 2.1 GB) and may resolve elsewhere tomorrow, which would silently invalidate every pinned result. Always pin an explicit size tag. |
| `tinyllama:1.1b`, `smollm2:1.7b` | Below the instruction-following floor this task needs. The task is "reply with exactly one of seven strings and nothing else"; spending our sub-2B slot on a model we expect to mostly produce `UNPARSEABLE` would measure our parser, not the trade-off. |
| `phi3:14b`, `gemma3:12b`/`27b`, `qwen2.5:14b`/`32b`/`72b`, anything larger | Not serious candidates on commodity CPU with no GPU. Listed so that the shortlist is visibly a choice rather than an omission. |

---

## What we could not verify, and what is still unverified

Stated explicitly so no reader mistakes any of it for a measurement.

1. **Download sizes and digests.** Every size in this document is Ollama's rounded web display, and every
   digest is a short manifest digest read from a web page. Nothing here has been pulled. Real byte counts
   and full digests appear in `models.yaml` only after `../scripts/pull_and_pin_models.sh` runs against
   the Ollama host we measure on. **Until then, treat this whole document as a proposal.**
2. **The llama.com licence URL.** <https://www.llama.com/llama3_2/license/> redirected via
   `developer.meta.com` to a Meta developer sign-in page on 23 September 2026, so the canonical text is
   not publicly fetchable there. We cite the GitHub copy and the Ollama licence blob instead.
3. **Whether the Llama 3.2 attribution clauses bind an internal-only deployment.** A legal question about
   the phrase "a product or service that contains any of them". We recommend the cheap precaution rather
   than an opinion.
4. **Licences absent from Ollama pages.** `qwen3`, `qwen3.5` and `phi4-mini` state no licence on their
   Ollama family pages. For the four shortlisted models the licence is stated on the per-tag page and
   confirmed upstream; for the rejected ones we have said where the gap is.
5. **Context length for `granite4:3b`.** The family page advertises a 128K context window; the per-tag
   details table did not show a context field when we read it. It does not matter for us — `NUM_CTX` is
   set explicitly to 4096 in the service — but do not quote 128K on a slide as though we had checked it
   per tag.
6. **Nothing about speed or accuracy.** No candidate in this document has been run. This file contains no
   latency figure, no accuracy figure and no ranking, by design: predictions belong in
   `../predictions/prediction_record.md` (before the freeze) and measurements belong in `../results/`
   (after it).

---

## How to act on this file

```bash
# 1. Yeo Kai Yuan confirms the shortlist above and resolves the Q8_0 decision.
# 2. Pull and pin, on the machine that will actually serve the models:
scripts/pull_and_pin_models.sh --dry-run          # check the plan first, contacts nothing
scripts/pull_and_pin_models.sh                    # pulls, then writes digests into models/models.yaml
# 3. Commit models/models.yaml. Those digests are what Slide 5 reports.
```

If a later re-pull reports a digest that differs from the one already pinned, the script **fails** rather
than overwriting it. That is deliberate: a changed digest means the weights behind the tag changed, and
every result already gathered under the old digest is no longer comparable. Read the script's message
before doing anything else.
