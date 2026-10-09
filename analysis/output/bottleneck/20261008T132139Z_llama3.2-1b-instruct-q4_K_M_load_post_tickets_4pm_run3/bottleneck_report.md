# Request time breakdown — llama3.2:1b-instruct-q4_K_M

* Run directory: `results/runs/20261008T132139Z_llama3.2-1b-instruct-q4_K_M_load_post_tickets_4pm_run3`
* Run mode: `real`
* Measured POST /tickets requests: 40
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 40
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **prompt_eval_ms** (205.2 ms, 42.0 per cent of the mean total latency).

What that means: prefill dominates: the cost is in reading the ticket, so it scales with ticket length and prompt size rather than with the length of the reply.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 198.0 | 40.6 | 182.7 | 261.0 | 385.1 | 154.8 | 394.0 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 9.4 | 1.9 | 7.7 | 19.2 | 27.6 | 7.1 | 27.8 |
| load_ms | Ollama loading the model (load_duration) | 1.2 | 0.2 | 1.0 | 1.8 | 3.9 | 0.9 | 3.9 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 205.2 | 42.0 | 150.1 | 663.4 | 772.1 | 29.8 | 810.2 |
| eval_ms | generating the reply tokens (eval_duration) | 62.7 | 12.9 | 60.0 | 88.8 | 105.9 | 57.7 | 116.4 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 11.4 | 2.3 | 2.9 | 54.8 | 160.4 | 1.5 | 224.9 |
| total_latency_ms | the whole request handler, as measured by the service | 487.9 | 100.0 | 444.1 | 1017.3 | 1072.0 | 271.3 | 1087.4 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 40 | 11984 | 8.21 | 1460.38 | 4867.19 | 1214.33 | 15045.13 | 299.60 |
| generation | 40 | 124 | 2.51 | 49.43 | 49.71 | 50.03 | 51.49 | 3.10 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
