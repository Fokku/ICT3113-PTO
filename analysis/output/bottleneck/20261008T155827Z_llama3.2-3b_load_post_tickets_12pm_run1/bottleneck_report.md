# Request time breakdown — llama3.2:3b

* Run directory: `results/runs/20261008T155827Z_llama3.2-3b_load_post_tickets_12pm_run1`
* Run mode: `real`
* Measured POST /tickets requests: 120
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 120
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **prompt_eval_ms** (911.9 ms, 56.2 per cent of the mean total latency).

What that means: prefill dominates: the cost is in reading the ticket, so it scales with ticket length and prompt size rather than with the length of the reply.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 201.4 | 12.4 | 188.9 | 265.1 | 480.2 | 153.5 | 902.9 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 10.9 | 0.7 | 7.8 | 24.6 | 30.8 | 7.1 | 66.7 |
| load_ms | Ollama loading the model (load_duration) | 1.4 | 0.1 | 1.1 | 4.1 | 4.6 | 0.9 | 5.6 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 911.9 | 56.2 | 836.8 | 1960.0 | 2275.9 | 75.2 | 2826.5 |
| eval_ms | generating the reply tokens (eval_duration) | 224.1 | 13.8 | 225.7 | 302.4 | 312.6 | 147.1 | 338.0 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 272.6 | 16.8 | 16.1 | 1693.4 | 2522.7 | 1.4 | 2660.4 |
| total_latency_ms | the whole request handler, as measured by the service | 1622.2 | 100.0 | 1502.6 | 3417.6 | 3649.7 | 423.8 | 4375.4 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 120 | 36872 | 109.42 | 336.97 | 935.26 | 313.68 | 4822.00 | 307.27 |
| generation | 120 | 477 | 26.89 | 17.74 | 18.20 | 17.72 | 20.26 | 3.98 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
