| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 198.6 | 16.1 | 189.3 | 260.8 | 329.5 | 148.5 | 449.0 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 10.3 | 0.8 | 7.8 | 20.7 | 38.7 | 6.9 | 55.7 |
| load_ms | Ollama loading the model (load_duration) | 1.3 | 0.1 | 1.1 | 1.9 | 5.7 | 0.9 | 7.7 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 684.8 | 55.6 | 609.6 | 1803.5 | 2048.3 | 74.8 | 2270.4 |
| eval_ms | generating the reply tokens (eval_duration) | 224.3 | 18.2 | 224.5 | 303.5 | 304.8 | 147.6 | 308.8 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 112.7 | 9.1 | 14.9 | 545.8 | 1388.0 | 1.5 | 1438.9 |
| total_latency_ms | the whole request handler, as measured by the service | 1232.0 | 100.0 | 1122.7 | 2317.6 | 3013.8 | 431.0 | 3733.2 |
