| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 250.0 | 21.7 | 204.1 | 442.7 | 642.5 | 164.3 | 706.1 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 10.0 | 0.9 | 9.2 | 15.3 | 17.3 | 8.1 | 17.6 |
| load_ms | Ollama loading the model (load_duration) | 1.6 | 0.1 | 1.5 | 2.3 | 3.4 | 1.2 | 3.7 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 626.8 | 54.5 | 468.7 | 2291.1 | 2688.6 | 83.8 | 2798.3 |
| eval_ms | generating the reply tokens (eval_duration) | 245.2 | 21.3 | 195.7 | 395.1 | 434.5 | 167.7 | 453.2 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 16.1 | 1.4 | 8.7 | 22.1 | 190.8 | 2.5 | 298.0 |
| total_latency_ms | the whole request handler, as measured by the service | 1149.5 | 100.0 | 963.4 | 2704.3 | 3066.2 | 490.4 | 3179.4 |
