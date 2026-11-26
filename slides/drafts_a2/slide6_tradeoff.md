# Slide 6 — Trade-off (draft)

**Brief (verbatim):** "One chart: accuracy vs latency, one point per configuration and setting, overall limit
drawn as a line. Short interpretation."
**Owner:** Jolie Ngai Ning Li (Part 3). Part 5 owns layout and assembly.
**Done when** (`../outline_a2.md`): every plotted point's two coordinates each trace to a number already
shown on Slides 4 and 5.

The chart introduces no new numbers. Accuracy comes from Slide 4 (`analysis/output/accuracy_a2/`) and
latency from Slide 5 (`analysis/output/speed_a2/per_config.csv`). No Assignment 1 speed figure is used
(TODO_A2.md, guardrail 10).

**Status:** data filled in 2026-11-26 by Part 1 (numbers only, from the output files). The title, the
interpretation lines and the chart itself are still Part 3's.

---

## Title

`<one line: e.g. "The cascade is / is not faster than qwen2.5:7b at the accuracy we need">`

## The chart

- **x-axis:** median latency, in seconds: the mean of the three per-run p50s (`p50_mean_ms` / 1000). Draw
  the per-run p50 range (`p50_min_ms`–`p50_max_ms`) as a horizontal error bar, so overlapping ranges are
  visible. Slide 7's "faster" rule depends on whether the ranges overlap.
- **y-axis:** overall accuracy on the 101 test rows, as a percentage. Label each point with its count
  (e.g. "75/101").
- **Horizontal reference line:** the overall limit, **64.26% (65/101)**, labelled "overall limit".
- **Points, one per configuration and setting:**

| Point | Accuracy (Slide 4) | Median latency (Slide 5) | Passes both limits? | Marker |
|---|---|---|---|---|
| `qwen2.5:7b` alone (reference) | 75/101 (74.26%) | 4.50 s (frozen rule: run 3 only). Secondary: 5.31 s, range 4.50–6.12 | Yes | filled |
| Cascade, Setting A | 76/101 (75.25%) | 7.63 s (frozen rule: run 2 only). Secondary: 8.83 s, range 7.63–9.61 | Yes | filled |
| Cascade, Setting B | 74/101 (73.27%) | 5.57 s (run 2 only, both readings) | Yes | filled |

Latency source: `analysis/output/speed_a2/per_config.csv` (`p50_mean_ms`, frozen §4 rule: one counted run per
configuration, so no range) and, labelled as secondary, `analysis/output/speed_a2_secondary/per_config.csv`
(`p50_min_ms`–`p50_max_ms`). Every run's own p50 (all nine, for an error bar that ignores the queue flag, if the
team wants one): `qwen2.5:7b` 6.12 / 6.54 / 4.50, cascade A 9.61 / 7.63 / 9.25, cascade B 5.50 / 5.57 / 5.03 s
(`p50_per_run_ms`). Say which one the chart uses.
| Any other single model that passes both limits | — | — | — | none currently: all three fail on Slide 4 |

- **Failing points stay on the chart, drawn hollow.** A cascade setting that fails accuracy still gets a
  point, because its speed was measured. The hollow marker should make "fast but failing" readable at a
  glance (`../outline_a2.md`).
- **Single models that failed accuracy have no point.** `granite4:3b`, `llama3.2:3b` and `llama3.2:1b` failed
  accuracy, so by the brief they are not speed-tested, and there is no latency to plot. Say this in one line
  under the chart so the missing points don't look like an omission.
  > **Team check:** the brief says "one point per configuration". Confirm with Part 4 / Part 5 that
  > leaving out unspeed-tested models is the right reading. The alternative is to list their accuracy in a
  > side note without a latency.

## Short interpretation (2–3 lines, under the chart)

1. Where the cascade sits against `qwen2.5:7b` alone: faster, slower, or not distinguishable (per-run p50
   ranges overlap)?
2. Whether each setting is above the limit line.
3. The trade-off in one sentence: Setting B escalates less (expected faster) but accepts more of granite's
   answers (expected less accurate). Did the measurement bear that out?

If the cascade is not faster, point to the break-even on Slide 7:
`L(small) + f × L(large) < L(large)`.

## Producing the chart

Plot from the CSVs, not by hand, so each coordinate traces to a file. One option is a short script next to
this file (`slide6_tradeoff_chart.py`, not written yet) that reads `pass_fail_a2.csv` and the cascade
accuracy file for y, and `speed_a2/per_config.csv` for x. It writes `slide6_tradeoff.png` / `.svg`, the same
way `cascade_diagram.py` produces Slide 2's diagram.

## Traceability rows to add to `../outline_a2.md` (Part 5's map)

| Slide | Figure | Source file | Produced by |
|---|---|---|---|
| 6 | y: overall accuracy per configuration | `analysis/output/accuracy_a2/pass_fail_a2.csv` + `cascade_pass_fail_a2.csv` | `python -m analysis.accuracy_a2`; `python -m analysis.cascade_accuracy_a2` |
| 6 | x: p50 mean and per-run range | `analysis/output/speed_a2/per_config.csv` | `python analysis/summarise_load_a2.py` |
| 6 | overall limit line | `docs/a2/accuracy_limits.md` §1 | Part 2 |
| 6 | the chart | `slides/drafts_a2/slide6_tradeoff.png` | `<chart script>` |
