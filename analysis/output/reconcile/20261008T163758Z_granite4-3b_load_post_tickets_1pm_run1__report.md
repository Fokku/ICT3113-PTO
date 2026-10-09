# Reconciliation report: `20261008T163758Z_granite4-3b_load_post_tickets_1pm_run1`

**Verdict: PASS**

* Run directory: `results/runs/20261008T163758Z_granite4-3b_load_post_tickets_1pm_run1`
* Model pin: `granite4:3b` (`sha256:89962fcc75239ac434cdebceb6b7e0669397f92eaef9c487774b718bc36a3e5f`)
* Mode: `real`, freeze commit: `41d6ce2c2aa8c9e03c9d1e2abe2e23096aba9fba`
* Prompt hash: `sha256:681131c48bdc15a1`, num_ctx: `4096`, seed: `42`

Measured `.jtl` samples: 10. Measured service log lines: 10. Joined on `request_id`: 10.

Thresholds in force: `--max-unmatched 0`, `--latency-threshold-ms 250`.

## Checks

| check | value | limit | verdict | detail |
|---|---|---|---|---|
| jtl_samples_without_log_line | 0 | <= 0 | pass | every measured sample has a service log line |
| log_lines_without_jtl_sample | 0 | <= 0 | pass | every log line in the run window has a matching sample |
| blank_request_ids | jtl=0 log=0 | 0 | pass | every row carries a request_id |
| duplicate_request_ids | jtl=0 log=0 | 0 | pass | request_ids are unique on both sides |
| status_disagreements | 0 | 0 | pass | every matched sample agrees with its log line on HTTP status |
| source_row_disagreements | 0 | 0 | pass | every matched sample agrees with its log line on source_row |
| client_minus_server_latency_p99_ms | 75.9 | <= 250 | pass | p99 of abs(elapsed minus total_latency_ms); a large value means the load generator or the clocks, not the service, are shaping the numbers |


## Unmatched and duplicated request_ids

_(none)_


## Field disagreements on matched rows

_(none)_


## Client-minus-server latency difference (ms)

`elapsed` (client-observed) minus `total_latency_ms` (the service's own handler clock). This is network plus framework overhead: it should be small and stable. The gate uses the p99 of the absolute difference.

| statistic | signed_ms | absolute_ms |
|---|---|---|
| rows_compared | 10.0 | 10.0 |
| p50 | 14.1 | 14.1 |
| p95 | 71.3 | 71.3 |
| p99 | 75.9 | 75.9 |
| min | 8.6 | 8.6 |
| max | 77.1 | 77.1 |
| mean | 28.5 | 28.5 |


## Why these are blockers

An unmatched sample means a number in our slides has no log line behind it, and the brief treats a number that cannot be traced to a log entry as unsupported. A duplicate `request_id` makes "the log line behind this sample" undefined. A status disagreement means one of our two instruments is wrong about what happened, so the error rate cannot be defended. A `source_row` disagreement means the traffic measured is not the traffic we think we measured. A large client-minus-server p99 means the load generator or the clocks are shaping the latency we are about to report, which the brief rejects as a measurement.
