| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 317.3 | 23.6 | 201.1 | 780.6 | 1840.8 | 151.1 | 1989.7 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 12.1 | 0.9 | 9.9 | 25.2 | 29.5 | 8.1 | 42.8 |
| load_ms | Ollama loading the model (load_duration) | 1.9 | 0.1 | 1.6 | 3.4 | 5.4 | 1.2 | 8.4 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 624.6 | 46.4 | 474.0 | 2167.4 | 2670.0 | 94.1 | 2890.9 |
| eval_ms | generating the reply tokens (eval_duration) | 259.0 | 19.2 | 203.3 | 403.0 | 434.1 | 186.6 | 456.2 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 131.7 | 9.8 | 13.0 | 1009.0 | 1444.8 | 2.4 | 1714.8 |
| total_latency_ms | the whole request handler, as measured by the service | 1346.7 | 100.0 | 1267.2 | 2845.5 | 3539.2 | 482.0 | 4364.8 |
