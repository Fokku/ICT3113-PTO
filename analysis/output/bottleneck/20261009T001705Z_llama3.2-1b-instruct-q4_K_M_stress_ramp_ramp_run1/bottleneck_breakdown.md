| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 192.4 | 24.0 | 167.3 | 358.9 | 502.3 | 131.7 | 1207.4 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 11.0 | 1.4 | 8.0 | 22.7 | 31.5 | 6.4 | 61.6 |
| load_ms | Ollama loading the model (load_duration) | 1.4 | 0.2 | 1.1 | 2.5 | 4.5 | 0.9 | 6.1 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 389.4 | 48.5 | 344.0 | 751.2 | 877.2 | 106.3 | 946.5 |
| eval_ms | generating the reply tokens (eval_duration) | 61.0 | 7.6 | 59.6 | 63.7 | 90.2 | 56.9 | 119.6 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 148.3 | 18.5 | 5.9 | 782.2 | 1225.0 | 1.4 | 1597.7 |
| total_latency_ms | the whole request handler, as measured by the service | 803.5 | 100.0 | 727.8 | 1511.2 | 1817.1 | 337.7 | 2128.6 |
