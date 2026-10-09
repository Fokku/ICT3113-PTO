| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 189.5 | 6.5 | 173.1 | 348.5 | 422.4 | 141.3 | 455.2 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 13.6 | 0.5 | 8.6 | 32.7 | 50.1 | 7.4 | 61.6 |
| load_ms | Ollama loading the model (load_duration) | 1.7 | 0.1 | 1.1 | 4.9 | 5.3 | 0.9 | 6.2 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1541.6 | 52.6 | 1348.0 | 3954.1 | 4681.3 | 152.1 | 5119.5 |
| eval_ms | generating the reply tokens (eval_duration) | 422.2 | 14.4 | 313.5 | 613.5 | 622.2 | 301.1 | 629.8 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 760.6 | 26.0 | 9.2 | 3796.0 | 5315.6 | 2.1 | 5898.2 |
| total_latency_ms | the whole request handler, as measured by the service | 2929.3 | 100.0 | 2474.2 | 6577.1 | 8520.3 | 624.7 | 9252.6 |
