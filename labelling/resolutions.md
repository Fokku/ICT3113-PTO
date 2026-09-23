# Disagreement resolutions — golden test set

**What this document is.** The human record of how every disagreement between the
two independent label sheets was resolved. The brief requires it: "Resolve every
disagreement by discussion, record each resolution, and update the protocol
where a disagreement revealed a gap in it." This is the record; its machine
readable counterpart is `resolutions.csv`, which `build_golden_set.py` consumes.

**Owner: Part 3 — Teammate B** (writes it up during and after the resolution
meeting). `TODO(Yeo Kai Yuan): replace with real name.`
**Co-owner: Part 2 — Teammate A** (agrees each resolution and makes any protocol
revision it implies). `TODO(Yeo Kai Yuan): replace with real name.`

**Feeds:** Slide 6 (Golden Test Set) — the number of disagreements, how they were
resolved, and **one or two worked examples quoted from this file**. Also a
submitted supporting file.

**"Done" looks like:** one numbered entry below for every row in
`labelling/disagreements.csv`; the same rows, with the same agreed labels, in
`labelling/resolutions.csv`; every entry that changed a rule cross-referenced to
a row of the Revision log in `protocol.md`; and one or two entries flagged as the
Slide 6 examples.

---

## How to use this file

1. Run `labelling/scripts/agreement.py` first. It writes
   `labelling/disagreements.csv`, ordered so that the disagreements either
   labeller was least confident about come first. Work down that list — those
   rows are where the protocol is most likely to have a gap.
2. Resolve each row **by discussion between the two labellers**, not by a vote,
   a coin toss, or by deferring to whoever labelled faster. The agreed label is
   the one the protocol implies once both people have read the narrative
   together; if the protocol does not imply one, that is a protocol gap and it
   goes in the Revision log.
3. Write the entry here, then add the matching line to `resolutions.csv`. The two
   files must describe the same rows; `build_golden_set.py` warns when a row
   appears in one and not the other.
4. Where the disagreement exposed a gap, revise `protocol.md` **and** log the
   revision in its Revision log, naming this row number.

**Keep the `- **Row number:** 10123` line exactly in that shape.**
`build_golden_set.py` reads the row numbers out of this file with that pattern in
order to cross-check it against `resolutions.csv`. If the shape changes, the
cross-check silently finds nothing.

Do not delete a resolution once written, even if a later revision changes the
outcome. Add a follow-up entry instead: the sequence of decisions is the
evidence of care that the brief is asking to see.

---

## Summary

Fill this in once every entry below is written. It is what Slide 6 quotes.

| Item | Value |
|---|---|
| Rows labelled by both labellers | `TODO(Part 3 — Teammate B)` |
| Disagreements | `TODO(Part 3 — Teammate B): the count from agreement.py` |
| Cohen's kappa | `TODO(Part 3 — Teammate B): the figure printed by agreement.py` |
| Resolutions that changed a category label | `TODO(Part 3 — Teammate B)` |
| Resolutions that excluded a row | `TODO(Part 3 — Teammate B)` |
| Protocol revisions caused | `TODO(Part 2 — Teammate A): count, and the revision ids` |
| Chosen as Slide 6 examples | `TODO(Part 3 — Teammate B): the entry numbers` |

---

## Entries

Copy the block below once per disagreement and number the entries consecutively.
Two blocks are shown so the shape of a second entry is unambiguous; delete the
unused one.

### Resolution 1

- **Row number:** `TODO(Part 3 — Teammate B): the row number, digits only, e.g. 10123`
- **Label A:** `TODO(Part 3 — Teammate B): exactly as it appears in labeller_A.csv`
- **Label B:** `TODO(Part 3 — Teammate B): exactly as it appears in labeller_B.csv`
- **Confidence A / B:** `TODO(Part 3 — Teammate B): e.g. low / high`
- **Agreed label:** `TODO(Part 3 — Teammate B): one of the seven categories, or EXCLUDE`
- **Reasoning:** `TODO(Part 3 — Teammate B): which rule of the protocol settles this row, quoted or referenced by its heading (E1-E7), and what in the narrative triggers that rule. If no rule settled it, say so plainly — that is the finding.`
- **Caused a protocol revision:** `TODO(Part 2 — Teammate A): the revision id from the Revision log in protocol.md (e.g. R2), or "no"`
- **Slide 6 example:** `TODO(Part 3 — Teammate B): yes / no`

### Resolution 2

- **Row number:** `TODO(Part 3 — Teammate B): the row number, digits only`
- **Label A:** `TODO(Part 3 — Teammate B)`
- **Label B:** `TODO(Part 3 — Teammate B)`
- **Confidence A / B:** `TODO(Part 3 — Teammate B)`
- **Agreed label:** `TODO(Part 3 — Teammate B)`
- **Reasoning:** `TODO(Part 3 — Teammate B)`
- **Caused a protocol revision:** `TODO(Part 2 — Teammate A)`
- **Slide 6 example:** `TODO(Part 3 — Teammate B): yes / no`

---

## Chosen examples for Slide 6

Pick one or two entries above and say, in two or three lines each, why that
disagreement was interesting: what the two labellers saw differently, what the
protocol did or did not say, and what changed as a result. A resolution that
changed the protocol makes the better slide than one that was simply a slip,
because it shows the mechanism working.

1. `TODO(Part 3 — Teammate B): entry number and the two- or three-line write-up.`
2. `TODO(Part 3 — Teammate B): entry number and the two- or three-line write-up, or delete this line if one example is enough.`
