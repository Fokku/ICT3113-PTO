| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 440.1 | 12.4 | 196.2 | 1547.6 | 2291.4 | 165.6 | 2477.4 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 11.2 | 0.3 | 9.3 | 21.0 | 28.2 | 8.1 | 30.0 |
| load_ms | Ollama loading the model (load_duration) | 1.5 | 0.0 | 1.2 | 3.0 | 3.9 | 1.0 | 4.1 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 2483.1 | 69.8 | 2279.8 | 4152.3 | 4528.1 | 952.0 | 4622.0 |
| eval_ms | generating the reply tokens (eval_duration) | 610.0 | 17.1 | 665.5 | 779.6 | 783.6 | 369.8 | 784.6 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 13.7 | 0.4 | 9.7 | 39.6 | 56.7 | 2.7 | 60.9 |
| total_latency_ms | the whole request handler, as measured by the service | 3559.7 | 100.0 | 3410.2 | 5484.3 | 5567.0 | 1748.4 | 5587.7 |
