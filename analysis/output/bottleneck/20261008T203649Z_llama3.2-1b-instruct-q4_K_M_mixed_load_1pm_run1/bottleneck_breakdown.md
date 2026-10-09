| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 178.6 | 30.6 | 179.1 | 187.5 | 188.1 | 169.0 | 188.2 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.0 | 1.4 | 7.5 | 10.5 | 12.1 | 7.2 | 12.5 |
| load_ms | Ollama loading the model (load_duration) | 1.0 | 0.2 | 1.0 | 1.1 | 1.1 | 0.9 | 1.1 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 331.5 | 56.9 | 296.0 | 567.3 | 620.2 | 136.3 | 633.4 |
| eval_ms | generating the reply tokens (eval_duration) | 59.5 | 10.2 | 59.3 | 61.7 | 62.1 | 57.4 | 62.2 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 4.2 | 0.7 | 4.5 | 6.8 | 7.3 | 1.6 | 7.5 |
| total_latency_ms | the whole request handler, as measured by the service | 582.9 | 100.0 | 547.5 | 829.2 | 884.1 | 378.3 | 897.8 |
