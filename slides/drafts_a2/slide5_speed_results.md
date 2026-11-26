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

**Status (2026-11-26): final content.** Every figure below is copied from `analysis/output/speed_a2/`
(primary, frozen rule) or `analysis/output/speed_a2_secondary/` (labelled secondary), produced from the nine runs
in `results/runs/20261126T*_speed_a2_8.98pm_run*` (`docs/a2/run-log.md`).

## Title

Speed under the same open-loop load: 8.98/min for 300 s, 3 runs per configuration. The cascade is not faster than
`qwen2.5:7b` alone.

Subtitle: rate and run length from S = 3.339 s (`qwen2.5:7b`, rows 10685 / 10910 / 10627, `docs/a2/arrival_rate.json`);
random arrivals; the same 100-ticket list in the same order; load generator on a separate machine.

## Main table: per-run p50 and the frozen-rule figures (`speed_a2/per_config.csv`)

| Configuration | p50 per run (ms) | Counted runs → p50 (ms) | Pooled p95 (ms) [n] | Throughput (req/s) | Error rate | Escalated under load | Accuracy (Slide 4) |
|---|---|---|---|---|---|---|---|
| `qwen2.5:7b` alone (reference) | 6121 q / 6535 q / **4505** | run 3 → 4505 | 10196 [44] | 0.150 | 0% | n/a | passes (75/101) |
| Cascade, Setting A | 9611 q / **7629** / 9250 q | run 2 → 7629, **slower** | 29706 [44] | 0.149 | 0% | 33/44 per run (75.0%) | passes (76/101) |
| Cascade, Setting B | 5501 q / **5569** / 5029 q | run 2 → 5569, **slower** | 18611 [44] | 0.157 | 0% | 23/44 per run (52.3%) | passes (74/101) |

**q** = flagged queued by the frozen no-queue check (`predictions/prediction_record_a2.md` §4), so listed but not
compared on p50. No single model other than `qwen2.5:7b` passed accuracy, so none other was speed-tested. No p99
anywhere.

## Beside it, labelled: the secondary reading (`speed_a2_secondary/per_config.csv`)

> **Secondary analysis, not the frozen rule:** halves test only (the queue-wait limit is not applied; see
> `predictions/prediction_record_a2_appendix.md`).

| Configuration | Counted runs | p50 mean ± SD (ms) | p50 range (ms) | Pooled p95 (ms) [n] | vs `qwen2.5:7b` |
|---|---|---|---|---|---|
| `qwen2.5:7b` alone | runs 1, 3 | 5313 ± 1143 | 4505–6121 | 11517 [88] | reference |
| Cascade, Setting A | runs 1, 2, 3 | 8830 ± 1056 | 7629–9611 | 29931 [132] | slower |
| Cascade, Setting B | run 2 | 5569 | 5569 | 18611 [44] | not distinguishable (overlaps) |

One line under it: *the two readings agree: neither cascade setting is distinguishably faster than `qwen2.5:7b`
alone.*

## Under the table: escalation under load vs in the accuracy test (cascade only)

| | Setting A | Setting B |
|---|---|---|
| Escalated under load (speed runs, service logs) | 99/132 (75.0%), 33/44 in every run | 69/132 (52.3%), 23/44 in every run |
| Escalated in the accuracy test (101 test rows) | 83/101 (82.2%) | 65/101 (64.4%) |
| Gap | −7.2 pp | −12.1 pp |
| p50 of accepted vs escalated tickets (counted run) | 2287 vs 9231 ms | 3354 vs 9006 ms |

Both gaps are under the 15 pp "large gap" line (§4). They differ because the 100-ticket workload and the 101
test rows are different tickets: proportionally more of the workload's tickets get an accepted category from
granite, so fewer escalate. The fraction is identical in all three runs because the same tickets go through a deterministic rule.

## Small print: run validity (`speed_a2/per_run.csv`)

- Every run: 44 sent / 44 completed / 0 errored / 0 unfinished, `GET /stats` delta 44, `reconcile.py` PASS, 3
  warm-ups, expected models resident before the run, no mid-run model load (largest `load_duration` 14 ms).
- No-queue check (frozen): queued in 6 of 9 runs. `qwen2.5:7b` runs 1–2 and cascade A runs 1 and 3 fail on queue wait
  (median `ollama_other_ms` up to 2.3 s; `qwen2.5:7b` run 2 also on the halves test). Cascade B runs 1 and 3 fail on the halves test. The cause, random
  arrivals at about 50% utilisation (Ollama busy 0.52–0.54 for `qwen2.5:7b` alone, 0.92–1.02 for cascade A), is
  in the appendix. No run was re-run.

## Traceability rows to add to `../outline_a2.md` (Part 5's map)

| Slide | Figure | Source file | Produced by |
|---|---|---|---|
| 5 | p50 per run, mean, SD, pooled p95 + n, throughput, error rate | `analysis/output/speed_a2/per_config.csv` | `python analysis/summarise_load_a2.py` over `results/runs/*_speed_a2_*` |
| 5 | sent/completed/errored/unfinished, no-queue check | `analysis/output/speed_a2/per_run.csv` | same |
| 5 | escalation under load | `analysis/output/speed_a2/per_config.csv` (`escalation_fraction`) ← each run's `service.jsonl` | same |
| 5 | every run reconciles | `analysis/output/reconcile/<run>__checks.csv` | `python analysis/reconcile.py --run-dir <run>` |
| 5 | secondary reading (labelled) | `analysis/output/speed_a2_secondary/per_config.csv` | `python analysis/summarise_load_a2.py --secondary-no-queue-wait --out-dir analysis/output/speed_a2_secondary --accuracy-verdicts analysis/output/accuracy_a2/verdicts_a2.csv` |
| 5 | accepted vs escalated p50, busy fraction | `analysis/output/speed_a2/per_run.csv` (`p50_accepted_ms`, `p50_escalated_ms`, `ollama_busy_fraction`) | `python analysis/summarise_load_a2.py --accuracy-verdicts analysis/output/accuracy_a2/verdicts_a2.csv` |
