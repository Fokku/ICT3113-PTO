| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 204.2 | 29.7 | 196.7 | 314.7 | 377.4 | 154.7 | 457.7 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 9.1 | 1.3 | 7.7 | 15.0 | 24.7 | 7.0 | 49.1 |
| load_ms | Ollama loading the model (load_duration) | 1.2 | 0.2 | 1.0 | 1.7 | 4.2 | 0.9 | 7.7 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 374.8 | 54.5 | 343.3 | 698.0 | 850.1 | 104.5 | 976.0 |
| eval_ms | generating the reply tokens (eval_duration) | 61.1 | 8.9 | 59.4 | 63.3 | 109.9 | 57.7 | 117.6 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 37.2 | 5.4 | 4.9 | 175.6 | 604.0 | 1.4 | 1007.4 |
| total_latency_ms | the whole request handler, as measured by the service | 687.7 | 100.0 | 625.0 | 1149.4 | 1345.8 | 343.7 | 1667.0 |
