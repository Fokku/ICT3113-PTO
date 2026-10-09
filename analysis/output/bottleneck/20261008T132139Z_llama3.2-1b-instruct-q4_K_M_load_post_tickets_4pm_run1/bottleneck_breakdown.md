| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 200.0 | 30.0 | 193.6 | 318.6 | 335.6 | 149.8 | 345.9 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.5 | 1.3 | 7.7 | 14.9 | 17.4 | 7.1 | 18.8 |
| load_ms | Ollama loading the model (load_duration) | 1.1 | 0.2 | 1.1 | 1.6 | 1.8 | 0.9 | 1.8 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 378.3 | 56.8 | 322.5 | 743.9 | 883.6 | 135.1 | 917.1 |
| eval_ms | generating the reply tokens (eval_duration) | 62.6 | 9.4 | 60.0 | 66.5 | 110.3 | 58.7 | 122.8 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 15.5 | 2.3 | 3.9 | 7.8 | 287.1 | 1.5 | 465.2 |
| total_latency_ms | the whole request handler, as measured by the service | 666.0 | 100.0 | 638.2 | 1020.5 | 1449.7 | 380.1 | 1670.4 |
