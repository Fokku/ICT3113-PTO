# Request time breakdown — llama3.2:1b-instruct-q4_K_M

* Run directory: `results/runs/20261008T231508Z_llama3.2-1b-instruct-q4_K_M_stress_ramp_ramp_run1`
* Run mode: `real`
* Measured POST /tickets requests: 132
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 132
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **prompt_eval_ms** (374.8 ms, 54.5 per cent of the mean total latency).

What that means: prefill dominates: the cost is in reading the ticket, so it scales with ticket length and prompt size rather than with the length of the reply.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 204.2 | 29.7 | 196.7 | 314.7 | 377.4 | 154.7 | 457.7 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 9.1 | 1.3 | 7.7 | 15.0 | 24.7 | 7.0 | 49.1 |
| load_ms | Ollama loading the model (load_duration) | 1.2 | 0.2 | 1.0 | 1.7 | 4.2 | 0.9 | 7.7 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 374.8 | 54.5 | 343.3 | 698.0 | 850.1 | 104.5 | 976.0 |
| eval_ms | generating the reply tokens (eval_duration) | 61.1 | 8.9 | 59.4 | 63.3 | 109.9 | 57.7 | 117.6 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 37.2 | 5.4 | 4.9 | 175.6 | 604.0 | 1.4 | 1007.4 |
| total_latency_ms | the whole request handler, as measured by the service | 687.7 | 100.0 | 625.0 | 1149.4 | 1345.8 | 343.7 | 1667.0 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 132 | 40475 | 49.47 | 818.09 | 903.21 | 844.77 | 1306.42 | 306.63 |
| generation | 132 | 403 | 8.07 | 49.94 | 50.13 | 50.52 | 51.42 | 3.05 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
