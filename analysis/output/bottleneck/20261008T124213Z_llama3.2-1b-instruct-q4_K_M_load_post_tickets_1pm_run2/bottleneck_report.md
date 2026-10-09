# Request time breakdown — llama3.2:1b-instruct-q4_K_M

* Run directory: `results/runs/20261008T124213Z_llama3.2-1b-instruct-q4_K_M_load_post_tickets_1pm_run2`
* Run mode: `real`
* Measured POST /tickets requests: 10
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 10
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **service_overhead_ms** (199.6 ms, 44.9 per cent of the mean total latency).

What that means: the time is in our own service, not in the model. Look at the per-request SQLite connection, the full-table LIKE scan if /search is in the mix, and the open-write-close log call on every request.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 199.6 | 44.9 | 189.2 | 271.5 | 273.6 | 155.1 | 274.1 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.8 | 2.0 | 7.5 | 13.1 | 13.3 | 7.2 | 13.4 |
| load_ms | Ollama loading the model (load_duration) | 1.1 | 0.3 | 1.1 | 1.5 | 1.7 | 1.0 | 1.7 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 169.7 | 38.2 | 163.0 | 398.5 | 477.3 | 31.3 | 497.0 |
| eval_ms | generating the reply tokens (eval_duration) | 60.9 | 13.7 | 60.6 | 62.3 | 62.3 | 59.7 | 62.4 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 4.0 | 0.9 | 4.5 | 6.3 | 6.6 | 1.6 | 6.7 |
| total_latency_ms | the whole request handler, as measured by the service | 444.2 | 100.0 | 455.0 | 637.1 | 709.3 | 280.8 | 727.4 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 10 | 2833 | 1.70 | 1669.76 | 5029.28 | 1157.44 | 12720.54 | 283.30 |
| generation | 10 | 30 | 0.61 | 49.25 | 49.26 | 49.53 | 50.24 | 3.00 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
