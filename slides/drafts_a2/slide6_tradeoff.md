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

**Part 3 update, 2026-11-26:** title, interpretation and chart added. Chart:
[`slide6_tradeoff.svg`](slide6_tradeoff.svg), produced by `python slides/drafts_a2/slide6_tradeoff_chart.py`.
Plotted values: `slide6_tradeoff_points.csv`.

---

## Title

All three pass accuracy, but neither cascade setting is faster than `qwen2.5:7b` alone

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

**The chart uses the frozen rule.** Each filled point is the p50 of the configuration's one counted run
(`speed_a2/per_config.csv` → `p50_mean_ms`). There is no error bar, because one counted run gives no range.
The runs flagged queued appear as faint hollow circles at their own p50 and are labelled "not counted", so
the spread is visible without being used for the comparison. This matches Slide 5's primary table and
Slide 7's rule.
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

1. **The cascade is slower, not faster.** Under the frozen rule, `qwen2.5:7b` alone has a median of 4.50 s.
   Setting A's is 7.63 s (+3.12 s) and Setting B's is 5.57 s (+1.06 s), so both are marked "slower"
   (`faster_than_reference`). Including the queued runs doesn't change this: every Setting A run
   (7.63–9.61 s) is slower than every `qwen2.5:7b` run (4.50–6.54 s). Setting B's runs (5.03–5.57 s) fall
   inside `qwen2.5:7b`'s range, so at best B is no faster.
2. **All three points are above the limit line, within two tickets of each other**: A 76/101, `qwen2.5:7b`
   75/101, B 74/101. Accuracy does not separate them; latency does.
3. **Why the cascade loses on speed.** An escalated ticket pays for two model calls. Under load, escalated
   tickets had a median of 9.23 s (A) and 9.01 s (B), against 2.29 s and 3.35 s for accepted tickets. The
   cascade escalated 75% (A) and 52% (B) of the speed-test tickets. B escalates less, so it is 2.06 s
   faster than A. It costs only two tickets of accuracy, but Consumer loan sits exactly at its limit
   (6/14), so one more wrong answer there would fail B. The break-even `L(small) + f × L(large) < L(large)`
   is worked on Slide 7.

Under the chart, one line: *"granite4:3b, llama3.2:3b and llama3.2:1b failed accuracy on Slide 4, so they
were not speed-tested and have no point."*

## Producing the chart

`python slides/drafts_a2/slide6_tradeoff_chart.py` (standard library only, no matplotlib) reads
`analysis/output/accuracy_a2/pass_fail_a2.csv` and `cascade_pass_fail_a2.csv` for y, and
`analysis/output/speed_a2/per_config.csv` for x. It works out the limit line from `qwen2.5:7b`'s row
(75/101 − 10 pp), so no number is typed in by hand. It writes:

- `slide6_tradeoff.svg`: the chart, 960×540 (16:9). PowerPoint inserts SVG directly.
- `slide6_tradeoff_points.csv`: every plotted value, as the table view and for traceability.

A configuration that fails accuracy is drawn automatically as a hollow marker labelled "fails accuracy".
None does at present. Colours are the reference palette's first three categorical slots, checked as a set
for colour-blind separation. Every point also has a direct text label, so identity never depends on colour
alone.

## Traceability rows to add to `../outline_a2.md` (Part 5's map)

| Slide | Figure | Source file | Produced by |
|---|---|---|---|
| 6 | y: overall accuracy per configuration | `analysis/output/accuracy_a2/pass_fail_a2.csv` + `cascade_pass_fail_a2.csv` | `python -m analysis.accuracy_a2`; `python -m analysis.cascade_accuracy_a2` |
| 6 | x: p50 mean and per-run range | `analysis/output/speed_a2/per_config.csv` | `python analysis/summarise_load_a2.py` |
| 6 | overall limit line | `docs/a2/accuracy_limits.md` §1 | Part 2 |
| 6 | the chart and its plotted values | `slides/drafts_a2/slide6_tradeoff.svg`, `slide6_tradeoff_points.csv` | `python slides/drafts_a2/slide6_tradeoff_chart.py` |
