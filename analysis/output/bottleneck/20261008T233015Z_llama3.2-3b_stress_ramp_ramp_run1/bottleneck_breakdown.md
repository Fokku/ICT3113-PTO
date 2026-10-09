| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 190.7 | 9.8 | 187.1 | 276.1 | 474.0 | 102.6 | 598.0 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 11.4 | 0.6 | 8.0 | 25.9 | 28.3 | 7.0 | 51.6 |
| load_ms | Ollama loading the model (load_duration) | 1.5 | 0.1 | 1.1 | 3.9 | 4.5 | 0.9 | 6.3 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1063.2 | 54.4 | 998.2 | 2010.6 | 2447.5 | 285.0 | 2639.2 |
| eval_ms | generating the reply tokens (eval_duration) | 219.6 | 11.2 | 219.4 | 297.6 | 303.7 | 143.6 | 307.7 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 466.4 | 23.9 | 16.5 | 1917.4 | 3223.3 | 1.5 | 4059.8 |
| total_latency_ms | the whole request handler, as measured by the service | 1952.8 | 100.0 | 1701.7 | 3659.7 | 5109.0 | 668.6 | 5317.1 |
