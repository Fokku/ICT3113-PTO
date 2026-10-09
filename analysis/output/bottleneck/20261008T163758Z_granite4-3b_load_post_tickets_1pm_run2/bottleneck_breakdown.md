| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 181.8 | 18.5 | 177.7 | 208.4 | 212.2 | 157.4 | 213.1 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.9 | 0.9 | 8.4 | 11.3 | 12.4 | 7.5 | 12.7 |
| load_ms | Ollama loading the model (load_duration) | 1.4 | 0.1 | 1.4 | 1.7 | 1.8 | 1.2 | 1.8 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 524.3 | 53.5 | 495.9 | 1277.3 | 1565.0 | 80.5 | 1636.9 |
| eval_ms | generating the reply tokens (eval_duration) | 254.2 | 25.9 | 276.3 | 320.6 | 322.3 | 156.8 | 322.8 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 10.0 | 1.0 | 12.8 | 15.9 | 16.3 | 2.5 | 16.5 |
| total_latency_ms | the whole request handler, as measured by the service | 980.7 | 100.0 | 909.4 | 1777.7 | 2078.2 | 457.9 | 2153.3 |
