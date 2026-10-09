| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 201.4 | 12.4 | 188.9 | 265.1 | 480.2 | 153.5 | 902.9 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 10.9 | 0.7 | 7.8 | 24.6 | 30.8 | 7.1 | 66.7 |
| load_ms | Ollama loading the model (load_duration) | 1.4 | 0.1 | 1.1 | 4.1 | 4.6 | 0.9 | 5.6 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 911.9 | 56.2 | 836.8 | 1960.0 | 2275.9 | 75.2 | 2826.5 |
| eval_ms | generating the reply tokens (eval_duration) | 224.1 | 13.8 | 225.7 | 302.4 | 312.6 | 147.1 | 338.0 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 272.6 | 16.8 | 16.1 | 1693.4 | 2522.7 | 1.4 | 2660.4 |
| total_latency_ms | the whole request handler, as measured by the service | 1622.2 | 100.0 | 1502.6 | 3417.6 | 3649.7 | 423.8 | 4375.4 |
