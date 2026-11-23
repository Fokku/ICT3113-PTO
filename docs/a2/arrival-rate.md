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
| 1 | 10685 (749 chars) | 3.851 |
| 2 | 10910 (749 chars) | 3.339 |
| 3 | 10627 (744 chars) | 3.029 |

**S (the middle value) = 3.339 seconds.**

**How it was measured.** On 2026-11-19 at 07:49 UTC, by `python scripts/measure_s_a2.py --restart docker` on
the service host (`omarchy`). The machine-readable record, which `../../scripts/run_load_test_a2.sh` reads,
is [`arrival_rate.json`](arrival_rate.json).

1. **Restart and warm-up.** The Ollama container was restarted (nothing loaded, prompt cache empty).
   The three fixed warm-up tickets every speed run uses (dev rows 900000–900002, from
   `../../data/dev/synthetic_tickets.csv`) were sent one at a time, with `X-Warmup: 1`.
2. **The three S tickets.** They were then sent one at a time through `POST /tickets` to the rebuilt
   Assignment 2 service, running `SERVICE_MODE=single`, `MODEL_TAG=qwen2.5:7b`.
   - Digest `sha256:845dbda0…`, prompt hash `sha256:681131c48bdc15a1`: both unchanged from Assignment 1.
   - They are the three team rows outside the golden set and outside the workload list whose length is
     closest to the 749-character median, ties going to the lower row number.
   - None of them is a warm-up ticket.
3. **Timings.** Each timing is the client-observed elapsed time, the same quantity JMeter records. The
   service's own `total_latency_ms` for the same three requests (`../../logs/service/2026-11-19.jsonl`,
   request ids `s-measure-*`) agrees to within 2 ms: 3850.2, 3337.4 and 3027.8 ms.

**Observation for the team.** About 0.55 s of each of these timings is the triage service itself, not
Ollama.
- `total_latency_ms − model_latency_ms` is 575, 666 and 681 ms, against about 190 ms in the Assignment 1
  `qwen2.5:7b` runs.
- A direct test inside the container puts it in SQLite's insert-and-commit. One commit takes about 0.5 s
  on this host's btrfs disk, on the database volume and the container filesystem alike, so the cost is the
  fsync, not the size of the table.

It is the same code path in every configuration, so it does not bias the comparison. It does mean the
brief's "a few milliseconds per ticket" does not hold on this machine. Part 4 may want this for Slide 7,
and Part 5 for Slide 8. Changing it is out of scope (the service code is not on the brief's "may change"
list; `../../TODO_A2.md` guardrail 14).

## 2. Derived rate and run length

| | |
|---|---|
| Rate = 60 / (2×S) per minute | **8.98 per minute**, one ticket every 6.678 s (2 × 3.339 s) |
| Run length = S minutes, minimum 5 | **300 s (5 minutes)**: S = 3.339 s is below the 5-minute minimum |
| Approx. tickets per run = rate × run length | **≈ 44.9** (8.98 × 5). That is about 135 over three runs, so the pooled p95 rests on roughly 135 requests, not the brief's "about 90". |
| Safe upper bound = expected + 3 × √expected | **≈ 65.0** (44.9 + 3 × 6.7) |
| Upper bound ≤ 100 (tickets in `../../workload/speed_test_rows_a2.txt`)? | **Yes**: 65 ≤ 100, so the list does not need regenerating. `run_load_test_a2.sh` sends each listed ticket at most once per run (JMeter CSV recycle off) and flags a run that uses all 100. |

This rate and run length are used for **every** speed-tested configuration, including the single models and
both cascade settings — not just `qwen2.5:7b` (brief: "Use the same rate and run length for every
configuration").

## 3. Derived timeout settings

| | |
|---|---|
| HTTP sampler response timeout = max(10×S, 5 min) | **300 000 ms (5 min)**: 10 × S = 33.4 s, below the 5-minute floor |
| Open Model Thread Group trailing pause ≥ timeout + 1 min | **360 s (6 min)**: `rate(8.98/min) random_arrivals(300 sec) pause(360 sec)` |

## 4. Comparison against the client's peak rate

| | |
|---|---|
| Client's peak rate, from `../../workload/workload_model.md` | 0.024 tickets/minute (about 1.4 per hour): the 0.012/min average × an assumed peak factor of 2 |
| Our Assignment 2 test rate (§2) | 8.98 tickets/minute |
| Is the test rate above or below the client's peak? | **Above**, by a factor of about 370 |
| Consequence (brief: "say which case you are in, on the limitations slide") | We are in the brief's first case: a configuration that sustains this rate without a queue also shows it can handle the client's modelled peak. Two caveats: it is one 5-minute rate on one machine, and the peak itself rests on an assumed ×2 factor (`workload_model.md`). Part 4 writes the Slide 8 paragraph (`../../TODO_A2.md` §4.1). |

This document feeds: every A2 run's `metadata.json`, `../../predictions/prediction_record_a2.md`, Slide 3
(test environment and method), and Slide 8 (limitations, via §4).
