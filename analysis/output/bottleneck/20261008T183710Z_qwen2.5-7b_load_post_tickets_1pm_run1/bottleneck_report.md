# Request time breakdown — qwen2.5:7b

* Run directory: `results/runs/20261008T183710Z_qwen2.5-7b_load_post_tickets_1pm_run1`
* Run mode: `real`
* Measured POST /tickets requests: 10
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 10
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **prompt_eval_ms** (2483.1 ms, 69.8 per cent of the mean total latency).

What that means: prefill dominates: the cost is in reading the ticket, so it scales with ticket length and prompt size rather than with the length of the reply.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 440.1 | 12.4 | 196.2 | 1547.6 | 2291.4 | 165.6 | 2477.4 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 11.2 | 0.3 | 9.3 | 21.0 | 28.2 | 8.1 | 30.0 |
| load_ms | Ollama loading the model (load_duration) | 1.5 | 0.0 | 1.2 | 3.0 | 3.9 | 1.0 | 4.1 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 2483.1 | 69.8 | 2279.8 | 4152.3 | 4528.1 | 952.0 | 4622.0 |
| eval_ms | generating the reply tokens (eval_duration) | 610.0 | 17.1 | 665.5 | 779.6 | 783.6 | 369.8 | 784.6 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 13.7 | 0.4 | 9.7 | 39.6 | 56.7 | 2.7 | 60.9 |
| total_latency_ms | the whole request handler, as measured by the service | 3559.7 | 100.0 | 3410.2 | 5484.3 | 5567.0 | 1748.4 | 5587.7 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 10 | 2907 | 24.83 | 117.07 | 127.69 | 118.90 | 170.97 | 290.70 |
| generation | 10 | 42 | 6.10 | 6.89 | 7.07 | 6.79 | 8.08 | 4.20 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
