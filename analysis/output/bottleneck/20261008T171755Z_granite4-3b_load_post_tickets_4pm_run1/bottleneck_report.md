# Request time breakdown — granite4:3b

* Run directory: `results/runs/20261008T171755Z_granite4-3b_load_post_tickets_4pm_run1`
* Run mode: `real`
* Measured POST /tickets requests: 40
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 40
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **prompt_eval_ms** (1018.7 ms, 68.0 per cent of the mean total latency).

What that means: prefill dominates: the cost is in reading the ticket, so it scales with ticket length and prompt size rather than with the length of the reply.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 211.2 | 14.1 | 201.8 | 255.7 | 360.9 | 167.5 | 406.1 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 9.3 | 0.6 | 8.3 | 15.1 | 17.8 | 7.6 | 19.2 |
| load_ms | Ollama loading the model (load_duration) | 1.5 | 0.1 | 1.4 | 2.0 | 2.2 | 1.2 | 2.2 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1018.7 | 68.0 | 766.5 | 2332.4 | 2842.5 | 81.1 | 2997.1 |
| eval_ms | generating the reply tokens (eval_duration) | 202.9 | 13.5 | 160.0 | 316.9 | 328.4 | 155.0 | 333.8 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 54.5 | 3.6 | 8.7 | 46.5 | 1020.9 | 2.2 | 1293.3 |
| total_latency_ms | the whole request handler, as measured by the service | 1498.1 | 100.0 | 1208.4 | 2709.1 | 3348.6 | 483.9 | 3590.1 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 40 | 12186 | 40.75 | 299.06 | 808.37 | 311.33 | 4296.55 | 304.65 |
| generation | 40 | 142 | 8.12 | 17.49 | 17.91 | 18.76 | 19.19 | 3.55 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
