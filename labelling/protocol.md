# Labelling protocol — golden test set

**What this document is.** The written rules by which every ticket in our golden
test set is labelled. It is the document the brief asks for first ("Write a
labelling protocol first: a definition of each category, with rules for the edge
cases you expect"), it is a submitted supporting file, and it is summarised on
Slide 6.

**Owner: Part 2 — Teammate A.** `TODO(Yeo Kai Yuan): replace with real name.`
**Second labeller: Part 3 — Teammate B.** `TODO(Yeo Kai Yuan): replace with real name.`
**Feeds:** Slide 6 (Golden Test Set), and the submitted supporting files
(protocol with revisions, the two independent label sheets, the agreement
statistic).

**"Done" looks like:** every `TODO(...)` below replaced with a decision; both
labellers have read it and signed the sign-off section; it is committed **before
the first label is entered in a sheet**; and every later change is recorded in
the Revision log at the bottom.

**How to use it while labelling:** apply the rules in this order — the category
definitions first, then the edge-case rules, and the tie-break ordering only
when a genuine tie survives both. If you find a case the protocol does not
cover, follow the procedure in "A case this protocol does not cover" rather than
inventing a rule silently.

---

## Rule zero — the protocol is written and agreed BEFORE labelling starts

Nothing in this document may be decided while looking at a disagreement, and
nothing may be decided while looking at a model's output. The brief is explicit:
labelling after seeing model output "drags your labels towards whatever the
model says, and quietly corrupts the accuracy measurement".

Two consequences, both non-negotiable:

1. **Write it first.** The protocol is committed before either labeller enters a
   single label. The commit history is the evidence.
2. **Log every revision.** Once labelling has started, any change to this
   document is a **revision** and goes in the Revision log with the
   disagreement that prompted it. Revisions are not embarrassing — the brief
   marks them ("Summary of the labelling protocol and its revisions", Slide 6)
   and warns that "a golden set with implausibly perfect agreement and no
   recorded resolutions will be examined closely". A protocol that needed
   revising, with the revisions recorded, is the expected outcome of careful
   work. Editing this file quietly, so that it looks as if it were right first
   time, throws away marks and is dishonest about the process.

---

## How the sample was drawn (facts — nothing to decide here)

Recorded here so that the protocol is self-contained for a reader who has only
the submitted files.

| Item | Value |
|---|---|
| Source | `data/team_rows.csv` — our team's 1,000 rows of the course extract |
| Candidates sampled | 200 (the top of the brief's 150–200 range, so that rows may be excluded during resolution and the set still complies) |
| Stratified by | `raw_label`, the noisy consumer-selected label, used only to guarantee that every category is represented |
| Allocation | proportional, largest-remainder (Hare quota); ties broken by canonical category order |
| Fixed seed | **3113** (the course code) — `random.Random(3113)` |
| Reproducibility | re-running `labelling/scripts/sample_golden_candidates.py` with the same seed draws the same 200 rows; the script proves this to itself on each run |
| Audit trail | `labelling/golden_candidates.csv` (`row_number,raw_label`) |

**Do not open `labelling/golden_candidates.csv` or `data/team_rows.csv` while
labelling.** Both carry `raw_label`, the consumer's own choice of category. It
is noisy — that is why this golden set exists — and seeing it would anchor your
judgement to it. The label sheets deliberately do not contain it.

---

## How to record a label (mechanics — nothing to decide here)

Each labeller fills in their own sheet, `labelling/labeller_A.csv` or
`labelling/labeller_B.csv`. Columns, exactly:

| Column | Fill in | Notes |
|---|---|---|
| `row_number` | pre-filled, do not touch | the row in the course extract |
| `narrative` | pre-filled, do not touch | verbatim ticket text, may contain line breaks |
| `label` | **you fill in** | exactly one of the seven strings below |
| `confidence` | **you fill in** | `high`, `medium` or `low` |
| `notes` | optional | why, if the row was not obvious; free text, keep it on one line |

The seven permitted `label` values, spelled exactly like this (the toolchain
accepts a case-insensitive exact match and nothing else — no abbreviations, no
synonyms, no "did you mean"):

1. `Credit reporting`
2. `Debt collection`
3. `Mortgage`
4. `Credit card`
5. `Bank account or service`
6. `Consumer loan`
7. `Money transfer or service`

This is the canonical order used everywhere in the repository (it is the order
in `service/categories.py` and the axis order of every confusion matrix). Do not
re-order it.

There is no "unknown", "other" or "unparseable" value. `UNPARSEABLE` exists only
for model output; a human labeller does not use it.

**What the confidence levels mean:**
`TODO(Part 2 — Teammate A): define high, medium and low in one line each, in
terms a labeller can apply consistently — for example what has to be true of a
narrative before it may be marked high. The agreement script puts the
disagreements with the lowest confidence at the top of the resolution queue, so
these definitions decide what the resolution meeting looks at first.`

**Do not confer while labelling.** The brief requires the two label sheets to be
independent ("At least two team members label every ticket independently,
following the protocol and without conferring"). Talking about specific rows
before the agreement statistic is computed destroys the statistic's meaning: a
kappa between two people who compared notes measures nothing.

---

## Category definitions

One section per category, in canonical order. Each needs all four subsections
filled in. Write them so that a competent stranger could label our 200 tickets
from this document alone and arrive at the same labels you did — that is the
standard the brief sets for playbooks, and it is the right standard here too.

For the worked example, choose a row that is **not** in
`labelling/golden_candidates.csv`. Using a sampled row would pre-label part of
the golden set in the protocol, and a marker would be right to ask whether the
example anchored the labelling.

### 1. Credit reporting

**Definition**
`TODO(Part 2 — Teammate A): one or two sentences that decide whether a narrative
belongs to "Credit reporting", applicable without consulting anyone.`

**Include**
`TODO(Part 2 — Teammate A): the features of a narrative that put it in this
category. Bullet points, concrete, drawn from what our rows actually contain.`

**Exclude**
`TODO(Part 2 — Teammate A): the near-misses that must NOT be labelled
"Credit reporting", and which category each goes to instead.`

**Worked example from our rows (row number + why)**
`TODO(Part 2 — Teammate A): one row number from data/team_rows.csv that is not
in golden_candidates.csv, plus one sentence naming the words in the narrative
that decide it.`

### 2. Debt collection

**Definition**
`TODO(Part 2 — Teammate A): one or two sentences that decide whether a narrative
belongs to "Debt collection", applicable without consulting anyone.`

**Include**
`TODO(Part 2 — Teammate A): the features of a narrative that put it in this
category.`

**Exclude**
`TODO(Part 2 — Teammate A): the near-misses that must NOT be labelled
"Debt collection", and which category each goes to instead.`

**Worked example from our rows (row number + why)**
`TODO(Part 2 — Teammate A): row number (not a sampled candidate) + why.`

### 3. Mortgage

**Definition**
`TODO(Part 2 — Teammate A): one or two sentences that decide whether a narrative
belongs to "Mortgage", applicable without consulting anyone.`

**Include**
`TODO(Part 2 — Teammate A): the features of a narrative that put it in this
category.`

**Exclude**
`TODO(Part 2 — Teammate A): the near-misses that must NOT be labelled
"Mortgage", and which category each goes to instead.`

**Worked example from our rows (row number + why)**
`TODO(Part 2 — Teammate A): row number (not a sampled candidate) + why.`

### 4. Credit card

**Definition**
`TODO(Part 2 — Teammate A): one or two sentences that decide whether a narrative
belongs to "Credit card", applicable without consulting anyone.`

**Include**
`TODO(Part 2 — Teammate A): the features of a narrative that put it in this
category.`

**Exclude**
`TODO(Part 2 — Teammate A): the near-misses that must NOT be labelled
"Credit card", and which category each goes to instead.`

**Worked example from our rows (row number + why)**
`TODO(Part 2 — Teammate A): row number (not a sampled candidate) + why.`

### 5. Bank account or service

**Definition**
`TODO(Part 2 — Teammate A): one or two sentences that decide whether a narrative
belongs to "Bank account or service", applicable without consulting anyone.`

**Include**
`TODO(Part 2 — Teammate A): the features of a narrative that put it in this
category.`

**Exclude**
`TODO(Part 2 — Teammate A): the near-misses that must NOT be labelled
"Bank account or service", and which category each goes to instead.`

**Worked example from our rows (row number + why)**
`TODO(Part 2 — Teammate A): row number (not a sampled candidate) + why.`

### 6. Consumer loan

**Definition**
`TODO(Part 2 — Teammate A): one or two sentences that decide whether a narrative
belongs to "Consumer loan", applicable without consulting anyone.`

**Include**
`TODO(Part 2 — Teammate A): the features of a narrative that put it in this
category.`

**Exclude**
`TODO(Part 2 — Teammate A): the near-misses that must NOT be labelled
"Consumer loan", and which category each goes to instead.`

**Worked example from our rows (row number + why)**
`TODO(Part 2 — Teammate A): row number (not a sampled candidate) + why.`

### 7. Money transfer or service

**Definition**
`TODO(Part 2 — Teammate A): one or two sentences that decide whether a narrative
belongs to "Money transfer or service", applicable without consulting anyone.`

**Include**
`TODO(Part 2 — Teammate A): the features of a narrative that put it in this
category.`

**Exclude**
`TODO(Part 2 — Teammate A): the near-misses that must NOT be labelled
"Money transfer or service", and which category each goes to instead.`

**Worked example from our rows (row number + why)**
`TODO(Part 2 — Teammate A): row number (not a sampled candidate) + why.`

---

## Edge-case rules

The brief names three kinds of edge case and expects rules for "the edge cases
you expect". The first three headings below are the brief's; the rest are cases
our own rows will certainly produce — a narrative whose bulk is about a
different product, a redaction that removes the deciding word, a narrative
listing several products, and the debt-collector-chasing-a-credit-card case.

Each heading is a **question for you to answer**. Replace the question with the
rule you have decided, stated so that two people applying it separately reach
the same label. A rule that says "use judgement" is not a rule and will produce
a low kappa.

### E1. A ticket that fits two categories

`TODO(Part 2 — Teammate A): when a narrative genuinely satisfies two category
definitions, what decides the label? State the deciding principle — for example
whether the financial product the complaint concerns wins, or the conduct
complained of wins — and say when the tie-break ordering below is used instead.`

### E2. A ticket that fits none of the seven

`TODO(Part 2 — Teammate A): do we force the closest category, or drop the row
from the golden set? If we drop it: dropping is recorded by writing EXCLUDE in
the agreed_label column of labelling/resolutions.csv (see
labelling/README.md), the row still needs a resolution note, and the finished
set must not fall below 150 rows. State how many exclusions you are prepared to
accept before you would instead force a label.`

### E3. An ambiguous narrative

`TODO(Part 2 — Teammate A): what is the minimum a narrative must say before it
can be labelled at all? What does a labeller do when the narrative is below
that threshold — and is that the same action as E2, or a different one? State
which confidence level such a row must carry.`

### E4. A narrative mostly about a different product from the one complained of

`TODO(Part 2 — Teammate A): some narratives spend most of their text on the
background (a different product, another institution, an earlier dispute) and
only a line or two on the actual complaint. Does the label follow the subject of
the complaint or the bulk of the text? Give the rule, not a preference.`

### E5. Redaction placeholders (XXXX) that remove the decisive detail

`TODO(Part 2 — Teammate A): our rows are redacted at source, so names, dates,
amounts and sometimes the product itself appear as XXXX. When the redacted token
is the very thing that would decide the category, may a labeller infer it from
the surrounding text, or is the row treated as E3? State the rule, and state
what goes in the notes column when it is applied.`

### E6. A narrative describing several products

`TODO(Part 2 — Teammate A): when one narrative describes several products (a
current account and a card and a loan, say), which one determines the label —
the first mentioned, the one that caused the loss, the one the complaint asks
the firm to fix, or something else? One rule, stated once.`

### E7. A debt collector chasing a credit-card debt

`TODO(Part 2 — Teammate A): this is the classic two-category case and it will
recur in our rows, so answer it explicitly rather than leaving it to E1.
"Debt collection" or "Credit card"? State the rule that produces your answer,
and state whether it generalises to a collector chasing a mortgage debt, a
consumer-loan debt, and so on.`

### A case this protocol does not cover

`TODO(Part 2 — Teammate A): state the procedure for a row that none of the rules
above settles. Remember that labellers may not confer while labelling, so the
procedure has to work for one person alone: which label do they enter, which
confidence, and what exactly goes in the notes column so the resolution meeting
can find the row afterwards?`

---

## Tie-break ordering

`TODO(Part 2 — Teammate A): state one total ordering of the seven categories, to
be used only when the rules above leave a genuine tie. You must state one — a
protocol with no tie-break leaves the two labellers to break ties differently,
which shows up as a lower kappa and as disagreements that reveal nothing.`

State the **principle** behind the ordering as well as the ordering itself
(most specific product first, highest routing cost first, or whatever you
choose), because the principle is what a reader can check and what Slide 6 can
summarise in a line.

| Rank | Category | Why it sits here |
|---|---|---|
| 1 | `TODO(Part 2 — Teammate A)` | `TODO(Part 2 — Teammate A)` |
| 2 | `TODO(Part 2 — Teammate A)` | `TODO(Part 2 — Teammate A)` |
| 3 | `TODO(Part 2 — Teammate A)` | `TODO(Part 2 — Teammate A)` |
| 4 | `TODO(Part 2 — Teammate A)` | `TODO(Part 2 — Teammate A)` |
| 5 | `TODO(Part 2 — Teammate A)` | `TODO(Part 2 — Teammate A)` |
| 6 | `TODO(Part 2 — Teammate A)` | `TODO(Part 2 — Teammate A)` |
| 7 | `TODO(Part 2 — Teammate A)` | `TODO(Part 2 — Teammate A)` |

---

## Sign-off (before labelling starts)

| Role | Name | Date read and agreed |
|---|---|---|
| Protocol author, labeller A | `TODO(Part 2 — Teammate A)` | `TODO(Part 2 — Teammate A)` |
| Labeller B | `TODO(Part 3 — Teammate B)` | `TODO(Part 3 — Teammate B)` |

---

## Revision log

Every change made to this document **after labelling started** gets a row.
`Which disagreement prompted it` names the row number (or numbers) from
`labelling/disagreements.csv` that exposed the gap — that link between a
disagreement and a protocol change is exactly what the brief asks for in
Step 1, item 4, and what Slide 6 reports.

Leave the example row in place until there is a real revision to replace it; do
not delete the table if there were no revisions, write "no revisions" in the
first row and be ready to say why.

| Revision | Date | What changed | Which disagreement prompted it | Agreed by |
|---|---|---|---|---|
| `TODO(Part 2 — Teammate A): R1, R2, ...` | `TODO: YYYY-MM-DD` | `TODO: the rule or definition that changed, and what it says now` | `TODO: row number(s) from disagreements.csv, or "none — found while labelling"` | `TODO: both labellers' names` |

---

## Where this fits

* Sampling and the toolchain: `README.md` in this folder.
* The resolution record that feeds Slide 6: `resolutions.md`.
* The finished ground truth: `../golden/golden_set.csv` (two columns,
  `row_number,label`).
* Accuracy is measured against that file and never against `raw_label`.
