# Request time breakdown — llama3.2:3b

* Run directory: `results/runs/20261009T003216Z_llama3.2-3b_stress_ramp_ramp_run1`
* Run mode: `real`
* Measured POST /tickets requests: 420
* Requests excluded because Ollama returned no timings: 0
* Non-/tickets log lines skipped (no model call to break down): 0
* Requests in the breakdown: 420
* num_ctx logged on these requests: [4096]

## Verdict

The largest component of the mean request is **ollama_other_ms** (17308.6 ms, 91.8 per cent of the mean total latency).

What that means: most of Ollama's own total_duration is in none of its three reported components. Check the Ollama version's accounting before drawing a conclusion from it.

## Breakdown

| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 206.3 | 1.1 | 178.7 | 371.8 | 631.5 | 132.2 | 1239.0 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 15.6 | 0.1 | 12.5 | 30.6 | 49.7 | 6.8 | 101.8 |
| load_ms | Ollama loading the model (load_duration) | 1.9 | 0.0 | 1.5 | 4.5 | 5.7 | 0.9 | 7.2 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1105.7 | 5.9 | 986.7 | 2160.1 | 2477.6 | 281.7 | 2640.4 |
| eval_ms | generating the reply tokens (eval_duration) | 225.5 | 1.2 | 220.8 | 298.3 | 301.9 | 142.3 | 312.0 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 17308.6 | 91.8 | 9122.8 | 58570.5 | 64430.5 | 1.5 | 65616.4 |
| total_latency_ms | the whole request handler, as measured by the service | 18863.7 | 100.0 | 10899.0 | 60638.6 | 65735.5 | 725.8 | 67080.4 |

The component means sum to the mean total latency. The percentile columns describe each component's own spread and do not sum to the percentile of the total.

`queue_residual_ms` is a **residual**, obtained by subtracting Ollama's own `total_duration` from the wall clock around our HTTP call. Ollama-side queueing appears there, and so do HTTP and container networking, JSON encoding, and the TCP connection we deliberately create per request. `ollama_other_ms` is the part of Ollama's own total that its three reported components do not explain.

See `bottleneck_stacked.png` for the mean breakdown and `bottleneck_per_request.csv` for the per-request values behind it.

## Token throughput

| stage | requests | total_tokens | total_seconds | aggregate_tokens_per_s | mean_tokens_per_s | p50_tokens_per_s | p95_tokens_per_s | mean_tokens_per_request |
|---|---|---|---|---|---|---|---|---|
| prompt evaluation | 420 | 130771 | 464.41 | 281.59 | 314.92 | 293.62 | 475.16 | 311.36 |
| generation | 420 | 1711 | 94.72 | 18.06 | 18.50 | 18.11 | 20.69 | 4.07 |


## num_ctx truncation check

Requests whose `prompt_eval_count` sits at or above the warning fraction of their logged `num_ctx`: **0**.

Ollama truncates a prompt longer than `num_ctx` silently, so a prompt-token count pinned at the limit means the model classified a ticket it had not fully read. Suspects are listed in `ctx_truncation_suspects.csv`.

## Interpretation

The one-line bottleneck diagnosis is on Slide 9, and its comparison with the bottleneck named in `predictions/prediction_record.md` is on Slide 11. Both rest on this breakdown and on how its components move with the offered rate across runs. This file reports; it does not interpret.
