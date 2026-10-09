| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 157.1 | 32.8 | 139.6 | 296.5 | 441.0 | 97.3 | 528.4 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.7 | 1.8 | 7.7 | 14.1 | 21.8 | 7.0 | 27.1 |
| load_ms | Ollama loading the model (load_duration) | 1.2 | 0.2 | 1.1 | 1.7 | 2.3 | 0.9 | 5.4 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 239.7 | 50.0 | 214.2 | 616.6 | 715.9 | 30.7 | 815.5 |
| eval_ms | generating the reply tokens (eval_duration) | 62.2 | 13.0 | 60.1 | 67.1 | 114.5 | 58.2 | 118.3 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 10.3 | 2.1 | 4.5 | 7.4 | 225.3 | 1.4 | 313.0 |
| total_latency_ms | the whole request handler, as measured by the service | 479.3 | 100.0 | 445.4 | 901.0 | 1082.9 | 207.8 | 1179.0 |
