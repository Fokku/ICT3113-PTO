# Stress test — llama3.2:3b

* Run directory: `results/runs/20261009T003216Z_llama3.2-3b_stress_ramp_ramp_run1`
* Plan: `stress_ramp`; run mode: `real`
* Samples analysed: 420 (excluded by the step boundaries: 0)
* p95 requirement supplied: 10000.0 ms
* Error-rate limit: 0.0500

## The limit

First step to cross a criterion: step 4 (offered 40/min, achieved 39.5/min): p95 13569.6 ms > limit 10000.0 ms.

* Step: 4
* Offered rate: 40/min
* Achieved rate: 39.5/min
* p95 at that step: 13569.6 ms
* Error rate at that step: 0.0000
* Criterion that tripped: p95 13569.6 ms > limit 10000.0 ms

## Saturation signals (threshold-free)

* p95 rises monotonically across the last 3 steps: **True** (p95 rose by a factor of 4.84 across them)
* Achieved rate stopped tracking the offered rate: **False** — the achieved rate kept tracking the offered rate
* Achieved/offered ratio: first step 1.000, last step 0.992

A rising p95 across consecutive steps, or an achieved rate that no longer follows the offered rate, is evidence of an unbounded queue. In an open-loop test the generator does not slow down when the server does, so the divergence is the system's own saturation showing through.

## Per-step table

| step | start_s | end_s | duration_s | offered_per_min | samples | achieved_per_min | tracking_ratio | errors | error_rate | error_rate_pct | p50_ms | p95_ms | p99_ms | max_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.00 | 120.00 | 120.00 | 10.00 | 20 | 10.00 | 1.00 | 0 | 0.00 | 0.00 | 1554.00 | 2957.25 | 3386.65 | 3494.00 |
| 2 | 120.00 | 240.00 | 120.00 | 20.00 | 41 | 20.50 | 1.02 | 0 | 0.00 | 0.00 | 1804.00 | 3563.00 | 3742.00 | 3858.00 |
| 3 | 240.00 | 360.00 | 120.00 | 30.00 | 60 | 30.00 | 1.00 | 0 | 0.00 | 0.00 | 1837.00 | 5671.65 | 6556.98 | 6957.00 |
| 4 | 360.00 | 480.00 | 120.00 | 40.00 | 79 | 39.50 | 0.99 | 0 | 0.00 | 0.00 | 4116.00 | 13569.60 | 13793.36 | 13940.00 |
| 5 | 480.00 | 600.00 | 120.00 | 50.00 | 101 | 50.50 | 1.01 | 0 | 0.00 | 0.00 | 19286.00 | 28216.00 | 28806.00 | 29479.00 |
| 6 | 600.00 | 720.00 | 120.00 | 60.00 | 119 | 59.50 | 0.99 | 0 | 0.00 | 0.00 | 46784.00 | 65662.50 | 66095.92 | 67090.00 |

`achieved_per_min` uses each step's nominal duration. `error_rate` is the fraction compared against --error-rate-limit; `error_rate_pct` is the same number as a percentage, for the slide.

See `stress_ramp.png` for p95 and the achieved rate against the offered rate.

## Warnings raised by this run

* Note: step boundaries are measured from the arrival schedule's start, 2026-10-09T00:33:02.070000+00:00 (jmeter-log); the first sample arrived 1.9 s later.

## Interpretation

The limit stated in one sentence, and the component it is attributed to, are on Slide 9, supported by `analysis/bottleneck_hints.py` run on this same run directory. Where no step crossed a criterion, Slide 9 reports the top offered rate as a lower bound on the limit, and `docs/playbooks/stress-test.md` section 2.1 names the steeper ramp that is then run. This file reports; it does not interpret.
