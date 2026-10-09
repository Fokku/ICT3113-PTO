# Request time breakdown — llama3.2:3b

* Run directory: `results/runs/20261008T155827Z_llama3.2-3b_load_post_tickets_12pm_run2`
* Run mode: `real`
* Measured POST /tickets requests: 120
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 120
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **prompt_eval_ms** (684.8 ms, 55.6 per cent of the mean total latency).

What that means: prefill dominates: the cost is in reading the ticket, so it scales with ticket length and prompt size rather than with the length of the reply.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 198.6 | 16.1 | 189.3 | 260.8 | 329.5 | 148.5 | 449.0 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 10.3 | 0.8 | 7.8 | 20.7 | 38.7 | 6.9 | 55.7 |
| load_ms | Ollama loading the model (load_duration) | 1.3 | 0.1 | 1.1 | 1.9 | 5.7 | 0.9 | 7.7 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 684.8 | 55.6 | 609.6 | 1803.5 | 2048.3 | 74.8 | 2270.4 |
| eval_ms | generating the reply tokens (eval_duration) | 224.3 | 18.2 | 224.5 | 303.5 | 304.8 | 147.6 | 308.8 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 112.7 | 9.1 | 14.9 | 545.8 | 1388.0 | 1.5 | 1438.9 |
| total_latency_ms | the whole request handler, as measured by the service | 1232.0 | 100.0 | 1122.7 | 2317.6 | 3013.8 | 431.0 | 3733.2 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 120 | 36872 | 82.18 | 448.69 | 1680.23 | 364.94 | 5967.18 | 307.27 |
| generation | 120 | 478 | 26.91 | 17.76 | 18.21 | 17.82 | 20.12 | 3.98 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
