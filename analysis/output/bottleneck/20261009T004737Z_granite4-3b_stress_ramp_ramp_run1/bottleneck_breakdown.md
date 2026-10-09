| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 219.5 | 0.9 | 192.2 | 377.3 | 770.6 | 145.8 | 1326.6 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 15.0 | 0.1 | 13.1 | 25.3 | 40.9 | 7.6 | 111.3 |
| load_ms | Ollama loading the model (load_duration) | 3.0 | 0.0 | 2.0 | 4.7 | 7.6 | 1.2 | 279.2 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1258.7 | 5.1 | 1118.4 | 2471.6 | 2869.4 | 321.5 | 3070.0 |
| eval_ms | generating the reply tokens (eval_duration) | 202.8 | 0.8 | 157.0 | 312.7 | 315.8 | 151.1 | 327.4 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 23188.4 | 93.2 | 11398.6 | 76127.0 | 86297.6 | 2.2 | 90064.7 |
| total_latency_ms | the whole request handler, as measured by the service | 24887.4 | 100.0 | 13414.6 | 77909.5 | 88279.0 | 775.4 | 90919.1 |
