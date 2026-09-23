#!/usr/bin/env python3
"""Inter-annotator agreement between the two label sheets: Cohen's kappa.

Part 2/3 helper (golden test set, brief Step 1, item 3).
Script owner: Yeo Kai Yuan.  TODO(Yeo Kai Yuan): replace with real name.
Consumer: Part 3 -- Teammate B, who reports the statistic on Slide 6 and runs
the resolution meeting from the disagreement list this script writes.

The brief asks for "an inter-annotator agreement statistic".  Raw percentage
agreement is not enough: with seven categories of unequal frequency, two
labellers who both guess the common category a lot agree often by accident.
Cohen's kappa removes that accidental agreement, which is why it is the
conventional statistic for exactly this situation.

Cohen's kappa, from first principles (Cohen 1960)
-------------------------------------------------
No library computes this for us.  The arithmetic is short enough to state, and
stating it is what lets a marker (or a teammate) check the figure by hand.

Let A and B be the two labellers and let there be ``N`` rows that both have
labelled with one of the ``K`` categories.  Write ``n_agree`` for the number of
rows where they chose the same category, ``n_Ak`` for the number of rows A
assigned to category ``k``, and ``n_Bk`` likewise for B.  Then

    observed agreement    Po   = n_agree / N
    A's marginal rate     p_Ak = n_Ak / N
    B's marginal rate     p_Bk = n_Bk / N
    expected agreement    Pe   = sum over k of ( p_Ak * p_Bk )
    Cohen's kappa         k    = ( Po - Pe ) / ( 1 - Pe )

``Pe`` is the agreement the two would have reached by chance if each had kept
his own overall rate of using each category but had assigned the categories
independently of the other.  ``Po - Pe`` is therefore the agreement over and
above chance, and ``1 - Pe`` is the most agreement over and above chance that
was available.  Kappa is the ratio: 1.0 is perfect agreement, 0.0 is exactly
chance, and a negative value is worse than chance.

Degenerate case: if both labellers used one and the same single category for
every row, ``Pe = 1``, the denominator is zero and kappa is undefined.  This
script says so and exits non-zero rather than print a number.

Per-category agreement
----------------------
Reported as **per-category (one-vs-rest) Cohen's kappa**: for each category
``k`` the seven-way problem is collapsed to the binary question "is this ticket
in ``k`` or not?" and the same formula is applied to the resulting 2x2 table.

Why that statistic and not another:

* Per-category *accuracy* does not exist here.  There is no ground truth at
  this stage -- only two opinions -- so there is nothing to be accurate against.
  Accuracy arrives later, against the finished golden set (``analysis/accuracy.py``).
* Per-category *percentage* agreement is available but misleading: for a
  category holding a seventh of the rows, two labellers who never use it at all
  agree about it on ~86% of rows.  The number would look excellent and mean
  nothing.
* One-vs-rest kappa keeps the chance correction, so a category that both
  labellers found easy and a category they both avoided do not look alike.  It
  is the standard way to read a multi-class kappa per class.

A category no labeller used has a degenerate 2x2 table (``Pe = 1``); it is
reported as ``n/a`` with the reason, never as 0 or 1.

What it refuses to do
---------------------
It will not compute kappa over incomplete sheets.  A blank or mistyped label is
reported with its row number and the script exits 4.  A kappa over "the rows
that happen to be filled in" is not the statistic the brief asks for, and it
would drift every time somebody labelled a few more rows.

Outputs
-------
Everything above is printed to stdout -- redirect it to
``labelling/agreement_report.txt`` and commit it (see labelling/README.md).
The one file this script writes is ``<out-dir>/disagreements.csv``:

    row_number,label_A,confidence_A,notes_A,label_B,confidence_B,notes_B,narrative_prefix

ordered so that the disagreements **either** labeller was least confident about
come first.  Those are the rows most likely to be protocol gaps rather than
slips, and they are the ones the resolution meeting should spend its time on.

No model is involved in this script.

Exit codes
----------
0  success
2  argparse usage error
4  unusable input: missing file, wrong columns, mismatched sheets, blank or
   invalid labels, or a degenerate kappa

Usage::

    python labelling/scripts/agreement.py --a labelling/labeller_A.csv \
        --b labelling/labeller_B.csv [--out-dir labelling]
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from service.categories import CATEGORIES  # noqa: E402

# The label-sheet format is owned by the script that writes the sheets. We
# import the reader and the validators rather than copy them, so that the two
# scripts can never disagree about what a valid sheet is -- a divergence there
# would silently change which rows reach the golden set.
from sample_golden_candidates import (  # noqa: E402
    CONFIDENCE_VALUES,
    LabellingError,
    SheetRow,
    canonical_label,
    confidence_rank,
    is_blank,
    read_label_sheet,
)

csv.field_size_limit(10 ** 9)

#: How much of the narrative goes into disagreements.csv. Enough to recognise
#: the ticket in a meeting; the full text is in the label sheets.
NARRATIVE_PREFIX_CHARS = 200

#: Columns of disagreements.csv, in order.
DISAGREEMENT_COLUMNS: tuple[str, ...] = (
    "row_number",
    "label_A",
    "confidence_A",
    "notes_A",
    "label_B",
    "confidence_B",
    "notes_B",
    "narrative_prefix",
)

#: Landis & Koch's interpretation bands, as (lower bound inclusive, label).
#: Source: J. R. Landis and G. G. Koch (1977), "The measurement of observer
#: agreement for categorical data", Biometrics 33(1), pp. 159-174.
#: These bands are a widely used *convention*, not a property of the statistic;
#: cite them as such.
KAPPA_BANDS: tuple[tuple[float, str], ...] = (
    (0.81, "almost perfect"),
    (0.61, "substantial"),
    (0.41, "moderate"),
    (0.21, "fair"),
    (0.00, "slight"),
    (float("-inf"), "poor (worse than chance)"),
)
KAPPA_BANDS_SOURCE = (
    "Landis, J.R. and Koch, G.G. (1977) 'The measurement of observer agreement "
    "for categorical data', Biometrics, 33(1), pp. 159-174."
)


@dataclass(frozen=True)
class Pair:
    """One row as labelled by both labellers."""

    row_number: int
    label_a: str
    label_b: str
    confidence_a: str
    confidence_b: str
    notes_a: str
    notes_b: str
    narrative: str

    @property
    def agrees(self) -> bool:
        return self.label_a == self.label_b

    @property
    def weakest_confidence(self) -> int:
        """Rank of the *less* confident of the two labellers (low sorts first)."""
        return min(confidence_rank(self.confidence_a), confidence_rank(self.confidence_b))


@dataclass(frozen=True)
class KappaResult:
    """Everything needed to print the arithmetic, not just the answer."""

    n: int
    n_agree: int
    po: float
    pe: float
    kappa: float | None  # None when Pe == 1 and kappa is undefined
    marginals_a: dict[str, int]
    marginals_b: dict[str, int]
    chance_terms: dict[str, float]

    @property
    def degenerate(self) -> bool:
        return self.kappa is None


@dataclass(frozen=True)
class CategoryAgreement:
    """One-vs-rest agreement for a single category."""

    category: str
    n_a: int
    n_b: int
    both: int  # A and B both put the row in this category
    neither: int
    po: float
    pe: float
    kappa: float | None
    reason: str  # why kappa is None, or ""


# ---------------------------------------------------------------------------
# Loading and validation
# ---------------------------------------------------------------------------

def _sheet_index(rows: Sequence[SheetRow]) -> dict[int, SheetRow]:
    return {row.row_number: row for row in rows}


def load_pairs(path_a: Path, path_b: Path) -> tuple[list[Pair], list[str]]:
    """Read both sheets and pair them by row number.

    Returns the pairs (in the sheets' own order) and a list of non-fatal
    warnings.  Raises :class:`LabellingError` when the sheets cannot be paired
    at all, or when any label is blank or not one of the seven categories --
    kappa over an incomplete sheet is not a statistic we can report.
    """
    rows_a = read_label_sheet(path_a)
    rows_b = read_label_sheet(path_b)
    index_b = _sheet_index(rows_b)

    numbers_a = [row.row_number for row in rows_a]
    numbers_b = [row.row_number for row in rows_b]
    if set(numbers_a) != set(numbers_b):
        only_a = sorted(set(numbers_a) - set(numbers_b))
        only_b = sorted(set(numbers_b) - set(numbers_a))
        raise LabellingError(
            "the two sheets do not cover the same rows.\n"
            f"  only in {path_a.name}: {only_a[:20]}{' ...' if len(only_a) > 20 else ''}\n"
            f"  only in {path_b.name}: {only_b[:20]}{' ...' if len(only_b) > 20 else ''}\n"
            "Both labellers must label the same sample. Re-run "
            "labelling/scripts/sample_golden_candidates.py only if labelling has "
            "not started."
        )

    warnings: list[str] = []
    if numbers_a != numbers_b:
        warnings.append(
            "the sheets hold the same rows but in a different order; pairing by "
            "row_number, which is safe, but somebody has re-sorted a sheet."
        )

    blanks: list[int] = []
    invalid: list[tuple[int, str, str]] = []  # (row, labeller, value)
    odd_confidence: list[tuple[int, str, str]] = []
    narrative_mismatch: list[int] = []
    pairs: list[Pair] = []

    for row_a in rows_a:
        row_b = index_b[row_a.row_number]
        label_a = canonical_label(row_a.label)
        label_b = canonical_label(row_b.label)
        if is_blank(row_a.label):
            blanks.append(row_a.row_number)
        elif label_a is None:
            invalid.append((row_a.row_number, "A", row_a.label))
        if is_blank(row_b.label):
            blanks.append(row_b.row_number)
        elif label_b is None:
            invalid.append((row_b.row_number, "B", row_b.label))
        for labeller, row in (("A", row_a), ("B", row_b)):
            if not is_blank(row.confidence) and row.confidence not in CONFIDENCE_VALUES:
                odd_confidence.append((row.row_number, labeller, row.confidence))
        if row_a.narrative != row_b.narrative:
            narrative_mismatch.append(row_a.row_number)
        if label_a is not None and label_b is not None:
            pairs.append(
                Pair(
                    row_number=row_a.row_number,
                    label_a=label_a,
                    label_b=label_b,
                    confidence_a=row_a.confidence,
                    confidence_b=row_b.confidence,
                    notes_a=row_a.notes,
                    notes_b=row_b.notes,
                    narrative=row_a.narrative,
                )
            )

    if narrative_mismatch:
        warnings.append(
            f"{len(narrative_mismatch)} row(s) have different narrative text in the "
            f"two sheets (first: {narrative_mismatch[:5]}). The labellers did not read "
            "the same ticket, or a spreadsheet has reflowed the text. Investigate "
            "before trusting the labels."
        )
    if odd_confidence:
        listed = ", ".join(f"row {r} ({who}: {v!r})" for r, who, v in odd_confidence[:10])
        warnings.append(
            f"{len(odd_confidence)} unrecognised confidence value(s): {listed}. "
            f"Allowed values are {list(CONFIDENCE_VALUES)}; unrecognised values sort "
            "last in the disagreement queue."
        )

    if blanks or invalid:
        message = ["the sheets are incomplete, so kappa cannot be computed."]
        if blanks:
            unique_blanks = sorted(set(blanks))
            shown = ", ".join(str(r) for r in unique_blanks[:40])
            more = f" (+{len(unique_blanks) - 40} more)" if len(unique_blanks) > 40 else ""
            message.append(
                f"  {len(blanks)} blank label cell(s) across {len(unique_blanks)} row(s): "
                f"{shown}{more}"
            )
        if invalid:
            shown = "; ".join(
                f"row {r}, labeller {who}: {value!r}" for r, who, value in invalid[:20]
            )
            more = f" (+{len(invalid) - 20} more)" if len(invalid) > 20 else ""
            message.append(f"  {len(invalid)} label(s) that are not one of the seven categories: {shown}{more}")
            message.append(
                "  A label must match a canonical category name exactly "
                "(case-insensitively). Nothing is guessed for you."
            )
        raise LabellingError("\n".join(message))

    return pairs, warnings


# ---------------------------------------------------------------------------
# The statistic
# ---------------------------------------------------------------------------

def cohen_kappa(pairs: Sequence[Pair]) -> KappaResult:
    """Cohen's kappa over paired labels. See the module docstring for the algebra."""
    n = len(pairs)
    if n == 0:
        raise LabellingError("no rows to compare")
    n_agree = sum(1 for pair in pairs if pair.agrees)
    marginals_a = {category: 0 for category in CATEGORIES}
    marginals_b = {category: 0 for category in CATEGORIES}
    for pair in pairs:
        marginals_a[pair.label_a] += 1
        marginals_b[pair.label_b] += 1

    po = n_agree / n
    chance_terms = {
        category: (marginals_a[category] / n) * (marginals_b[category] / n)
        for category in CATEGORIES
    }
    pe = sum(chance_terms.values())
    # Pe == 1 only when both labellers used exactly one and the same category
    # throughout: there is then no chance-corrected agreement to measure.
    kappa = None if pe >= 1.0 else (po - pe) / (1.0 - pe)
    return KappaResult(
        n=n,
        n_agree=n_agree,
        po=po,
        pe=pe,
        kappa=kappa,
        marginals_a=marginals_a,
        marginals_b=marginals_b,
        chance_terms=chance_terms,
    )


def category_agreement(pairs: Sequence[Pair], category: str) -> CategoryAgreement:
    """One-vs-rest Cohen's kappa for a single category."""
    n = len(pairs)
    both = sum(1 for p in pairs if p.label_a == category and p.label_b == category)
    only_a = sum(1 for p in pairs if p.label_a == category and p.label_b != category)
    only_b = sum(1 for p in pairs if p.label_a != category and p.label_b == category)
    neither = n - both - only_a - only_b
    n_a = both + only_a
    n_b = both + only_b

    po = (both + neither) / n
    # The same formula as the multi-class case, over the two classes
    # "in this category" and "not in this category".
    pe = (n_a / n) * (n_b / n) + ((n - n_a) / n) * ((n - n_b) / n)
    if pe >= 1.0:
        if n_a == 0 and n_b == 0:
            reason = "neither labeller used this category"
        else:
            reason = "both labellers used this category for every row"
        return CategoryAgreement(category, n_a, n_b, both, neither, po, pe, None, reason)
    return CategoryAgreement(category, n_a, n_b, both, neither, po, pe, (po - pe) / (1 - pe), "")


def confusion_matrix(pairs: Sequence[Pair]) -> dict[str, dict[str, int]]:
    """A's label (rows) against B's label (columns), in canonical order."""
    matrix = {a: {b: 0 for b in CATEGORIES} for a in CATEGORIES}
    for pair in pairs:
        matrix[pair.label_a][pair.label_b] += 1
    return matrix


def interpret(kappa: float) -> str:
    """The Landis & Koch band for a kappa value."""
    for lower, label in KAPPA_BANDS:
        if kappa >= lower:
            return label
    return KAPPA_BANDS[-1][1]  # pragma: no cover - -inf catches everything


# ---------------------------------------------------------------------------
# Disagreement report
# ---------------------------------------------------------------------------

def narrative_prefix(text: str, limit: int = NARRATIVE_PREFIX_CHARS) -> str:
    """Whitespace-collapsed opening of a narrative, for the resolution meeting."""
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit] + "..."


def disagreements(pairs: Sequence[Pair]) -> list[Pair]:
    """Disagreeing pairs, least-confident first, then by row number.

    Ordering is the point of this function: a disagreement where one labeller
    was unsure is evidence that the protocol did not cover the case, which is
    what the resolution meeting is for.  A confident disagreement is more often
    a plain slip.
    """
    return sorted(
        (pair for pair in pairs if not pair.agrees),
        key=lambda pair: (pair.weakest_confidence, pair.row_number),
    )


def write_disagreements(path: Path, rows: Sequence[Pair]) -> None:
    """Write disagreements.csv."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(DISAGREEMENT_COLUMNS)
        for pair in rows:
            writer.writerow(
                [
                    pair.row_number,
                    pair.label_a,
                    pair.confidence_a,
                    pair.notes_a,
                    pair.label_b,
                    pair.confidence_b,
                    pair.notes_b,
                    narrative_prefix(pair.narrative),
                ]
            )


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def print_report(
    *,
    path_a: Path,
    path_b: Path,
    pairs: Sequence[Pair],
    result: KappaResult,
    per_category: Sequence[CategoryAgreement],
    matrix: dict[str, dict[str, int]],
    disagreeing: Sequence[Pair],
    out_path: Path,
) -> None:
    """Print the whole report. Every figure is shown with its inputs."""
    print("Inter-annotator agreement -- Cohen's kappa")
    print("=" * 42)
    print()
    print("Sheets")
    print(f"  labeller A   {path_a}")
    print(f"  labeller B   {path_b}")
    print(f"  categories   {len(CATEGORIES)} (service.categories.CATEGORIES)")
    print()

    print("Raw counts (these are the numbers to check the kappa by hand)")
    print(f"  N, rows labelled by both        {result.n}")
    print(f"  rows where A and B agree        {result.n_agree}")
    print(f"  rows where they disagree        {result.n - result.n_agree}")
    print(
        f"  observed agreement  Po = {result.n_agree}/{result.n} = {result.po:.6f}"
    )
    print()
    print("  Marginal category use, and the chance term Pe")
    header = (
        f"    {'category':<27}{'n_A':>6}{'p_A':>9}{'n_B':>6}{'p_B':>9}{'p_A*p_B':>11}"
    )
    print(header)
    print("    " + "-" * (len(header) - 4))
    for category in CATEGORIES:
        n_a = result.marginals_a[category]
        n_b = result.marginals_b[category]
        print(
            f"    {category:<27}{n_a:>6}{n_a / result.n:>9.4f}"
            f"{n_b:>6}{n_b / result.n:>9.4f}{result.chance_terms[category]:>11.6f}"
        )
    print("    " + "-" * (len(header) - 4))
    print(
        f"    {'TOTAL':<27}{sum(result.marginals_a.values()):>6}{1.0:>9.4f}"
        f"{sum(result.marginals_b.values()):>6}{1.0:>9.4f}{result.pe:>11.6f}"
    )
    print()
    if result.degenerate:
        print("  kappa is UNDEFINED: Pe = 1, so the denominator (1 - Pe) is zero.")
        print("  Both labellers used a single identical category for every row.")
    else:
        assert result.kappa is not None
        print("  kappa = (Po - Pe) / (1 - Pe)")
        print(
            f"        = ({result.po:.6f} - {result.pe:.6f}) / (1 - {result.pe:.6f})"
        )
        print(
            f"        = {result.po - result.pe:.6f} / {1 - result.pe:.6f}"
        )
        print(f"        = {result.kappa:.6f}")
        print()
        print(f"  COHEN'S KAPPA = {result.kappa:.3f}  ({interpret(result.kappa)})")
        print()
        print("  Interpretation bands used above (a convention, not a law):")
        print("    0.81 to 1.00   almost perfect")
        print("    0.61 to 0.80   substantial")
        print("    0.41 to 0.60   moderate")
        print("    0.21 to 0.40   fair")
        print("    0.00 to 0.20   slight")
        print("    below 0.00     poor, worse than chance")
        print(f"    source: {KAPPA_BANDS_SOURCE}")
    print()

    print("Confusion matrix: labeller A (rows) against labeller B (columns)")
    legend = {category: str(index + 1) for index, category in enumerate(CATEGORIES)}
    columns = "".join(f"{legend[c]:>6}" for c in CATEGORIES)
    # Built outside the f-string: a backslash inside an f-string expression is a
    # syntax error before Python 3.12, and this repository targets 3.11+.
    corner = "A \\ B"
    print(f"    {corner:<29}{columns}{'total':>7}")
    for category in CATEGORIES:
        cells = "".join(f"{matrix[category][b]:>6}" for b in CATEGORIES)
        total = sum(matrix[category].values())
        print(f"    {legend[category] + '. ' + category:<29}{cells}{total:>7}")
    totals = "".join(
        f"{sum(matrix[a][b] for a in CATEGORIES):>6}" for b in CATEGORIES
    )
    print(f"    {'total':<29}{totals}{result.n:>7}")
    print("    Column key: " + ", ".join(f"{legend[c]}={c}" for c in CATEGORIES))
    print("    The diagonal is agreement; off-diagonal cells name the confusion.")
    print()

    print("Per-category agreement: one-vs-rest Cohen's kappa")
    print("  (see the module docstring for why this statistic and not per-category %)")
    header = (
        f"    {'category':<27}{'n_A':>6}{'n_B':>6}{'both':>6}{'Po':>9}{'Pe':>9}{'kappa':>9}"
    )
    print(header)
    print("    " + "-" * (len(header) - 4))
    for entry in per_category:
        kappa_text = "n/a" if entry.kappa is None else f"{entry.kappa:.3f}"
        print(
            f"    {entry.category:<27}{entry.n_a:>6}{entry.n_b:>6}{entry.both:>6}"
            f"{entry.po:>9.4f}{entry.pe:>9.4f}{kappa_text:>9}"
        )
    for entry in per_category:
        if entry.kappa is None:
            print(f"    n/a for {entry.category}: {entry.reason}")
    print()

    print("Disagreements")
    print(f"  count                   {len(disagreeing)}")
    print(f"  written to              {out_path}")
    print(
        "  ordered least-confident first, so the rows most likely to be protocol"
    )
    print("  gaps are at the top of the resolution queue.")
    if disagreeing:
        print()
        print("  First rows to discuss:")
        for pair in disagreeing[:10]:
            conf_a = pair.confidence_a or "-"
            conf_b = pair.confidence_b or "-"
            print(
                f"    row {pair.row_number}: A={pair.label_a} ({conf_a}) "
                f"vs B={pair.label_b} ({conf_b})"
            )
    print()
    print("Next: resolve every disagreement together, record each one in")
    print("labelling/resolutions.md AND labelling/resolutions.csv, log any protocol")
    print("revision in labelling/protocol.md, then run build_golden_set.py.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compute Cohen's kappa between the two independent label sheets, print "
            "the arithmetic and the confusion matrix, and write disagreements.csv."
        ),
        epilog=(
            "Refuses to compute kappa over incomplete sheets. Redirect stdout to "
            "labelling/agreement_report.txt and commit it: the brief requires the "
            "agreement statistic as a supporting file."
        ),
    )
    parser.add_argument(
        "--a",
        required=True,
        type=Path,
        help="Labeller A's completed sheet (e.g. labelling/labeller_A.csv).",
    )
    parser.add_argument(
        "--b",
        required=True,
        type=Path,
        help="Labeller B's completed sheet (e.g. labelling/labeller_B.csv).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "labelling",
        help="Directory for disagreements.csv (default: labelling).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        pairs, warnings = load_pairs(args.a, args.b)
        result = cohen_kappa(pairs)
    except LabellingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 4

    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    per_category = [category_agreement(pairs, category) for category in CATEGORIES]
    matrix = confusion_matrix(pairs)
    disagreeing = disagreements(pairs)
    out_path = args.out_dir / "disagreements.csv"
    write_disagreements(out_path, disagreeing)

    print_report(
        path_a=args.a,
        path_b=args.b,
        pairs=pairs,
        result=result,
        per_category=per_category,
        matrix=matrix,
        disagreeing=disagreeing,
        out_path=out_path,
    )

    if result.degenerate:
        # Exit non-zero: there is no statistic to report, and silence would let
        # a missing figure reach the slides.
        print(
            "ERROR: kappa is undefined for these sheets (Pe = 1). There is no "
            "agreement statistic to report.",
            file=sys.stderr,
        )
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
