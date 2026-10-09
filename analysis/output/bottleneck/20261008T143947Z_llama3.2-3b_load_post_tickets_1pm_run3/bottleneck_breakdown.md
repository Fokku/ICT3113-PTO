| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 218.4 | 22.5 | 177.7 | 418.9 | 570.3 | 155.4 | 608.2 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 7.9 | 0.8 | 7.7 | 8.8 | 8.9 | 7.2 | 8.9 |
| load_ms | Ollama loading the model (load_duration) | 1.1 | 0.1 | 1.1 | 1.3 | 1.4 | 1.0 | 1.4 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 483.9 | 49.9 | 454.4 | 1181.7 | 1424.9 | 74.8 | 1485.7 |
| eval_ms | generating the reply tokens (eval_duration) | 248.0 | 25.6 | 279.2 | 336.9 | 346.9 | 147.5 | 349.4 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 11.4 | 1.2 | 14.8 | 18.9 | 19.5 | 1.6 | 19.6 |
| total_latency_ms | the whole request handler, as measured by the service | 970.7 | 100.0 | 969.6 | 1674.2 | 1947.0 | 436.5 | 2015.2 |
