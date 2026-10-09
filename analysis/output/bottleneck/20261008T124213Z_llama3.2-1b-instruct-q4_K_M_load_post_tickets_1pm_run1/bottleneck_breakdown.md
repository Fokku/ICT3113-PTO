| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 219.7 | 34.4 | 191.3 | 339.1 | 407.9 | 168.9 | 425.1 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.2 | 1.3 | 7.8 | 11.1 | 12.7 | 7.2 | 13.1 |
| load_ms | Ollama loading the model (load_duration) | 1.0 | 0.2 | 1.0 | 1.1 | 1.1 | 0.9 | 1.1 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 344.7 | 54.0 | 306.0 | 595.6 | 654.9 | 144.1 | 669.7 |
| eval_ms | generating the reply tokens (eval_duration) | 60.2 | 9.4 | 60.3 | 61.9 | 62.3 | 58.7 | 62.4 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 4.2 | 0.7 | 4.8 | 6.9 | 7.4 | 1.5 | 7.5 |
| total_latency_ms | the whole request handler, as measured by the service | 638.2 | 100.0 | 564.0 | 947.6 | 968.6 | 454.4 | 973.9 |
