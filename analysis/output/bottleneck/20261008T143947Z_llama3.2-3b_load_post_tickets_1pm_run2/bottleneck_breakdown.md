| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 174.2 | 11.8 | 172.7 | 235.6 | 270.2 | 113.4 | 278.9 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.3 | 0.6 | 8.2 | 9.2 | 9.3 | 7.3 | 9.3 |
| load_ms | Ollama loading the model (load_duration) | 1.1 | 0.1 | 1.0 | 1.2 | 1.2 | 0.9 | 1.2 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1016.3 | 68.9 | 922.0 | 1749.9 | 1931.1 | 398.3 | 1976.4 |
| eval_ms | generating the reply tokens (eval_duration) | 265.7 | 18.0 | 298.6 | 343.8 | 344.0 | 169.5 | 344.0 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 10.3 | 0.7 | 10.6 | 18.6 | 20.4 | 1.8 | 20.8 |
| total_latency_ms | the whole request handler, as measured by the service | 1475.9 | 100.0 | 1355.9 | 2291.5 | 2466.5 | 879.2 | 2510.2 |
