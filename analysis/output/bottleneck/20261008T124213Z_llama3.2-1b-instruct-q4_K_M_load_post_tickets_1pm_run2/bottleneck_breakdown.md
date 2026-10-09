| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 199.6 | 44.9 | 189.2 | 271.5 | 273.6 | 155.1 | 274.1 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.8 | 2.0 | 7.5 | 13.1 | 13.3 | 7.2 | 13.4 |
| load_ms | Ollama loading the model (load_duration) | 1.1 | 0.3 | 1.1 | 1.5 | 1.7 | 1.0 | 1.7 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 169.7 | 38.2 | 163.0 | 398.5 | 477.3 | 31.3 | 497.0 |
| eval_ms | generating the reply tokens (eval_duration) | 60.9 | 13.7 | 60.6 | 62.3 | 62.3 | 59.7 | 62.4 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 4.0 | 0.9 | 4.5 | 6.3 | 6.6 | 1.6 | 6.7 |
| total_latency_ms | the whole request handler, as measured by the service | 444.2 | 100.0 | 455.0 | 637.1 | 709.3 | 280.8 | 727.4 |
