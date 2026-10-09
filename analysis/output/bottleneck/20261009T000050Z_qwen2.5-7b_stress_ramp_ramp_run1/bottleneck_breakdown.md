| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 151.6 | 1.7 | 136.9 | 276.5 | 361.0 | 100.5 | 522.5 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 13.9 | 0.2 | 12.8 | 28.2 | 32.0 | 7.7 | 32.1 |
| load_ms | Ollama loading the model (load_duration) | 1.7 | 0.0 | 1.5 | 4.3 | 5.1 | 0.9 | 5.4 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 2468.5 | 27.2 | 2274.0 | 4661.7 | 5585.6 | 638.1 | 6131.5 |
| eval_ms | generating the reply tokens (eval_duration) | 423.1 | 4.7 | 312.2 | 617.2 | 627.0 | 301.8 | 633.9 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 6018.7 | 66.3 | 2528.7 | 20804.7 | 23765.3 | 2.2 | 25163.0 |
| total_latency_ms | the whole request handler, as measured by the service | 9077.5 | 100.0 | 5226.8 | 24706.3 | 26387.3 | 1254.9 | 29684.5 |
