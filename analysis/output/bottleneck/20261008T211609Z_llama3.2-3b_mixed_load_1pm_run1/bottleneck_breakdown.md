| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 209.6 | 15.2 | 195.5 | 284.7 | 320.1 | 164.2 | 328.9 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 7.9 | 0.6 | 7.4 | 10.3 | 12.0 | 7.2 | 12.4 |
| load_ms | Ollama loading the model (load_duration) | 1.1 | 0.1 | 1.0 | 1.2 | 1.2 | 1.0 | 1.2 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 927.8 | 67.1 | 829.5 | 1608.5 | 1770.3 | 362.0 | 1810.7 |
| eval_ms | generating the reply tokens (eval_duration) | 226.7 | 16.4 | 253.3 | 293.7 | 294.1 | 145.5 | 294.2 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 9.1 | 0.7 | 9.7 | 17.5 | 20.0 | 1.6 | 20.6 |
| total_latency_ms | the whole request handler, as measured by the service | 1382.1 | 100.0 | 1295.0 | 2120.6 | 2303.2 | 746.1 | 2348.8 |
