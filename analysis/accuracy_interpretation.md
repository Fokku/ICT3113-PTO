# 3.3 After the benchmarks: interpret the accuracy results

This interpretation uses the completed accuracy outputs in [output/accuracy](output/accuracy/), measured against the golden labels. It compares them with [the prediction record](../predictions/prediction_record.md), Sections 2 and 3, and explains plausible category boundaries using [the labelling protocol](../labelling/protocol.md). No new benchmark or code is needed.

## Overall accuracy and format failures

Source: [model_comparison.md](output/accuracy/model_comparison.md). Every candidate has 200 evaluated responses, complete coverage, and no missing, errored, duplicate or unmatched responses.

| Candidate | Correct / evaluated | Overall accuracy | UNPARSEABLE count | Accuracy excluding UNPARSEABLE |
|---|---|---|---|---|
| `llama3.2:1b-instruct-q4_K_M` | 52/200 | 26.0% | 0 | 26.0% |
| `llama3.2:3b` | 97/200 | 48.5% | 0 | 48.5% |
| `granite4:3b` | 132/200 | 66.0% | 0 | 66.0% |
| `qwen2.5:7b` | 148/200 | 74.0% | 0 | 74.0% |

All observed failures are misclassifications with parseable labels. The client could route a wrong label to the wrong team; an unparseable answer would instead require a format fallback, retry or manual routing. These tests observed no parsing failures. That establishes parser acceptance on this set, rather than proving every raw reply followed the requested format exactly.

Qwen is the strongest candidate on overall accuracy, but none meets [workload R3's 90% overall accuracy threshold](../workload/requirements.md). None meets R4's 80% recall threshold for every category either. Accuracy alone does not establish suitability for deployment.

## Per-category accuracy

Here, accuracy per category means **recall**: correct predictions divided by the number of tickets with that golden label. Percentages below are rounded to one decimal place from the full-precision recalls in each run's `per_category.csv`, avoiding double rounding of the Markdown tables. The fractions retain the exact correct counts and support.

| Golden category | Llama 1B | Llama 3B | Granite 3B | Qwen 7B |
|---|---|---|---|---|
| Credit reporting | 41/41 (100.0%) | 27/41 (65.9%) | 37/41 (90.2%) | 36/41 (87.8%) |
| Debt collection | 1/23 (4.3%) | 13/23 (56.5%) | 9/23 (39.1%) | 17/23 (73.9%) |
| Mortgage | 0/27 (0.0%) | 3/27 (11.1%) | 17/27 (63.0%) | 19/27 (70.4%) |
| Credit card | 2/27 (7.4%) | 6/27 (22.2%) | 21/27 (77.8%) | 17/27 (63.0%) |
| Bank account or service | 0/40 (0.0%) | 36/40 (90.0%) | 33/40 (82.5%) | 33/40 (82.5%) |
| Consumer loan | 8/23 (34.8%) | 12/23 (52.2%) | 8/23 (34.8%) | 13/23 (56.5%) |
| Money transfer or service | 0/19 (0.0%) | 0/19 (0.0%) | 7/19 (36.8%) | 13/19 (68.4%) |

Sources: each run's `per_category.md`: [Llama 1B](output/accuracy/llama3.2-1b-instruct-q4_K_M_20261008T121612Z/per_category.md), [Llama 3B](output/accuracy/llama3.2-3b_20261008T121848Z/per_category.md), [Granite](output/accuracy/granite4-3b_20261008T122430Z/per_category.md), [Qwen](output/accuracy/qwen2.5-7b_20261008T123045Z/per_category.md).

## Where each model goes wrong

The hardest category is the one with the lowest recall, as defined by the prediction record. The largest number of wrong tickets can occur in a different category because category supports differ. Confusion counts below are exact off-diagonal entries: golden category → predicted category.

### Llama 1B

Mortgage, Bank account or service and Money transfer or service tie for lowest recall, all at zero. Their dominant errors are Mortgage → Credit reporting (19), Bank account → Credit reporting (37), and Money transfer → Credit reporting (14). Bank account is also the largest source of wrong tickets by count. Debt collection → Credit reporting (21) and Credit card → Credit reporting (21) show that this is a broad fallback pattern, rather than one isolated category boundary. The model predicts Credit reporting for 168 tickets, against a true support of 41.

Protocol E1 and E4 require the label to follow the remedy and subject of the complaint, rather than a mention of a credit report in the background. Mortgage servicing belongs under Mortgage (R1); account access, fees and freezes belong under Bank account (R6); a specific failed payment belongs under Money transfer. Those distinctions offer a plausible explanation for these errors. The matrix establishes the fallback pattern but cannot establish the model's reasoning or prove that category order caused it.

Source: [confusion matrix](output/accuracy/llama3.2-1b-instruct-q4_K_M_20261008T121612Z/confusion_matrix.md) and the per-category output linked above.

### Llama 3B

Money transfer has the lowest recall, with 0/19 correct: 16 go to Bank account, two to Credit reporting and one to Credit card. Mortgage and Credit card are the next weakest categories. Mortgage's main error is → Bank account (10), followed by → Consumer loan (6); Credit card's main error is → Bank account (15), followed by → Credit reporting (4). Mortgage contributes the most wrong tickets by count, followed by Credit card. The model predicts Bank account for 94 tickets, against a true support of 40.

R6 distinguishes a specific movement of money from an account relationship. Naming a bank in a transfer complaint does not make it an account complaint. R1 similarly keeps escrow and mortgage payment servicing under Mortgage, even when the narrative discusses accounts or loans. R4 includes prepaid and gift cards under Credit card, and the Credit card definition separates issuer billing or fraud handling from a credit-file-only remedy. These boundaries can explain why broad Bank account predictions absorb more specific complaints, though identifying which rule explains an individual error would require reading that ticket.

Source: [confusion matrix](output/accuracy/llama3.2-3b_20261008T121848Z/confusion_matrix.md) and the per-category output linked above.

### Granite 3B

Consumer loan has the lowest recall, with 8/23 correct. Its main confusion is → Credit reporting (9), followed by → Credit card (5). Money transfer is next weakest, with 7/19 correct and nine → Bank account. Debt collection has 9/23 correct, and all its other tickets go to Credit reporting (14). Consumer loan also contributes the most wrong tickets by count, followed by Debt collection.

R5 puts student-loan forgiveness, deferment, consolidation and repayment under Consumer loan. A reporting dispute that depends on the loan's terms also stays under Consumer loan; a dispute only about file accuracy is Credit reporting. R2/E7 makes collector conduct Debt collection even when it includes reporting the debt. These rules explain plausible Consumer loan and Debt collection boundaries with Credit reporting. Consumer loan → Credit card has no clear explanation from the aggregate matrix alone. The Money transfer → Bank account errors match the R6 boundary described above.

Source: [confusion matrix](output/accuracy/granite4-3b_20261008T122430Z/confusion_matrix.md) and the per-category output linked above.

### Qwen 7B

Consumer loan has the lowest recall, with 13/23 correct: five → Debt collection, four → Credit reporting and one → Mortgage. Credit card is next weakest, with 17/27 correct: its largest confusion is → Bank account (5), followed by → Credit reporting (3). Consumer loan and Credit card tie for the largest number of wrong tickets. All Money transfer misses go to Bank account (6); most Debt collection misses go to Credit reporting (5).

R5 distinguishes non-mortgage loan servicing and repayment from collector conduct and credit-file-only disputes. R2/E7 gives collector conduct precedence, so the deciding issue is the actor and remedy, rather than merely whether the narrative mentions a debt. R4's inclusion of prepaid and gift cards creates another boundary with account services. These are plausible explanations for Qwen's remaining confusions, not proof that every error concerns a student loan or prepaid card.

Source: [confusion matrix](output/accuracy/qwen2.5-7b_20261008T123045Z/confusion_matrix.md) and the per-category output linked above.

## Where our predictions were wrong

Prediction source: [prediction_record.md](../predictions/prediction_record.md), Sections 2 and 3. Measured evidence comes from the output files linked above. Expected categories and bands below are historical predictions, not measured figures.

**Freeze provenance:** all four accuracy runs' `results/accuracy/<run>/freeze.json` files record freeze commit `41d6ce2c2aa8c9e03c9d1e2abe2e23096aba9fba`. The current prediction file matches the prediction blob at that commit (`c1d1da3f0e2db2487d8f38a231affc6ddee0e608`). However, the local `golden-freeze` tag currently resolves to the earlier commit `ef5a1b2`, whose prediction file is still an unfilled template. Therefore this comparison uses the prediction version recorded by the runs, rather than the current local tag. The local tag does not currently substantiate the prediction record's statement that it was moved to the completed record.

| Candidate | Predicted hardest | Measured hardest | What we got wrong |
|---|---|---|---|
| Llama 1B | Debt collection and Money transfer, both near zero; explicitly not blind | Mortgage, Bank account and Money transfer tie at zero | We missed the complete failure on Mortgage and Bank account. Debt collection is very weak but is not tied for lowest recall. |
| Llama 3B | Money transfer | Money transfer | The hardest-category prediction holds, but it did not capture how weak Mortgage and Credit card also are. The record says the error direction may have been coloured by earlier observations. |
| Granite 3B | Credit card | Consumer loan | We focused on the prepaid-card boundary in R4 and overlooked the Consumer loan boundary in R5. Credit card recall is 77.8%, while Consumer loan recall is 34.8%. |
| Qwen 7B | Credit card | Consumer loan | We again overlooked R5. Credit card is second weakest, but Consumer loan is weakest at 56.5%. Its errors mainly go to Debt collection and Credit reporting. |

Our shared claim that **Mortgage would be easiest** was wrong for every candidate. Mortgage recall is 0.0%, 11.1%, 63.0% and 70.4% in model order above. Distinctive vocabulary did not reliably preserve the product boundary. R1 already warned that escrow, payment disputes and servicing changes could be confused with other account or loan categories; we should have treated that boundary as a risk in the prediction.

We also predicted **Bank account would fail the per-category requirement for every model**. It reaches 90.0% for Llama 3B and 82.5% for both Granite and Qwen. For Llama 3B, that high recall coexists with precision of only 38.3%: frequent Bank account predictions catch true account tickets while misrouting many other tickets. Recall alone therefore understates the client-facing cost of this fallback. The requirement-level prediction that Mortgage would clear 80% for the three larger models is also wrong: none reaches that threshold.

Our prediction that **Credit reporting would have the most false positives for every model** was wrong for Llama 3B and Qwen. Llama 3B has 58 Bank account false positives versus 20 Credit reporting false positives; Qwen has 16 versus 14. False positives are calculated as `predicted_as - correct` in the per-category CSVs (equivalently, the off-diagonal column total in the matrices). Predicting Credit reporting more often than its true support does not by itself establish that it has the largest false-positive count. We underestimated how strongly Bank account would absorb other categories for these two models.

Our predicted Credit card → Bank account error direction holds for Llama 3B and Qwen, but Granite's largest Credit card confusion is → Credit reporting (4), ahead of → Bank account (2). Our predicted Bank account → Money transfer direction holds for Qwen (4); Granite instead ties at three each → Credit reporting and → Credit card, and Llama 3B has no Bank account → Money transfer errors. The expected boundary errors were model-dependent.

Both Llama models also fell below their predicted overall accuracy bands: Llama 1B measured 26.0% against the accepted 33–43% band, and Llama 3B measured 48.5% against 49–61%. Their broad-category fallback patterns are consistent with that shortfall. The 1B prediction was explicitly not blind. Its predicted UNPARSEABLE range was 1–5, whereas the measured count is zero; the larger models' zero counts fall inside their predicted ranges. We cannot test the predicted source of unparseable replies because none occurred.

## Figure verification

Every measured figure quoted here is traceable to `output/accuracy/model_comparison.csv` or the four runs' `per_category.csv` and `confusion_matrix.csv`; the corresponding Markdown reports are linked above. Percentages are rounded from the full-precision CSV metrics; counts are taken from the generated tables. Category ranking and error-count ordering are checked against those same tables. Protocol explanations are interpretations of the definitions, with uncertainty stated where the matrices cannot identify the cause. The prediction record remains unchanged.

An additional audit checked every confusion-matrix cell against the run's raw `responses.csv`, joined to `golden/golden_set.csv` by row number. All four runs match their generated matrices, and all source links in this document resolve.
