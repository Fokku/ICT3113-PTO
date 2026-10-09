| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 187.3 | 44.5 | 179.7 | 250.8 | 291.3 | 159.0 | 301.4 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 9.1 | 2.2 | 7.5 | 15.5 | 17.3 | 7.1 | 17.7 |
| load_ms | Ollama loading the model (load_duration) | 1.1 | 0.3 | 1.0 | 1.6 | 1.6 | 0.8 | 1.6 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 161.2 | 38.3 | 153.2 | 380.1 | 464.0 | 30.3 | 485.0 |
| eval_ms | generating the reply tokens (eval_duration) | 58.6 | 13.9 | 58.5 | 59.4 | 59.7 | 57.5 | 59.8 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 3.8 | 0.9 | 4.3 | 6.1 | 6.3 | 1.5 | 6.4 |
| total_latency_ms | the whole request handler, as measured by the service | 421.1 | 100.0 | 399.1 | 698.1 | 826.7 | 263.1 | 858.9 |
