#!/usr/bin/env python3
"""Draw the golden-set candidate sample and write the two blank label sheets.

Part 2/3 helper (golden test set, brief Step 1).
Script owner: Yeo Kai Yuan.  TODO(Yeo Kai Yuan): replace with real name.
Consumers: Part 2 -- Teammate A and Part 3 -- Teammate B, who label the sheets
independently and without conferring.

What this script does
---------------------
Reads ``data/team_rows.csv`` (our 1,000 rows -- the only rows we are permitted
to use) and draws a stratified sample of ``--n`` rows.  It then writes three
files into ``--out-dir``:

``golden_candidates.csv``
    ``row_number,raw_label``.  The audit trail of *what was sampled*.  It is
    committed, and it is the evidence that the sample was drawn mechanically
    before labelling rather than cherry-picked afterwards.

``labeller_A.csv``, ``labeller_B.csv``
    ``row_number,narrative,label,confidence,notes`` -- the same sampled rows,
    in the same order, with ``label``, ``confidence`` and ``notes`` EMPTY.

``raw_label`` deliberately does **not** appear in the label sheets.  The golden
set exists precisely because the consumer-selected labels in the course extract
are noisy (brief, Step 1); showing a labeller the consumer's label would anchor
them to it, and the golden set would inherit the very noise it exists to
remove.  For the same reason, a labeller must not open ``golden_candidates.csv``
(or ``data/team_rows.csv``) until labelling is finished.

Sampling method -- state this in the report
-------------------------------------------
1. **Strata.** The sample is stratified by ``raw_label``.  The consumer label is
   not trusted as ground truth, but it is a serviceable *coverage* device: it is
   correlated with the true category, so stratifying on it is what stops a
   simple random draw from under-representing a category and leaving us unable
   to report per-category accuracy (brief, Step 5: accuracy "overall and per
   category").
2. **Allocation.** Proportional allocation by the largest-remainder (Hare
   quota) method.  Each stratum's exact quota is ``n * stratum_size / total``.
   Every stratum first receives ``floor(quota)`` places; the places still
   unallocated (always fewer than the number of strata) then go to the strata
   with the largest fractional remainders, one each.  Ties on the remainder are
   broken by canonical ``service.categories.CATEGORIES`` order, so the outcome
   is fully determined -- no coin flip, no dictionary-ordering accident.
3. **Repair passes.** Two documented corrections are applied after allocation,
   both no-ops for our data but present so the script cannot silently produce a
   nonsense plan on a different slice: (a) no stratum is asked for more rows
   than it has, any surplus going to the stratum with the most spare capacity;
   (b) every stratum that exists in the input contributes at least
   :data:`MIN_PER_STRATUM` row, taken from the largest stratum that can spare
   it.  Pass (b) is what guarantees "every category has coverage".
4. **Reproducibility.**  Within each stratum the candidate rows are **sorted by
   row number** and then drawn with ``random.Random(seed).sample(...)``; the
   strata are visited in canonical category order, so the RNG stream is
   consumed in a fixed order.  The sample is therefore an exact function of
   (input rows, n, seed) and of nothing else -- not of the order the CSV
   happened to be read in, and not of any set or dict iteration order.  The
   script proves this to itself on every run (see :func:`build_candidates`).
5. **Seed.** The default seed is :data:`DEFAULT_SEED` = 3113, the course code.
   It is recorded here, in ``labelling/protocol.md`` and in
   ``labelling/README.md``.  Re-running with the same seed reproduces the same
   200 rows exactly; anyone marking this work can check that.

Why ``--n`` defaults to 200 and not 150
---------------------------------------
The brief requires a finished golden set of 150 to 200 tickets.  We sample at
the top of that range so that the team can *exclude* a candidate during
resolution (a ticket the protocol says fits none of the seven, say) and still
land inside the range.  ``build_golden_set.py`` enforces the 150-200 bound on
the finished set.

Safety
------
No model is involved in this script, and it never reads
``golden/golden_set.csv``.  It refuses to overwrite a label sheet that somebody
has already started working in unless ``--force`` is given: regenerating over a
part-labelled sheet would destroy hours of a teammate's judgement work, which
is not recoverable from anything else in the repository.

Exit codes
----------
0  success
2  argparse usage error
3  refused: a label sheet already contains work (pass ``--force`` to override)
4  unusable input (missing file, bad columns, unknown ``raw_label``, ``--n``
   larger than the number of available rows)

Usage::

    python labelling/scripts/sample_golden_candidates.py \
        [--team-rows data/team_rows.csv] [--n 200] [--seed 3113] \
        [--out-dir labelling] [--force]
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:  # so `python labelling/scripts/...` works anywhere
    sys.path.insert(0, str(REPO_ROOT))

from service.categories import CATEGORIES  # noqa: E402  (after the sys.path fix)

# Complaint narratives are long free text. The stdlib default field-size limit
# is generous enough for our rows (max 1,999 characters) but the course CSV is
# the same shape, so we keep the same guard the extractor uses.
csv.field_size_limit(10 ** 9)

#: Default number of candidates. See "Why --n defaults to 200" above.
DEFAULT_N = 200
#: Default RNG seed: the course code. Documented in protocol.md and README.md.
DEFAULT_SEED = 3113
#: Every stratum present in the input contributes at least this many rows.
MIN_PER_STRATUM = 1
#: The brief's bound on the size of the finished golden set.
BRIEF_MIN_GOLDEN, BRIEF_MAX_GOLDEN = 150, 200

#: Columns of ``data/team_rows.csv`` (written by scripts/extract_team_rows.py).
TEAM_ROW_COLUMNS: tuple[str, ...] = ("row_number", "narrative", "raw_label")
#: Columns of the audit trail.
CANDIDATE_COLUMNS: tuple[str, ...] = ("row_number", "raw_label")
#: Columns of a label sheet. This module owns the sheet format; ``agreement.py``
#: and ``build_golden_set.py`` import these names so the three cannot diverge.
SHEET_COLUMNS: tuple[str, ...] = (
    "row_number",
    "narrative",
    "label",
    "confidence",
    "notes",
)
#: The labeller identifiers. A third independent labeller is added by extending
#: this tuple -- nothing else in the toolchain hard-codes "A" and "B" except the
#: ``--a``/``--b`` flags of the two downstream scripts.
LABELLER_IDS: tuple[str, ...] = ("A", "B")
#: Allowed values of the ``confidence`` column, lowest first. What each level
#: *means* is a protocol decision (see labelling/protocol.md); the toolchain
#: only needs the ordering, to put the shakiest disagreements at the top of the
#: resolution queue.
CONFIDENCE_VALUES: tuple[str, ...] = ("low", "medium", "high")


class LabellingError(RuntimeError):
    """Raised when input to the labelling toolchain is unusable.

    Shared with ``agreement.py`` and ``build_golden_set.py``, which import it
    from here. Always fail loudly: a golden set built from a sheet we did not
    fully understand is worse than no golden set at all.
    """


@dataclass(frozen=True)
class TeamRow:
    """One row of ``data/team_rows.csv``."""

    row_number: int
    narrative: str
    raw_label: str


@dataclass(frozen=True)
class SheetRow:
    """One row of a label sheet, as filled in by a labeller."""

    row_number: int
    narrative: str
    label: str
    confidence: str
    notes: str
    line: int  # 1-based line in the CSV, for error messages


@dataclass(frozen=True)
class StratumPlan:
    """The arithmetic of one stratum, kept so the run can print its own method."""

    category: str
    available: int
    quota: float
    base: int  # floor(quota)
    drawn: int

    @property
    def extra(self) -> int:
        """Places added after the floor (largest-remainder pass and repairs)."""
        return self.drawn - self.base


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def read_team_rows(path: Path) -> list[TeamRow]:
    """Read ``data/team_rows.csv``, validating its columns and row numbers."""
    if not path.is_file():
        raise LabellingError(f"team rows file not found: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in TEAM_ROW_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise LabellingError(
                f"{path}: missing column(s) {missing}; expected {list(TEAM_ROW_COLUMNS)}"
            )
        rows: list[TeamRow] = []
        seen: set[int] = set()
        for line, record in enumerate(reader, start=2):
            raw_number = (record["row_number"] or "").strip()
            try:
                row_number = int(raw_number)
            except ValueError as exc:
                raise LabellingError(
                    f"{path} line {line}: row_number {raw_number!r} is not an integer"
                ) from exc
            if row_number in seen:
                raise LabellingError(f"{path} line {line}: duplicate row_number {row_number}")
            seen.add(row_number)
            rows.append(
                TeamRow(
                    row_number=row_number,
                    narrative=record["narrative"] or "",
                    raw_label=(record["raw_label"] or "").strip(),
                )
            )
    if not rows:
        raise LabellingError(f"{path}: no data rows")
    return rows


def read_label_sheet(path: Path) -> list[SheetRow]:
    """Read a label sheet and validate its shape (not its labels).

    Lives here because this module writes the sheets, so it owns the format.
    Label *values* are validated by the caller, which wants to collect every
    bad cell rather than stop at the first one.
    """
    if not path.is_file():
        raise LabellingError(f"label sheet not found: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        if fieldnames != SHEET_COLUMNS:
            raise LabellingError(
                f"{path}: columns are {list(fieldnames)} but must be exactly "
                f"{list(SHEET_COLUMNS)}. Do not add, remove or reorder columns -- "
                "the agreement and build scripts read them positionally by name."
            )
        rows: list[SheetRow] = []
        seen: set[int] = set()
        for line, record in enumerate(reader, start=2):
            raw_number = (record["row_number"] or "").strip()
            try:
                row_number = int(raw_number)
            except ValueError as exc:
                raise LabellingError(
                    f"{path} line {line}: row_number {raw_number!r} is not an integer. "
                    "Did a spreadsheet reformat the column?"
                ) from exc
            if row_number in seen:
                raise LabellingError(f"{path} line {line}: duplicate row_number {row_number}")
            seen.add(row_number)
            rows.append(
                SheetRow(
                    row_number=row_number,
                    narrative=record["narrative"] or "",
                    label=(record["label"] or "").strip(),
                    confidence=(record["confidence"] or "").strip().lower(),
                    notes=(record["notes"] or "").strip(),
                    line=line,
                )
            )
    if not rows:
        raise LabellingError(f"{path}: no data rows")
    return rows


def is_blank(value: str | None) -> bool:
    """True if a cell is empty or whitespace only."""
    return value is None or not value.strip()


def canonical_label(value: str | None) -> str | None:
    """Return the canonical category name, or ``None`` if ``value`` is not one.

    The match is an exact, case-insensitive match against the seven canonical
    names -- nothing else.  No aliasing, no fuzzy matching, no "did you mean".
    Guessing what a human meant by a mistyped label is the same mistake as
    guessing what a model meant by an odd reply: it quietly changes the data.
    A typo is reported and the labeller fixes it.
    """
    if is_blank(value):
        return None
    folded = " ".join(str(value).split()).casefold()
    for category in CATEGORIES:
        if folded == category.casefold():
            return category
    return None


def confidence_rank(value: str | None) -> int:
    """Sort key for confidence: low first, then medium, high, then unrecognised."""
    if value is not None:
        folded = value.strip().lower()
        if folded in CONFIDENCE_VALUES:
            return CONFIDENCE_VALUES.index(folded)
    return len(CONFIDENCE_VALUES)  # blank or unrecognised sorts last


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------

def stratum_counts(rows: Iterable[TeamRow]) -> dict[str, int]:
    """Count rows per ``raw_label``, keyed in canonical category order.

    An unexpected ``raw_label`` is an error, not a new stratum: it means the
    extract we are sampling from is not the one we think it is.
    """
    counts: dict[str, int] = {category: 0 for category in CATEGORIES}
    unexpected: dict[str, int] = {}
    for row in rows:
        if row.raw_label in counts:
            counts[row.raw_label] += 1
        else:
            unexpected[row.raw_label] = unexpected.get(row.raw_label, 0) + 1
    if unexpected:
        listed = ", ".join(f"{label!r} ({n})" for label, n in sorted(unexpected.items()))
        raise LabellingError(
            "raw_label value(s) not in service.categories.CATEGORIES: "
            f"{listed}. Re-check scripts/extract_team_rows.py and the course CSV."
        )
    # Drop strata with no rows: a category absent from our slice cannot be
    # sampled, and the printed plan should not pretend otherwise.
    return {category: n for category, n in counts.items() if n > 0}


def allocate(available: Mapping[str, int], n: int) -> dict[str, int]:
    """Allocate ``n`` places across strata. See the module docstring, item 2-3."""
    order = list(available)
    total = sum(available.values())
    if n <= 0:
        raise LabellingError(f"--n must be positive, got {n}")
    if n > total:
        raise LabellingError(
            f"asked for {n} candidates but only {total} rows are available"
        )
    rank = {category: index for index, category in enumerate(order)}
    quotas = {category: n * available[category] / total for category in order}
    allocation = {category: int(quotas[category]) for category in order}  # floor
    remainders = {category: quotas[category] - allocation[category] for category in order}

    # Largest-remainder pass. Ties broken by canonical order, never by chance.
    places_left = n - sum(allocation.values())
    ranked = sorted(order, key=lambda c: (-remainders[c], rank[c]))
    for category in ranked[:places_left]:
        allocation[category] += 1

    # Repair (a): never ask a stratum for more rows than it has.
    surplus = 0
    for category in order:
        if allocation[category] > available[category]:
            surplus += allocation[category] - available[category]
            allocation[category] = available[category]
    while surplus:
        target = max(order, key=lambda c: (available[c] - allocation[c], -rank[c]))
        if available[target] - allocation[target] <= 0:  # pragma: no cover - n<=total
            raise LabellingError("internal error: no spare capacity to place surplus")
        allocation[target] += 1
        surplus -= 1

    # Repair (b): every stratum that exists contributes at least MIN_PER_STRATUM.
    for category in order:
        floor_for_category = min(MIN_PER_STRATUM, available[category])
        while allocation[category] < floor_for_category:
            donors = [
                c
                for c in order
                if allocation[c] > min(MIN_PER_STRATUM, available[c])
            ]
            if not donors:
                raise LabellingError(
                    f"cannot give every category at least {MIN_PER_STRATUM} row(s) "
                    f"with --n {n}: increase --n"
                )
            donor = max(donors, key=lambda c: (allocation[c], -rank[c]))
            allocation[donor] -= 1
            allocation[category] += 1

    if sum(allocation.values()) != n:  # pragma: no cover - guarded by construction
        raise LabellingError(
            f"internal error: allocation sums to {sum(allocation.values())}, not {n}"
        )
    return allocation


def plan(available: Mapping[str, int], allocation: Mapping[str, int], n: int) -> list[StratumPlan]:
    """The per-stratum arithmetic, for printing."""
    total = sum(available.values())
    rows: list[StratumPlan] = []
    for category in available:
        quota = n * available[category] / total
        rows.append(
            StratumPlan(
                category=category,
                available=available[category],
                quota=quota,
                base=int(quota),
                drawn=allocation[category],
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def draw_sample(
    rows: Sequence[TeamRow],
    allocation: Mapping[str, int],
    seed: int,
) -> list[TeamRow]:
    """Draw the sample. Deterministic given ``(rows, allocation, seed)``.

    Every stratum's pool is sorted by row number before it is handed to
    ``random.Random.sample``, and the strata are visited in the order of
    ``allocation`` (canonical category order), so neither the order of ``rows``
    nor any hash ordering can influence the result.
    """
    pools: dict[str, list[TeamRow]] = {category: [] for category in allocation}
    for row in rows:
        if row.raw_label in pools:
            pools[row.raw_label].append(row)
    rng = random.Random(seed)
    chosen: list[TeamRow] = []
    for category, wanted in allocation.items():
        pool = sorted(pools[category], key=lambda r: r.row_number)
        if wanted > len(pool):  # pragma: no cover - guarded by allocate()
            raise LabellingError(
                f"stratum {category!r}: asked for {wanted} of {len(pool)} rows"
            )
        chosen.extend(rng.sample(pool, wanted))
    # Sheets are emitted in row-number order: it is the order a marker can
    # check against data/team_rows.csv by eye, and it tells a labeller nothing
    # about which stratum a ticket came from.
    chosen.sort(key=lambda r: r.row_number)
    return chosen


def build_candidates(
    rows: Sequence[TeamRow],
    n: int,
    seed: int,
) -> tuple[list[TeamRow], list[StratumPlan]]:
    """Plan and draw the sample, and prove the draw is reproducible.

    The two self-checks are cheap (a thousand rows) and they close off the one
    way this script could quietly betray us: a future edit that reintroduces a
    dependency on set or dict ordering, or on the order of the input file, would
    still *look* fine while making the "same seed, same 200 rows" claim in our
    report false.
    """
    available = stratum_counts(rows)
    allocation = allocate(available, n)

    first = draw_sample(rows, allocation, seed)
    # Property 1: an independent draw with the same seed gives the same rows.
    second = draw_sample(rows, allocation, seed)
    # Property 2: the draw is independent of the order the rows were read in.
    shuffled = list(rows)
    random.Random(seed + 1).shuffle(shuffled)
    third = draw_sample(shuffled, allocation, seed)
    numbers = [tuple(r.row_number for r in draw) for draw in (first, second, third)]
    if not (numbers[0] == numbers[1] == numbers[2]):  # pragma: no cover
        raise LabellingError(
            "reproducibility self-check FAILED: the sample depends on something "
            "other than (rows, n, seed). Do not use this sample."
        )
    return first, plan(available, allocation, n)


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def sheet_work_count(path: Path) -> int:
    """How many rows of an existing sheet already carry a labeller's work.

    A cell counts as work if ``label``, ``confidence`` or ``notes`` is non-blank.
    A freshly generated sheet therefore counts zero, which is what lets the
    sampler be re-run for a reproducibility check without ``--force``.
    """
    if not path.is_file():
        return 0
    try:
        rows = read_label_sheet(path)
    except LabellingError:
        # An unreadable sheet is treated as work in progress: something is in
        # there that we do not understand, and overwriting it blind is worse
        # than making a human look at it.
        return -1
    return sum(
        1
        for row in rows
        if not (is_blank(row.label) and is_blank(row.confidence) and is_blank(row.notes))
    )


def write_candidates_csv(path: Path, sample: Sequence[TeamRow]) -> None:
    """Write the ``row_number,raw_label`` audit trail."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(CANDIDATE_COLUMNS)
        for row in sample:
            writer.writerow([row.row_number, row.raw_label])


def write_label_sheet(path: Path, sample: Sequence[TeamRow]) -> None:
    """Write a blank label sheet: narrative verbatim, no ``raw_label``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(SHEET_COLUMNS)
        for row in sample:
            # The narrative is copied verbatim, newlines and all: the labeller
            # must read exactly the text the service will send to the model.
            writer.writerow([row.row_number, row.narrative, "", "", ""])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Draw a stratified golden-set candidate sample from the team rows and "
            "write the blank independent label sheets."
        ),
        epilog=(
            "The sample is an exact function of (--team-rows, --n, --seed): the same "
            "seed always draws the same rows. Default seed 3113 is the course code."
        ),
    )
    parser.add_argument(
        "--team-rows",
        type=Path,
        default=REPO_ROOT / "data" / "team_rows.csv",
        help="Team slice to sample from (default: data/team_rows.csv).",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=DEFAULT_N,
        help=f"Number of candidate tickets to sample (default: {DEFAULT_N}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Fixed RNG seed, recorded in the report (default: {DEFAULT_SEED}).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "labelling",
        help="Directory for golden_candidates.csv and the label sheets (default: labelling).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Overwrite label sheets that already contain labels. This DESTROYS "
            "a labeller's work and cannot be undone except from git."
        ),
    )
    return parser.parse_args(argv)


def print_method(
    *,
    team_rows: Path,
    total_rows: int,
    n: int,
    seed: int,
    strata: Sequence[StratumPlan],
) -> None:
    """Print the sampling method in full. The report quotes this block."""
    places_from_remainder = sum(s.extra for s in strata)
    print("Sampling method")
    print(f"  input             {team_rows} ({total_rows} rows)")
    print(f"  requested sample  {n} rows")
    print(f"  seed              {seed}   (random.Random({seed}))")
    print("  strata            raw_label, in service.categories.CATEGORIES order")
    print("  allocation        proportional, largest-remainder (Hare quota):")
    print("                      quota  = n * stratum_size / total")
    print("                      base   = floor(quota) places to every stratum")
    print(
        f"                      +{places_from_remainder} place(s) left over go to the largest"
    )
    print("                      fractional remainders, ties broken by canonical")
    print("                      category order")
    print(f"  minimum           {MIN_PER_STRATUM} row per stratum present in the input")
    print("  reproducibility   each stratum's rows are sorted by row_number, strata")
    print("                    are visited in canonical order, then")
    print("                    random.Random(seed).sample() draws each stratum, so")
    print("                    the same seed always yields the same rows")
    print()
    header = f"  {'category':<27}{'available':>10}{'quota':>9}{'base':>6}{'extra':>7}{'drawn':>7}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for stratum in strata:
        print(
            f"  {stratum.category:<27}{stratum.available:>10}{stratum.quota:>9.3f}"
            f"{stratum.base:>6}{stratum.extra:>7}{stratum.drawn:>7}"
        )
    print("  " + "-" * (len(header) - 2))
    print(
        f"  {'TOTAL':<27}{sum(s.available for s in strata):>10}{'':>9}"
        f"{sum(s.base for s in strata):>6}{places_from_remainder:>7}"
        f"{sum(s.drawn for s in strata):>7}"
    )
    print()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir: Path = args.out_dir
    sheet_paths = {
        labeller: out_dir / f"labeller_{labeller}.csv" for labeller in LABELLER_IDS
    }

    # Guard first: never do work we might refuse to write.
    if not args.force:
        blocked: list[str] = []
        for labeller, path in sheet_paths.items():
            count = sheet_work_count(path)
            if count > 0:
                blocked.append(f"{path} ({count} row(s) already labelled)")
            elif count < 0:
                blocked.append(f"{path} (exists but could not be parsed)")
        if blocked:
            print(
                "REFUSING to overwrite work in progress:\n  "
                + "\n  ".join(blocked)
                + "\n\nRegenerating would destroy a labeller's judgement work, which "
                "nothing else\nin the repository can reconstruct. If the sample really "
                "must be redrawn,\ncommit the current sheets first and then re-run with "
                "--force.",
                file=sys.stderr,
            )
            return 3

    try:
        rows = read_team_rows(args.team_rows)
        sample, strata = build_candidates(rows, args.n, args.seed)
    except LabellingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 4

    print_method(
        team_rows=args.team_rows,
        total_rows=len(rows),
        n=args.n,
        seed=args.seed,
        strata=strata,
    )
    print("Reproducibility self-check: PASSED (same seed and shuffled input agree)")

    candidates_path = out_dir / "golden_candidates.csv"
    write_candidates_csv(candidates_path, sample)
    for path in sheet_paths.values():
        write_label_sheet(path, sample)

    print()
    print(f"Wrote {len(sample)} candidates:")
    print(f"  {candidates_path}   (audit trail: row_number,raw_label)")
    for labeller, path in sheet_paths.items():
        print(f"  {path}   (labeller {labeller}: {','.join(SHEET_COLUMNS)}, labels blank)")
    print()
    print(
        "raw_label is NOT in the label sheets, and must not be shown to a labeller "
        "before\nlabelling is finished -- it is the noisy consumer label the golden "
        "set exists to replace."
    )
    print("Next: read labelling/README.md, step 3.")

    if not BRIEF_MIN_GOLDEN <= args.n <= BRIEF_MAX_GOLDEN:
        print(
            f"WARNING: --n {args.n} is outside the brief's 150-200 golden-set range. "
            "build_golden_set.py enforces that range on the finished set, so this "
            "sample cannot produce a compliant golden set unless rows are added or "
            "excluded during resolution.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
