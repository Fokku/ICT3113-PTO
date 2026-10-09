| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 226.7 | 24.7 | 192.4 | 391.1 | 463.5 | 162.0 | 481.6 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 7.7 | 0.8 | 7.6 | 8.2 | 8.4 | 7.4 | 8.4 |
| load_ms | Ollama loading the model (load_duration) | 1.1 | 0.1 | 1.1 | 1.4 | 1.6 | 1.0 | 1.7 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 446.5 | 48.5 | 434.5 | 1075.7 | 1320.0 | 72.8 | 1381.1 |
| eval_ms | generating the reply tokens (eval_duration) | 226.8 | 24.7 | 253.4 | 295.0 | 295.9 | 145.0 | 296.1 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 10.9 | 1.2 | 13.5 | 18.8 | 19.5 | 1.5 | 19.7 |
| total_latency_ms | the whole request handler, as measured by the service | 919.7 | 100.0 | 802.0 | 1630.9 | 1820.5 | 445.5 | 1867.9 |
