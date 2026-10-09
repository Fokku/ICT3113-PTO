# Request time breakdown — granite4:3b

* Run directory: `results/runs/20261008T171755Z_granite4-3b_load_post_tickets_4pm_run3`
* Run mode: `real`
* Measured POST /tickets requests: 40
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 40
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **prompt_eval_ms** (626.8 ms, 54.5 per cent of the mean total latency).

What that means: prefill dominates: the cost is in reading the ticket, so it scales with ticket length and prompt size rather than with the length of the reply.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 250.0 | 21.7 | 204.1 | 442.7 | 642.5 | 164.3 | 706.1 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 10.0 | 0.9 | 9.2 | 15.3 | 17.3 | 8.1 | 17.6 |
| load_ms | Ollama loading the model (load_duration) | 1.6 | 0.1 | 1.5 | 2.3 | 3.4 | 1.2 | 3.7 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 626.8 | 54.5 | 468.7 | 2291.1 | 2688.6 | 83.8 | 2798.3 |
| eval_ms | generating the reply tokens (eval_duration) | 245.2 | 21.3 | 195.7 | 395.1 | 434.5 | 167.7 | 453.2 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 16.1 | 1.4 | 8.7 | 22.1 | 190.8 | 2.5 | 298.0 |
| total_latency_ms | the whole request handler, as measured by the service | 1149.5 | 100.0 | 963.4 | 2704.3 | 3066.2 | 490.4 | 3179.4 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 40 | 12186 | 25.07 | 486.07 | 1795.54 | 385.17 | 4831.46 | 304.65 |
| generation | 40 | 142 | 9.81 | 14.48 | 14.89 | 15.33 | 16.93 | 3.55 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
