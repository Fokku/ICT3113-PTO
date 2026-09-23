# Workload model — the client's complaints desk

**What this document is for.** Step 3 of the brief: a quantitative model of the workload the
client's ticket triage service must carry. Every performance requirement in `requirements.md` is
justified from a figure in here, and every arrival rate we test at is derived from it.

**Owner: Part 4 — Teammate C.**
`TODO(Yeo Kai Yuan): replace "Teammate C" with the real name once the team roles are confirmed.`

**Which slide this feeds.** **Slide 3 — Workload Model** (ticket volumes, search rates, peak
versus non-peak, ticket length distribution, with the source of every figure and a clear statement
of which figures are estimates). The sources listed at the bottom also go to **Slide 12**.

**What "done" looks like.**

* Every figure table below is complete: no `TODO` markers remain.
* Every figure has either a citation (with a URL and the date accessed) **or** `Estimate? = Y` and
  a stated estimation method that a marker could follow and reproduce.
* Units are explicit and consistent. If a published figure is per year and you need it per hour,
  show the conversion in the estimation method, do not just write the converted number.
* The *Derived arrival rates for testing* section ends with a list that Part 1 can run
  `scripts/run_load_test.sh` against, unchanged.
* Nothing in here is contradicted by `requirements.md`.

**How to fill in a figure table.** These are the exact columns; do not add, remove or reorder
them. Here is the shape, with an example row that is entirely a placeholder — replace it, do not
build on it:

| Figure | Value | Unit | Source (citation or URL) | Estimate? (Y/N) | Estimation method |
|---|---|---|---|---|---|
| TODO | TODO | TODO | TODO | TODO | TODO |

Rules for the columns:

* **Value** — a number, not a range, unless the range is the finding; then give the range and say
  which end the requirements use.
* **Unit** — always stated, always in full (`tickets per working day`, not `per day`).
* **Source** — a citation a marker can follow. A publisher, a title, a year, a URL and the date
  you accessed it. If the figure is ours, write `derived — see estimation method`.
* **Estimate? (Y/N)** — `N` only when the figure is read directly from a published source or
  measured from our own data. Anything we computed, scaled or judged is `Y`.
* **Estimation method** — what you did, in enough detail to be repeated: the input figure, the
  arithmetic, and the assumption that made the arithmetic legitimate.

---

## Scope and assumptions

Describe the client this model is about, and the boundaries of the model, before any figure
appears. A figure without a stated scope cannot be checked.

`TODO(Part 4 — Teammate C): state the scope of the modelled business.` The brief tells us the
client is "a financial services company whose customer relations desk receives a steady stream of
complaint tickets", and nothing more. That leaves the size of the firm open, and the size of the
firm drives every volume figure in this document. Write down, explicitly:

* What size and kind of firm we are modelling, and why that choice is reasonable for the brief.
* Which products the complaints cover (our seven categories span retail banking, cards, mortgages,
  loans, credit reporting, debt collection and money transfer — is the modelled firm in all of
  them?).
* Which channels tickets arrive through, and whether the model covers all of them or only the
  digital intake that would call `POST /tickets`.
* The working pattern assumed: days per week, hours per day, and whether the intake is open
  outside those hours.
* Whether agents triage tickets in a batch at the start of a shift or continuously through it,
  because that changes the peak, not the volume.

`TODO(Part 4 — Teammate C): list the assumptions this model rests on, as a numbered list.` Each
one should be phrased so that a reader can see what would change if it were wrong. Assumptions
that are known to be shaky are worth more marks stated than hidden — the brief asks for
completeness and plausibility, not certainty.

**A question you will have to answer explicitly.** Published complaint statistics are usually
published by a *regulator* and cover a whole national market, or a whole industry, across many
firms. Our client is one firm. If you use such a figure, you must scale it down, and the scaling
assumption is then the weakest link in the model. So:

* What are you scaling by — market share, number of customers, number of accounts, share of
  branches, headcount? Which of those can you actually find a published figure for?
* Does the regulator's figure count *complaints escalated to the regulator* or *complaints
  received by firms*? Those differ by a large factor, and the two are not interchangeable.
* Is the figure for a comparable market? Our dataset is a US federal database; if your volume
  source is from another jurisdiction, say why that is still a reasonable basis.
* State the scaling assumption in the *Estimation method* column of every figure it touches, not
  once in prose. Slide 3 must show which figures inherit it.

---

## Ticket volume

How many tickets the client receives in a relevant period. This is the figure the whole model
turns on: the arrival rates we test at are derived from it.

`TODO(Part 4 — Teammate C): fill in the volume figures and cite each one.` As a minimum, the model
needs a base period volume (whatever period your source publishes) and the same volume converted
to tickets per hour of opening, because that is the unit an arrival rate is derived from.

| Figure | Value | Unit | Source (citation or URL) | Estimate? (Y/N) | Estimation method |
|---|---|---|---|---|---|
| Complaint volume, published base figure | TODO | TODO | TODO | TODO | TODO |
| Share of that volume attributable to the modelled firm | TODO | TODO | TODO | TODO | TODO |
| Tickets received per year by the modelled firm | TODO | TODO | TODO | TODO | TODO |
| Tickets received per working day (average) | TODO | TODO | TODO | TODO | TODO |
| Tickets received per hour of opening (average) | TODO | TODO | TODO | TODO | TODO |
| Share arriving through the digital intake that calls `POST /tickets` | TODO | TODO | TODO | TODO | TODO |

Things to get right here:

* Say whether the volume is *complaints* or *contacts*. Most published figures count formal
  complaints; a triage desk usually sees more traffic than that.
* Keep the conversion visible: annual to daily needs a working-days-per-year assumption, and daily
  to hourly needs an opening-hours assumption. Both belong in the *Estimation method* column.
* If growth or seasonality is in the source, say which year you took and why.

---

## Agent search rate

How often agents search stored tickets — the traffic that hits `GET /search`. This is what the
mixed-load plan (`jmeter/mixed_load.jmx`) exercises alongside `POST /tickets`, and it is the
second rate that plan needs.

`TODO(Part 4 — Teammate C): fill in the search-rate figures.` There is unlikely to be a published
figure for this, so it will probably be an estimate. That is expected and acceptable — the brief
says so — provided the estimation method is stated.

| Figure | Value | Unit | Source (citation or URL) | Estimate? (Y/N) | Estimation method |
|---|---|---|---|---|---|
| Agents handling triage at one time | TODO | TODO | TODO | TODO | TODO |
| Searches per agent per hour | TODO | TODO | TODO | TODO | TODO |
| Searches per hour, whole desk | TODO | TODO | TODO | TODO | TODO |
| Search-to-ticket ratio | TODO | TODO | TODO | TODO | TODO |

Things to get right here:

* Build the figure from something countable — agents on shift multiplied by searches per agent per
  hour is an estimation method; "roughly a few hundred an hour" is not.
* Say whether searches follow the ticket peak or lag it. Agents searching about yesterday's
  tickets produce a flatter profile than the intake does, and the mixed-load plan runs both rates
  at once.
* The search-to-ticket ratio is the number `scripts/run_load_test.sh --search-rate` is set from.
  Give it explicitly even if you derive it from the two rows above it.

---

## Peak versus non-peak

Whether the client's traffic has peaks, how large they are, and how long they last. The brief is
explicit: **if the model implies peak periods, the requirements must cater for the peak.** A model
with no peak is a claim, not an omission — if you conclude the traffic is flat, say so and say why.

`TODO(Part 4 — Teammate C): establish whether peaks exist, and quantify them.`

| Figure | Value | Unit | Source (citation or URL) | Estimate? (Y/N) | Estimation method |
|---|---|---|---|---|---|
| Peak period(s) — when they occur | TODO | TODO | TODO | TODO | TODO |
| Peak duration | TODO | TODO | TODO | TODO | TODO |
| Peak factor (peak rate ÷ average rate) | TODO | TODO | TODO | TODO | TODO |
| Peak ticket arrival rate | TODO | TODO | TODO | TODO | TODO |
| Peak search rate | TODO | TODO | TODO | TODO | TODO |
| Non-peak (baseline) ticket arrival rate | TODO | TODO | TODO | TODO | TODO |

Things to get right here:

* Distinguish the *within-day* peak (a morning rush) from the *within-year* peak (a product
  failure, a regulatory deadline, a billing cycle). They imply different requirements: one is a
  daily capacity question, the other a headroom question.
* A peak factor derived from a published hourly profile is far stronger than one asserted. If you
  cannot find a profile for complaints, say which analogous profile you used (contact-centre call
  arrival profiles are published) and treat the substitution as the assumption it is.
* Whatever peak rate you land on, it must reappear in the arrival-rate list below, because a
  requirement that must hold at peak has to be measured at peak.

---

## Ticket length distribution

The expected distribution of ticket lengths. Slide 3 asks for it, and it matters for performance:
prompt length drives model latency on CPU, and a ticket that overflows `NUM_CTX` is silently
truncated before the model ever sees the end of it.

**This is the one figure in this document that is measured, not estimated.** We hold the exact
narratives the load generator will post — `data/team_rows.csv` — so the distribution of our own
traffic is a fact, and it is recorded with `Estimate? = N`. Produce it with:

```bash
.venv/bin/python workload/scripts/ticket_length_stats.py --out-dir workload/output
```

That script (`scripts/ticket_length_stats.py` in this folder) reports characters, words and
approximate tokens at the percentiles min, p5, p25, p50, p75, p90, p95, p99 and max, plus the
mean, the standard deviation, a histogram, an empirical CDF, and the number of rows that would
exceed `NUM_CTX` once the prompt is added. Read `workload/output/ticket_length_stats.md` before
filling the table in.

Two things about it you must repeat on the slide:

* **Token counts from that script are an approximation** (characters divided by four, rounded up).
  The true count is tokeniser-specific and therefore differs per candidate model. The
  authoritative per-request figure is `prompt_eval_count` in the service log, which exists once
  benchmarking begins — see `../service/log_schema.py`.
* **Measured is not the same as representative.** Our rows are consumer complaints filed through a
  US regulator's web form. That is the measurement; whether the client's intake looks like it is a
  judgement.

`TODO(Part 4 — Teammate C): run the script and transfer its figures into this table.` Copy the
values from `workload/output/length_distribution.csv`; do not retype them from the chart.

| Figure | Value | Unit | Source (citation or URL) | Estimate? (Y/N) | Estimation method |
|---|---|---|---|---|---|
| Ticket length, median (p50) | TODO | TODO | TODO | TODO | TODO |
| Ticket length, p95 | TODO | TODO | TODO | TODO | TODO |
| Ticket length, p99 | TODO | TODO | TODO | TODO | TODO |
| Ticket length, maximum | TODO | TODO | TODO | TODO | TODO |
| Ticket length, mean and standard deviation | TODO | TODO | TODO | TODO | TODO |
| Approximate prompt tokens, p99 | TODO | TODO | TODO | TODO | TODO |
| Rows at risk of truncation at the configured `NUM_CTX` | TODO | TODO | TODO | TODO | TODO |

For the measured rows, the source is `data/team_rows.csv` via
`workload/scripts/ticket_length_stats.py`, `Estimate?` is `N`, and the estimation method column
says `measured, not estimated` — except for the token rows, where it must state the approximation
rule, because those *are* derived.

`TODO(Part 4 — Teammate C): answer this question in prose, in this section.` **Would the client's
real traffic resemble this distribution?** Consider:

* These narratives were typed into a regulator's complaint form, after the consumer had already
  failed to resolve the matter with the firm. A complaint arriving at the firm's own desk may be
  shorter, angrier, or arrive with structured form fields attached.
* The extract is redacted at source (names, numbers and dates replaced by runs of `X`), which
  changes length slightly and changes the token mix more than it changes the character count.
* Our rows are a thousand consecutive rows of a course extract, not a random sample of the
  database. Say so.
* If you conclude the client's tickets would be longer, that is a latency risk and Part 1 should
  hear about it, because it affects both `NUM_CTX` and the expected per-request latency.

---

## Derived arrival rates for testing

**This section is the hand-off to Part 1. It is what unblocks the benchmark campaign.**

Everything above is a model of the client. This section turns it into the concrete arrival rates
`scripts/run_load_test.sh` will be driven at. Until this list exists and is final, Part 1 cannot
start benchmarking, because there is nothing to benchmark *at*, and the measurement campaign is
the longest job left in the assignment.

`TODO(Part 4 — Teammate C): produce the list of arrival rates, in requests per minute.` The rules:

1. **Requests per minute.** JMeter's Open Model Thread Group is configured in requests per minute
   (`rate(<n>/min)`), so the list must be in that unit. Convert from whatever unit your volume
   figures are in and show the conversion.
2. **At least one rate at or above the modelled peak.** A requirement that must hold at peak can
   only be tested at peak. If the peak rate turns out to be lower than the average rate, something
   is wrong above.
3. **At least one rate below it**, so the shape of the latency curve is visible rather than a
   single point. Two points cannot show where a system turns over.
4. **Every rate traceable to a figure above.** Each row states which one.
5. **Keep the list short.** Each rate is run three times, for every candidate model, and each run
   takes its full duration plus model-load time. Rates × models × three runs × duration is the
   whole campaign, and it is measured in hours of CPU time on machines we share.

| Rate label | Arrival rate (requests per minute) | Which workload figure it comes from | At or above the modelled peak? (Y/N) | Plan | Duration (seconds) | Runs |
|---|---|---|---|---|---|---|
| TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | TODO | TODO | TODO | TODO | TODO | TODO |

Also settle these, because the run script needs them and it will not guess:

* `TODO(Part 4 — Teammate C): the search rate, in requests per minute, for the mixed-load plan`
  (`scripts/run_load_test.sh --search-rate`). Derived from the search-to-ticket ratio above.
* `TODO(Part 4 — Teammate C): the duration of each run, in seconds`, long enough that the
  measured window contains enough samples for a meaningful p99 at the *lowest* rate on the list.
  At a low arrival rate a short run yields very few samples, and a p99 computed from a handful of
  samples is noise. State how many samples you expect at the lowest rate.
* `TODO(Part 4 — Teammate C): the starting rate, step size and number of steps for the stress
  ramp` (`stress_ramp.jmx`), which should start below your lowest load rate and climb past the
  peak until the system breaks. The point of the stress test is to find a limit, so the top of the
  ramp must be beyond anything the load tests cover.

**Hand-off checklist — do all four:**

1. Fill in the table above and the three settings under it.
2. Commit this file.
3. Tell Part 1 — Yeo Kai Yuan, in writing, that the list is final, and name the commit.
   `TODO(Yeo Kai Yuan): replace with the real name.`
4. Confirm with Part 1 that the resulting campaign fits in the time between the freeze and the
   submission deadline. If it does not, cut a rate — not a run: the brief requires three runs per
   configuration and results from fewer will not be accepted.

The command each row of that table turns into, for reference:

```bash
scripts/run_load_test.sh --plan load_post_tickets --model <ollama-tag> \
    --rate <requests per minute> --duration <seconds> --runs 3
```

---

## Sources

Every source cited above, formatted properly, ready to be copied onto **Slide 12**. Include the
publisher, the title, the year, the URL and the date accessed.

`TODO(Part 4 — Teammate C): list every source used above.` Keep the numbering stable, because the
figure tables refer to these entries.

1. US Consumer Financial Protection Bureau, *Consumer Complaint Database*.
   https://www.consumerfinance.gov/data-research/consumer-complaints/ —
   `TODO(Part 4 — Teammate C): add the date accessed.` (The source of the course extract our team
   rows are drawn from; the brief requires it to be acknowledged, so it stays in this list
   regardless of which other sources you use.)
2. `TODO(Part 4 — Teammate C): complaint volume source.`
3. `TODO(Part 4 — Teammate C): peak profile source, or the analogous profile you substituted.`
4. `TODO(Part 4 — Teammate C): any source used for the search rate, or "none — estimated, see
   above".`

**Sources we could not find.** `TODO(Part 4 — Teammate C): list the figures you looked for and
could not find a published source for.` This is worth writing down rather than leaving silent: the
brief accepts estimates where no figure is available, and a short note saying what you searched
for and what did not exist is evidence that the estimate was a last resort rather than a first one.
