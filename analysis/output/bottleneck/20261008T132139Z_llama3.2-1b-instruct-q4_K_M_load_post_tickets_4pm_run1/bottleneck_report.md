# Request time breakdown — llama3.2:1b-instruct-q4_K_M

* Run directory: `results/runs/20261008T132139Z_llama3.2-1b-instruct-q4_K_M_load_post_tickets_4pm_run1`
* Run mode: `real`
* Measured POST /tickets requests: 40
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 40
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **prompt_eval_ms** (378.3 ms, 56.8 per cent of the mean total latency).

What that means: prefill dominates: the cost is in reading the ticket, so it scales with ticket length and prompt size rather than with the length of the reply.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 200.0 | 30.0 | 193.6 | 318.6 | 335.6 | 149.8 | 345.9 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.5 | 1.3 | 7.7 | 14.9 | 17.4 | 7.1 | 18.8 |
| load_ms | Ollama loading the model (load_duration) | 1.1 | 0.2 | 1.1 | 1.6 | 1.8 | 0.9 | 1.8 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 378.3 | 56.8 | 322.5 | 743.9 | 883.6 | 135.1 | 917.1 |
| eval_ms | generating the reply tokens (eval_duration) | 62.6 | 9.4 | 60.0 | 66.5 | 110.3 | 58.7 | 122.8 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 15.5 | 2.3 | 3.9 | 7.8 | 287.1 | 1.5 | 465.2 |
| total_latency_ms | the whole request handler, as measured by the service | 666.0 | 100.0 | 638.2 | 1020.5 | 1449.7 | 380.1 | 1670.4 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 40 | 11984 | 15.13 | 791.94 | 892.75 | 851.07 | 1245.93 | 299.60 |
| generation | 40 | 123 | 2.50 | 49.14 | 49.44 | 49.98 | 50.99 | 3.08 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
