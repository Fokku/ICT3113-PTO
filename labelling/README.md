# `labelling/` — building the golden test set

**What this folder is for.** Everything behind Step 1 of the brief: a written
labelling protocol, a reproducible sample of candidate tickets, two independent
label sheets, an inter-annotator agreement statistic, a record of how every
disagreement was resolved, and the script that turns all of that into
`../golden/golden_set.csv`.

**Owners.**

| Part | Person | Responsible for |
|---|---|---|
| Part 2 | Loh Wen Xuan | `protocol.md`, labelling sheet A, any protocol revision |
| Part 3 | Jolie Ngai Ning Li | labelling sheet B, running `agreement.py`, writing up `resolutions.md` / `resolutions.csv`, running `build_golden_set.py` |
| Technical core | **Yeo Kai Yuan** — `TODO(Yeo Kai Yuan): replace with real name` | the three scripts, the freeze gate, the commit and the tag |

**"Done" looks like:** `../golden/golden_set.csv` exists with 150–200 rows, it and
`../predictions/prediction_record.md` are committed, and the commit is tagged
`golden-freeze` so that `python scripts/freeze_gate.py` passes. Nothing may be
benchmarked before then.

**Feeds:** Slide 6 (Golden Test Set) and Slide 10 (Accuracy Results, which is
measured against the golden set). The protocol, the two label sheets, the
agreement statistic and the golden set are also **submitted supporting files**.

---

## The deadline

| Date | What must be true |
|---|---|
| **Tuesday 29 September 2026** | **Freeze gate.** `golden/golden_set.csv` and `predictions/prediction_record.md` are committed and the commit is tagged `golden-freeze`. This is our internal target, chosen to leave Weeks 5 and 6 for the three-run load tests, the accuracy runs and the stress test — those take wall-clock time on CPU inference and cannot be compressed. |
| Friday 9 October 2026, 2359 | Assignment due on xSiTe. |

The freeze is not an administrative date. The brief makes Step 5 depend on it:
"Step 5 cannot begin until Steps 1 to 4 are complete: your golden test set and
your prediction record must both be committed to your repository before your
first benchmark run." The commit history is the evidence that our labels predate
our measurements, and `scripts/freeze_gate.py` enforces it in code — the
benchmark scripts refuse to run against team rows until the gate passes.

Work backwards from 29 September:

| By | Step |
|---|---|
| Thu 24 Sep | `protocol.md` filled in and signed off; sampler run; the blank sheets committed |
| Sat 26 Sep | both labellers finished, independently — 200 tickets each |
| Sun 27 Sep | `agreement.py` run and the kappa reported; resolution meeting held |
| Mon 28 Sep | `resolutions.md` and `resolutions.csv` written up; protocol revisions logged; `build_golden_set.py` run and the golden set reviewed by both labellers |
| Tue 29 Sep | freeze commit + `golden-freeze` tag + `scripts/freeze_gate.py` passes |

`TODO(Yeo Kai Yuan): confirm these interim dates with the team, or replace them
with the dates the team actually agrees. The 29 September gate is the one that
must not move.`

---

## What must be committed

**At the freeze** (one commit, then the tag):

| Path | Why |
|---|---|
| `labelling/protocol.md` | the protocol with its revision log — a submitted file, summarised on Slide 6 |
| `labelling/golden_candidates.csv` | audit trail: which 200 rows were sampled, and with which consumer labels |
| `labelling/labeller_A.csv`, `labelling/labeller_B.csv` | the two independent label sheets — submitted files |
| `labelling/disagreements.csv` | what the two labellers differed on |
| `labelling/agreement_report.txt` | the agreement statistic and its arithmetic — a submitted file |
| `labelling/resolutions.md`, `labelling/resolutions.csv` | how every disagreement was resolved |
| `golden/golden_set.csv` | the ground truth: `row_number,label`, 150–200 rows |
| `predictions/prediction_record.md` | owned by Part 4, but the same tag covers it |

Commit the **blank** sheets as soon as they are generated, before labelling
starts. That way the git history shows the sample was drawn before anyone
labelled anything, and a labeller who loses their working copy loses nothing.

**Submitted on xSiTe** with `Group10.pptx` (brief, Deliverables): the golden test
set, the prediction record, and "the labelling protocol with its revisions, the
independent label sheets, and the agreement statistic".

---

## Files in this folder

| File | What it is | Written by |
|---|---|---|
| `README.md` | this file | Yeo Kai Yuan |
| `protocol.md` | the labelling rules; **write it first** | Part 2 — Loh Wen Xuan |
| `scripts/sample_golden_candidates.py` | draws the stratified sample, writes the blank sheets | Yeo Kai Yuan |
| `golden_candidates.csv` | `row_number,raw_label` — the audit trail of what was sampled | the sampler |
| `labeller_A.csv`, `labeller_B.csv` | `row_number,narrative,label,confidence,notes` | the sampler creates them blank; the labellers fill them in |
| `scripts/agreement.py` | Cohen's kappa, per-category kappa, confusion matrix, disagreement list | Yeo Kai Yuan |
| `disagreements.csv` | the rows the two labellers differ on, least-confident first | `agreement.py` |
| `agreement_report.txt` | the printed output of `agreement.py`, redirected and committed | Part 3 — Jolie Ngai Ning Li |
| `resolutions.md` | the narrative record of each resolution — **what Slide 6 quotes** | Part 3 — Jolie Ngai Ning Li |
| `resolutions.csv` | the same resolutions in machine-readable form — **what the build script consumes** | Part 3 — Jolie Ngai Ning Li |
| `scripts/build_golden_set.py` | merges sheets + resolutions into the golden set | Yeo Kai Yuan |

### Why the resolutions live in two files

`resolutions.md` is prose for a human: the reasoning, the protocol rule that
settled the row, and the one or two examples that go on Slide 6. A marker reads
it. `resolutions.csv` is four columns a script can consume: `build_golden_set.py`
reads it to decide the label of every row the labellers disagreed on.

**The two must agree.** `build_golden_set.py` parses the row numbers out of the
`.md` (lines of the form `- **Row number:** 10123`) and warns in both
directions:

* resolved in the `.csv` but not written up in the `.md` — the marker's record is
  incomplete;
* written up in the `.md` but missing from the `.csv` — the resolution has had no
  effect on the golden set at all.

Neither warning stops the build, because the `.md` is prose and a build step
should not dictate its shape. Both warnings mean somebody has more to write.

---

## The procedure, in order

Run everything from the repository root. `python` below means the project
virtualenv: `.venv/bin/python`.

### Step 1 — write the protocol (Part 2 — Loh Wen Xuan)

Fill in every `TODO(...)` in `protocol.md`: the seven category definitions, the
edge-case rules, the tie-break ordering, and what the three confidence levels
mean. Both labellers read and sign it. **Commit it before Step 3 begins.**

This is the part of the assignment that is being assessed as judgement. A
protocol that says "use common sense" produces a low kappa and nothing to write
on Slide 6.

### Step 2 — draw the sample (once)

```
python labelling/scripts/sample_golden_candidates.py
```

Defaults: `--team-rows data/team_rows.csv --n 200 --seed 3113 --out-dir labelling`.

It prints the full sampling method — per-stratum arithmetic included — and writes
`golden_candidates.csv`, `labeller_A.csv` and `labeller_B.csv`. Copy the printed
method block into Slide 6's notes; it is the answer to "how did you choose the
200?".

The draw is reproducible: the same seed draws the same 200 rows, and the script
checks that property on every run. Seed **3113** is the course code; it is
recorded in the script's docstring and in `protocol.md`.

Both sheets hold the same 200 rows in the same order, and neither contains
`raw_label`. Do not add it, and do not open `golden_candidates.csv` or
`data/team_rows.csv` while labelling: the consumer label in those files is the
noise the golden set exists to replace, and seeing it anchors your judgement to
it.

Re-running the sampler is refused (exit 3) once either sheet contains any label,
confidence or note — regenerating would destroy a labeller's work. `--force`
overrides that, and should only ever be used on sheets that are committed.

### Step 3 — label independently (Teammates A and B)

Each labeller fills in `label` and `confidence` (and `notes` where the row was
not obvious) in **their own sheet only**. Allowed labels are the seven exact
strings listed in `protocol.md`; allowed confidence values are `high`, `medium`
and `low`.

**No conferring about specific rows.** The brief requires independent labelling,
and an agreement statistic between two people who compared notes measures
nothing.

Practical warning: the `narrative` column contains commas, quotation marks and
line breaks. Open the sheet in a spreadsheet (LibreOffice Calc, Excel or Google
Sheets) as UTF-8, comma-separated, with `"` as the text delimiter, and save it
back as CSV. Do not edit it in a plain text editor, and do not re-sort, rename or
add columns — the downstream scripts check the header and will refuse a sheet
whose shape has changed.

### Step 4 — compute the agreement statistic (Part 3 — Jolie Ngai Ning Li)

```
python labelling/scripts/agreement.py \
    --a labelling/labeller_A.csv \
    --b labelling/labeller_B.csv \
    --out-dir labelling > labelling/agreement_report.txt
echo "exit code: $?"
cat labelling/agreement_report.txt
```

Commit `agreement_report.txt`: the brief asks for the agreement statistic as a
supporting file, and the report shows the arithmetic, so the figure can be
checked by hand.

The report gives Cohen's kappa with every input to it, the Landis and Koch
interpretation band and its citation, per-category one-vs-rest kappa, the
confusion matrix between the two labellers, and the disagreement count. It also
writes `disagreements.csv`, ordered so that the rows either labeller was least
confident about come first — those are the likely protocol gaps.

It refuses (exit 4) to compute kappa over sheets with blank or mistyped labels,
and names the rows. Finish the sheets first; a kappa over "the rows that happen
to be filled in" is not a statistic we can report.

### Step 5 — resolve every disagreement (both labellers together)

Work down `disagreements.csv`. For each row, agree a label by discussion, write
the entry in `resolutions.md`, and add the line to `resolutions.csv`. Where the
disagreement exposed a gap in the protocol, revise `protocol.md` **and** log the
revision in its Revision log naming that row.

`resolutions.csv` columns: `row_number,agreed_label,resolution_note,protocol_revision`.

* `agreed_label` is one of the seven categories, or the token `EXCLUDE` to drop
  the row from the golden set. Whether a row may ever be excluded is a protocol
  decision (`protocol.md`, rule E2); the token exists so that the decision is
  recorded rather than achieved by deleting a line.
* `resolution_note` is required. A resolution with no reasoning is not a
  resolution.
* `protocol_revision` is the revision id from `protocol.md` (for example `R2`),
  or `none`.

### Step 6 — build the golden set (Part 3 — Jolie Ngai Ning Li)

```
python labelling/scripts/build_golden_set.py \
    --a labelling/labeller_A.csv \
    --b labelling/labeller_B.csv \
    --resolutions labelling/resolutions.csv \
    --out golden/golden_set.csv
```

Output: `golden/golden_set.csv`, two columns, `row_number,label`. Where the
labellers agreed, the agreed label is used; where they differed, the resolution
is used; a disagreement with no resolution is a hard failure that names every
unresolved row. The script also checks that every row exists in
`data/team_rows.csv`, that every label is one of the seven, and that the finished
set holds between 150 and 200 rows.

Read the per-category counts it prints. A category with no golden rows means
Slide 10 cannot report accuracy for that category, which the brief asks for.

### Step 7 — freeze

```
git add labelling golden/golden_set.csv predictions/prediction_record.md
git commit -m "Freeze golden test set and prediction record"
git tag golden-freeze
python scripts/freeze_gate.py --json
```

`freeze_gate.py` exits 0 only when both files are committed, unmodified, and
present in the tagged commit. Until then, every benchmark script refuses to
touch team rows and runs in `--dev` mode against `data/dev/synthetic_tickets.csv`
only.

After the freeze, `build_golden_set.py` refuses to run again (exit 3) unless
`--force` is given. Rebuilding a frozen golden set destroys the evidence that
our labels predate our measurements, so that decision belongs to the whole team
and to the commit message.

---

## Exit codes

All three scripts use the same convention, so a wrapper or a teammate can tell a
refusal from a data problem.

| Code | Meaning |
|---|---|
| 0 | success |
| 2 | command-line usage error (argparse) |
| 3 | **refused**: it would have destroyed something — a part-labelled sheet, or a frozen golden set. Re-run with `--force` only when the team has agreed to it. |
| 4 | unusable input: a missing file, a changed header, a blank or invalid label, an unresolved disagreement, a golden set outside the 150–200 range. The message names the rows. |

---

## Rules that are not negotiable

1. **No model sees these rows before the freeze.** Not through the service, not
   through a prompt, not "just to see what it says". The moment a model output
   has been seen, the labels are suspect and the accuracy measurement is
   worthless (brief, Step 1).
2. **Label independently.** Two sheets, no conferring, then the statistic.
3. **Never label from `raw_label`.** It is the consumer's own noisy choice; it is
   in `golden_candidates.csv` for stratification and audit only.
4. **Log protocol revisions.** A protocol that was quietly edited to match the
   labels is worth nothing, and the brief awards marks for the revisions.
5. **The tests must pass.** `.venv/bin/pytest tests/test_labelling.py -q`
   exercises all three scripts, including the kappa arithmetic against a
   hand-computed example.

---

## Related

* `../docs/assignment-brief.md` — Step 1 and the Deliverables section.
* `../scripts/freeze_gate.py` — the gate that enforces the freeze in code.
* `../service/categories.py` — the seven category names, canonical order.
* `../analysis/accuracy.py` — measures accuracy against `../golden/golden_set.csv`.
