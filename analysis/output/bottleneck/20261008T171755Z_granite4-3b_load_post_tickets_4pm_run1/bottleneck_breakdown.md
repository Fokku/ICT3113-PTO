| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 211.2 | 14.1 | 201.8 | 255.7 | 360.9 | 167.5 | 406.1 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 9.3 | 0.6 | 8.3 | 15.1 | 17.8 | 7.6 | 19.2 |
| load_ms | Ollama loading the model (load_duration) | 1.5 | 0.1 | 1.4 | 2.0 | 2.2 | 1.2 | 2.2 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1018.7 | 68.0 | 766.5 | 2332.4 | 2842.5 | 81.1 | 2997.1 |
| eval_ms | generating the reply tokens (eval_duration) | 202.9 | 13.5 | 160.0 | 316.9 | 328.4 | 155.0 | 333.8 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 54.5 | 3.6 | 8.7 | 46.5 | 1020.9 | 2.2 | 1293.3 |
| total_latency_ms | the whole request handler, as measured by the service | 1498.1 | 100.0 | 1208.4 | 2709.1 | 3348.6 | 483.9 | 3590.1 |
