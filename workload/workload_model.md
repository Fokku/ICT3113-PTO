# Workload model — the client's complaints desk

**What this document is for.** Step 3 of the brief: a quantitative model of the workload the
client's ticket triage service must carry. Every performance requirement in `requirements.md` is
justified from a figure in here, and every arrival rate we test at is derived from it.

**Owner: Part 4 — Si Pei.**

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

We model a **mid-sized diversified financial-services company** whose customer-relations desk receives complaint tickets through a digital intake service. This is a reasonable interpretation of the brief because the client is described only as a financial-services company with a steady stream of complaint tickets; no specific company size or market share is provided.

The model covers complaints relating to the seven product categories represented in the team's dataset: **retail banking, cards, mortgages, loans, credit reporting, debt collection, and money transfer**. The workload model focuses on the digital ticket-intake path represented by `POST /tickets`; other channels such as telephone, postal mail or branch visits are outside the benchmark workload unless they subsequently generate a digital ticket.

The assumed operating pattern is **5 working days per week and 8 opening hours per day**, with the digital complaint intake treated as available during those opening hours. Annual-to-daily and daily-to-hourly conversions therefore use **260 working days per year (52 weeks × 5 days)** and **8 opening hours per working day**.

Agents are assumed to **triage tickets continuously as they arrive**, rather than processing one large batch at the start of a shift. This means the workload model treats ticket arrivals as a continuous stream and allows within-day peak periods to affect the required processing capacity.

### Assumptions

1. **Firm size:** The client is modelled as a mid-sized diversified financial-services company. Because no client-specific customer or complaint volume is supplied, external published complaint statistics must be scaled to represent one firm.

2. **Product coverage:** The modelled firm is assumed to handle complaints across all seven categories represented in the dataset: retail banking, cards, mortgages, loans, credit reporting, debt collection, and money transfer.

3. **Channel coverage:** The benchmark represents complaints entering through the digital intake service that calls `POST /tickets`. Non-digital channels are excluded unless they are subsequently converted into a digital ticket.

4. **Operating hours:** The desk operates 5 days per week for 8 hours per day, giving 260 working days and 2,080 opening hours per year.

5. **Triage behaviour:** Agents triage continuously during opening hours rather than in a single batch at the beginning of a shift.

6. **Complaint-volume scaling:** The CFPB published complaint total is a regulator-wide figure and therefore cannot be treated as the workload of one firm directly. It will be scaled to the modelled firm using an explicitly stated firm-share assumption in the Ticket Volume section. Every derived figure that uses this scaling will identify the assumption in its estimation method.

7. **Complaint versus contact volume:** The published CFPB figure represents formal consumer complaints, not every customer contact received by firms. Therefore, the model treats the scaled complaint volume as the benchmark ticket volume rather than claiming it represents all customer-relations contacts.

8. **Geographic comparability:** The workload model uses the US CFPB complaint data because the team's measured ticket narratives are also drawn from the US CFPB Consumer Complaint Database. This provides a closer source match than using complaint statistics from another jurisdiction.

9. **Traffic profile:** Where a published hourly complaint-arrival profile is unavailable, an analogous financial-services/contact-centre arrival profile may be used. Any such substitution will be explicitly marked as an estimate and its effect on the peak rate will be stated.

10. **Ticket-length representativeness:** The measured ticket-length distribution from `data/team_rows.csv` is used as the benchmark input distribution. It is not assumed to be a statistically representative sample of the client's actual production tickets; this is a workload-modelling assumption that should be validated if client-specific data become available.

### Complaint-volume scaling basis

The published complaint figure is regulator-wide rather than specific to the modelled firm, so it must be scaled before it is used as the firm's workload.

**Scaling basis:** The model uses an **equal-share approximation**: the CFPB total is divided by the 4,000+ companies the CFPB reports sending complaints to (1 firm ÷ 4,000 = 0.025%). A customer-share basis would be preferable, but no published market-wide customer denominator was found that would make it reproducible for a hypothetical client. Equal share is therefore a deliberately simple, reproducible baseline, not a claim that companies receive equal numbers of complaints. Every figure derived from it is marked `Estimate? = Y`.

**What the regulator figure represents:** The CFPB Consumer Complaint Database records consumer complaints submitted to the CFPB. The CFPB explains that complaints are generally sent to companies for response and that the database is updated regularly. Therefore, the regulator-wide published total is treated as **complaints received by the CFPB and eligible for processing/publication**, not as the total number of complaints received directly by all financial-services firms. The model does not equate the CFPB total with total customer contacts received by firms.

**Market comparability:** The complaint-volume source and the measured ticket dataset are both based on the **US CFPB Consumer Complaint Database**. This makes the source market directly comparable to the dataset used for ticket narratives. The model therefore does not need to transfer a complaint rate from another country's financial-services market.

**Scaling limitation:** The equal-share scaling is an estimate rather than a measured value for the client. It is therefore marked `Estimate? = Y` wherever it is used. The resulting firm-level ticket volume should be interpreted as a workload-model assumption rather than an observed production volume. If the client's actual customer base or complaint volume becomes available, the scaled figure should be replaced. The equal-share figure is likely to overstate the volume for a typical firm: the CFPB's 2025 report shows that about 5.1 million of the 6.6 million complaints received (roughly 77%) concerned just three nationwide consumer reporting agencies (Source 2, Sections 2 and 4.1). The 1,496 tickets/year baseline should therefore be read as a deliberately generous benchmark load, not a typical firm's volume.

---

## Ticket volume

The 2025 CFPB Consumer Response Annual Report states that the CFPB received approximately 6,635,400 consumer complaints during 2025 and sent approximately **5,984,100 complaints (90%) to companies for review and response**. The report states that these complaints were sent to **more than 4,000 companies**.

The CFPB advises that company-level complaint volume should be considered in the context of **company size and/or market share**, because companies with more customers may receive more complaints. No published market-wide customer denominator was identified that would allow a reproducible customer-share calculation for the hypothetical client used in this assignment.

Therefore, this workload model uses an **equal-share approximation across 4,000 companies** as a deliberately simple scaling assumption. It is **not** a claim that companies receive equal numbers of complaints, and it is not presented as an observed complaint rate for a real company. The resulting figure is therefore marked as an estimate and should be interpreted as a reproducible baseline workload for benchmarking.

The CFPB reports **more than 4,000 companies**, rather than exactly 4,000, so using 4,000 is a generous simplification that makes the calculation reproducible. Actual complaint distributions are highly uneven, particularly because company size and product mix differ.

| Figure                                      |     Value | Unit                                  | Source (citation or URL)                              | Estimate? (Y/N) | Estimation method                                                                                                                                                                                                      |
| ------------------------------------------- | --------: | ------------------------------------- | ----------------------------------------------------- | --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Complaint volume, published base figure     | 5,984,100 | complaints sent to companies per year | US CFPB, *2025 Consumer Response Annual Report*, 2026 | N               | Published 2025 figure: approximately 5,984,100 complaints were sent to companies for review and response.                                                                                                              |
| Share allocated to the modelled firm        |    0.025% | share of complaints sent to companies | derived — see estimation method                       | Y               | Equal-share baseline: 1 firm ÷ 4,000 companies = 0.00025 = 0.025%. This is a modelling assumption, not an observed company complaint share.                                                                            |
| Tickets received per year                   | 1,496 | tickets per year                      | derived — see estimation method                       | Y               | 5,984,100 × 0.025% = 1,496 tickets/year (1,496.025 rounded)                                                                                                                                |
| Tickets received per working day (average)  |     5.754 | tickets per working day               | derived — see estimation method                       | Y               | 1,496.025 ÷ 260 working days/year = 5.754 tickets/working day.                                                                                                                                                         |
| Tickets received per opening hour (average) |     0.719 | tickets per opening hour              | derived — see estimation method                       | Y               | 5.754 ÷ 8 opening hours/day = 0.719 tickets/hour.                                                                                                                                                                      |
| Share assigned to `POST /tickets` benchmark |      100% | share of modelled benchmark tickets   | derived — see estimation method                       | Y               | The benchmark covers the digital intake path represented by `POST /tickets`, so 100% of the modelled benchmark workload is assigned to this path. This does not claim that all real-world complaints arrive digitally. |


---

## Agent search rate

How often agents search stored tickets — the traffic that hits `GET /search`. This is what the
mixed-load plan (`jmeter/mixed_load.jmx`) exercises alongside `POST /tickets`, and it is the
second rate that plan needs.

| Figure | Value | Unit | Source (citation or URL) | Estimate? (Y/N) | Estimation method |
|---|---:|---|---|---|---|
| Agents handling triage at one time | 2 | agents | derived — see estimation method | Y | Small-desk workload assumption for the hypothetical mid-sized firm; two agents are assumed to triage continuously during opening hours. |
| Searches per agent per hour | 5 | searches/agent/hour | derived — see estimation method | Y | Our assumption, not a published figure. Context: CNA (Source 3) reports a UOB customer service officer handling 30–40 calls per day, "one call every 12–15 minutes" (4–5 calls/hour), up to 60 on busy days. We assume about one ticket-system search per call, so 5 searches/agent/hour is the top of that range. CNA describes call volumes at one bank and does not measure searches. |
| Searches per hour, whole desk | 10 | searches/hour | derived — see estimation method | Y | 2 agents × 5 searches/agent/hour = 10 searches/hour. |
| Agent search rate | 0.167 | searches/minute | derived — see estimation method | Y | 10 searches/hour ÷ 60 = 0.167 searches/minute. This is the modelled rate. The run script accepts whole numbers only, so the mixed-load test uses 1 search/minute (see below). |
| Search-to-ticket ratio | 13.9 | searches/ticket | derived — see estimation method | Y | 10 searches/hour ÷ 0.719 tickets/hour = 13.9 searches per modelled ticket. |

The search stream is modelled as concurrent with ticket intake during opening hours. The modelled desk rate is **0.167 searches/minute**. The run script (`scripts/run_load_test.sh --search-rate`) accepts only whole numbers of at least 1, so the **lowest runnable search rate is 1 search/minute (about 6× the modelled rate)**. The mixed-load test uses 1 search/minute as a headroom margin. Both figures are estimates: the CNA article gives call volumes per officer (30–40 calls/day), which is an operational proxy for agent activity. It does not measure searches against this service, and the 5 searches/agent/hour figure is our own assumption.

---

## Peak versus non-peak

Source 4 uses an illustrative medium-sized financial-services call-centre example that shows strong time-of-day variation in arrivals. This supports the existence of an intraday peak, but it is an analogous source, not a measurement of this client's digital complaint traffic, and it does not support any particular peak multiplier. The peak factor of 2× is an **assumption**, chosen as a simple, reproducible above-average load. It is not read from a published profile.

| Figure | Value | Unit | Source (citation or URL) | Estimate? (Y/N) | Estimation method |
|---|---:|---|---|---|---|
| Peak period(s) — when they occur | Daytime, within opening hours | n/a | Source 4 (illustrative call-centre example) | Y | Analogous profile substituted for a complaint-arrival profile, which was not found. |
| Peak duration | Not separately modelled | n/a | derived — see estimation method | Y | The 2× factor is applied as a conservative uplift; no peak length is claimed. |
| Peak factor (peak rate ÷ average rate) | 2 | ratio | derived — see estimation method | Y | Assumed, not read from a published profile. |
| Peak ticket arrival rate | 0.024 | tickets/minute | derived — see estimation method | Y | 0.01198 × 2 = 0.02396, rounded to 0.024 (about 1.4 tickets/hour). |
| Peak search rate | 0.167 | searches/minute | derived — see estimation method | Y | Kept at the baseline; the search stream is controlled independently of the ticket peak. |
| Average (baseline) ticket arrival rate | 0.012 | tickets/minute | derived — see estimation method | Y | 0.719 tickets/hour ÷ 60 = 0.01198, rounded. The average is used as the baseline; a lower off-peak rate is not modelled separately. |

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

| Figure                                                 |             Value | Unit               | Source (citation or URL)                  | Estimate? (Y/N) | Estimation method                                                                                |
| ------------------------------------------------------ | ----------------: | ------------------ | ----------------------------------------- | --------------- | ------------------------------------------------------------------------------------------------ |
| Ticket length, median (p50)                            |             743.5 | characters         | `workload/output/length_distribution.csv` | N               | Measured from 1,000 rows in `data/team_rows.csv` using `workload/scripts/ticket_length_stats.py` |
| Ticket length, p95                                     |            1799.3 | characters         | `workload/output/length_distribution.csv` | N               | Measured from 1,000 rows in `data/team_rows.csv` using `workload/scripts/ticket_length_stats.py` |
| Ticket length, p99                                     |           1967.04 | characters         | `workload/output/length_distribution.csv` | N               | Measured from 1,000 rows in `data/team_rows.csv` using `workload/scripts/ticket_length_stats.py` |
| Ticket length, maximum                                 |              1999 | characters         | `workload/output/length_distribution.csv` | N               | Measured from 1,000 rows in `data/team_rows.csv` using `workload/scripts/ticket_length_stats.py` |
| Ticket length, mean and standard deviation             | 860.955 / 473.054 | characters         | `workload/output/length_distribution.csv` | N               | Measured from 1,000 rows in `data/team_rows.csv` using `workload/scripts/ticket_length_stats.py` |
| Approximate prompt tokens, p99                         |            605 | approximate tokens | `workload/output/ticket_length_stats.md`  | Y               | Approximate prompt tokens using `ceil((characters + 449-character prompt overhead) / 4)`  (604.01 rounded up)        |
| Rows at risk of truncation at the configured `NUM_CTX` |         0 (0.00%) | rows               | `workload/output/ticket_length_stats.md`  | N               | Measured against `NUM_CTX=4096`; no rows exceeded the truncation-risk threshold                  |

Even the longest ticket (1,999 characters, about 612 approximate tokens with the 449-character prompt overhead) uses roughly 15% of the 4,096-token window, so truncation is not a risk for this data.

For the measured rows, the source is `data/team_rows.csv` via
`workload/scripts/ticket_length_stats.py`, `Estimate?` is `N`, and the estimation method column
says `measured, not estimated` — except for the token rows, where it must state the approximation
rule, because those *are* derived.

### Would the client's real traffic resemble this distribution?

The measured distribution is a useful benchmark for this assignment, but it should **not be assumed to be fully representative of the client's real complaint traffic**. The rows in `data/team_rows.csv` are consumer complaints submitted through the US CFPB's regulator web form, meaning the consumer has already reached the stage of filing a formal complaint after attempting to resolve the issue with the firm. A complaint submitted directly to the client's own customer-relations desk could therefore have a different length distribution. For example, the client's tickets may be shorter because structured form fields capture some information separately, or they may be longer if customers provide additional context.

The source data is also redacted: names, numbers and dates are replaced by runs of `X`. This changes the measured character and token counts slightly and can change the token mix, although the effect on overall character length is expected to be smaller than the difference between the CFPB complaint format and the client's actual intake format.

The 1,000 rows are a **consecutive course extract rather than a random sample of the CFPB Consumer Complaint Database**. Therefore, the measured percentiles describe the exact benchmark traffic that the team currently has available, but they should not be interpreted as population estimates for all financial-services complaints.

For performance testing, the team will therefore use this measured distribution as the **working benchmark assumption**. If client-specific evidence later shows that real tickets are materially longer, this becomes a performance risk: longer prompts can increase model inference time and could affect `NUM_CTX` usage. Part 1 should be informed of that risk because it may affect both context-window headroom and expected per-request latency.


---

## Derived arrival rates for testing

**This section is the hand-off to Part 1. It is what unblocks the benchmark campaign.**
The modelled peak is 0.024 tickets/minute. The run script accepts only whole rates of at least 1 request/minute, so every runnable rate is above the modelled peak (1/min is about 42× peak). No rate below peak can be tested, so the shape of the latency curve is shown by rates above peak: 1/min is the headroom floor, and 4 and 12/min show where latency turns over.

| Rate label | Arrival rate (requests per minute) | Which workload figure it comes from | At or above the modelled peak? (Y/N) | Plan | Duration (seconds) | Runs |
|---|---|---|---|---|---|---|
| Floor | 1 | Lowest runnable rate; 1 ÷ 0.02396 ≈ 42× modelled peak | Y | `load_post_tickets` | 600 | 3 |
| Mid | 4 | About 4× the floor, to show the curve | Y | `load_post_tickets` | 600 | 3 |
| High | 12 | Capacity test; 12 req/min = 720 tickets/hour (R2) | Y | `load_post_tickets` | 600 | 3 |

Also settled, because the run script needs them and it will not guess:

* **Mixed-load search rate:** 1 search/minute (lowest runnable; the modelled rate is 0.167/min). Run with `--plan mixed_load --rate 1 --search-rate 1 --duration 600`.
* **Run duration:** 600 s. Expected samples per run: about 10 per run at 1/min (30 across three runs; each run's p95 rests on about 10 samples), 40 at 4/min and 120 at 12/min. At 1/min p95 is indicative and p99 is not meaningful, so p99 is reported only at 4 and 12/min. Arrivals are Poisson (`random_arrivals` in the JMeter plan), so actual counts vary around these expectations: standard deviation about 3 at 1/min, 6 at 4/min and 11 at 12/min.
* **Stress ramp:** start 1/min, step +4/min, 6 steps of 120 s (1, 5, 9, 13, 17, 21/min; 720 s of arrivals), then a 120 s drain with no new arrivals, so each run lasts 840 s. The top is above the highest load rate. Steps are additive (start + k × step) as written in jmeter/stress_ramp.jmx. Command: RAMP_STEP_PER_MIN=4 RAMP_STEPS=6 RAMP_STEP_DURATION_S=120 scripts/run_load_test.sh --plan stress_ramp --model <ollama-tag> --rate 1 --duration 840. --duration is recorded in the run metadata but does not control the ramp. Analysis: python analysis/stress_summary.py --run-dir <run-dir> --step-seconds 120 --offered-rates 1,5,9,13,17,21 --p95-limit-ms 10000 --error-rate-limit 0.05.

**Hand-off checklist — do all four:**

1. Fill in the table above and the three settings under it.
2. Commit this file.
3. Tell Part 1 — Yeo Kai Yuan, in writing, that the list is final, and name the commit.
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

Every source cited above, formatted properly for **Slide 12**. Each entry includes the publisher, title, year, URL and date accessed.

1. US Consumer Financial Protection Bureau, *Consumer Complaint Database*, 2026.
   https://www.consumerfinance.gov/data-research/consumer-complaints/ — Accessed 28 September 2026.

2. US Consumer Financial Protection Bureau, *Consumer Response Annual Report: January 1 – December 31, 2025*, March 2026.
   https://www.consumerfinance.gov/data-research/research-reports/2025-consumer-response-annual-report/ — Accessed 28 September 2026.

3. CNA, *IN FOCUS: What happens when you contact a bank or telco customer care centre?*, 2024.
   https://www.channelnewsasia.com/singapore/in-focus-what-happens-when-you-contact-bank-or-telco-customer-care-centre-4735346 — Accessed 28 September 2026.

4. Ward Whitt, Columbia University, *What You Should Know About Queueing Models To Set Staffing Requirements in Service Systems*, 2007.
   https://www.columbia.edu/~ww2040/shorter041907.pdf — Accessed 28 September 2026.

Source 3 concerns Singapore, while Source 4 uses an illustrative medium-sized financial-services call-centre example whose country is not specified in the paper. Both are used only as analogous proxies (agent activity pace and the existence of time-of-day demand variation). The complaint volume itself comes from the US CFPB, matching the dataset.


**Sources we could not find.** We searched for (a) a published hourly complaint-arrival profile for a financial-services complaints desk, (b) a published rate of agent searches per hour against a ticket system, and (c) a published customer-count denominator for scaling regulator-wide complaints to one firm. None was found, so the peak factor, the search rate and the firm share are estimates with stated methods.
