# Slide 5 — Speed results (draft)

**Brief (verbatim):** "p50 per run with spread, pooled p95, throughput and error rate for every
speed-tested configuration. Escalation fraction under load."
**Owner:** Yeo Kai Yuan (Part 1).
**Done when** (`../outline_a2.md`): every number traces to a `.jtl` file or a run's `service.jsonl` under
`results/`, through `analysis/output/speed_a2/`.

Every figure below comes from `python analysis/summarise_load_a2.py` (default output
`analysis/output/speed_a2/`). Nothing is typed in by hand, and **no Assignment 1 speed figure is used**
(TODO_A2.md, guardrail 10).

---

## Title

Speed under the same open-loop load: `<rate>/min for <duration>, 3 runs per configuration`

The rate and run length come from `docs/a2/arrival_rate.json` (S = `<s>` s, from `qwen2.5:7b`).

## Main table: one row per speed-tested configuration (`per_config.csv`)

| Configuration | p50 per run (ms) | p50 mean ± SD (ms) | Pooled p95 (ms) [n] | Throughput (req/s) | Error rate | Escalated under load | Accuracy |
|---|---|---|---|---|---|---|---|
| `qwen2.5:7b` alone (reference) | `p50_per_run_ms` | `p50_mean_ms` ± `p50_sd_ms` | `pooled_p95_ms` [`pooled_n`] | `throughput_mean_rps` | `error_rate_mean_pct` | n/a | passes |
| each other single model that passed both limits | ... | ... | ... | ... | ... | n/a | passes |
| cascade, Setting A | ... | ... | ... | ... | ... | `escalated_count`/`escalation_total` | `passes_accuracy` |
| cascade, Setting B | ... | ... | ... | ... | ... | ... | ... |

- **Spread.** Show the three per-run p50s, not just the mean (brief: "p50 per run with spread"). Use
  `p50_min_ms`–`p50_max_ms` for the range.
- **Pooled p95.** One figure per configuration over all three runs, always followed by its count `[pooled_n]`
  (brief: "state the number it is based on"). **No p99 anywhere on this slide.**
- **Failing configurations.** If a cascade setting failed its accuracy limits (Slide 4), keep its row but
  **visibly mark it "not passing accuracy"** (`label` column). Single models that failed accuracy are not
  speed-tested and do not appear.
- **"Faster than the reference".** `faster_than_reference` applies the prediction record §4 rule: per-run p50
  ranges that don't overlap. Slide 7 uses it; here it can be a small marker.

## Under the table: escalation under load vs in the accuracy test (cascade only)

From `per_config.csv`: `escalation_fraction` (speed runs, from each run's `service.jsonl`) against
`accuracy_escalation_fraction` (the 101 test rows), and `escalation_gap_pp`. If `escalation_gap_flag` is
true (gap above the 15 pp threshold in `predictions/prediction_record_a2.md` §4), give the one-line
explanation the brief asks for. The two ticket sets differ: the 100-ticket workload vs the 101 test rows.

## Small print: run validity (`per_run.csv`)

- Requests **sent / completed / errored / unfinished** per run (`sent`, `completed`, `errored`,
  `unfinished`), reported even when non-zero. A run with unfinished requests is reported, not dropped
  (brief, Step 4).
- **No-queue check** per run (`no_queue_check`). A run flagged `queued` is listed but not compared on p50.
- Every run's `valid` and `reasons`. An invalid run stays listed alongside its replacement (playbook §6).

## Traceability rows to add to `../outline_a2.md` (Part 5's map)

| Slide | Figure | Source file | Produced by |
|---|---|---|---|
| 5 | p50 per run, mean, SD, pooled p95 + n, throughput, error rate | `analysis/output/speed_a2/per_config.csv` | `python analysis/summarise_load_a2.py` over `results/runs/*_speed_a2_*` |
| 5 | sent/completed/errored/unfinished, no-queue check | `analysis/output/speed_a2/per_run.csv` | same |
| 5 | escalation under load | `analysis/output/speed_a2/per_config.csv` (`escalation_fraction`) ← each run's `service.jsonl` | same |
| 5 | every run reconciles | `analysis/output/reconcile/<run>__checks.csv` | `python analysis/reconcile.py --run-dir <run>` |
