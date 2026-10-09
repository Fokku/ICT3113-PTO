| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 221.8 | 14.5 | 192.7 | 311.9 | 318.7 | 171.5 | 320.4 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 10.3 | 0.7 | 9.0 | 14.5 | 14.7 | 7.7 | 14.7 |
| load_ms | Ollama loading the model (load_duration) | 1.1 | 0.1 | 1.1 | 1.3 | 1.4 | 1.0 | 1.4 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 758.4 | 49.6 | 496.9 | 1722.6 | 1776.7 | 163.2 | 1790.2 |
| eval_ms | generating the reply tokens (eval_duration) | 529.9 | 34.7 | 571.3 | 678.2 | 681.7 | 314.0 | 682.6 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 7.1 | 0.5 | 8.9 | 10.7 | 10.9 | 2.2 | 11.0 |
| total_latency_ms | the whole request handler, as measured by the service | 1528.7 | 100.0 | 1355.6 | 2470.3 | 2480.3 | 705.9 | 2482.8 |
