| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 213.4 | 39.1 | 199.2 | 292.3 | 440.4 | 162.5 | 444.2 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.2 | 1.5 | 7.6 | 8.4 | 20.6 | 7.2 | 28.2 |
| load_ms | Ollama loading the model (load_duration) | 1.1 | 0.2 | 1.1 | 1.6 | 1.7 | 0.9 | 1.7 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 257.0 | 47.1 | 205.0 | 670.7 | 777.3 | 30.5 | 811.5 |
| eval_ms | generating the reply tokens (eval_duration) | 62.4 | 11.4 | 60.2 | 64.3 | 106.1 | 58.3 | 116.2 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 3.5 | 0.6 | 3.2 | 6.6 | 7.6 | 1.5 | 8.2 |
| total_latency_ms | the whole request handler, as measured by the service | 545.6 | 100.0 | 499.5 | 921.5 | 1053.7 | 280.6 | 1083.7 |
