| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 231.8 | 8.0 | 195.2 | 390.6 | 413.4 | 166.3 | 419.1 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 8.8 | 0.3 | 8.4 | 11.6 | 13.3 | 7.6 | 13.7 |
| load_ms | Ollama loading the model (load_duration) | 1.1 | 0.0 | 1.0 | 1.6 | 1.6 | 1.0 | 1.6 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 2143.8 | 74.4 | 1935.7 | 3642.3 | 3988.4 | 804.6 | 4074.9 |
| eval_ms | generating the reply tokens (eval_duration) | 489.3 | 17.0 | 535.0 | 614.1 | 615.2 | 303.9 | 615.5 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 6.9 | 0.2 | 7.4 | 10.9 | 11.5 | 2.5 | 11.7 |
| total_latency_ms | the whole request handler, as measured by the service | 2881.8 | 100.0 | 2766.9 | 4449.4 | 4786.9 | 1461.9 | 4871.3 |
