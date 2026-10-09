| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 196.2 | 12.9 | 165.9 | 399.9 | 447.3 | 110.7 | 675.5 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 12.3 | 0.8 | 9.7 | 26.7 | 46.2 | 7.9 | 57.8 |
| load_ms | Ollama loading the model (load_duration) | 1.9 | 0.1 | 1.6 | 3.7 | 7.1 | 1.2 | 9.0 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 871.9 | 57.5 | 762.5 | 2287.9 | 2513.2 | 94.0 | 2843.5 |
| eval_ms | generating the reply tokens (eval_duration) | 257.1 | 16.9 | 200.0 | 406.8 | 417.6 | 186.0 | 433.0 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 177.7 | 11.7 | 13.0 | 1033.3 | 2108.0 | 2.7 | 2231.8 |
| total_latency_ms | the whole request handler, as measured by the service | 1517.1 | 100.0 | 1470.7 | 3101.4 | 4089.9 | 451.1 | 4294.4 |
