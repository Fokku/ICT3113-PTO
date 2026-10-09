| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 160.9 | 7.5 | 139.6 | 292.3 | 465.8 | 105.4 | 599.8 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 10.9 | 0.5 | 8.7 | 18.6 | 21.8 | 7.5 | 28.0 |
| load_ms | Ollama loading the model (load_duration) | 1.7 | 0.1 | 1.8 | 2.3 | 3.4 | 1.1 | 5.0 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1207.5 | 56.3 | 1103.9 | 2294.3 | 2775.9 | 331.9 | 3088.0 |
| eval_ms | generating the reply tokens (eval_duration) | 199.6 | 9.3 | 156.7 | 310.1 | 312.6 | 150.9 | 314.2 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 562.3 | 26.2 | 12.5 | 3089.3 | 3756.5 | 2.2 | 5076.3 |
| total_latency_ms | the whole request handler, as measured by the service | 2142.9 | 100.0 | 1772.8 | 4858.2 | 6049.1 | 691.0 | 6668.0 |
