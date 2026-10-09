| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 206.3 | 1.1 | 178.7 | 371.8 | 631.5 | 132.2 | 1239.0 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 15.6 | 0.1 | 12.5 | 30.6 | 49.7 | 6.8 | 101.8 |
| load_ms | Ollama loading the model (load_duration) | 1.9 | 0.0 | 1.5 | 4.5 | 5.7 | 0.9 | 7.2 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1105.7 | 5.9 | 986.7 | 2160.1 | 2477.6 | 281.7 | 2640.4 |
| eval_ms | generating the reply tokens (eval_duration) | 225.5 | 1.2 | 220.8 | 298.3 | 301.9 | 142.3 | 312.0 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 17308.6 | 91.8 | 9122.8 | 58570.5 | 64430.5 | 1.5 | 65616.4 |
| total_latency_ms | the whole request handler, as measured by the service | 18863.7 | 100.0 | 10899.0 | 60638.6 | 65735.5 | 725.8 | 67080.4 |
