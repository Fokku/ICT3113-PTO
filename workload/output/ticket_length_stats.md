# Ticket length distribution (measured)

Produced by `workload/scripts/ticket_length_stats.py` from `C:\Users\tohsi\Desktop\SIT Y3 S1\Performance\ICT3113-PTO\data\team_rows.csv`.

- Input SHA-256: `cfe08a5b81c8fa565d93675f32a4381f75454cc3f9ae5608e93caa1d75f12e77`
- These figures are **measured from our own team rows**, not estimated, so
  the workload model records them with `Estimate? = N` and cites this script
  and the input file as the source.
- Token counts are an **approximation**: `ceil(characters / 4)`. The true count is
  tokeniser-specific and therefore differs per candidate model. The
  authoritative per-request figure is `prompt_eval_count` in the service log
  (`service/log_schema.py`), available once benchmarks run. Do not report the
  approximation as a token measurement.

## Length distribution

| metric | unit | n | min | p5 | p25 | p50 | p75 | p90 | p95 | p99 | max | mean | sd |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| chars | characters | 1000 | 201 | 252.9 | 471.0 | 743.5 | 1193.0 | 1604.2 | 1799.3 | 1967.0 | 1999 | 861.0 | 473.1 |
| words | words | 1000 | 29 | 47.0 | 83.0 | 132.5 | 206.2 | 273.0 | 312.0 | 348.0 | 382 | 150.2 | 82.3 |
| approx_tokens | approximate tokens | 1000 | 51 | 64.0 | 118.0 | 186.0 | 299.0 | 401.1 | 450.1 | 492.0 | 500 | 215.6 | 118.3 |

## Context-window (num_ctx) sizing

| quantity | value | unit | how it was obtained |
|---|---|---|---|
| num_ctx | 4096 | tokens | --num-ctx (configuration contract NUM_CTX) |
| prompt overhead | 449 | characters | measured: len(service.prompt.build_prompt('')), the prompt the service sends |
| output tokens reserved | 0 | tokens | --reserve-output-tokens (default 0; the reply is a category name) |
| rows measured | 1000 | rows | counted from the input CSV |
| approximate prompt tokens, p99 | 604.01 | approximate tokens | approximation ceil((characters + prompt overhead) / 4), linear-interpolated p99 |
| approximate prompt tokens, longest row | 612 | approximate tokens | approximation ceil((characters + prompt overhead) / 4) |
| context headroom at the longest row | 3484 | approximate tokens | num_ctx - (longest prompt + reserved output); negative means it would not fit |
| rows at truncation risk | 0 | rows | count of rows where ceil((characters + prompt overhead) / 4) + reserved output > num_ctx |
| share of rows at truncation risk | 0.00 | % of rows measured | rows at risk / rows measured |

## Charts

- `length_histogram.png`
- `length_cdf.png`

## What Part 4 must still do with this

TODO(Part 4 — Teammate C): decide and write down, in
`../workload_model.md`, whether the client's real complaint traffic would
resemble this distribution. These narratives are CFPB complaints filed
through a regulator's web form; the client's own intake channel may differ
in length, and if it does, say so and say which direction.

TODO(Part 4 — Teammate C): if any row is at truncation risk, raise it with
Part 1 -- Yeo Kai Yuan before the benchmark runs. A silently truncated
prompt is a classification error we would otherwise blame on the model.
