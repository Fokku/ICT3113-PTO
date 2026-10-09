# Request time breakdown — llama3.2:1b-instruct-q4_K_M

* Run directory: `results/runs/20261008T124213Z_llama3.2-1b-instruct-q4_K_M_load_post_tickets_1pm_run3`
* Run mode: `real`
* Measured POST /tickets requests: 10
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 10
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **service_overhead_ms** (189.6 ms, 46.8 per cent of the mean total latency).

What that means: the time is in our own service, not in the model. Look at the per-request SQLite connection, the full-table LIKE scan if /search is in the mix, and the open-write-close log call on every request.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 189.6 | 46.8 | 191.5 | 204.4 | 204.7 | 160.8 | 204.8 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 9.2 | 2.3 | 7.5 | 15.7 | 18.4 | 7.3 | 19.1 |
| load_ms | Ollama loading the model (load_duration) | 1.2 | 0.3 | 1.0 | 1.5 | 1.6 | 1.0 | 1.6 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 122.9 | 30.3 | 83.3 | 271.9 | 276.3 | 30.6 | 277.4 |
| eval_ms | generating the reply tokens (eval_duration) | 60.6 | 15.0 | 60.0 | 63.5 | 63.9 | 58.9 | 64.0 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 21.6 | 5.3 | 4.5 | 101.7 | 164.6 | 1.4 | 180.4 |
| total_latency_ms | the whole request handler, as measured by the service | 405.1 | 100.0 | 362.2 | 600.1 | 630.1 | 287.2 | 637.6 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 10 | 2833 | 1.23 | 2305.87 | 6062.04 | 5046.53 | 12987.65 | 283.30 |
| generation | 10 | 30 | 0.61 | 49.47 | 49.50 | 50.00 | 50.87 | 3.00 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
