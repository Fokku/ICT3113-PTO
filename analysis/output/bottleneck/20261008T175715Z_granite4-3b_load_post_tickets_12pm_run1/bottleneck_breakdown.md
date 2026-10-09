| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 252.0 | 12.7 | 200.9 | 470.8 | 615.8 | 159.0 | 753.9 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 12.9 | 0.7 | 10.0 | 26.2 | 49.4 | 8.1 | 69.9 |
| load_ms | Ollama loading the model (load_duration) | 2.0 | 0.1 | 1.5 | 4.5 | 6.0 | 1.2 | 6.1 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1154.7 | 58.3 | 1036.5 | 2569.4 | 2830.9 | 92.7 | 3364.3 |
| eval_ms | generating the reply tokens (eval_duration) | 253.4 | 12.8 | 199.3 | 388.9 | 404.6 | 185.8 | 442.7 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 306.0 | 15.4 | 13.0 | 1635.8 | 3900.0 | 2.4 | 4380.8 |
| total_latency_ms | the whole request handler, as measured by the service | 1981.0 | 100.0 | 1774.5 | 3733.2 | 6027.6 | 496.6 | 6130.7 |
