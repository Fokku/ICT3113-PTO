| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 196.0 | 14.2 | 188.6 | 239.6 | 299.0 | 151.9 | 332.9 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.5 | 0.6 | 7.6 | 13.2 | 16.4 | 7.1 | 18.1 |
| load_ms | Ollama loading the model (load_duration) | 1.2 | 0.1 | 1.1 | 1.6 | 1.7 | 1.0 | 1.8 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 897.1 | 65.1 | 668.5 | 2031.8 | 2515.6 | 75.4 | 2640.3 |
| eval_ms | generating the reply tokens (eval_duration) | 228.7 | 16.6 | 224.4 | 302.7 | 314.2 | 146.8 | 321.3 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 47.4 | 3.4 | 10.2 | 55.5 | 784.4 | 1.5 | 835.1 |
| total_latency_ms | the whole request handler, as measured by the service | 1378.9 | 100.0 | 1066.8 | 2443.0 | 3502.9 | 426.8 | 4024.5 |
