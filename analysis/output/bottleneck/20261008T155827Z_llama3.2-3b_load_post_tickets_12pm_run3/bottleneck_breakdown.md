| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 244.0 | 22.1 | 220.2 | 382.7 | 527.5 | 167.6 | 555.2 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 9.8 | 0.9 | 7.7 | 19.0 | 28.4 | 7.0 | 57.3 |
| load_ms | Ollama loading the model (load_duration) | 1.3 | 0.1 | 1.1 | 2.6 | 4.5 | 0.9 | 6.5 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 503.4 | 45.7 | 373.9 | 1576.8 | 2014.3 | 74.7 | 2279.7 |
| eval_ms | generating the reply tokens (eval_duration) | 227.0 | 20.6 | 227.3 | 307.1 | 310.8 | 147.3 | 321.9 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 116.8 | 10.6 | 14.2 | 695.1 | 1669.0 | 1.5 | 2111.0 |
| total_latency_ms | the whole request handler, as measured by the service | 1102.3 | 100.0 | 922.1 | 2457.8 | 2976.1 | 417.6 | 3052.5 |
