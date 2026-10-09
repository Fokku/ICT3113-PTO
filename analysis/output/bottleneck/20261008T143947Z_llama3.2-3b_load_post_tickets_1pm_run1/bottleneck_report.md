# Request time breakdown — llama3.2:3b

* Run directory: `results/runs/20261008T143947Z_llama3.2-3b_load_post_tickets_1pm_run1`
* Run mode: `real`
* Measured POST /tickets requests: 10
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 10
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **prompt_eval_ms** (957.1 ms, 70.1 per cent of the mean total latency).

What that means: prefill dominates: the cost is in reading the ticket, so it scales with ticket length and prompt size rather than with the length of the reply.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 158.3 | 11.6 | 160.4 | 188.1 | 200.5 | 123.9 | 203.6 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.0 | 0.6 | 7.6 | 9.7 | 10.1 | 7.3 | 10.2 |
| load_ms | Ollama loading the model (load_duration) | 1.2 | 0.1 | 1.0 | 1.7 | 1.7 | 0.9 | 1.7 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 957.1 | 70.1 | 863.0 | 1667.0 | 1841.6 | 379.7 | 1885.2 |
| eval_ms | generating the reply tokens (eval_duration) | 232.1 | 17.0 | 263.5 | 298.2 | 298.3 | 146.9 | 298.4 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 9.3 | 0.7 | 9.8 | 17.8 | 20.0 | 1.6 | 20.6 |
| total_latency_ms | the whole request handler, as measured by the service | 1365.9 | 100.0 | 1282.0 | 2149.8 | 2324.6 | 724.9 | 2368.3 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 10 | 2833 | 9.57 | 296.00 | 324.53 | 311.52 | 433.72 | 283.30 |
| generation | 10 | 41 | 2.32 | 17.67 | 18.10 | 17.10 | 20.37 | 4.10 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
