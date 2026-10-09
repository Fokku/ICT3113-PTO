| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 260.4 | 12.7 | 191.2 | 502.1 | 551.9 | 166.4 | 564.3 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 9.7 | 0.5 | 9.8 | 10.7 | 10.8 | 8.5 | 10.8 |
| load_ms | Ollama loading the model (load_duration) | 1.3 | 0.1 | 1.2 | 1.6 | 1.6 | 1.0 | 1.6 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1178.6 | 57.4 | 1065.0 | 2839.2 | 3444.1 | 187.7 | 3595.4 |
| eval_ms | generating the reply tokens (eval_duration) | 595.1 | 29.0 | 608.0 | 764.2 | 767.3 | 370.9 | 768.1 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 9.0 | 0.4 | 10.8 | 14.7 | 15.9 | 2.2 | 16.2 |
| total_latency_ms | the whole request handler, as measured by the service | 2054.0 | 100.0 | 1860.2 | 3965.0 | 4433.9 | 901.6 | 4551.1 |
