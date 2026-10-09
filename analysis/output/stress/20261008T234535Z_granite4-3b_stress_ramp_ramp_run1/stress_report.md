# Stress test — granite4:3b

* Run directory: `results/runs/20261008T234535Z_granite4-3b_stress_ramp_ramp_run1`
* Plan: `stress_ramp`; run mode: `real`
* Samples analysed: 132 (excluded by the step boundaries: 0)
* p95 requirement supplied: 10000.0 ms
* Error-rate limit: 0.0500

## The limit

No step crossed either criterion within this ramp.

## Saturation signals (threshold-free)

* p95 rises monotonically across the last 3 steps: **True** (p95 rose by a factor of 2.29 across them)
* Achieved rate stopped tracking the offered rate: **False** — the achieved rate kept tracking the offered rate
* Achieved/offered ratio: first step 1.000, last step 1.000

A rising p95 across consecutive steps, or an achieved rate that no longer follows the offered rate, is evidence of an unbounded queue. In an open-loop test the generator does not slow down when the server does, so the divergence is the system's own saturation showing through.

## Per-step table

| step | start_s | end_s | duration_s | offered_per_min | samples | achieved_per_min | tracking_ratio | errors | error_rate | error_rate_pct | p50_ms | p95_ms | p99_ms | max_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.00 | 120.00 | 120.00 | 1.00 | 2 | 1.00 | 1.00 | 0 | 0.00 | 0.00 | 1311.00 | 1476.60 | 1491.32 | 1495.00 |
| 2 | 120.00 | 240.00 | 120.00 | 5.00 | 10 | 5.00 | 1.00 | 0 | 0.00 | 0.00 | 1433.50 | 2514.45 | 2528.49 | 2532.00 |
| 3 | 240.00 | 360.00 | 120.00 | 9.00 | 18 | 9.00 | 1.00 | 0 | 0.00 | 0.00 | 1141.50 | 2996.55 | 3660.91 | 3827.00 |
| 4 | 360.00 | 480.00 | 120.00 | 13.00 | 26 | 13.00 | 1.00 | 0 | 0.00 | 0.00 | 1753.00 | 2524.75 | 2704.50 | 2745.00 |
| 5 | 480.00 | 600.00 | 120.00 | 17.00 | 34 | 17.00 | 1.00 | 0 | 0.00 | 0.00 | 1803.50 | 4394.10 | 4975.20 | 5061.00 |
| 6 | 600.00 | 720.00 | 120.00 | 21.00 | 42 | 21.00 | 1.00 | 0 | 0.00 | 0.00 | 2969.00 | 5790.05 | 6516.59 | 6681.00 |

`achieved_per_min` uses each step's nominal duration. `error_rate` is the fraction compared against --error-rate-limit; `error_rate_pct` is the same number as a percentage, for the slide.

See `stress_ramp.png` for p95 and the achieved rate against the offered rate.

## Warnings raised by this run

* Note: step boundaries are measured from the arrival schedule's start, 2026-10-08T23:46:16.256000+00:00 (jmeter-log); the first sample arrived 67.5 s later.

## Interpretation

The limit stated in one sentence, and the component it is attributed to, are on Slide 9, supported by `analysis/bottleneck_hints.py` run on this same run directory. Where no step crossed a criterion, Slide 9 reports the top offered rate as a lower bound on the limit, and `docs/playbooks/stress-test.md` section 2.1 names the steeper ramp that is then run. This file reports; it does not interpret.
