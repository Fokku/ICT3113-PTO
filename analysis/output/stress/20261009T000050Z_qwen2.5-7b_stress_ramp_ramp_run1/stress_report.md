# Stress test — qwen2.5:7b

* Run directory: `results/runs/20261009T000050Z_qwen2.5-7b_stress_ramp_ramp_run1`
* Plan: `stress_ramp`; run mode: `real`
* Samples analysed: 132 (excluded by the step boundaries: 0)
* p95 requirement supplied: 10000.0 ms
* Error-rate limit: 0.0500

## The limit

First step to cross a criterion: step 6 (offered 21/min, achieved 21.0/min): p95 26375.4 ms > limit 10000.0 ms.

* Step: 6
* Offered rate: 21/min
* Achieved rate: 21.0/min
* p95 at that step: 26375.4 ms
* Error rate at that step: 0.0000
* Criterion that tripped: p95 26375.4 ms > limit 10000.0 ms

## Saturation signals (threshold-free)

* p95 rises monotonically across the last 3 steps: **True** (p95 rose by a factor of 3.05 across them)
* Achieved rate stopped tracking the offered rate: **False** — the achieved rate kept tracking the offered rate
* Achieved/offered ratio: first step 1.000, last step 1.000

A rising p95 across consecutive steps, or an achieved rate that no longer follows the offered rate, is evidence of an unbounded queue. In an open-loop test the generator does not slow down when the server does, so the divergence is the system's own saturation showing through.

## Per-step table

| step | start_s | end_s | duration_s | offered_per_min | samples | achieved_per_min | tracking_ratio | errors | error_rate | error_rate_pct | p50_ms | p95_ms | p99_ms | max_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.00 | 120.00 | 120.00 | 1.00 | 2 | 1.00 | 1.00 | 0 | 0.00 | 0.00 | 3452.00 | 4622.90 | 4726.98 | 4753.00 |
| 2 | 120.00 | 240.00 | 120.00 | 5.00 | 10 | 5.00 | 1.00 | 0 | 0.00 | 0.00 | 3191.50 | 4718.50 | 4880.50 | 4921.00 |
| 3 | 240.00 | 360.00 | 120.00 | 9.00 | 18 | 9.00 | 1.00 | 0 | 0.00 | 0.00 | 3329.50 | 6825.45 | 7194.69 | 7287.00 |
| 4 | 360.00 | 480.00 | 120.00 | 13.00 | 27 | 13.50 | 1.04 | 0 | 0.00 | 0.00 | 4805.00 | 8637.00 | 9342.82 | 9497.00 |
| 5 | 480.00 | 600.00 | 120.00 | 17.00 | 33 | 16.50 | 0.97 | 0 | 0.00 | 0.00 | 4473.00 | 9770.60 | 10445.68 | 10590.00 |
| 6 | 600.00 | 720.00 | 120.00 | 21.00 | 42 | 21.00 | 1.00 | 0 | 0.00 | 0.00 | 20191.50 | 26375.40 | 28429.53 | 29769.00 |

`achieved_per_min` uses each step's nominal duration. `error_rate` is the fraction compared against --error-rate-limit; `error_rate_pct` is the same number as a percentage, for the slide.

See `stress_ramp.png` for p95 and the achieved rate against the offered rate.

## Warnings raised by this run

* Note: step boundaries are measured from the arrival schedule's start, 2026-10-09T00:01:47.956000+00:00 (jmeter-log); the first sample arrived 30.1 s later.

## Interpretation

The limit stated in one sentence, and the component it is attributed to, are on Slide 9, supported by `analysis/bottleneck_hints.py` run on this same run directory. Where no step crossed a criterion, Slide 9 reports the top offered rate as a lower bound on the limit, and `docs/playbooks/stress-test.md` section 2.1 names the steeper ramp that is then run. This file reports; it does not interpret.
