# Request time breakdown — granite4:3b

* Run directory: `results/runs/20261008T234535Z_granite4-3b_stress_ramp_ramp_run1`
* Run mode: `real`
* Measured POST /tickets requests: 132
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 132
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **prompt_eval_ms** (1207.5 ms, 56.3 per cent of the mean total latency).

What that means: prefill dominates: the cost is in reading the ticket, so it scales with ticket length and prompt size rather than with the length of the reply.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 160.9 | 7.5 | 139.6 | 292.3 | 465.8 | 105.4 | 599.8 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 10.9 | 0.5 | 8.7 | 18.6 | 21.8 | 7.5 | 28.0 |
| load_ms | Ollama loading the model (load_duration) | 1.7 | 0.1 | 1.8 | 2.3 | 3.4 | 1.1 | 5.0 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1207.5 | 56.3 | 1103.9 | 2294.3 | 2775.9 | 331.9 | 3088.0 |
| eval_ms | generating the reply tokens (eval_duration) | 199.6 | 9.3 | 156.7 | 310.1 | 312.6 | 150.9 | 314.2 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 562.3 | 26.2 | 12.5 | 3089.3 | 3756.5 | 2.2 | 5076.3 |
| total_latency_ms | the whole request handler, as measured by the service | 2142.9 | 100.0 | 1772.8 | 4858.2 | 6049.1 | 691.0 | 6668.0 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 132 | 41141 | 159.39 | 258.12 | 288.57 | 267.49 | 429.93 | 311.67 |
| generation | 132 | 473 | 26.35 | 17.95 | 18.37 | 19.14 | 19.70 | 3.58 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
