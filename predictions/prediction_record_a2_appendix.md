# Prediction record A2 — dated appendix (2026-11-26)

**What this is.** A finding made **after** the `a2-predictions-freeze` tag, written down where it can be seen
next to the record. It is **not** part of the frozen record: `prediction_record_a2.md` is unchanged since the
tag (`python ../scripts/a2_gate.py` checks this, and passes). Nothing in the record's §1–§4 is changed by this
page. It explains how the frozen §4 no-queue check behaved on the real runs, and what extra, clearly labelled
analysis was added because of it.

**Who.** Drafted by the AI coding tool at Yeo Kai Yuan's instruction on 2026-11-26, from the run outputs named
below. Yeo Kai Yuan decided the handling in §A.3 when the issue appeared mid-campaign. **The whole team should
review this page** (W.2 recommendation meeting), because it touches how the recommendation is read.

---

## A.1 What §4 says, and what happened

The frozen §4 calls a speed run **queued** (reported, but not compared on p50, and its configuration not
eligible for the recommendation) if **either**:

1. its second-half p50 is more than 20% above its first-half p50 (the *halves test*), **or**
2. its median `ollama_other_ms` (queue wait inside Ollama) is 100 ms or more (the *queue-wait test*).

All runs used the brief's own procedure: S = 3.339 s, so 8.98 tickets/min with JMeter random arrivals, 300 s
of arrivals, the same 100-ticket list in the same order, three runs per configuration
(`../docs/a2/arrival-rate.md`, `../docs/a2/run-log.md`). Results (`../analysis/output/speed_a2/per_run.csv`):

| Run | p50 (ms) | Halves change | Median queue wait (ms) | Ollama busy fraction | §4 verdict (frozen) |
|---|---|---|---|---|---|
| `qwen2.5:7b` run 1 | 6121 | +12.9% | 1773 | 0.54 | queued (queue wait) |
| `qwen2.5:7b` run 2 | 6535 | +187.0% | 2305 | 0.52 | queued (both) |
| `qwen2.5:7b` run 3 | 4505 | +19.1% | 11 | 0.52 | pass |
| cascade A run 1 | 9611 | −56.7% | 934 | 0.92 | queued (queue wait) |
| cascade A run 2 | 7629 | −41.1% | 49 | 0.94 | pass |
| cascade A run 3 | 9250 | −3.9% | 2241 | 1.02 | queued (queue wait) |
| cascade B run 1 | 5501 | +212.3% | 28 | 0.75 | queued (halves) |
| cascade B run 2 | 5569 | +7.8% | 29 | 0.85 | pass |
| cascade B run 3 | 5029 | +87.7% | 35 | 0.83 | queued (halves) |

So the reference model alone fails the frozen check in two of its three runs, and every configuration ends
with exactly one run that passes it. Every run had 44 sent, 44 completed, 0 errored and 0 unfinished, no
mid-run model load, and reconciles with `analysis/reconcile.py`.

## A.2 Why: the threshold assumed less waiting than the brief's rate produces

The brief sets the rate so the top model is "idle about half the time, so no queue builds". The busy fraction
above confirms it: `qwen2.5:7b` computed for 52–54% of each run. But the arrivals are **random**, not evenly
spaced. A ticket that arrives while another is still being served waits for it, and at about 50% utilisation
roughly half the tickets do. The median queue wait therefore sits right at the boundary between "no wait" and
"a few seconds", and which side it lands on depends on the run's random arrival pattern: 11 ms in qwen run 3,
2305 ms in run 2, with the same tickets and the same model. The 100 ms line was carried over from Assignment
1's queueing threshold (`prediction_record_a2.md` §4, "Why" column); nobody checked it against the waiting
that random arrivals produce at about 50% utilisation.

The brief's actual concern is different: a queue that **keeps growing through the run**, so that "the p50 you
measure then depends on how long you ran". That is what the halves test measures. The waits behind a
momentary burst are part of every configuration's latency at this rate, and every configuration faced the same
rate and the same tickets.

The cascades' busy fractions (0.92–1.02 for Setting A) are a real result, not an artefact: at this rate the
cascade keeps the CPU almost permanently busy, because `granite4:3b`'s call (median about 1.9 s of compute on
the tickets it answered alone) is added to `qwen2.5:7b`'s on three quarters of the tickets. A value above 1.0
is possible because the two models run in separate Ollama runners that can compute at the same time.

**Why the queued runs were not re-run.** The playbook (§6) allows a re-run when the no-queue check fails. Here
the flag comes from chance in the random arrival pattern, not from a fault, so re-running until a run passes
would select favourable arrival patterns: "the best three of six", which §6 forbids in spirit. Every run is
kept and reported.

## A.3 How the results are reported (decided 2026-11-26)

- **Primary result: the frozen rule, applied as written.** `../analysis/output/speed_a2/` (`python
  analysis/summarise_load_a2.py`). Runs flagged queued are listed with their p50 but not compared on it.
- **Secondary analysis, labelled as such everywhere it appears.** `../analysis/output/speed_a2_secondary/`
  (`python analysis/summarise_load_a2.py --secondary-no-queue-wait --out-dir analysis/output/speed_a2_secondary`):
  the same runs with the halves test only. Each run's queue wait is still reported. Its report is headed
  "SECONDARY ANALYSIS, NOT THE FROZEN RULE".
- Slides 5 to 7 show the primary result and say plainly what the frozen rule implies. Where the secondary
  analysis is shown, it is labelled, and this page is cited.
- The thresholds in the record are **not** changed after seeing the data. This page is the only place the
  issue is discussed.

## A.4 What it changes

**It does not change what §4's rule selects.** Both readings point the same way (the recommendation itself is the team's to confirm at the W.2 meeting):

| | `qwen2.5:7b` alone | Cascade A | Cascade B |
|---|---|---|---|
| Per-run p50 (ms), all runs | 6121 / 6535 / 4505 | 9611 / 7629 / 9250 | 5501 / 5569 / 5029 |
| **Primary** (frozen §4): runs counted → p50 | run 3 → 4505 | run 2 → 7629, "slower" | run 2 → 5569, "slower" |
| **Secondary** (halves test only): runs counted → p50 range | runs 1, 3 → 4505–6121 | all three → 7629–9611, "slower" | run 2 → 5569, "not distinguishable" |

(`analysis/output/speed_a2/per_config.csv` and `analysis/output/speed_a2_secondary/per_config.csv`,
`faster_than_reference`.)

- Under the frozen rule, **no configuration has three valid runs**, so strictly none is eligible. §4's last
  clause then applies: "A configuration must be distinguishably faster than `qwen2.5:7b` alone, or the
  recommendation is `qwen2.5:7b`." Neither cascade setting is distinguishably faster on any reading, so the
  recommendation is `qwen2.5:7b` alone.
- In the secondary reading cascade A is slower outright. Cascade B's per-run p50s (5.0–5.6 s) sit inside
  `qwen2.5:7b`'s spread (4.5–6.5 s) on every reading: not distinguishable, so §4's tie-break (higher accuracy,
  then the simpler configuration) also picks `qwen2.5:7b` alone (75/101 vs 74/101, one model vs two).
- What the flag does change is **how firmly the latency numbers can be stated**. With one counted run per
  configuration under the frozen rule there is no spread to report, and the slides must say so rather than
  present a single run as a three-run result.
