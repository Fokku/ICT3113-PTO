# Request time breakdown — llama3.2:1b-instruct-q4_K_M

* Run directory: `results/runs/20261009T001705Z_llama3.2-1b-instruct-q4_K_M_stress_ramp_ramp_run1`
* Run mode: `real`
* Measured POST /tickets requests: 420
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 420
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **prompt_eval_ms** (389.4 ms, 48.5 per cent of the mean total latency).

What that means: prefill dominates: the cost is in reading the ticket, so it scales with ticket length and prompt size rather than with the length of the reply.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 192.4 | 24.0 | 167.3 | 358.9 | 502.3 | 131.7 | 1207.4 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 11.0 | 1.4 | 8.0 | 22.7 | 31.5 | 6.4 | 61.6 |
| load_ms | Ollama loading the model (load_duration) | 1.4 | 0.2 | 1.1 | 2.5 | 4.5 | 0.9 | 6.1 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 389.4 | 48.5 | 344.0 | 751.2 | 877.2 | 106.3 | 946.5 |
| eval_ms | generating the reply tokens (eval_duration) | 61.0 | 7.6 | 59.6 | 63.7 | 90.2 | 56.9 | 119.6 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 148.3 | 18.5 | 5.9 | 782.2 | 1225.0 | 1.4 | 1597.7 |
| total_latency_ms | the whole request handler, as measured by the service | 803.5 | 100.0 | 727.8 | 1511.2 | 1817.1 | 337.7 | 2128.6 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 420 | 130771 | 163.54 | 799.62 | 887.07 | 846.07 | 1288.90 | 311.36 |
| generation | 420 | 1276 | 25.60 | 49.84 | 49.98 | 50.32 | 51.65 | 3.04 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
