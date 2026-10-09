# Stress test — llama3.2:1b-instruct-q4_K_M

* Run directory: `results/runs/20261008T231508Z_llama3.2-1b-instruct-q4_K_M_stress_ramp_ramp_run1`
* Plan: `stress_ramp`; run mode: `real`
* Samples analysed: 132 (excluded by the step boundaries: 0)
* p95 requirement supplied: 10000.0 ms
* Error-rate limit: 0.0500

## The limit

No step crossed either criterion within this ramp.

## Saturation signals (threshold-free)

* p95 rises monotonically across the last 3 steps: **False** (p95 rose by a factor of 1.17 across them)
* Achieved rate stopped tracking the offered rate: **False** — the achieved rate kept tracking the offered rate
* Achieved/offered ratio: first step 1.000, last step 0.976

A rising p95 across consecutive steps, or an achieved rate that no longer follows the offered rate, is evidence of an unbounded queue. In an open-loop test the generator does not slow down when the server does, so the divergence is the system's own saturation showing through.

## Per-step table

| step | start_s | end_s | duration_s | offered_per_min | samples | achieved_per_min | tracking_ratio | errors | error_rate | error_rate_pct | p50_ms | p95_ms | p99_ms | max_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.00 | 120.00 | 120.00 | 1.00 | 2 | 1.00 | 1.00 | 0 | 0.00 | 0.00 | 681.00 | 735.00 | 739.80 | 741.00 |
| 2 | 120.00 | 240.00 | 120.00 | 5.00 | 10 | 5.00 | 1.00 | 0 | 0.00 | 0.00 | 665.50 | 946.40 | 978.08 | 986.00 |
| 3 | 240.00 | 360.00 | 120.00 | 9.00 | 18 | 9.00 | 1.00 | 0 | 0.00 | 0.00 | 550.00 | 1267.60 | 1365.52 | 1390.00 |
| 4 | 360.00 | 480.00 | 120.00 | 13.00 | 26 | 13.00 | 1.00 | 0 | 0.00 | 0.00 | 722.00 | 1061.50 | 1180.50 | 1216.00 |
| 5 | 480.00 | 600.00 | 120.00 | 17.00 | 35 | 17.50 | 1.03 | 0 | 0.00 | 0.00 | 621.00 | 999.60 | 1082.98 | 1118.00 |
| 6 | 600.00 | 720.00 | 120.00 | 21.00 | 41 | 20.50 | 0.98 | 0 | 0.00 | 0.00 | 744.00 | 1246.00 | 1541.40 | 1679.00 |

`achieved_per_min` uses each step's nominal duration. `error_rate` is the fraction compared against --error-rate-limit; `error_rate_pct` is the same number as a percentage, for the slide.

See `stress_ramp.png` for p95 and the achieved rate against the offered rate.

## Warnings raised by this run

* Note: step boundaries are measured from the arrival schedule's start, 2026-10-08T23:15:41.726000+00:00 (jmeter-log); the first sample arrived 7.8 s later.

## Check that failed

No limit was found within the ramp and no saturation signal was present: the stress test did not stress the system and must be re-run at higher rates.

## Interpretation

The limit stated in one sentence, and the component it is attributed to, are on Slide 9, supported by `analysis/bottleneck_hints.py` run on this same run directory. Where no step crossed a criterion, Slide 9 reports the top offered rate as a lower bound on the limit, and `docs/playbooks/stress-test.md` section 2.1 names the steeper ramp that is then run. This file reports; it does not interpret.
