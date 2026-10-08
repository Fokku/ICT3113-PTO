# Disagreement resolutions — golden test set

**What this document is.** The human record of how every disagreement between the
two independent label sheets was resolved. The brief requires it: "Resolve every
disagreement by discussion, record each resolution, and update the protocol
where a disagreement revealed a gap in it." This is the record; its machine
readable counterpart is `resolutions.csv`, which `build_golden_set.py` consumes.

**Owner: Part 3 — Jolie Ngai Ning Li** (writes it up during and after the resolution
meeting).
**Co-owner: Part 2 — Loh Wen Xuan** (agrees each resolution and makes any protocol
revision it implies).

**Feeds:** Slide 6 (Golden Test Set) — the number of disagreements, how they were
resolved, and **one or two worked examples quoted from this file**. Also a
submitted supporting file.

**"Done" looks like:** one numbered entry below for every row in
`labelling/disagreements.csv`; the same rows, with the same agreed labels, in
`labelling/resolutions.csv`; every entry that changed a rule cross-referenced to
a row of the Revision log in `protocol.md`; and one or two entries flagged as the
Slide 6 examples.

---

## How to use this file

1. Run `labelling/scripts/agreement.py` first. It writes
   `labelling/disagreements.csv`, ordered so that the disagreements either
   labeller was least confident about come first. Work down that list — those
   rows are where the protocol is most likely to have a gap.
2. Resolve each row **by discussion between the two labellers**, not by a vote,
   a coin toss, or by deferring to whoever labelled faster. The agreed label is
   the one the protocol implies once both people have read the narrative
   together; if the protocol does not imply one, that is a protocol gap and it
   goes in the Revision log.
3. Write the entry here, then add the matching line to `resolutions.csv`. The two
   files must describe the same rows; `build_golden_set.py` warns when a row
   appears in one and not the other.
4. Where the disagreement exposed a gap, revise `protocol.md` **and** log the
   revision in its Revision log, naming this row number.

**Keep the `- **Row number:** 10123` line exactly in that shape.**
`build_golden_set.py` reads the row numbers out of this file with that pattern in
order to cross-check it against `resolutions.csv`. If the shape changes, the
cross-check silently finds nothing.

Do not delete a resolution once written, even if a later revision changes the
outcome. Add a follow-up entry instead: the sequence of decisions is the
evidence of care that the brief is asking to see.

---

## Summary

| Item | Value |
|---|---|
| Rows labelled by both labellers | 200 |
| Disagreements | 68 (132 of 200 agreed, observed agreement 0.66) |
| Cohen's kappa | 0.599 (moderate), from `labelling/agreement_report.txt` |
| Resolutions that changed a category label | 68 (every resolution settled on one category; none produced a label neither labeller chose) |
| Resolutions that excluded a row | 0 |
| Protocol revisions caused | 6 (R1: 6 rows, R2: 7 rows, R3: 16 rows, R4: 6 rows, R5: 4 rows, R6: 3 rows), plus R0, the first full write-up of the protocol, which was completed after labelling; see the Revision log in `protocol.md` |
| Chosen as Slide 6 examples | Resolution 37 (row 10666) and Resolution 52 (row 10454) |

---

## Entries

One entry per row of `labelling/disagreements.csv`, in the order of that file (least confident first). Each agreed label is the same one recorded in `resolutions.csv`.

### Resolution 1

- **Row number:** 10214
- **Label A:** Bank account or service
- **Label B:** Credit card
- **Confidence A / B:** low / high
- **Agreed label:** Credit card
- **Reasoning:** Fraudulent charges (out-of-state pizza orders, an unknown payee) were disputed with the card issuer, which closed the escalations without investigating. The complaint is about card dispute handling, so Credit card. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Credit card definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 2

- **Row number:** 10271
- **Label A:** Bank account or service
- **Label B:** Credit card
- **Confidence A / B:** low / medium
- **Agreed label:** Credit card
- **Reasoning:** The consumer's Vanilla prepaid card cannot be set up and the funds on it are inaccessible. The problem sits with the card product itself, so Credit card. Settled by the Credit card definition (revision R4: card products, including prepaid cards where the card itself is the problem, are Credit card).
- **Caused a protocol revision:** R4
- **Slide 6 example:** no

### Resolution 3

- **Row number:** 10469
- **Label A:** Bank account or service
- **Label B:** Credit card
- **Confidence A / B:** low / high
- **Agreed label:** Credit card
- **Reasoning:** RushCard is a prepaid debit card and the outage cut off access to the money on that card. The withdrawals mentioned are a consequence of the card failing, so Credit card. Settled by the Credit card definition (revision R4: card products, including prepaid cards where the card itself is the problem, are Credit card).
- **Caused a protocol revision:** R4
- **Slide 6 example:** no

### Resolution 4

- **Row number:** 10510
- **Label A:** Consumer loan
- **Label B:** Credit reporting
- **Confidence A / B:** medium / low
- **Agreed label:** Consumer loan
- **Reasoning:** The consumer consolidated Parent PLUS loans after being told they would qualify for PSLF, then learned they did not. The issue is the loan product and its terms, so Consumer loan. Settled by the Consumer loan definition (revision R5: student loan forgiveness, consolidation, deferment and repayment are Consumer loan).
- **Caused a protocol revision:** R5
- **Slide 6 example:** no

### Resolution 5

- **Row number:** 10517
- **Label A:** Debt collection
- **Label B:** Bank account or service
- **Confidence A / B:** high / low
- **Agreed label:** Debt collection
- **Reasoning:** Alco Collections Inc is pursuing a debt the consumer never received notice of and will not respond to calls. The credit report is only where the debt surfaced, so Debt collection. Settled by E7 and the Debt collection definition (revision R2: a collector's conduct is Debt collection).
- **Caused a protocol revision:** R2
- **Slide 6 example:** no

### Resolution 6

- **Row number:** 10551
- **Label A:** Bank account or service
- **Label B:** Money transfer or service
- **Confidence A / B:** high / low
- **Agreed label:** Bank account or service
- **Reasoning:** The complaint is about Cash App failing to protect the consumer's account from fraud and running an unfair dispute process. That is the provider's handling of the account, so Bank account or service. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Bank account or service definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 7

- **Row number:** 10604
- **Label A:** Credit reporting
- **Label B:** Money transfer or service
- **Confidence A / B:** medium / low
- **Agreed label:** Credit reporting
- **Reasoning:** A late payment caused by the company's system outage is being reported on the consumer's credit file, and the request to correct it was denied. The complaint is about the misreporting, so Credit reporting. Settled by E1 override 2 and the Credit reporting definition (revision R3: a complaint whose only remedy is a change to the credit file is Credit reporting).
- **Caused a protocol revision:** R3
- **Slide 6 example:** no

### Resolution 8

- **Row number:** 10653
- **Label A:** Credit card
- **Label B:** Money transfer or service
- **Confidence A / B:** high / low
- **Agreed label:** Credit card
- **Reasoning:** The consumer disputed a never-delivered purchase with Goldman Sachs on their Apple Card and the dispute was not resolved. This is a card dispute with the issuer, so Credit card. Settled by the Credit card definition (revision R4: card products, including prepaid cards where the card itself is the problem, are Credit card).
- **Caused a protocol revision:** R4
- **Slide 6 example:** no

### Resolution 9

- **Row number:** 10799
- **Label A:** Bank account or service
- **Label B:** Debt collection
- **Confidence A / B:** low / high
- **Agreed label:** Bank account or service
- **Reasoning:** Unauthorized transactions were made on the consumer's Direct Express benefits account and Comerica has not reimbursed them. This is the bank's handling of a fraud claim on a benefits account, the same pattern as 10483, so Bank account or service. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Bank account or service definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 10

- **Row number:** 10024
- **Label A:** Money transfer or service
- **Label B:** Credit card
- **Confidence A / B:** medium / medium
- **Agreed label:** Money transfer or service
- **Reasoning:** The consumer overpaid a closed Citibank account and Citibank is refusing to send the surplus back. The complaint is about getting the funds returned, so Money transfer or service. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Money transfer or service definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 11

- **Row number:** 10045
- **Label A:** Consumer loan
- **Label B:** Debt collection
- **Confidence A / B:** medium / medium
- **Agreed label:** Consumer loan
- **Reasoning:** Payments on a federal student loan rose after the consumer was close to forgiveness under the program. The complaint is about the loan's repayment and forgiveness terms, so Consumer loan. Settled by the Consumer loan definition (revision R5: student loan forgiveness, consolidation, deferment and repayment are Consumer loan).
- **Caused a protocol revision:** R5
- **Slide 6 example:** no

### Resolution 12

- **Row number:** 10085
- **Label A:** Credit card
- **Label B:** Credit reporting
- **Confidence A / B:** medium / medium
- **Agreed label:** Credit card
- **Reasoning:** A dental office billed the full estimate to a financing credit card for treatment never performed, and the issuer is adding interest and penalties. The charge sits on the card, so Credit card. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Credit card definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 13

- **Row number:** 10110
- **Label A:** Credit card
- **Label B:** Credit reporting
- **Confidence A / B:** high / medium
- **Agreed label:** Credit card
- **Reasoning:** The consumer applied for a Chase business credit card and the issuer's fraud team stalled the application with document requests. This is about the card application, so Credit card. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Credit card definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 14

- **Row number:** 10116
- **Label A:** Debt collection
- **Label B:** Credit reporting
- **Confidence A / B:** medium / high
- **Agreed label:** Debt collection
- **Reasoning:** The consumer sent a debt validation letter, got no response, and the unvalidated debt is still being reported. Failing to validate a debt is collector conduct, so Debt collection. Settled by E7 and the Debt collection definition (revision R2: a collector's conduct is Debt collection).
- **Caused a protocol revision:** R2
- **Slide 6 example:** no

### Resolution 15

- **Row number:** 10127
- **Label A:** Mortgage
- **Label B:** Credit reporting
- **Confidence A / B:** high / medium
- **Agreed label:** Mortgage
- **Reasoning:** Someone changed the autopay bank details on the consumer's NewRez mortgage account without permission. The complaint is about the servicer's handling of the mortgage account, so Mortgage. Settled by the Mortgage definition (revision R1: servicing, escrow and loss mitigation on a mortgage are Mortgage).
- **Caused a protocol revision:** R1
- **Slide 6 example:** no

### Resolution 16

- **Row number:** 10129
- **Label A:** Credit card
- **Label B:** Credit reporting
- **Confidence A / B:** medium / medium
- **Agreed label:** Credit card
- **Reasoning:** A Chime Credit Builder secured credit card was opened fraudulently in the consumer's name. The complaint is about that card account, so Credit card. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Credit card definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 17

- **Row number:** 10167
- **Label A:** Bank account or service
- **Label B:** Credit card
- **Confidence A / B:** medium / medium
- **Agreed label:** Bank account or service
- **Reasoning:** PayPal sent a fraudulent account in the consumer's name to collections and would not fix it. The complaint is about PayPal's handling of the account, so Bank account or service. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Bank account or service definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 18

- **Row number:** 10178
- **Label A:** Debt collection
- **Label B:** Mortgage
- **Confidence A / B:** high / medium
- **Agreed label:** Debt collection
- **Reasoning:** After moving out, the apartment sent vague damage charges to a collections company that will not itemise them. This is a third-party collector dispute, so Debt collection. Settled by E7 and the Debt collection definition (revision R2: a collector's conduct is Debt collection).
- **Caused a protocol revision:** R2
- **Slide 6 example:** no

### Resolution 19

- **Row number:** 10210
- **Label A:** Credit reporting
- **Label B:** Bank account or service
- **Confidence A / B:** medium / high
- **Agreed label:** Credit reporting
- **Reasoning:** The consumer was never given a chance to dispute an account and wants it deleted from their credit report, or proof of proper notice. This is a credit report dispute, the same pattern as 10497 and 10338, so Credit reporting. Settled by E1 override 2 and the Credit reporting definition (revision R3: a complaint whose only remedy is a change to the credit file is Credit reporting).
- **Caused a protocol revision:** R3
- **Slide 6 example:** no

### Resolution 20

- **Row number:** 10219
- **Label A:** Mortgage
- **Label B:** Money transfer or service
- **Confidence A / B:** high / medium
- **Agreed label:** Mortgage
- **Reasoning:** Formal notice that a mortgage servicer missed the Regulation X deadline to request documents for a loss mitigation application. This is mortgage servicing, so Mortgage. Settled by the Mortgage definition (revision R1: servicing, escrow and loss mitigation on a mortgage are Mortgage).
- **Caused a protocol revision:** R1
- **Slide 6 example:** no

### Resolution 21

- **Row number:** 10297
- **Label A:** Credit card
- **Label B:** Credit reporting
- **Confidence A / B:** medium / medium
- **Agreed label:** Credit card
- **Reasoning:** The card issuer removed fraudulent charges earlier but is now making them permanent, saying the fraud window has passed. This is a card dispute, so Credit card. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Credit card definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 22

- **Row number:** 10338
- **Label A:** Credit reporting
- **Label B:** Bank account or service
- **Confidence A / B:** high / medium
- **Agreed label:** Credit reporting
- **Reasoning:** Two accounts opened through identity theft appear on the credit report, and no product detail is given beyond the account names. The complaint is about the report, so Credit reporting. Settled by E1 override 2 and the Credit reporting definition (revision R3: a complaint whose only remedy is a change to the credit file is Credit reporting).
- **Caused a protocol revision:** R3
- **Slide 6 example:** no

### Resolution 23

- **Row number:** 10358
- **Label A:** Credit reporting
- **Label B:** Consumer loan
- **Confidence A / B:** medium / high
- **Agreed label:** Credit reporting
- **Reasoning:** A loan application through a marketplace was denied and the inquiry lowered the consumer's credit score. The harm described is to the credit file, so Credit reporting. Settled by E1 override 2 and the Credit reporting definition (revision R3: a complaint whose only remedy is a change to the credit file is Credit reporting).
- **Caused a protocol revision:** R3
- **Slide 6 example:** no

### Resolution 24

- **Row number:** 10381
- **Label A:** Bank account or service
- **Label B:** Money transfer or service
- **Confidence A / B:** high / medium
- **Agreed label:** Bank account or service
- **Reasoning:** Ally flagged a $50,000 outgoing transfer as fraud, restricted all access to the savings account and then closed it, leaving the consumer without their funds for weeks. The restriction and closure of the account is the complaint, so Bank account or service. Settled by the Bank account and Money transfer definitions (revision R6: freezes, closures and unauthorised transactions on a deposit account are Bank account or service).
- **Caused a protocol revision:** R6
- **Slide 6 example:** no

### Resolution 25

- **Row number:** 10452
- **Label A:** Credit reporting
- **Label B:** Mortgage
- **Confidence A / B:** medium / medium
- **Agreed label:** Credit reporting
- **Reasoning:** A mortgage company pulled the consumer's credit twice for a refinance she never authorised. The complaint is about the unauthorised hard inquiries, so Credit reporting. Settled by E1 override 2 and the Credit reporting definition (revision R3: a complaint whose only remedy is a change to the credit file is Credit reporting).
- **Caused a protocol revision:** R3
- **Slide 6 example:** no

### Resolution 26

- **Row number:** 10463
- **Label A:** Bank account or service
- **Label B:** Money transfer or service
- **Confidence A / B:** high / medium
- **Agreed label:** Bank account or service
- **Reasoning:** TCF reversed a deposit, closed the account after a fraud review, and then deposited two Social Security checks into the closed account. The closure and handling of the account is the complaint, so Bank account or service. Settled by the Bank account and Money transfer definitions (revision R6: freezes, closures and unauthorised transactions on a deposit account are Bank account or service).
- **Caused a protocol revision:** R6
- **Slide 6 example:** no

### Resolution 27

- **Row number:** 10467
- **Label A:** Credit reporting
- **Label B:** Consumer loan
- **Confidence A / B:** medium / high
- **Agreed label:** Consumer loan
- **Reasoning:** Student loans on an approved deferment are reported as late and duplicated. The deferment terms of the loan decide whether the reporting is right, so Consumer loan. Settled by the Consumer loan definition (revision R5: student loan forgiveness, consolidation, deferment and repayment are Consumer loan).
- **Caused a protocol revision:** R5
- **Slide 6 example:** no

### Resolution 28

- **Row number:** 10483
- **Label A:** Bank account or service
- **Label B:** Money transfer or service
- **Confidence A / B:** medium / high
- **Agreed label:** Bank account or service
- **Reasoning:** An account takeover drained the consumer's Bank of America checking and savings, and the bank is now billing the consumer. The complaint is about the bank's handling of the deposit accounts, so Bank account or service. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Bank account or service definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 29

- **Row number:** 10497
- **Label A:** Credit reporting
- **Label B:** Mortgage
- **Confidence A / B:** high / medium
- **Agreed label:** Credit reporting
- **Reasoning:** An apartment was rented using the consumer's stolen identity and the consumer wants it removed from the credit report. No financial product is involved, so Credit reporting. Settled by E1 override 2 and the Credit reporting definition (revision R3: a complaint whose only remedy is a change to the credit file is Credit reporting).
- **Caused a protocol revision:** R3
- **Slide 6 example:** no

### Resolution 30

- **Row number:** 10528
- **Label A:** Credit reporting
- **Label B:** Bank account or service
- **Confidence A / B:** medium / high
- **Agreed label:** Bank account or service
- **Reasoning:** Bank of America is still showing a balance on an account that should have been closed for fraud. The complaint is about the bank's failure to close the account properly, so Bank account or service. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Bank account or service definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 31

- **Row number:** 10537
- **Label A:** Debt collection
- **Label B:** Credit card
- **Confidence A / B:** high / medium
- **Agreed label:** Debt collection
- **Reasoning:** Credit Collections USA LLC placed an $83 collection that the consumer says it is not licensed to collect in Florida. This is collector conduct, so Debt collection. Settled by E7 and the Debt collection definition (revision R2: a collector's conduct is Debt collection).
- **Caused a protocol revision:** R2
- **Slide 6 example:** no

### Resolution 32

- **Row number:** 10540
- **Label A:** Bank account or service
- **Label B:** Money transfer or service
- **Confidence A / B:** high / medium
- **Agreed label:** Bank account or service
- **Reasoning:** Truist charged overdraft fees despite a positive balance and never called back about the complaint. This is a deposit account fee issue, so Bank account or service. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Bank account or service definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 33

- **Row number:** 10575
- **Label A:** Debt collection
- **Label B:** Consumer loan
- **Confidence A / B:** medium / high
- **Agreed label:** Debt collection
- **Reasoning:** Robocalls from Naviant (as the narrative spells it) demand payment on a student loan the consumer denies any connection to, and threaten vague legal action. This is collector conduct, so Debt collection. Settled by E7 and the Debt collection definition (revision R2: a collector's conduct is Debt collection).
- **Caused a protocol revision:** R2
- **Slide 6 example:** no

### Resolution 34

- **Row number:** 10602
- **Label A:** Mortgage
- **Label B:** Debt collection
- **Confidence A / B:** medium / high
- **Agreed label:** Mortgage
- **Reasoning:** The consumer's Wells Fargo home loan payment keeps rising and the amount now demanded does not match what was paid. This is a mortgage payment dispute with the servicer, so Mortgage. Settled by the Mortgage definition (revision R1: servicing, escrow and loss mitigation on a mortgage are Mortgage).
- **Caused a protocol revision:** R1
- **Slide 6 example:** no

### Resolution 35

- **Row number:** 10622
- **Label A:** Credit reporting
- **Label B:** Bank account or service
- **Confidence A / B:** medium / high
- **Agreed label:** Credit reporting
- **Reasoning:** A paid-off loan is reported with a balance rather than as paid in full. This is a report accuracy complaint, so Credit reporting. Settled by E1 override 2 and the Credit reporting definition (revision R3: a complaint whose only remedy is a change to the credit file is Credit reporting).
- **Caused a protocol revision:** R3
- **Slide 6 example:** no

### Resolution 36

- **Row number:** 10638
- **Label A:** Credit reporting
- **Label B:** Debt collection
- **Confidence A / B:** medium / high
- **Agreed label:** Credit reporting
- **Reasoning:** Discover is reporting a debt it no longer owns, and the consumer cites the FCRA. The complaint is about inaccurate reporting, so Credit reporting. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Credit reporting definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 37

- **Row number:** 10666
- **Label A:** Debt collection
- **Label B:** Credit card
- **Confidence A / B:** high / medium
- **Agreed label:** Debt collection
- **Reasoning:** Sunrise Credit Service is trying to collect a card debt the consumer already paid and settled, and is threatening to force repayment. The complaint is about the collector's conduct, the same pattern as 10517 and 10537, so Debt collection. Settled by E7 and the Debt collection definition (revision R2: a collector's conduct is Debt collection).
- **Caused a protocol revision:** R2
- **Slide 6 example:** yes

### Resolution 38

- **Row number:** 10747
- **Label A:** Money transfer or service
- **Label B:** Bank account or service
- **Confidence A / B:** medium / high
- **Agreed label:** Bank account or service
- **Reasoning:** Wells Fargo took $500 more than the agreed payment plan amount from the consumer's account. The complaint is about the bank debiting the account, so Bank account or service. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Bank account or service definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 39

- **Row number:** 10763
- **Label A:** Consumer loan
- **Label B:** Credit reporting
- **Confidence A / B:** medium / high
- **Agreed label:** Credit reporting
- **Reasoning:** Klarna approved a line of credit opened with the consumer's stolen details. The consumer's concern is the fraudulent account showing up against their identity, so Credit reporting. Settled by E1 override 2 and the Credit reporting definition (revision R3: a complaint whose only remedy is a change to the credit file is Credit reporting).
- **Caused a protocol revision:** R3
- **Slide 6 example:** no

### Resolution 40

- **Row number:** 10774
- **Label A:** Debt collection
- **Label B:** Credit reporting
- **Confidence A / B:** medium / high
- **Agreed label:** Debt collection
- **Reasoning:** LVNV re-reported three accounts after a bureau investigation and never answered the validation request. This is collector conduct, so Debt collection. Settled by E7 and the Debt collection definition (revision R2: a collector's conduct is Debt collection).
- **Caused a protocol revision:** R2
- **Slide 6 example:** no

### Resolution 41

- **Row number:** 10790
- **Label A:** Consumer loan
- **Label B:** Debt collection
- **Confidence A / B:** medium / high
- **Agreed label:** Consumer loan
- **Reasoning:** The consumer is seeking forgiveness on federal student loans because of hardship and a school that was closed for fraud. No collector is involved and the issue is the loan itself, so Consumer loan. Settled by the Consumer loan definition (revision R5: student loan forgiveness, consolidation, deferment and repayment are Consumer loan).
- **Caused a protocol revision:** R5
- **Slide 6 example:** no

### Resolution 42

- **Row number:** 10805
- **Label A:** Bank account or service
- **Label B:** Credit card
- **Confidence A / B:** medium / medium
- **Agreed label:** Bank account or service
- **Reasoning:** Money disappeared from the consumer's Chase account and Chase will not help. This is a deposit account service complaint, so Bank account or service. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Bank account or service definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 43

- **Row number:** 10858
- **Label A:** Credit card
- **Label B:** Bank account or service
- **Confidence A / B:** high / medium
- **Agreed label:** Credit card
- **Reasoning:** Autopay drew money for a Bank of America credit card even though a dispute was resolved and the balance was zero. This is card billing, so Credit card. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Credit card definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 44

- **Row number:** 10945
- **Label A:** Credit card
- **Label B:** Bank account or service
- **Confidence A / B:** medium / medium
- **Agreed label:** Credit card
- **Reasoning:** The consumer paid for an online training program with PayPal Credit and the promised money-back guarantee was not honoured. The dispute is on the credit card, so Credit card. Settled by the Credit card definition (revision R4: card products, including prepaid cards where the card itself is the problem, are Credit card).
- **Caused a protocol revision:** R4
- **Slide 6 example:** no

### Resolution 45

- **Row number:** 10120
- **Label A:** Credit reporting
- **Label B:** Bank account or service
- **Confidence A / B:** high / high
- **Agreed label:** Credit reporting
- **Reasoning:** The complaint quotes FCRA sections to argue an account was furnished without consent. This is a credit report dispute, so Credit reporting. Settled by E1 override 2 and the Credit reporting definition (revision R3: a complaint whose only remedy is a change to the credit file is Credit reporting).
- **Caused a protocol revision:** R3
- **Slide 6 example:** no

### Resolution 46

- **Row number:** 10196
- **Label A:** Bank account or service
- **Label B:** Credit card
- **Confidence A / B:** high / high
- **Agreed label:** Bank account or service
- **Reasoning:** Bank of America charged a check imaging fee the consumer never ordered. This is a deposit account fee, so Bank account or service. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Bank account or service definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 47

- **Row number:** 10322
- **Label A:** Credit reporting
- **Label B:** Bank account or service
- **Confidence A / B:** high / high
- **Agreed label:** Credit reporting
- **Reasoning:** A Sezzle account opened through identity theft appears on the consumer's credit report, and the consumer wants it removed. This is a credit report dispute, the same pattern as 10763, so Credit reporting. Settled by E1 override 2 and the Credit reporting definition (revision R3: a complaint whose only remedy is a change to the credit file is Credit reporting).
- **Caused a protocol revision:** R3
- **Slide 6 example:** no

### Resolution 48

- **Row number:** 10337
- **Label A:** Money transfer or service
- **Label B:** Bank account or service
- **Confidence A / B:** high / high
- **Agreed label:** Bank account or service
- **Reasoning:** A large transfer out of a Flagstar high-yield savings account is stuck waiting for approval over the transfer limit. The bank's account-level limits are the issue, so Bank account or service. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Bank account or service definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 49

- **Row number:** 10396
- **Label A:** Money transfer or service
- **Label B:** Bank account or service
- **Confidence A / B:** high / high
- **Agreed label:** Bank account or service
- **Reasoning:** Wise froze the consumer's new account after identity verification, so incoming funds cannot be received. Wise is acting as the account provider, so Bank account or service. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Bank account or service definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 50

- **Row number:** 10406
- **Label A:** Credit reporting
- **Label B:** Bank account or service
- **Confidence A / B:** high / high
- **Agreed label:** Credit reporting
- **Reasoning:** A boilerplate FCRA complaint about an account furnished to the credit bureaus without consent. This is a credit report dispute, so Credit reporting. Settled by E1 override 2 and the Credit reporting definition (revision R3: a complaint whose only remedy is a change to the credit file is Credit reporting).
- **Caused a protocol revision:** R3
- **Slide 6 example:** no

### Resolution 51

- **Row number:** 10409
- **Label A:** Credit reporting
- **Label B:** Bank account or service
- **Confidence A / B:** high / high
- **Agreed label:** Credit reporting
- **Reasoning:** Fraudulent accounts and inquiries keep being reported on the consumer's credit file by the bureaus. This is a credit report dispute, so Credit reporting. Settled by E1 override 2 and the Credit reporting definition (revision R3: a complaint whose only remedy is a change to the credit file is Credit reporting).
- **Caused a protocol revision:** R3
- **Slide 6 example:** no

### Resolution 52

- **Row number:** 10454
- **Label A:** Mortgage
- **Label B:** Bank account or service
- **Confidence A / B:** high / high
- **Agreed label:** Mortgage
- **Reasoning:** Select Portfolio Servicing, the mortgage servicer, has repeatedly failed to manage the consumer's escrow account correctly. Escrow mismanagement by a mortgage servicer is a mortgage servicing issue, so Mortgage. Settled by the Mortgage definition (revision R1: servicing, escrow and loss mitigation on a mortgage are Mortgage).
- **Caused a protocol revision:** R1
- **Slide 6 example:** yes

### Resolution 53

- **Row number:** 10461
- **Label A:** Money transfer or service
- **Label B:** Bank account or service
- **Confidence A / B:** high / high
- **Agreed label:** Bank account or service
- **Reasoning:** The consumer's bank confirms a wire reached Coinbase but Coinbase will not credit the account. The issue is how Coinbase handles the account, so Bank account or service. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Bank account or service definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 54

- **Row number:** 10465
- **Label A:** Credit card
- **Label B:** Credit reporting
- **Confidence A / B:** high / high
- **Agreed label:** Credit card
- **Reasoning:** After a data breach notice deactivated the card, the consumer's payments posted but no replacement card was sent. This is a card account problem, so Credit card. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Credit card definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 55

- **Row number:** 10471
- **Label A:** Bank account or service
- **Label B:** Money transfer or service
- **Confidence A / B:** high / high
- **Agreed label:** Money transfer or service
- **Reasoning:** A Citibank ATM failed during a deposit, kept the cash, and the money has not been credited. The failed transaction is the complaint, so Money transfer or service. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Money transfer or service definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 56

- **Row number:** 10520
- **Label A:** Mortgage
- **Label B:** Consumer loan
- **Confidence A / B:** high / high
- **Agreed label:** Mortgage
- **Reasoning:** GreenTree, the mortgage servicer, paid property insurance out of the consumer's escrow account to the wrong company. This is the same escrow mishandling pattern as 10454, so Mortgage. Settled by the Mortgage definition (revision R1: servicing, escrow and loss mitigation on a mortgage are Mortgage).
- **Caused a protocol revision:** R1
- **Slide 6 example:** no

### Resolution 57

- **Row number:** 10524
- **Label A:** Bank account or service
- **Label B:** Money transfer or service
- **Confidence A / B:** high / high
- **Agreed label:** Money transfer or service
- **Reasoning:** Wells Fargo moved money from the daughter's minor account into the consumer's account without explanation. The complaint is about that transfer between accounts, so Money transfer or service. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Money transfer or service definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 58

- **Row number:** 10549
- **Label A:** Credit reporting
- **Label B:** Bank account or service
- **Confidence A / B:** high / high
- **Agreed label:** Credit reporting
- **Reasoning:** A boilerplate FCRA complaint naming a specific account and balance. This is a credit report dispute, so Credit reporting. Settled by E1 override 2 and the Credit reporting definition (revision R3: a complaint whose only remedy is a change to the credit file is Credit reporting).
- **Caused a protocol revision:** R3
- **Slide 6 example:** no

### Resolution 59

- **Row number:** 10557
- **Label A:** Credit reporting
- **Label B:** Bank account or service
- **Confidence A / B:** high / high
- **Agreed label:** Credit reporting
- **Reasoning:** An FCRA template complaint asserting the right to accurate reporting, the same pattern as 10549 and 10120. This is a credit report dispute, so Credit reporting. Settled by E1 override 2 and the Credit reporting definition (revision R3: a complaint whose only remedy is a change to the credit file is Credit reporting).
- **Caused a protocol revision:** R3
- **Slide 6 example:** no

### Resolution 60

- **Row number:** 10560
- **Label A:** Bank account or service
- **Label B:** Money transfer or service
- **Confidence A / B:** high / high
- **Agreed label:** Bank account or service
- **Reasoning:** Small unauthorised transactions hit several Bank of America checking accounts and the bank made no adjustments. This is fraud on deposit accounts, the same pattern as 10483 and 10805, so Bank account or service. Settled by the Bank account and Money transfer definitions (revision R6: freezes, closures and unauthorised transactions on a deposit account are Bank account or service).
- **Caused a protocol revision:** R6
- **Slide 6 example:** no

### Resolution 61

- **Row number:** 10609
- **Label A:** Money transfer or service
- **Label B:** Bank account or service
- **Confidence A / B:** high / high
- **Agreed label:** Bank account or service
- **Reasoning:** Cash App closed the consumer's account and the remaining funds were never returned. Cash App is the account provider here, so Bank account or service. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Bank account or service definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 62

- **Row number:** 10714
- **Label A:** Credit reporting
- **Label B:** Debt collection
- **Confidence A / B:** high / high
- **Agreed label:** Debt collection
- **Reasoning:** A creditor kept reporting derogatory history on a debt discharged in bankruptcy, which the consumer frames as a violation of the automatic stay. Continuing to treat a discharged debt as owed is collection conduct, so Debt collection. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Debt collection definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 63

- **Row number:** 10827
- **Label A:** Mortgage
- **Label B:** Consumer loan
- **Confidence A / B:** high / high
- **Agreed label:** Mortgage
- **Reasoning:** Fay Servicing lost the consumer's mortgage loan modification application and stalled the loss mitigation process for months. This is mortgage loss mitigation, so Mortgage. Settled by the Mortgage definition (revision R1: servicing, escrow and loss mitigation on a mortgage are Mortgage).
- **Caused a protocol revision:** R1
- **Slide 6 example:** no

### Resolution 64

- **Row number:** 10887
- **Label A:** Credit reporting
- **Label B:** Bank account or service
- **Confidence A / B:** high / high
- **Agreed label:** Credit reporting
- **Reasoning:** A boilerplate FCRA complaint about an account furnished without consent, with no product named. This is a credit report dispute, so Credit reporting. Settled by E1 override 2 and the Credit reporting definition (revision R3: a complaint whose only remedy is a change to the credit file is Credit reporting).
- **Caused a protocol revision:** R3
- **Slide 6 example:** no

### Resolution 65

- **Row number:** 10933
- **Label A:** Credit card
- **Label B:** Consumer loan
- **Confidence A / B:** high / high
- **Agreed label:** Credit card
- **Reasoning:** Car insurance bought with a PayPal Credit card did not get the advertised six months of no interest. This is a card promotion dispute, so Credit card. Settled by the Credit card definition (revision R4: card products, including prepaid cards where the card itself is the problem, are Credit card).
- **Caused a protocol revision:** R4
- **Slide 6 example:** no

### Resolution 66

- **Row number:** 10951
- **Label A:** Credit card
- **Label B:** Money transfer or service
- **Confidence A / B:** high / high
- **Agreed label:** Credit card
- **Reasoning:** The consumer paid a PayPal Credit balance by money order and was billed again for the same amount. The billing is on the card account, so Credit card. Settled by the Credit card definition (revision R4: card products, including prepaid cards where the card itself is the problem, are Credit card).
- **Caused a protocol revision:** R4
- **Slide 6 example:** no

### Resolution 67

- **Row number:** 10962
- **Label A:** Bank account or service
- **Label B:** Credit reporting
- **Confidence A / B:** high / high
- **Agreed label:** Bank account or service
- **Reasoning:** The consumer cannot link an external bank to an Ally money market savings account. This is an account functionality issue, so Bank account or service. Settled by E1 (label by the product or service the consumer asks the firm to fix) and the Bank account or service definition.
- **Caused a protocol revision:** no
- **Slide 6 example:** no

### Resolution 68

- **Row number:** 10996
- **Label A:** Credit reporting
- **Label B:** Mortgage
- **Confidence A / B:** high / high
- **Agreed label:** Credit reporting
- **Reasoning:** Credco, a third-party mortgage agency, ran the consumer's credit twice for a rehab mortgage without a signed authorisation. The complaint is the unauthorised inquiries, the same pattern as 10452, so Credit reporting. Settled by E1 override 2 and the Credit reporting definition (revision R3: a complaint whose only remedy is a change to the credit file is Credit reporting).
- **Caused a protocol revision:** R3
- **Slide 6 example:** no

---

## Chosen examples for Slide 6

1. **Resolution 37 (row 10666, revision R2).** A labelled it Debt collection with
   high confidence and B labelled it Credit card with medium confidence: a
   collector (Sunrise Credit Service) was chasing a card debt the consumer said was
   already settled. The protocol had no rule for exactly this case (E7), so the
   disagreement exposed a gap. The rule now says a collector's conduct is Debt
   collection even when the underlying debt is a credit card, and the same pattern
   settled rows 10517, 10537, 10178, 10116, 10774 and 10575.
2. **Resolution 52 (row 10454, revision R1).** A labelled the escrow mishandling
   by Select Portfolio Servicing as Mortgage and B as Bank account or service. Row
   10520 was the same situation (escrow mishandled by a servicer) and was split
   Mortgage versus Consumer loan, so the labellers had put one pattern into three
   different categories. The Mortgage definition now names escrow, loan
   modification and payment disputes at a servicer as Mortgage, which settled six
   rows (10127, 10219, 10454, 10520, 10602, 10827).
