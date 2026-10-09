# Request time breakdown — llama3.2:3b

* Run directory: `results/runs/20261008T151917Z_llama3.2-3b_load_post_tickets_4pm_run2`
* Run mode: `real`
* Measured POST /tickets requests: 40
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 40
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **prompt_eval_ms** (666.4 ms, 57.3 per cent of the mean total latency).

What that means: prefill dominates: the cost is in reading the ticket, so it scales with ticket length and prompt size rather than with the length of the reply.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 213.5 | 18.3 | 191.2 | 299.8 | 652.3 | 146.9 | 847.8 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 9.6 | 0.8 | 7.7 | 14.2 | 38.8 | 7.0 | 54.3 |
| load_ms | Ollama loading the model (load_duration) | 1.2 | 0.1 | 1.1 | 1.5 | 3.5 | 0.9 | 4.2 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 666.4 | 57.3 | 531.9 | 1878.9 | 2190.9 | 75.0 | 2297.9 |
| eval_ms | generating the reply tokens (eval_duration) | 228.6 | 19.6 | 225.9 | 300.5 | 306.7 | 146.7 | 310.4 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 44.5 | 3.8 | 7.1 | 25.0 | 878.5 | 1.5 | 1388.7 |
| total_latency_ms | the whole request handler, as measured by the service | 1163.8 | 100.0 | 1014.1 | 2462.1 | 2618.5 | 416.7 | 2653.8 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 40 | 11984 | 26.65 | 449.61 | 1601.49 | 382.87 | 5810.85 | 299.60 |
| generation | 40 | 162 | 9.14 | 17.72 | 18.13 | 17.71 | 20.19 | 4.05 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
