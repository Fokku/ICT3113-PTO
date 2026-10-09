| component | note | mean_ms | share_of_mean_total_pct | p50_ms | p95_ms | p99_ms | min_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| service_overhead_ms | our own handler outside the model call: request parsing, prompt construction, category normalisation, the SQLite insert, the log write | 150.4 | 5.9 | 132.9 | 275.6 | 338.9 | 104.1 | 374.8 |
| queue_residual_ms | RESIDUAL: our HTTP call minus Ollama's own total_duration. Where Ollama-side queueing shows up, but also HTTP and container-network overhead and per-request connection setup | 9.4 | 0.4 | 8.4 | 13.7 | 16.0 | 7.6 | 16.5 |
| load_ms | Ollama loading the model (load_duration) | 1.1 | 0.0 | 1.1 | 1.6 | 1.6 | 1.0 | 1.6 |
| prompt_eval_ms | evaluating the prompt tokens, the prefill (prompt_eval_duration) | 1689.6 | 66.4 | 1334.6 | 4215.7 | 5155.7 | 155.2 | 5349.1 |
| eval_ms | generating the reply tokens (eval_duration) | 453.8 | 17.8 | 403.8 | 665.1 | 689.8 | 303.4 | 702.8 |
| ollama_other_ms | RESIDUAL: Ollama's total_duration minus load + prompt eval + generation | 239.6 | 9.4 | 5.5 | 1527.5 | 4419.7 | 2.2 | 6184.3 |
| total_latency_ms | the whole request handler, as measured by the service | 2543.9 | 100.0 | 2078.4 | 6523.6 | 7766.9 | 614.8 | 8123.8 |
