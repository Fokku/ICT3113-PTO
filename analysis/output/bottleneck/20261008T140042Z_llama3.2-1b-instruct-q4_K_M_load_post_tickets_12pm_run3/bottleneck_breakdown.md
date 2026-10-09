| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 166.4 | 36.7 | 160.9 | 222.4 | 369.9 | 97.3 | 403.5 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 9.3 | 2.1 | 8.0 | 16.1 | 23.6 | 7.1 | 25.7 |
| load_ms | Ollama loading the model (load_duration) | 1.2 | 0.3 | 1.1 | 1.8 | 2.2 | 0.9 | 4.5 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 189.1 | 41.8 | 143.7 | 570.4 | 747.2 | 30.2 | 846.4 |
| eval_ms | generating the reply tokens (eval_duration) | 68.8 | 15.2 | 67.4 | 75.6 | 133.8 | 58.2 | 140.5 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 18.0 | 4.0 | 4.6 | 8.4 | 430.0 | 1.5 | 651.7 |
| total_latency_ms | the whole request handler, as measured by the service | 452.7 | 100.0 | 393.1 | 939.5 | 1056.0 | 239.0 | 1149.0 |
