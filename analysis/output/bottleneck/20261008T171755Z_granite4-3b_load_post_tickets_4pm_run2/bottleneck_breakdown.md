| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 333.1 | 21.3 | 211.7 | 707.4 | 1287.4 | 173.8 | 1465.4 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 10.5 | 0.7 | 9.4 | 19.2 | 22.0 | 7.9 | 22.4 |
| load_ms | Ollama loading the model (load_duration) | 1.6 | 0.1 | 1.4 | 2.7 | 2.8 | 1.2 | 2.8 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 912.4 | 58.4 | 740.4 | 2257.4 | 2706.5 | 94.0 | 2795.6 |
| eval_ms | generating the reply tokens (eval_duration) | 243.9 | 15.6 | 195.4 | 389.9 | 412.9 | 174.7 | 416.7 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 60.0 | 3.8 | 9.0 | 631.8 | 721.7 | 2.5 | 724.3 |
| total_latency_ms | the whole request handler, as measured by the service | 1561.6 | 100.0 | 1462.2 | 3008.0 | 3166.0 | 499.8 | 3212.2 |
