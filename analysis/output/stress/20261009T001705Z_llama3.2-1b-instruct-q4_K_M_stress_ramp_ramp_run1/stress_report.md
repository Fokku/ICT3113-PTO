# Stress test — llama3.2:1b-instruct-q4_K_M

* Run directory: `results/runs/20261009T001705Z_llama3.2-1b-instruct-q4_K_M_stress_ramp_ramp_run1`
* Plan: `stress_ramp`; run mode: `real`
* Samples analysed: 420 (excluded by the step boundaries: 0)
* p95 requirement supplied: 10000.0 ms
* Error-rate limit: 0.0500

## The limit

No step crossed either criterion within this ramp.

## Saturation signals (threshold-free)

* p95 rises monotonically across the last 3 steps: **False** (p95 rose by a factor of 1.25 across them)
* Achieved rate stopped tracking the offered rate: **False** — the achieved rate kept tracking the offered rate
* Achieved/offered ratio: first step 1.000, last step 1.000

A rising p95 across consecutive steps, or an achieved rate that no longer follows the offered rate, is evidence of an unbounded queue. In an open-loop test the generator does not slow down when the server does, so the divergence is the system's own saturation showing through.

## Per-step table

| step | start_s | end_s | duration_s | offered_per_min | samples | achieved_per_min | tracking_ratio | errors | error_rate | error_rate_pct | p50_ms | p95_ms | p99_ms | max_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.00 | 120.00 | 120.00 | 10.00 | 20 | 10.00 | 1.00 | 0 | 0.00 | 0.00 | 587.00 | 1152.10 | 1199.22 | 1211.00 |
| 2 | 120.00 | 240.00 | 120.00 | 20.00 | 40 | 20.00 | 1.00 | 0 | 0.00 | 0.00 | 634.50 | 1071.80 | 1607.23 | 1624.00 |
| 3 | 240.00 | 360.00 | 120.00 | 30.00 | 60 | 30.00 | 1.00 | 0 | 0.00 | 0.00 | 739.50 | 1273.20 | 1479.65 | 1636.00 |
| 4 | 360.00 | 480.00 | 120.00 | 40.00 | 80 | 40.00 | 1.00 | 0 | 0.00 | 0.00 | 827.50 | 1454.85 | 1531.66 | 1568.00 |
| 5 | 480.00 | 600.00 | 120.00 | 50.00 | 100 | 50.00 | 1.00 | 0 | 0.00 | 0.00 | 723.50 | 1406.20 | 1777.43 | 2117.00 |
| 6 | 600.00 | 720.00 | 120.00 | 60.00 | 120 | 60.00 | 1.00 | 0 | 0.00 | 0.00 | 829.00 | 1818.95 | 2009.78 | 2143.00 |

`achieved_per_min` uses each step's nominal duration. `error_rate` is the fraction compared against --error-rate-limit; `error_rate_pct` is the same number as a percentage, for the slide.

See `stress_ramp.png` for p95 and the achieved rate against the offered rate.

## Warnings raised by this run

* Note: step boundaries are measured from the arrival schedule's start, 2026-10-09T00:17:42.457000+00:00 (jmeter-log); the first sample arrived 12.2 s later.

## Check that failed

No limit was found within the ramp and no saturation signal was present: the stress test did not stress the system and must be re-run at higher rates.

## Interpretation

The limit stated in one sentence, and the component it is attributed to, are on Slide 9, supported by `analysis/bottleneck_hints.py` run on this same run directory. Where no step crossed a criterion, Slide 9 reports the top offered rate as a lower bound on the limit, and `docs/playbooks/stress-test.md` section 2.1 names the steeper ramp that is then run. This file reports; it does not interpret.
