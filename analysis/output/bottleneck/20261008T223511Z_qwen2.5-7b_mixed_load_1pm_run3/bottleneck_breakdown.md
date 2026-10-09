| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 227.0 | 13.1 | 192.5 | 336.1 | 342.1 | 173.3 | 343.6 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.3 | 0.5 | 8.4 | 8.7 | 8.8 | 7.7 | 8.9 |
| load_ms | Ollama loading the model (load_duration) | 1.1 | 0.1 | 1.1 | 1.2 | 1.2 | 0.9 | 1.3 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1004.6 | 57.9 | 953.6 | 2418.7 | 2948.9 | 153.0 | 3081.5 |
| eval_ms | generating the reply tokens (eval_duration) | 485.6 | 28.0 | 529.7 | 609.7 | 610.7 | 302.5 | 610.9 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 7.9 | 0.5 | 9.5 | 12.6 | 13.2 | 2.6 | 13.3 |
| total_latency_ms | the whole request handler, as measured by the service | 1734.4 | 100.0 | 1676.9 | 3221.6 | 3764.6 | 653.5 | 3900.4 |
