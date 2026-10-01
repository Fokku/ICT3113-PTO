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

* `high`: the narrative names the product or actor and says what the consumer
  wants fixed, exactly one category definition fits, and no edge-case rule was
  needed to choose it.
* `medium`: the category is identifiable, but a second category also fits and
  you chose between them using an edge-case rule (E1, E4, E6 or E7).
* `low`: you are guessing: the narrative is vague or redacted (E3, E5), the
  tie-break ordering decided it, or no rule covered the case.

The agreement script puts the disagreements with the lowest confidence at the
top of the resolution queue, so `low` means "look at this row first".

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
The complaint is about what a credit file (credit report, score or inquiry
list) says, or about who has looked at it, and the remedy the consumer wants is
a change to that file. No particular product account is the thing to be fixed.

**Include**
* An entry that is wrong, outdated, duplicated or unverified: a wrong balance,
  a late payment that was not late, a paid-off account still showing a balance.
* Accounts or hard inquiries the consumer did not authorise, including
  identity-theft entries, where the consumer's ask is that they be removed from
  the report.
* Template or boilerplate letters that quote the FCRA and name an account but no
  product ("furnished without my written instructions").
* Harm described only as damage to the credit score or the inquiry list.

**Exclude**
* A collector calling, writing, threatening or ignoring a validation request,
  even when the debt also shows on the report: Debt collection (E7).
* A complaint about how a named product account was handled, where the credit
  report is only where the problem surfaced: that product's category (for
  example a fraudulently opened card account whose handling is the complaint:
  Credit card; a bank failing to close an account properly: Bank account or
  service).
* A reporting dispute that depends on the loan's own terms, such as whether a
  deferment was approved: Consumer loan.

**Worked example from our rows (row number + why)**
Row 10190: a creditor "sold all my consumer credit accounts" and the consumer
demands they "be removed" from the "consumer credit report". The remedy is a
change to the file and no product account is being fixed.

### 2. Debt collection

**Definition**
The complaint is about a third party (or a creditor acting as a collector)
pursuing, validating or reporting a debt as a collection effort: its calls,
letters, threats, licensing, validation duties, or collecting a debt the
consumer says is settled, discharged, time-barred or not theirs.

**Include**
* Calls, robocalls, letters or threats demanding payment from a collection
  company or debt buyer.
* A collector that ignores a debt validation request, or re-reports a debt after
  an unanswered validation request.
* Collecting a debt the consumer says was already settled, paid, discharged in
  bankruptcy or never owed.
* A charge sent to a collections company with no itemisation.

**Exclude**
* An original creditor's report entry disputed only for accuracy (for example a
  creditor reporting a debt it no longer owns): Credit reporting.
* A billing or terms dispute with the original lender about its own product:
  that product's category (Credit card, Consumer loan, Mortgage).
* A servicer's ordinary payment demand within normal servicing of a mortgage or
  loan: Mortgage or Consumer loan.

**Worked example from our rows (row number + why)**
Row 10151: a representative "continues to call & harass me over a time-barred
debt" and threatens a lawsuit. The collector's conduct is the whole complaint.

### 3. Mortgage

**Definition**
The complaint is about a mortgage loan or its servicer: payments, escrow, loan
modification or loss mitigation, foreclosure, servicing transfers, or changes to
the mortgage account.

**Include**
* Escrow handling: insurance or tax payments made wrongly, escrow cushions,
  payment increases caused by escrow.
* Loan modification and loss mitigation, including Regulation X notices and
  dual-tracking complaints.
* Mortgage payment amounts that do not reconcile, and servicing transfers.
* Foreclosure, and unauthorised changes to a mortgage servicer account.

**Exclude**
* A collector pursuing a mortgage debt: Debt collection (E7).
* Hard inquiries run by a mortgage company that the consumer never authorised,
  where the complaint is the inquiry itself: Credit reporting.
* Servicing of any non-mortgage loan: Consumer loan. Escrow is not a bank
  account: do not use Bank account or service for it.

**Worked example from our rows (row number + why)**
Row 10532: the servicer "set up an invalid escrow account" and paid a second
insurance premium. Escrow mismanagement by the servicer is a mortgage servicing
complaint.

### 4. Credit card

**Definition**
The complaint is about a credit card or prepaid card account issued as a card:
charges, disputes, interest, fees, billing, applications, activation or
replacement, or the issuer's fraud process.

**Include**
* Fraudulent or disputed charges taken up with the card issuer, and the issuer's
  handling of that dispute.
* Interest, promotional rates, late fees, autopay and billing on a card.
* Card applications, activation and replacement cards.
* Prepaid and gift cards sold as cards (a "Vanilla" or RushCard style product)
  where the card product itself is the problem (activation, outage, funds
  inaccessible), and store or PayPal Credit style card accounts.

**Exclude**
* A collector pursuing a card debt: Debt collection (E7).
* How a card account appears on the credit report: Credit reporting.
* A deposit account, including a government-benefits account held at a bank,
  where the problem is the account itself: Bank account or service.

**Worked example from our rows (row number + why)**
Row 10293: the account "was closed with a" balance, and the credit card
company "just keeps charging" late and missed payment fees to create it. The fees
and balance on the card are the complaint.

### 5. Bank account or service

**Definition**
The complaint is about a deposit account (checking, savings, money market) or
about an account provider's service: fees, overdrafts, holds, limits, closure,
access, linking external accounts, or fraud on the account.

**Include**
* Overdraft, maintenance and other account fees.
* Account freezes, closures, restrictions, transfer limits and approval queues.
* Fraud on, takeover of, or unauthorised transactions on the deposit account,
  and the bank's refusal to reimburse them.
* Fintech wallets and money apps acting as the account provider (closing the
  account, freezing it, not releasing the remaining funds).

**Exclude**
* One specific transfer, wire, payment, deposit or refund that went wrong, where
  the account relationship is not the issue: Money transfer or service.
* Billing on a credit or prepaid card: Credit card.
* An account entry that the consumer wants removed from the credit report:
  Credit reporting.

**Worked example from our rows (row number + why)**
Row 10624: repeated overdraft fees because the "available balance" was wrong.
The fees and balance reporting of the deposit account are the complaint.

### 6. Consumer loan

**Definition**
The complaint is about a non-mortgage loan: student, auto, personal or payday
loans, covering origination, repayment terms, forgiveness, deferment, servicing
or the servicer's responsiveness.

**Include**
* Student loan servicing, repayment, consolidation, forgiveness, PSLF and
  deferment.
* A loan servicer that cannot be reached or does not answer letters.
* Auto, personal and payday loan terms and payments.

**Exclude**
* A collector demanding payment: Debt collection (E7).
* Any mortgage servicing: Mortgage.
* A report entry disputed only for accuracy: Credit reporting.

**Worked example from our rows (row number + why)**
Row 10952: the borrower cannot reach "Nelnet", their student loan provider, to
arrange repayment. The loan servicer's responsiveness on a student loan is the
complaint.

### 7. Money transfer or service

**Definition**
The complaint is about one specific movement of money (a wire, transfer, peer to
peer payment, money order, deposit or refund) that failed, was misdirected,
was unauthorised or cannot be recovered, where the account relationship itself
is not the issue.

**Include**
* Scam or mistaken payments through Zelle, Venmo, Cash App or a similar service
  that cannot be reversed.
* A failed or misdirected deposit, wire or transfer between accounts.
* Unauthorised transfers made through a payment app or wire, and refunds or
  surplus funds that are not being sent back.

**Exclude**
* Fees, limits, freezes, closure or access problems on an account, and
  unauthorised transactions on a deposit account: Bank account or service.
* Charges or billing on a card: Credit card.
* A collector's demand for payment: Debt collection.

**Worked example from our rows (row number + why)**
Row 10474: the consumer sent money through Zelle to a scammer and the bank "could
not" stop the payment. The payment itself is the complaint.

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

Label by the product or service the consumer is asking the firm to fix (the
remedy sought), not by the law quoted, the channel through which the problem
arrived, or the order in which things are mentioned.

Two rules override this, and are tested first:

1. A third-party collector's conduct is Debt collection (E7).
2. A complaint whose only remedy is a change to the credit file is Credit
   reporting.

If a genuine tie survives both, use the tie-break ordering below.

### E2. A ticket that fits none of the seven

Force the closest category and enter `low` confidence. Dropping a row is for
narratives that contain no readable complaint at all (empty, or nothing but
redaction); write `EXCLUDE` in the resolution and give the reason in
`resolution_note`. Accept at most 10 exclusions; beyond that, force a label, so
the finished set stays above the brief's floor of 150 rows.

### E3. An ambiguous narrative

The minimum is a product or actor, plus what went wrong. If the narrative gives
only one of the two, label the closest category, enter `low` and start the notes
with `E3:`. This is not the same action as E2: E3 rows are still labelled, E2
rows are the rare ones dropped.

### E4. A narrative mostly about a different product from the one complained of

The label follows the subject of the complaint, which is what the consumer asks
to be fixed, not the bulk of the text. Background about another product,
institution or earlier dispute does not decide the label.

### E5. Redaction placeholders (XXXX) that remove the decisive detail

A labeller may infer a redacted product from the surrounding text (a named firm
or product word elsewhere in the narrative). If the only way to name it is to
guess, treat the row as E3: `low` confidence. Whenever E5 is applied, the notes
start with `E5:` and say what was inferred and from which words.

### E6. A narrative describing several products

The product that determines the label is the one the consumer asks the firm to
fix, or where the loss occurred. It is not the first one mentioned. If two
products are equally the subject, use the tie-break ordering.

### E7. A debt collector chasing a credit-card debt

Debt collection. When a third-party collector or debt buyer (or a creditor
acting as one) is the actor, and the complaint is about its collection conduct
(calls, letters, threats, licensing, validation, collecting a debt already
settled), the label is Debt collection, even when the underlying debt is a
credit card.

This generalises to a collector chasing a mortgage debt, a consumer-loan debt or
any other debt. It does not apply when the complaint is with the original
lender about its own billing or terms (that is the product's category), or when
the only issue is the accuracy of an entry on the credit report (Credit
reporting).

### A case this protocol does not cover

Enter the closest category, `low` confidence, and start the notes with
`PROTOCOL-GAP:`, then name the two candidate categories and the one-line reason
the rules do not settle it (for example
`PROTOCOL-GAP: Bank account or service vs Money transfer or service, blocked wire`).
Do not confer. The resolution meeting finds these rows by searching the notes
column for `PROTOCOL-GAP`, and each one becomes a revision-log entry.

---

## Tie-break ordering

Used only when E1 to E7 leave a genuine tie.

**Principle:** the category with the narrowest definition outranks broader
catch-alls. A category that needs a specific actor or product to be present
(a collector, a mortgage, a card) beats one that merely describes where the
problem surfaced (an account, a credit file).

| Rank | Category | Why it sits here |
|---|---|---|
| 1 | Debt collection | requires a collector or debt buyer as the actor |
| 2 | Mortgage | requires a mortgage loan or its servicer |
| 3 | Credit card | requires a card account |
| 4 | Consumer loan | requires a named non-mortgage loan |
| 5 | Money transfer or service | requires one specific movement of money |
| 6 | Bank account or service | the broad catch-all for deposit-account problems |
| 7 | Credit reporting | the broad catch-all for anything that surfaces on a credit file |

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
| R0 | 2026-10-02 | Protocol text completed for the first time: confidence levels, the seven category definitions, E1 to E7, the procedure for uncovered cases and the tie-break ordering. This was written after both sheets were labelled and the disagreements resolved, from the patterns in the resolutions. It was not available to the labellers during independent labelling. | none (whole document) | `TODO: both labellers' names` |
| R1 | 2026-10-02 | Mortgage definition: escrow handling, loan modification and loss mitigation, payment disputes and unauthorised account changes at a mortgage servicer are Mortgage, not Bank account or service, Consumer loan or Credit reporting. | 10127, 10219, 10454, 10520, 10602, 10827 | `TODO: both labellers' names` |
| R2 | 2026-10-02 | E7 and Debt collection definition: a collector's conduct (including collecting a settled debt, ignoring validation, or re-reporting after an unanswered validation request) is Debt collection even when the debt is a card debt. | 10666, 10517, 10537, 10178, 10116, 10774, 10575 | `TODO: both labellers' names` |
| R3 | 2026-10-02 | E1 and Credit reporting definition: a complaint whose only remedy is a change to the credit file (FCRA boilerplate, unauthorised accounts or inquiries, report accuracy) is Credit reporting. | 10120, 10549, 10557, 10887, 10406, 10409, 10210, 10322, 10338, 10497, 10763, 10452, 10604, 10622, 10358, 10996 | `TODO: both labellers' names` |
| R4 | 2026-10-02 | Credit card definition: prepaid and gift cards sold as cards, and PayPal Credit style accounts, are Credit card. | 10271, 10469, 10653, 10933, 10945, 10951 | `TODO: both labellers' names` |
| R5 | 2026-10-02 | Consumer loan definition: student loan forgiveness, consolidation, deferment and repayment are Consumer loan, not Debt collection or Credit reporting. | 10045, 10510, 10790, 10467 | `TODO: both labellers' names` |
| R6 | 2026-10-02 | Bank account and Money transfer definitions: account freezes, closures, and unauthorised transactions on a deposit account are Bank account or service, not Money transfer or service. Money transfer is limited to a specific transfer, wire, payment, deposit or refund that went wrong. | 10381, 10463, 10560 | `TODO: both labellers' names` |

---

## Where this fits

* Sampling and the toolchain: `README.md` in this folder.
* The resolution record that feeds Slide 6: `resolutions.md`.
* The finished ground truth: `../golden/golden_set.csv` (two columns,
  `row_number,label`).
* Accuracy is measured against that file and never against `raw_label`.
