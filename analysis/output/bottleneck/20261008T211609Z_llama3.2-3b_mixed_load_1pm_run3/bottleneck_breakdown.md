| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 232.1 | 29.3 | 203.3 | 375.3 | 384.7 | 171.0 | 387.0 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 7.6 | 1.0 | 7.6 | 8.0 | 8.0 | 7.1 | 8.0 |
| load_ms | Ollama loading the model (load_duration) | 1.1 | 0.1 | 1.1 | 1.1 | 1.1 | 1.0 | 1.1 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 316.0 | 39.8 | 220.1 | 706.7 | 711.5 | 72.6 | 712.7 |
| eval_ms | generating the reply tokens (eval_duration) | 225.9 | 28.5 | 252.6 | 297.1 | 298.9 | 144.3 | 299.4 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 10.7 | 1.3 | 11.7 | 18.6 | 19.3 | 1.6 | 19.5 |
| total_latency_ms | the whole request handler, as measured by the service | 793.4 | 100.0 | 775.7 | 1136.9 | 1200.0 | 429.1 | 1215.8 |
