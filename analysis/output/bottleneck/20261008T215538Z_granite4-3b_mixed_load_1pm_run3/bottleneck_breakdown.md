| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 214.5 | 25.7 | 192.2 | 314.0 | 373.7 | 176.7 | 388.6 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.7 | 1.0 | 8.1 | 11.4 | 13.1 | 7.7 | 13.5 |
| load_ms | Ollama loading the model (load_duration) | 1.4 | 0.2 | 1.3 | 1.7 | 1.9 | 1.2 | 2.0 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 355.8 | 42.6 | 240.8 | 797.6 | 809.9 | 78.0 | 813.0 |
| eval_ms | generating the reply tokens (eval_duration) | 245.4 | 29.4 | 269.5 | 308.9 | 309.6 | 151.5 | 309.8 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 8.8 | 1.1 | 10.2 | 14.6 | 15.2 | 2.4 | 15.3 |
| total_latency_ms | the whole request handler, as measured by the service | 834.5 | 100.0 | 735.5 | 1288.9 | 1307.2 | 438.6 | 1311.8 |
