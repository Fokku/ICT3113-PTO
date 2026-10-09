# Request time breakdown — granite4:3b

* Run directory: `results/runs/20261008T175715Z_granite4-3b_load_post_tickets_12pm_run1`
* Run mode: `real`
* Measured POST /tickets requests: 120
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 120
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **prompt_eval_ms** (1154.7 ms, 58.3 per cent of the mean total latency).

What that means: prefill dominates: the cost is in reading the ticket, so it scales with ticket length and prompt size rather than with the length of the reply.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 252.0 | 12.7 | 200.9 | 470.8 | 615.8 | 159.0 | 753.9 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 12.9 | 0.7 | 10.0 | 26.2 | 49.4 | 8.1 | 69.9 |
| load_ms | Ollama loading the model (load_duration) | 2.0 | 0.1 | 1.5 | 4.5 | 6.0 | 1.2 | 6.1 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1154.7 | 58.3 | 1036.5 | 2569.4 | 2830.9 | 92.7 | 3364.3 |
| eval_ms | generating the reply tokens (eval_duration) | 253.4 | 12.8 | 199.3 | 388.9 | 404.6 | 185.8 | 442.7 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 306.0 | 15.4 | 13.0 | 1635.8 | 3900.0 | 2.4 | 4380.8 |
| total_latency_ms | the whole request handler, as measured by the service | 1981.0 | 100.0 | 1774.5 | 3733.2 | 6027.6 | 496.6 | 6130.7 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 120 | 37478 | 138.57 | 270.47 | 749.27 | 255.32 | 3881.97 | 312.32 |
| generation | 120 | 433 | 30.41 | 14.24 | 14.60 | 15.05 | 15.91 | 3.61 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
