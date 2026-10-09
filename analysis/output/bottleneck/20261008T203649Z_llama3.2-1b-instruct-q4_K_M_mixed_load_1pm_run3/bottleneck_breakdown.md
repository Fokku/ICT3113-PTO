| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 188.4 | 49.7 | 182.8 | 232.3 | 255.3 | 164.9 | 261.1 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.5 | 2.3 | 7.5 | 12.9 | 13.1 | 7.0 | 13.1 |
| load_ms | Ollama loading the model (load_duration) | 1.1 | 0.3 | 1.0 | 1.3 | 1.5 | 1.0 | 1.5 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 118.7 | 31.3 | 82.1 | 262.2 | 270.6 | 30.6 | 272.7 |
| eval_ms | generating the reply tokens (eval_duration) | 58.4 | 15.4 | 58.2 | 59.5 | 59.6 | 57.1 | 59.6 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 3.8 | 1.0 | 4.5 | 5.9 | 6.3 | 1.5 | 6.4 |
| total_latency_ms | the whole request handler, as measured by the service | 379.0 | 100.0 | 341.3 | 508.4 | 509.9 | 269.4 | 510.3 |
