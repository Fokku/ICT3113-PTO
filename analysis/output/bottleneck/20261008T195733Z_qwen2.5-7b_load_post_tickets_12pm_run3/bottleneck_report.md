# Request time breakdown — qwen2.5:7b

* Run directory: `results/runs/20261008T195733Z_qwen2.5-7b_load_post_tickets_12pm_run3`
* Run mode: `real`
* Measured POST /tickets requests: 120
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 120
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **prompt_eval_ms** (1119.8 ms, 52.6 per cent of the mean total latency).

What that means: prefill dominates: the cost is in reading the ticket, so it scales with ticket length and prompt size rather than with the length of the reply.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 197.2 | 9.3 | 171.5 | 381.8 | 528.1 | 133.0 | 672.9 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 11.8 | 0.6 | 8.7 | 27.9 | 30.6 | 7.7 | 55.0 |
| load_ms | Ollama loading the model (load_duration) | 1.5 | 0.1 | 1.1 | 4.2 | 5.1 | 1.0 | 5.2 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1119.8 | 52.6 | 805.0 | 3869.3 | 4718.6 | 151.1 | 5106.7 |
| eval_ms | generating the reply tokens (eval_duration) | 419.2 | 19.7 | 310.2 | 615.3 | 622.8 | 301.6 | 628.5 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 379.6 | 17.8 | 8.7 | 2213.0 | 3878.7 | 1.9 | 4191.0 |
| total_latency_ms | the whole request handler, as measured by the service | 2129.0 | 100.0 | 1889.8 | 4998.1 | 6936.9 | 633.3 | 9780.3 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 120 | 37891 | 134.37 | 281.99 | 1166.37 | 223.20 | 2975.85 | 315.76 |
| generation | 120 | 449 | 50.30 | 8.93 | 9.15 | 9.67 | 9.91 | 3.74 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
