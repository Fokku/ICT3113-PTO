| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 194.3 | 12.5 | 190.5 | 236.1 | 242.3 | 162.5 | 243.9 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 9.3 | 0.6 | 8.4 | 12.9 | 13.5 | 7.7 | 13.6 |
| load_ms | Ollama loading the model (load_duration) | 1.4 | 0.1 | 1.4 | 1.5 | 1.6 | 1.2 | 1.6 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1099.0 | 70.7 | 986.8 | 1913.5 | 2092.4 | 420.2 | 2137.1 |
| eval_ms | generating the reply tokens (eval_duration) | 240.6 | 15.5 | 235.5 | 336.9 | 346.1 | 157.2 | 348.4 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 10.1 | 0.6 | 10.8 | 19.8 | 22.3 | 2.5 | 22.9 |
| total_latency_ms | the whole request handler, as measured by the service | 1554.6 | 100.0 | 1452.1 | 2385.5 | 2493.2 | 906.9 | 2520.1 |
