| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 192.7 | 4.9 | 182.9 | 353.3 | 403.4 | 110.4 | 418.5 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 12.7 | 0.3 | 9.1 | 27.8 | 54.5 | 7.6 | 54.7 |
| load_ms | Ollama loading the model (load_duration) | 1.5 | 0.0 | 1.2 | 2.3 | 4.0 | 1.0 | 4.9 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 2088.0 | 53.6 | 1610.1 | 4830.9 | 5765.1 | 178.8 | 6032.3 |
| eval_ms | generating the reply tokens (eval_duration) | 453.9 | 11.7 | 415.1 | 732.2 | 738.1 | 311.2 | 741.4 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 1145.8 | 29.4 | 9.6 | 6623.3 | 7684.5 | 2.4 | 7693.2 |
| total_latency_ms | the whole request handler, as measured by the service | 3894.6 | 100.0 | 2729.6 | 9432.8 | 12194.7 | 746.5 | 12479.5 |
