# Request time breakdown — granite4:3b

* Run directory: `results/runs/20261008T215538Z_granite4-3b_mixed_load_1pm_run2`
* Run mode: `real`
* Measured POST /tickets requests: 10
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 10
* Requests in the breakdown: 10
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **prompt_eval_ms** (504.4 ms, 50.6 per cent of the mean total latency).

What that means: prefill dominates: the cost is in reading the ticket, so it scales with ticket length and prompt size rather than with the length of the reply.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 226.1 | 22.7 | 191.2 | 385.6 | 493.6 | 169.7 | 520.6 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.3 | 0.8 | 8.3 | 8.9 | 9.1 | 7.7 | 9.1 |
| load_ms | Ollama loading the model (load_duration) | 1.5 | 0.1 | 1.3 | 2.0 | 2.0 | 1.2 | 2.0 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 504.4 | 50.6 | 479.8 | 1217.0 | 1483.6 | 78.0 | 1550.3 |
| eval_ms | generating the reply tokens (eval_duration) | 247.4 | 24.8 | 267.7 | 311.7 | 313.8 | 153.3 | 314.3 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 10.1 | 1.0 | 12.1 | 16.7 | 17.2 | 2.7 | 17.4 |
| total_latency_ms | the whole request handler, as measured by the service | 997.8 | 100.0 | 907.1 | 1729.9 | 1992.8 | 539.6 | 2058.5 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 10 | 2883 | 5.04 | 571.55 | 2007.96 | 408.11 | 5177.51 | 288.30 |
| generation | 10 | 42 | 2.47 | 16.98 | 17.32 | 16.88 | 19.42 | 4.20 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
