| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 213.5 | 18.3 | 191.2 | 299.8 | 652.3 | 146.9 | 847.8 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 9.6 | 0.8 | 7.7 | 14.2 | 38.8 | 7.0 | 54.3 |
| load_ms | Ollama loading the model (load_duration) | 1.2 | 0.1 | 1.1 | 1.5 | 3.5 | 0.9 | 4.2 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 666.4 | 57.3 | 531.9 | 1878.9 | 2190.9 | 75.0 | 2297.9 |
| eval_ms | generating the reply tokens (eval_duration) | 228.6 | 19.6 | 225.9 | 300.5 | 306.7 | 146.7 | 310.4 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 44.5 | 3.8 | 7.1 | 25.0 | 878.5 | 1.5 | 1388.7 |
| total_latency_ms | the whole request handler, as measured by the service | 1163.8 | 100.0 | 1014.1 | 2462.1 | 2618.5 | 416.7 | 2653.8 |
