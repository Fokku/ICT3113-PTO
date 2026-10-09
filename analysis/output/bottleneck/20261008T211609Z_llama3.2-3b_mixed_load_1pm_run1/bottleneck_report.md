# Request time breakdown — llama3.2:3b

* Run directory: `results/runs/20261008T211609Z_llama3.2-3b_mixed_load_1pm_run1`
* Run mode: `real`
* Measured POST /tickets requests: 10
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 10
* Requests in the breakdown: 10
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **prompt_eval_ms** (927.8 ms, 67.1 per cent of the mean total latency).

What that means: prefill dominates: the cost is in reading the ticket, so it scales with ticket length and prompt size rather than with the length of the reply.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 209.6 | 15.2 | 195.5 | 284.7 | 320.1 | 164.2 | 328.9 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 7.9 | 0.6 | 7.4 | 10.3 | 12.0 | 7.2 | 12.4 |
| load_ms | Ollama loading the model (load_duration) | 1.1 | 0.1 | 1.0 | 1.2 | 1.2 | 1.0 | 1.2 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 927.8 | 67.1 | 829.5 | 1608.5 | 1770.3 | 362.0 | 1810.7 |
| eval_ms | generating the reply tokens (eval_duration) | 226.7 | 16.4 | 253.3 | 293.7 | 294.1 | 145.5 | 294.2 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 9.1 | 0.7 | 9.7 | 17.5 | 20.0 | 1.6 | 20.6 |
| total_latency_ms | the whole request handler, as measured by the service | 1382.1 | 100.0 | 1295.0 | 2120.6 | 2303.2 | 746.1 | 2348.8 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 10 | 2833 | 9.28 | 305.36 | 334.62 | 321.80 | 449.55 | 283.30 |
| generation | 10 | 41 | 2.27 | 18.09 | 18.56 | 17.84 | 20.61 | 4.10 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
