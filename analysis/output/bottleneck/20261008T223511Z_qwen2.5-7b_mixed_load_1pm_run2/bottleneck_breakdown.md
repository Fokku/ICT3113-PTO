| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 235.2 | 7.8 | 211.1 | 361.4 | 388.3 | 186.6 | 395.0 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 10.6 | 0.4 | 7.9 | 20.9 | 23.8 | 7.6 | 24.5 |
| load_ms | Ollama loading the model (load_duration) | 1.2 | 0.0 | 1.1 | 1.6 | 1.6 | 0.9 | 1.6 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 2140.4 | 71.0 | 1925.3 | 3642.8 | 3992.5 | 830.7 | 4080.0 |
| eval_ms | generating the reply tokens (eval_duration) | 489.9 | 16.2 | 541.0 | 616.0 | 618.0 | 302.5 | 618.5 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 138.9 | 4.6 | 8.2 | 735.0 | 1208.4 | 2.2 | 1326.8 |
| total_latency_ms | the whole request handler, as measured by the service | 3016.2 | 100.0 | 2673.2 | 5118.2 | 5255.6 | 1542.1 | 5290.0 |
