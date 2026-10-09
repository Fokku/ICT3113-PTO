# Request time breakdown — granite4:3b

* Run directory: `results/runs/20261009T004737Z_granite4-3b_stress_ramp_ramp_run1`
* Run mode: `real`
* Measured POST /tickets requests: 420
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 420
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **ollama_other_ms** (23188.4 ms, 93.2 per cent of the mean total latency).

What that means: most of Ollama's own total_duration is in none of its three reported components. Check the Ollama version's accounting before drawing a conclusion from it.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 219.5 | 0.9 | 192.2 | 377.3 | 770.6 | 145.8 | 1326.6 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 15.0 | 0.1 | 13.1 | 25.3 | 40.9 | 7.6 | 111.3 |
| load_ms | Ollama loading the model (load_duration) | 3.0 | 0.0 | 2.0 | 4.7 | 7.6 | 1.2 | 279.2 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1258.7 | 5.1 | 1118.4 | 2471.6 | 2869.4 | 321.5 | 3070.0 |
| eval_ms | generating the reply tokens (eval_duration) | 202.8 | 0.8 | 157.0 | 312.7 | 315.8 | 151.1 | 327.4 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 23188.4 | 93.2 | 11398.6 | 76127.0 | 86297.6 | 2.2 | 90064.7 |
| total_latency_ms | the whole request handler, as measured by the service | 24887.4 | 100.0 | 13414.6 | 77909.5 | 88279.0 | 775.4 | 90919.1 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 420 | 132887 | 528.66 | 251.36 | 282.89 | 263.62 | 429.99 | 316.40 |
| generation | 420 | 1518 | 85.19 | 17.82 | 18.25 | 19.11 | 19.66 | 3.61 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
