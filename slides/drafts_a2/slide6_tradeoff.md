# Slide 6 — Trade-off (draft)

**Brief (verbatim):** "One chart: accuracy vs latency, one point per configuration and setting, overall limit
drawn as a line. Short interpretation."
**Owner:** Jolie Ngai Ning Li (Part 3). Part 5 owns layout and assembly.
**Done when** (`../outline_a2.md`): every plotted point's two coordinates each trace to a number already
shown on Slides 4 and 5.

The chart introduces no new numbers. Accuracy comes from Slide 4 (`analysis/output/accuracy_a2/`) and
latency from Slide 5 (`analysis/output/speed_a2/per_config.csv`). No Assignment 1 speed figure is used
(TODO_A2.md, guardrail 10).

**Status:** structure only. Waiting for the cascade accuracy runs (Slide 4) and every speed run (Slide 5).

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
| `qwen2.5:7b` alone (reference) | 75/101 (74.26%) | `<p50_mean_ms>` | Yes | filled |
| Cascade, Setting A | `<n>/101` | `<p50_mean_ms>` | `<>` | filled if passes, hollow if not |
| Cascade, Setting B | `<n>/101` | `<p50_mean_ms>` | `<>` | filled if passes, hollow if not |
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
| 6 | y: overall accuracy per configuration | `analysis/output/accuracy_a2/pass_fail_a2.csv` + `<cascade file>` | `python -m analysis.accuracy_a2` |
| 6 | x: p50 mean and per-run range | `analysis/output/speed_a2/per_config.csv` | `python analysis/summarise_load_a2.py` |
| 6 | overall limit line | `docs/a2/accuracy_limits.md` §1 | Part 2 |
| 6 | the chart | `slides/drafts_a2/slide6_tradeoff.png` | `<chart script>` |
