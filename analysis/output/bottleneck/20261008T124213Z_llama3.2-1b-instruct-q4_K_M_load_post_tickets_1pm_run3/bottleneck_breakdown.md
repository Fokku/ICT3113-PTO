| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 189.6 | 46.8 | 191.5 | 204.4 | 204.7 | 160.8 | 204.8 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 9.2 | 2.3 | 7.5 | 15.7 | 18.4 | 7.3 | 19.1 |
| load_ms | Ollama loading the model (load_duration) | 1.2 | 0.3 | 1.0 | 1.5 | 1.6 | 1.0 | 1.6 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 122.9 | 30.3 | 83.3 | 271.9 | 276.3 | 30.6 | 277.4 |
| eval_ms | generating the reply tokens (eval_duration) | 60.6 | 15.0 | 60.0 | 63.5 | 63.9 | 58.9 | 64.0 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 21.6 | 5.3 | 4.5 | 101.7 | 164.6 | 1.4 | 180.4 |
| total_latency_ms | the whole request handler, as measured by the service | 405.1 | 100.0 | 362.2 | 600.1 | 630.1 | 287.2 | 637.6 |
