# Request time breakdown — llama3.2:1b-instruct-q4_K_M

* Run directory: `results/runs/20261008T140042Z_llama3.2-1b-instruct-q4_K_M_load_post_tickets_12pm_run3`
* Run mode: `real`
* Measured POST /tickets requests: 120
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 120
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **prompt_eval_ms** (189.1 ms, 41.8 per cent of the mean total latency).

What that means: prefill dominates: the cost is in reading the ticket, so it scales with ticket length and prompt size rather than with the length of the reply.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 166.4 | 36.7 | 160.9 | 222.4 | 369.9 | 97.3 | 403.5 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 9.3 | 2.1 | 8.0 | 16.1 | 23.6 | 7.1 | 25.7 |
| load_ms | Ollama loading the model (load_duration) | 1.2 | 0.3 | 1.1 | 1.8 | 2.2 | 0.9 | 4.5 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 189.1 | 41.8 | 143.7 | 570.4 | 747.2 | 30.2 | 846.4 |
| eval_ms | generating the reply tokens (eval_duration) | 68.8 | 15.2 | 67.4 | 75.6 | 133.8 | 58.2 | 140.5 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 18.0 | 4.0 | 4.6 | 8.4 | 430.0 | 1.5 | 651.7 |
| total_latency_ms | the whole request handler, as measured by the service | 452.7 | 100.0 | 393.1 | 939.5 | 1056.0 | 239.0 | 1149.0 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 120 | 36872 | 22.69 | 1624.77 | 5164.10 | 1207.15 | 13050.20 | 307.27 |
| generation | 120 | 367 | 8.25 | 44.47 | 44.86 | 44.48 | 49.66 | 3.06 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
