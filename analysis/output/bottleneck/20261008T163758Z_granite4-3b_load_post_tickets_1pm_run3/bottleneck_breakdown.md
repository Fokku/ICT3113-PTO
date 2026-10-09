| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 210.0 | 24.7 | 194.7 | 300.2 | 331.9 | 170.3 | 339.8 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.4 | 1.0 | 8.5 | 9.0 | 9.1 | 7.6 | 9.2 |
| load_ms | Ollama loading the model (load_duration) | 1.4 | 0.2 | 1.3 | 1.7 | 1.9 | 1.3 | 1.9 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 367.9 | 43.2 | 257.1 | 817.7 | 828.1 | 79.8 | 830.7 |
| eval_ms | generating the reply tokens (eval_duration) | 254.9 | 29.9 | 282.6 | 318.9 | 319.1 | 156.1 | 319.1 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 8.7 | 1.0 | 10.8 | 14.7 | 15.1 | 2.2 | 15.2 |
| total_latency_ms | the whole request handler, as measured by the service | 851.3 | 100.0 | 784.0 | 1259.1 | 1316.8 | 459.3 | 1331.2 |
