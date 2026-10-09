| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 226.1 | 22.7 | 191.2 | 385.6 | 493.6 | 169.7 | 520.6 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.3 | 0.8 | 8.3 | 8.9 | 9.1 | 7.7 | 9.1 |
| load_ms | Ollama loading the model (load_duration) | 1.5 | 0.1 | 1.3 | 2.0 | 2.0 | 1.2 | 2.0 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 504.4 | 50.6 | 479.8 | 1217.0 | 1483.6 | 78.0 | 1550.3 |
| eval_ms | generating the reply tokens (eval_duration) | 247.4 | 24.8 | 267.7 | 311.7 | 313.8 | 153.3 | 314.3 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 10.1 | 1.0 | 12.1 | 16.7 | 17.2 | 2.7 | 17.4 |
| total_latency_ms | the whole request handler, as measured by the service | 997.8 | 100.0 | 907.1 | 1729.9 | 1992.8 | 539.6 | 2058.5 |
