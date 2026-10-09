| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 252.2 | 37.3 | 189.3 | 727.0 | 1019.0 | 109.9 | 1385.5 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 9.1 | 1.3 | 7.7 | 14.6 | 25.8 | 7.1 | 36.7 |
| load_ms | Ollama loading the model (load_duration) | 1.2 | 0.2 | 1.1 | 1.7 | 2.7 | 0.9 | 3.8 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 328.5 | 48.5 | 301.0 | 701.8 | 805.3 | 30.3 | 974.8 |
| eval_ms | generating the reply tokens (eval_duration) | 62.6 | 9.2 | 60.5 | 67.3 | 111.2 | 57.8 | 121.0 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 23.1 | 3.4 | 4.5 | 117.1 | 472.7 | 1.4 | 553.7 |
| total_latency_ms | the whole request handler, as measured by the service | 676.7 | 100.0 | 619.0 | 1208.7 | 1614.8 | 248.9 | 1846.7 |
