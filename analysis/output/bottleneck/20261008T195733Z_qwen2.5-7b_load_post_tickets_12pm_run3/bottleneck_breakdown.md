| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 197.2 | 9.3 | 171.5 | 381.8 | 528.1 | 133.0 | 672.9 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 11.8 | 0.6 | 8.7 | 27.9 | 30.6 | 7.7 | 55.0 |
| load_ms | Ollama loading the model (load_duration) | 1.5 | 0.1 | 1.1 | 4.2 | 5.1 | 1.0 | 5.2 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1119.8 | 52.6 | 805.0 | 3869.3 | 4718.6 | 151.1 | 5106.7 |
| eval_ms | generating the reply tokens (eval_duration) | 419.2 | 19.7 | 310.2 | 615.3 | 622.8 | 301.6 | 628.5 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 379.6 | 17.8 | 8.7 | 2213.0 | 3878.7 | 1.9 | 4191.0 |
| total_latency_ms | the whole request handler, as measured by the service | 2129.0 | 100.0 | 1889.8 | 4998.1 | 6936.9 | 633.3 | 9780.3 |
