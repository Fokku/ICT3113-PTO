| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 198.0 | 40.6 | 182.7 | 261.0 | 385.1 | 154.8 | 394.0 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 9.4 | 1.9 | 7.7 | 19.2 | 27.6 | 7.1 | 27.8 |
| load_ms | Ollama loading the model (load_duration) | 1.2 | 0.2 | 1.0 | 1.8 | 3.9 | 0.9 | 3.9 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 205.2 | 42.0 | 150.1 | 663.4 | 772.1 | 29.8 | 810.2 |
| eval_ms | generating the reply tokens (eval_duration) | 62.7 | 12.9 | 60.0 | 88.8 | 105.9 | 57.7 | 116.4 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 11.4 | 2.3 | 2.9 | 54.8 | 160.4 | 1.5 | 224.9 |
| total_latency_ms | the whole request handler, as measured by the service | 487.9 | 100.0 | 444.1 | 1017.3 | 1072.0 | 271.3 | 1087.4 |
