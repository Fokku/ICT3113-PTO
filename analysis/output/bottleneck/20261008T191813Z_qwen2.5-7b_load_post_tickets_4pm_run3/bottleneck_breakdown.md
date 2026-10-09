| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 191.1 | 10.5 | 160.3 | 346.6 | 435.1 | 95.9 | 447.3 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 12.6 | 0.7 | 8.2 | 31.8 | 57.2 | 7.5 | 60.8 |
| load_ms | Ollama loading the model (load_duration) | 1.5 | 0.1 | 1.1 | 4.5 | 5.1 | 1.0 | 5.3 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1122.1 | 61.5 | 825.2 | 4184.4 | 4949.9 | 152.1 | 5117.0 |
| eval_ms | generating the reply tokens (eval_duration) | 417.8 | 22.9 | 320.2 | 617.7 | 626.0 | 301.3 | 629.2 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 79.2 | 4.3 | 6.7 | 287.6 | 1270.2 | 2.1 | 1298.5 |
| total_latency_ms | the whole request handler, as measured by the service | 1824.3 | 100.0 | 1581.1 | 4988.8 | 5494.9 | 636.3 | 5612.4 |
