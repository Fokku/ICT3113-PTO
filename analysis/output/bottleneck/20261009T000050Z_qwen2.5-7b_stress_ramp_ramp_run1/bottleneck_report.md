# Request time breakdown — qwen2.5:7b

* Run directory: `results/runs/20261009T000050Z_qwen2.5-7b_stress_ramp_ramp_run1`
* Run mode: `real`
* Measured POST /tickets requests: 132
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 132
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **ollama_other_ms** (6018.7 ms, 66.3 per cent of the mean total latency).

What that means: most of Ollama's own total_duration is in none of its three reported components. Check the Ollama version's accounting before drawing a conclusion from it.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 151.6 | 1.7 | 136.9 | 276.5 | 361.0 | 100.5 | 522.5 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 13.9 | 0.2 | 12.8 | 28.2 | 32.0 | 7.7 | 32.1 |
| load_ms | Ollama loading the model (load_duration) | 1.7 | 0.0 | 1.5 | 4.3 | 5.1 | 0.9 | 5.4 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 2468.5 | 27.2 | 2274.0 | 4661.7 | 5585.6 | 638.1 | 6131.5 |
| eval_ms | generating the reply tokens (eval_duration) | 423.1 | 4.7 | 312.2 | 617.2 | 627.0 | 301.8 | 633.9 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 6018.7 | 66.3 | 2528.7 | 20804.7 | 23765.3 | 2.2 | 25163.0 |
| total_latency_ms | the whole request handler, as measured by the service | 9077.5 | 100.0 | 5226.8 | 24706.3 | 26387.3 | 1254.9 | 29684.5 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 132 | 41570 | 325.84 | 127.58 | 142.51 | 131.49 | 219.73 | 314.92 |
| generation | 132 | 496 | 55.85 | 8.88 | 9.10 | 9.61 | 9.89 | 3.76 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
