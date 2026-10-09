| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 198.6 | 20.2 | 188.3 | 266.5 | 436.9 | 145.1 | 505.2 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.8 | 0.9 | 7.5 | 13.6 | 23.5 | 7.0 | 29.2 |
| load_ms | Ollama loading the model (load_duration) | 1.2 | 0.1 | 1.1 | 1.7 | 3.5 | 0.9 | 4.6 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 497.8 | 50.6 | 372.2 | 1866.1 | 2176.2 | 74.0 | 2296.9 |
| eval_ms | generating the reply tokens (eval_duration) | 229.2 | 23.3 | 226.0 | 303.4 | 306.9 | 148.1 | 308.0 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 47.4 | 4.8 | 6.4 | 32.0 | 915.3 | 1.4 | 1352.3 |
| total_latency_ms | the whole request handler, as measured by the service | 983.0 | 100.0 | 857.0 | 2281.6 | 2540.7 | 417.4 | 2626.5 |
