# Arrival rate for the Assignment 2 speed tests — Group 10

**What this is.** The brief's Set-up procedure (Step 4), executed: the arrival rate every Assignment 2 speed
test uses, derived from the **top model's** (`qwen2.5:7b`) speed, not from the Assignment 1 workload model.

**Owner:** Part 1 — Yeo Kai Yuan.

---

## 1. Measuring S

Procedure (brief): restart Ollama, do the normal warm-up, then send **three different** tickets of typical
length to `qwen2.5:7b`, one at a time (never the same ticket three times — Ollama caches prompts it has
seen). Take the middle of the three timings.

Pick the three tickets from team rows outside `../../golden/golden_set.csv`, of typical length (near the
749-character median of the non-golden rows), and **not** in `../../workload/speed_test_rows_a2.txt` or
the warm-up list (`../playbooks/cascade-test.md` §4.2) — overlap would let the prompt cache leak into
either the S measurement or the speed runs.

| Run | Source row number | Elapsed time (s) |
|---|---|---|
| 1 | TODO(a2) | TODO(a2) |
| 2 | TODO(a2) | TODO(a2) |
| 3 | TODO(a2) | TODO(a2) |

**S (the middle value) = TODO(a2) seconds.**

## 2. Derived rate and run length

| | |
|---|---|
| Rate = 60 / (2×S) per minute | TODO(a2) |
| Run length = S minutes, minimum 5 | TODO(a2) |
| Approx. tickets per run | TODO(a2) (should land near 30) |

This rate and run length are used for **every** speed-tested configuration, including the single models and
both cascade settings — not just `qwen2.5:7b` (brief: "Use the same rate and run length for every
configuration").

## 3. Derived timeout settings

| | |
|---|---|
| HTTP sampler response timeout = max(10×S, 5 min) | TODO(a2) |
| Open Model Thread Group trailing pause ≥ timeout + 1 min | TODO(a2) |

## 4. Comparison against the client's peak rate

| | |
|---|---|
| Client's peak rate, from `../../workload/workload_model.md` | TODO(a2) |
| Our Assignment 2 test rate (§2) | TODO(a2) |
| Is the test rate above or below the client's peak? | TODO(a2) |
| Consequence (brief: "say which case you are in, on the limitations slide") | TODO(a2): if below, state plainly that the result compares configurations but does not show the recommended one can handle the client's peak |

This document feeds: every A2 run's `metadata.json`, `../../predictions/prediction_record_a2.md`, Slide 3
(test environment and method), and Slide 8 (limitations, via §4).
