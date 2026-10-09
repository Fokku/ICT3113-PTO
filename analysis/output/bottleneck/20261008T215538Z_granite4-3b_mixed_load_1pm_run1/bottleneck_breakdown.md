| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 252.7 | 16.2 | 182.4 | 571.3 | 649.5 | 151.8 | 669.0 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.7 | 0.6 | 8.3 | 11.5 | 13.5 | 7.5 | 14.0 |
| load_ms | Ollama loading the model (load_duration) | 1.4 | 0.1 | 1.3 | 1.7 | 1.9 | 1.2 | 1.9 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1055.4 | 67.8 | 942.3 | 1836.7 | 2016.8 | 406.0 | 2061.8 |
| eval_ms | generating the reply tokens (eval_duration) | 230.6 | 14.8 | 228.8 | 309.1 | 309.7 | 151.5 | 309.9 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 8.6 | 0.6 | 9.1 | 14.7 | 16.4 | 2.4 | 16.9 |
| total_latency_ms | the whole request handler, as measured by the service | 1557.4 | 100.0 | 1550.7 | 2267.6 | 2390.0 | 957.2 | 2420.6 |
