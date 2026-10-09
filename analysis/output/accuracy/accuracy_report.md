# Accuracy results (all models)

* Golden set: `golden/golden_set.csv` (200 rows)
* Accuracy runs read from: `results/accuracy`
* Accuracy runs found: 4

### How to read these figures

* **Overall accuracy** = correct / evaluated golden rows. `UNPARSEABLE` counts
  in the denominator and never in the numerator: an unreadable reply routes no
  ticket.
* **Accuracy excluding UNPARSEABLE** is the same figure over the parseable
  replies only. Quote both, so that a parsing problem is never presented as a
  classification problem.
* **Per-category accuracy is recall**: of the golden rows truly in category C,
  the fraction predicted C. This is the figure the per-category accuracy
  requirement is written against.
* **Precision** for C: of the rows predicted C, the fraction truly C.
* **Support**: evaluated golden rows truly in C. Read every recall next to its
  support.
* `UNPARSEABLE` is a **predicted-only** column of the confusion matrix. It is
  never attributed to a category the model did not name.

## Per-model comparison

| model_tag | stamp | mode | golden_rows | responses | evaluated | coverage | correct | accuracy | unparseable | unparseable_rate | accuracy_excl_unparseable | macro_recall | macro_precision | missing_golden_rows | errored_responses | duplicate_rows | unmatched_responses |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| granite4:3b | 20261008T122430Z | real | 200 | 200 | 200 | 1.0000 | 132 | 0.6600 | 0 | 0.0000 | 0.6600 | 0.6061 | 0.7639 | 0 | 0 | 0 | 0 |
| llama3.2:1b-instruct-q4_K_M | 20261008T121612Z | real | 200 | 200 | 200 | 1.0000 | 52 | 0.2600 | 0 | 0.0000 | 0.2600 | 0.2093 | 0.3628 | 0 | 0 | 0 | 0 |
| llama3.2:3b | 20261008T121848Z | real | 200 | 200 | 200 | 1.0000 | 97 | 0.4850 | 0 | 0.0000 | 0.4850 | 0.4255 | 0.6417 | 0 | 0 | 0 | 0 |
| qwen2.5:7b | 20261008T123045Z | real | 200 | 200 | 200 | 1.0000 | 148 | 0.7400 | 0 | 0.0000 | 0.7400 | 0.7178 | 0.7615 | 0 | 0 | 0 | 0 |

Per-model detail, including the confusion matrix and the list of misclassified rows, is in the subdirectory named after each run.

## Interpretation

Which model these figures support on accuracy grounds, and which candidates fail requirements R3 and R4, is argued on Slides 10 and 11. Accuracy alone does not decide the recommendation: it is weighed there against the latency and throughput results.
