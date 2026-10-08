# Excluded results — kept, not reported

Every directory under `results/excluded/` is evidence we keep but do **not** report. Nothing in here
appears on a slide or in `analysis/output/`, and the analysis scripts are never pointed at this folder.
Each entry says what the run was and why it is excluded. Entries are never deleted.

- `results/excluded/accuracy/llama3.2-1b_20261008T052403Z/` — an aborted start of the accuracy test for
  `llama3.2:1b` on the original service host `tw`, 2026-10-08 05:24 UTC (13:24 SGT): 9 tickets posted, then
  stopped. Excluded because it predates the prediction record: the `golden-freeze` tag then in force
  (commit `ef5a1b2`) froze an empty prediction-record template. See `predictions/prediction_record.md`, §0.
- `results/excluded/accuracy/llama3.2-1b_20261008T052511Z/` — the complete accuracy test for `llama3.2:1b` on
  `tw`, 2026-10-08 05:25–05:42 UTC, 200 tickets, `freeze.json` pointing at `ef5a1b2`. Excluded for the same
  reason: it is the one measurement made before any prediction was written. Its predicted-category counts
  were seen by the person who drafted the prediction record, which is why the `llama3.2:1b` accuracy entries
  in the record are marked "not blind". The accuracy test is repeated for every model after the re-cut
  freeze, on the new test environment (`docs/test-environment.md`).
