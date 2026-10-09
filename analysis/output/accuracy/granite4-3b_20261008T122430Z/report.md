# Accuracy -- granite4:3b (20261008T122430Z)

* Accuracy run directory: `results/accuracy/granite4-3b_20261008T122430Z`
* Run mode: `real`
* Freeze commit: `41d6ce2c2aa8c9e03c9d1e2abe2e23096aba9fba`
* Narrative source for misclassified.csv: /home/fokku/claude/ICT3113-PTO/data/team_rows.csv

## Overall

* Golden rows: 200
* Evaluated (golden rows with a usable prediction): 200
* Coverage of the golden set: 1.0000
* Overall accuracy: 0.6600
* Accuracy excluding UNPARSEABLE: 0.6600
* UNPARSEABLE replies: 0 (rate 0.0000)
* Macro recall: 0.6061; macro precision: 0.7639

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
| Credit reporting | 41 | 71 | 37 | 0.9024 | 0.5211 | 0.6607 | 0 |
| Debt collection | 23 | 9 | 9 | 0.3913 | 1.0000 | 0.5625 | 0 |
| Mortgage | 27 | 20 | 17 | 0.6296 | 0.8500 | 0.7234 | 0 |
| Credit card | 27 | 37 | 21 | 0.7778 | 0.5676 | 0.6562 | 0 |
| Bank account or service | 40 | 45 | 33 | 0.8250 | 0.7333 | 0.7765 | 0 |
| Consumer loan | 23 | 10 | 8 | 0.3478 | 0.8000 | 0.4848 | 0 |
| Money transfer or service | 19 | 8 | 7 | 0.3684 | 0.8750 | 0.5185 | 0 |

## Confusion matrix

| golden_label | Credit reporting | Debt collection | Mortgage | Credit card | Bank account or service | Consumer loan | Money transfer or service | UNPARSEABLE |
|---|---|---|---|---|---|---|---|---|
| Credit reporting | 37 | 0 | 2 | 2 | 0 | 0 | 0 | 0 |
| Debt collection | 14 | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| Mortgage | 2 | 0 | 17 | 5 | 1 | 2 | 0 | 0 |
| Credit card | 4 | 0 | 0 | 21 | 2 | 0 | 0 | 0 |
| Bank account or service | 3 | 0 | 0 | 3 | 33 | 0 | 1 | 0 |
| Consumer loan | 9 | 0 | 1 | 5 | 0 | 8 | 0 | 0 |
| Money transfer or service | 2 | 0 | 0 | 1 | 9 | 0 | 7 | 0 |

See `confusion_matrix.png` for the annotated greyscale heatmap.

## Data quality

* Responses in the service log: 200
* Golden rows with no response: 0 (`missing_rows.csv`)
* Responses with a failed model call: 0 (`errored_responses.csv`)
* Golden rows with more than one response: 0 (`duplicates.csv`; the last by timestamp was scored)
* Responses that could not be joined to a golden row: 0 (`unmatched_responses.csv`)

## Interpretation

`misclassified.csv` lists every wrong row with the golden label, the predicted label, the raw model reply and the first characters of the ticket. It is the input to the Slide 10 commentary (Part 3 — Jolie Ngai Ning Li): which category pairs this model confuses, what the narratives in those pairs have in common, and which categories miss the per-category requirement R4 in `workload/requirements.md`. This file reports; it does not interpret.
