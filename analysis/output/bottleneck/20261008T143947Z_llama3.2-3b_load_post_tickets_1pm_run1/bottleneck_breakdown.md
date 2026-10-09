| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 158.3 | 11.6 | 160.4 | 188.1 | 200.5 | 123.9 | 203.6 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.0 | 0.6 | 7.6 | 9.7 | 10.1 | 7.3 | 10.2 |
| load_ms | Ollama loading the model (load_duration) | 1.2 | 0.1 | 1.0 | 1.7 | 1.7 | 0.9 | 1.7 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 957.1 | 70.1 | 863.0 | 1667.0 | 1841.6 | 379.7 | 1885.2 |
| eval_ms | generating the reply tokens (eval_duration) | 232.1 | 17.0 | 263.5 | 298.2 | 298.3 | 146.9 | 298.4 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 9.3 | 0.7 | 9.8 | 17.8 | 20.0 | 1.6 | 20.6 |
| total_latency_ms | the whole request handler, as measured by the service | 1365.9 | 100.0 | 1282.0 | 2149.8 | 2324.6 | 724.9 | 2368.3 |
