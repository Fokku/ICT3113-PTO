# Stress test — granite4:3b

* Run directory: `results/runs/20261009T004737Z_granite4-3b_stress_ramp_ramp_run1`
* Plan: `stress_ramp`; run mode: `real`
* Samples analysed: 420 (excluded by the step boundaries: 0)
* p95 requirement supplied: 10000.0 ms
* Error-rate limit: 0.0500

## The limit

First step to cross a criterion: step 4 (offered 40/min, achieved 41.0/min): p95 14565.2 ms > limit 10000.0 ms.

* Step: 4
* Offered rate: 40/min
* Achieved rate: 41.0/min
* p95 at that step: 14565.2 ms
* Error rate at that step: 0.0000
* Criterion that tripped: p95 14565.2 ms > limit 10000.0 ms

## Saturation signals (threshold-free)

* p95 rises monotonically across the last 3 steps: **True** (p95 rose by a factor of 5.92 across them)
* Achieved rate stopped tracking the offered rate: **False** — the achieved rate kept tracking the offered rate
* Achieved/offered ratio: first step 1.000, last step 1.000

A rising p95 across consecutive steps, or an achieved rate that no longer follows the offered rate, is evidence of an unbounded queue. In an open-loop test the generator does not slow down when the server does, so the divergence is the system's own saturation showing through.

## Per-step table

| step | start_s | end_s | duration_s | offered_per_min | samples | achieved_per_min | tracking_ratio | errors | error_rate | error_rate_pct | p50_ms | p95_ms | p99_ms | max_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.00 | 120.00 | 120.00 | 10.00 | 20 | 10.00 | 1.00 | 0 | 0.00 | 0.00 | 1503.50 | 3115.90 | 3372.78 | 3437.00 |
| 2 | 120.00 | 240.00 | 120.00 | 20.00 | 40 | 20.00 | 1.00 | 0 | 0.00 | 0.00 | 2034.50 | 4079.05 | 4276.42 | 4402.00 |
| 3 | 240.00 | 360.00 | 120.00 | 30.00 | 60 | 30.00 | 1.00 | 0 | 0.00 | 0.00 | 3123.00 | 9282.50 | 10171.40 | 11021.00 |
| 4 | 360.00 | 480.00 | 120.00 | 40.00 | 82 | 41.00 | 1.02 | 0 | 0.00 | 0.00 | 10109.50 | 14565.20 | 15358.70 | 15788.00 |
| 5 | 480.00 | 600.00 | 120.00 | 50.00 | 98 | 49.00 | 0.98 | 0 | 0.00 | 0.00 | 22896.00 | 31086.30 | 31835.61 | 32405.00 |
| 6 | 600.00 | 720.00 | 120.00 | 60.00 | 120 | 60.00 | 1.00 | 0 | 0.00 | 0.00 | 61124.00 | 86215.55 | 90640.19 | 90928.00 |

`achieved_per_min` uses each step's nominal duration. `error_rate` is the fraction compared against --error-rate-limit; `error_rate_pct` is the same number as a percentage, for the slide.

See `stress_ramp.png` for p95 and the achieved rate against the offered rate.

## Warnings raised by this run

* Note: step boundaries are measured from the arrival schedule's start, 2026-10-09T00:48:26.908000+00:00 (jmeter-log); the first sample arrived 2.5 s later.

## Interpretation

The limit stated in one sentence, and the component it is attributed to, are on Slide 9, supported by `analysis/bottleneck_hints.py` run on this same run directory. Where no step crossed a criterion, Slide 9 reports the top offered rate as a lower bound on the limit, and `docs/playbooks/stress-test.md` section 2.1 names the steeper ramp that is then run. This file reports; it does not interpret.
