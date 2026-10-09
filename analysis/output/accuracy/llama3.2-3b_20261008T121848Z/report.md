# Accuracy -- llama3.2:3b (20261008T121848Z)

* Accuracy run directory: `results/accuracy/llama3.2-3b_20261008T121848Z`
* Run mode: `real`
* Freeze commit: `41d6ce2c2aa8c9e03c9d1e2abe2e23096aba9fba`
* Narrative source for misclassified.csv: /home/fokku/claude/ICT3113-PTO/data/team_rows.csv

## Overall

* Golden rows: 200
* Evaluated (golden rows with a usable prediction): 200
* Coverage of the golden set: 1.0000
* Overall accuracy: 0.4850
* Accuracy excluding UNPARSEABLE: 0.4850
* UNPARSEABLE replies: 0 (rate 0.0000)
* Macro recall: 0.4255; macro precision: 0.6417

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

## Per category

| category | support | predicted_as | correct | recall | precision | f1 | unparseable |
|---|---|---|---|---|---|---|---|
| Credit reporting | 41 | 47 | 27 | 0.6585 | 0.5745 | 0.6136 | 0 |
| Debt collection | 23 | 28 | 13 | 0.5652 | 0.4643 | 0.5098 | 0 |
| Mortgage | 27 | 3 | 3 | 0.1111 | 1.0000 | 0.2000 | 0 |
| Credit card | 27 | 7 | 6 | 0.2222 | 0.8571 | 0.3529 | 0 |
| Bank account or service | 40 | 94 | 36 | 0.9000 | 0.3830 | 0.5373 | 0 |
| Consumer loan | 23 | 21 | 12 | 0.5217 | 0.5714 | 0.5455 | 0 |
| Money transfer or service | 19 | 0 | 0 | 0.0000 | n/a | n/a | 0 |

## Confusion matrix

| golden_label | Credit reporting | Debt collection | Mortgage | Credit card | Bank account or service | Consumer loan | Money transfer or service | UNPARSEABLE |
|---|---|---|---|---|---|---|---|---|
| Credit reporting | 27 | 1 | 0 | 0 | 11 | 2 | 0 | 0 |
| Debt collection | 5 | 13 | 0 | 0 | 5 | 0 | 0 | 0 |
| Mortgage | 4 | 4 | 3 | 0 | 10 | 6 | 0 | 0 |
| Credit card | 4 | 1 | 0 | 6 | 15 | 1 | 0 | 0 |
| Bank account or service | 2 | 2 | 0 | 0 | 36 | 0 | 0 | 0 |
| Consumer loan | 3 | 7 | 0 | 0 | 1 | 12 | 0 | 0 |
| Money transfer or service | 2 | 0 | 0 | 1 | 16 | 0 | 0 | 0 |

See `confusion_matrix.png` for the annotated greyscale heatmap.

## Data quality

* Responses in the service log: 200
* Golden rows with no response: 0 (`missing_rows.csv`)
* Responses with a failed model call: 0 (`errored_responses.csv`)
* Golden rows with more than one response: 0 (`duplicates.csv`; the last by timestamp was scored)
* Responses that could not be joined to a golden row: 0 (`unmatched_responses.csv`)

## Interpretation

`misclassified.csv` lists every wrong row with the golden label, the predicted label, the raw model reply and the first characters of the ticket. It is the input to the Slide 10 commentary (Part 3 — Jolie Ngai Ning Li): which category pairs this model confuses, what the narratives in those pairs have in common, and which categories miss the per-category requirement R4 in `workload/requirements.md`. This file reports; it does not interpret.
