# Request time breakdown — qwen2.5:7b

* Run directory: `results/runs/20261008T195733Z_qwen2.5-7b_load_post_tickets_12pm_run2`
* Run mode: `real`
* Measured POST /tickets requests: 120
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 120
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **prompt_eval_ms** (1541.6 ms, 52.6 per cent of the mean total latency).

What that means: prefill dominates: the cost is in reading the ticket, so it scales with ticket length and prompt size rather than with the length of the reply.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 189.5 | 6.5 | 173.1 | 348.5 | 422.4 | 141.3 | 455.2 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 13.6 | 0.5 | 8.6 | 32.7 | 50.1 | 7.4 | 61.6 |
| load_ms | Ollama loading the model (load_duration) | 1.7 | 0.1 | 1.1 | 4.9 | 5.3 | 0.9 | 6.2 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1541.6 | 52.6 | 1348.0 | 3954.1 | 4681.3 | 152.1 | 5119.5 |
| eval_ms | generating the reply tokens (eval_duration) | 422.2 | 14.4 | 313.5 | 613.5 | 622.2 | 301.1 | 629.8 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 760.6 | 26.0 | 9.2 | 3796.0 | 5315.6 | 2.1 | 5898.2 |
| total_latency_ms | the whole request handler, as measured by the service | 2929.3 | 100.0 | 2474.2 | 6577.1 | 8520.3 | 624.7 | 9252.6 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 120 | 37891 | 184.99 | 204.83 | 844.17 | 165.44 | 2989.86 | 315.76 |
| generation | 120 | 451 | 50.67 | 8.90 | 9.13 | 9.57 | 9.91 | 3.76 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
