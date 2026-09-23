#!/usr/bin/env python3
"""Merge the two label sheets and the resolutions into golden/golden_set.csv.

Part 2/3 helper (golden test set, brief Step 1, item 4).
Script owner: Yeo Kai Yuan.  TODO(Yeo Kai Yuan): replace with real name.
Run by: Part 3 -- Teammate B, once every disagreement has been resolved and
recorded.  This is the last step before the freeze.

Output
------
``golden/golden_set.csv`` with **exactly two columns**::

    row_number,label

Two columns and no more, on purpose.  The golden set is the ground truth the
accuracy measurement joins against; anything else in the file (a narrative, a
confidence, a note, the consumer's ``raw_label``) is either redundant with
``data/team_rows.csv`` or is an invitation to score a model against the wrong
column.  The narrative is fetched from ``data/team_rows.csv`` by row number
when it is needed, exactly as the brief describes the golden set: "final labels
for the 150 to 200 tickets, identified by row number".

Merge rules -- all enforced, none inferred
------------------------------------------
1. Both sheets must cover the same rows, with no blank labels and no label that
   is not one of the seven canonical categories.  ``UNPARSEABLE`` is a
   *model-output* value and is rejected here: a human labeller does not produce
   it.
2. Where A and B chose the same label, that label is the golden label.
3. Where A and B differ, an entry in ``resolutions.csv`` is **required**.  A
   missing entry is a hard failure that names every unresolved row.  The team
   resolves disagreements by discussion (brief, Step 1, item 4); this script
   will not pick a winner, average the two, or prefer a labeller.
4. A resolution may record the token ``EXCLUDE`` instead of a category, which
   drops that row from the golden set.  Whether a ticket should ever be
   excluded, and on what grounds, is a protocol decision -- see
   ``labelling/protocol.md``, "Edge-case rules".  The mechanism exists here so
   that the decision, if the team takes it, is recorded rather than achieved by
   quietly deleting a line.
5. A resolution for a row where A and B already agreed is reported as a warning
   and **ignored**, unless it is ``EXCLUDE``.  If the pair agreed on a label the
   team now believes is wrong, both labellers correct their sheets and the
   protocol revision is logged, so that the golden set stays derivable from the
   sheets.  An override that lived only in ``resolutions.csv`` would make the
   sheets and the golden set disagree, and the sheets are a submitted artefact.
6. Every row number must exist in ``data/team_rows.csv``.  A golden label on a
   row outside our 1,000-row slice is not usable evidence.
7. The finished set must hold between 150 and 200 rows (brief, Step 1).  Out of
   range is a hard failure with the count and the arithmetic to fix it.

Consistency between ``resolutions.md`` and ``resolutions.csv``
-------------------------------------------------------------
``resolutions.md`` is the narrative record a human reads (and the source of the
one or two examples on Slide 6); ``resolutions.csv`` is what this script
consumes.  They must describe the same rows.  This script parses the row
numbers out of the ``.md`` (lines of the form ``- **Row number:** 10123``) and
**warns** in both directions when a row appears in one file and not the other.
It warns rather than fails because the ``.md`` is prose and its exact shape is
not something a build step should dictate -- but an asymmetry always means one
of the two records is incomplete, and the marker reads the ``.md``.

The freeze
----------
The golden set is frozen before any model sees it (brief, Step 1 and
Deliverables).  This script therefore refuses to overwrite
``golden/golden_set.csv`` once that file is committed, or once the
``golden-freeze`` tag exists, unless ``--force`` is given: rebuilding a frozen
golden set would destroy the evidence that our labels predate our measurements,
which is the whole point of the freeze.  The authoritative gate is
``scripts/freeze_gate.py``; the check here is a narrower local guard on this one
output, not a replacement for it.

No model is involved in this script.

Exit codes
----------
0  success
2  argparse usage error
3  refused: the golden set is already frozen (pass ``--force`` to override)
4  unusable input: see the merge rules above

Usage::

    python labelling/scripts/build_golden_set.py --a labelling/labeller_A.csv \
        --b labelling/labeller_B.csv --resolutions labelling/resolutions.csv \
        [--out golden/golden_set.csv] [--team-rows data/team_rows.csv] [--force]
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from service.categories import CATEGORIES, UNPARSEABLE  # noqa: E402

# Imported, not copied: see the same note in agreement.py. One definition of
# "a valid label sheet" for the whole toolchain.
from sample_golden_candidates import (  # noqa: E402
    BRIEF_MAX_GOLDEN,
    BRIEF_MIN_GOLDEN,
    LabellingError,
    canonical_label,
    is_blank,
    read_team_rows,
)

# agreement.py owns the pairing of the two sheets (and the checks that they are
# complete and comparable). Reusing it means the golden set is built from
# exactly the rows the reported kappa was computed over.
from agreement import Pair, load_pairs  # noqa: E402

csv.field_size_limit(10 ** 9)

#: Columns of ``labelling/resolutions.csv``, in order.
RESOLUTION_COLUMNS: tuple[str, ...] = (
    "row_number",
    "agreed_label",
    "resolution_note",
    "protocol_revision",
)
#: Written in ``agreed_label`` to drop a candidate from the golden set.
EXCLUDE_TOKEN = "EXCLUDE"
#: Accepted in ``protocol_revision`` to mean "this resolution changed nothing".
NO_REVISION_VALUES: tuple[str, ...] = ("none", "no", "-", "n/a")
#: Columns of the output. Exactly two -- see the module docstring.
GOLDEN_COLUMNS: tuple[str, ...] = ("row_number", "label")
#: The line shape ``resolutions.md`` uses to state a row number. Keep the two in
#: step: if the template changes, change this regular expression with it.
MD_ROW_RE = re.compile(r"^\s*[-*]\s*\*\*Row number:\*\*\s*(\d+)\s*$", re.MULTILINE)
#: The git tag that marks the freeze (see scripts/freeze_gate.py).
FREEZE_TAG = "golden-freeze"


@dataclass(frozen=True)
class Resolution:
    """One row of ``resolutions.csv``."""

    row_number: int
    agreed_label: str  # a canonical category, or EXCLUDE_TOKEN
    resolution_note: str
    protocol_revision: str
    ordinal: int  # 1-based position in the file, for error messages

    @property
    def excludes(self) -> bool:
        return self.agreed_label == EXCLUDE_TOKEN


@dataclass
class MergeResult:
    """The merged golden set plus everything the summary needs to report."""

    entries: list[tuple[int, str]]
    agreements: int
    resolved: int
    excluded: list[int]
    ignored_resolutions: list[int]


# ---------------------------------------------------------------------------
# Reading the resolutions
# ---------------------------------------------------------------------------

def _uncommented(path: Path) -> Iterable[str]:
    """Yield the lines of a CSV, dropping whole-line ``#`` comments.

    ``resolutions.csv`` ships with a commented example row, so the reader has to
    skip comments.  Only a line whose first non-space character is ``#`` is
    dropped; continuation lines of a quoted multi-line field pass through
    untouched, so a note containing a line break still parses -- unless that
    break is followed by ``#``, which the template warns against.
    """
    with path.open(newline="", encoding="utf-8") as handle:
        for line in handle:
            if line.lstrip().startswith("#"):
                continue
            if not line.strip():
                continue
            yield line


def read_resolutions(path: Path) -> list[Resolution]:
    """Read and validate ``resolutions.csv``."""
    if not path.is_file():
        raise LabellingError(
            f"resolutions file not found: {path}. Every disagreement must be "
            "resolved and recorded before the golden set can be built."
        )
    reader = csv.DictReader(_uncommented(path))
    fieldnames = tuple(reader.fieldnames or ())
    if fieldnames != RESOLUTION_COLUMNS:
        raise LabellingError(
            f"{path}: columns are {list(fieldnames)} but must be exactly "
            f"{list(RESOLUTION_COLUMNS)}."
        )
    resolutions: list[Resolution] = []
    seen: set[int] = set()
    for ordinal, record in enumerate(reader, start=1):
        raw_number = (record.get("row_number") or "").strip()
        try:
            row_number = int(raw_number)
        except ValueError as exc:
            raise LabellingError(
                f"{path}, resolution {ordinal}: row_number {raw_number!r} is not an "
                "integer (a TODO placeholder must be deleted or commented out with #)"
            ) from exc
        if row_number in seen:
            raise LabellingError(
                f"{path}, resolution {ordinal}: row {row_number} is resolved twice. "
                "One resolution per row; amend the first entry instead."
            )
        seen.add(row_number)

        raw_label = (record.get("agreed_label") or "").strip()
        if raw_label.upper() == EXCLUDE_TOKEN:
            agreed = EXCLUDE_TOKEN
        else:
            agreed_or_none = canonical_label(raw_label)
            if agreed_or_none is None:
                hint = ""
                if raw_label.upper() == UNPARSEABLE:
                    hint = (
                        f" {UNPARSEABLE} is a model-output value and is never a golden "
                        "label; a human labeller must choose a category or EXCLUDE."
                    )
                elif is_blank(raw_label):
                    hint = " The cell is empty."
                raise LabellingError(
                    f"{path}, resolution {ordinal} (row {row_number}): agreed_label "
                    f"{raw_label!r} is not one of the seven categories and is not "
                    f"{EXCLUDE_TOKEN}.{hint}"
                )
            agreed = agreed_or_none

        note = (record.get("resolution_note") or "").strip()
        if is_blank(note):
            raise LabellingError(
                f"{path}, resolution {ordinal} (row {row_number}): resolution_note is "
                "empty. The brief asks for each resolution to be recorded, so the "
                "reasoning is not optional."
            )
        revision = (record.get("protocol_revision") or "").strip()
        if is_blank(revision):
            raise LabellingError(
                f"{path}, resolution {ordinal} (row {row_number}): protocol_revision is "
                f"empty. Write the revision id from the protocol's revision log (e.g. "
                f"R2), or one of {list(NO_REVISION_VALUES)} if this disagreement "
                "changed nothing."
            )
        resolutions.append(
            Resolution(
                row_number=row_number,
                agreed_label=agreed,
                resolution_note=note,
                protocol_revision=revision,
                ordinal=ordinal,
            )
        )
    return resolutions


def read_resolution_md_rows(path: Path) -> set[int] | None:
    """Row numbers mentioned in ``resolutions.md``, or ``None`` if it is absent."""
    if not path.is_file():
        return None
    return {int(match) for match in MD_ROW_RE.findall(path.read_text(encoding="utf-8"))}


# ---------------------------------------------------------------------------
# Merging
# ---------------------------------------------------------------------------

def merge(
    pairs: Sequence[Pair],
    resolutions: Sequence[Resolution],
) -> tuple[MergeResult, list[str]]:
    """Apply the merge rules to the paired labels and the recorded resolutions.

    Returns the merge result and a list of non-fatal warnings.  Raises
    :class:`LabellingError` on any unresolved disagreement or unknown row, and
    names every offending row so the fix is one pass rather than a dozen runs.
    """
    by_row = {resolution.row_number: resolution for resolution in resolutions}
    sheet_rows = {pair.row_number for pair in pairs}

    unknown = sorted(row for row in by_row if row not in sheet_rows)
    if unknown:
        raise LabellingError(
            f"resolutions.csv resolves {len(unknown)} row(s) that are not in the label "
            f"sheets: {unknown[:20]}{' ...' if len(unknown) > 20 else ''}. Either the "
            "sample was redrawn after the resolution meeting, or a row number is "
            "mistyped."
        )

    entries: list[tuple[int, str]] = []
    unresolved: list[int] = []
    warnings: list[str] = []
    agreements = 0
    resolved = 0
    excluded: list[int] = []
    ignored: list[int] = []

    for pair in pairs:
        row_number = pair.row_number
        resolution = by_row.get(row_number)
        if pair.agrees:
            if resolution is not None and resolution.excludes:
                excluded.append(row_number)
                continue
            if resolution is not None:
                ignored.append(row_number)
            agreements += 1
            entries.append((row_number, pair.label_a))
            continue
        if resolution is None:
            unresolved.append(row_number)
            continue
        if resolution.excludes:
            excluded.append(row_number)
            continue
        resolved += 1
        entries.append((row_number, resolution.agreed_label))

    if unresolved:
        listed = ", ".join(str(row) for row in unresolved)
        raise LabellingError(
            f"{len(unresolved)} disagreement(s) have no entry in resolutions.csv:\n"
            f"  {listed}\n"
            "Every disagreement must be resolved by discussion and recorded (brief, "
            "Step 1, item 4). This script will not choose between the two labellers. "
            "Add one line per row to resolutions.csv (and the matching entry to "
            "resolutions.md), then re-run."
        )
    if ignored:
        listed = ", ".join(str(row) for row in ignored)
        warnings.append(
            f"{len(ignored)} resolution(s) are for row(s) where A and B already agreed "
            f"and have been IGNORED: {listed}. The agreed label stands (merge rule 5). "
            "If the agreed label is wrong, both labellers correct their sheets and log "
            f"a protocol revision; use {EXCLUDE_TOKEN} if the row should be dropped."
        )

    entries.sort(key=lambda entry: entry[0])
    return (
        MergeResult(
            entries=entries,
            agreements=agreements,
            resolved=resolved,
            excluded=sorted(excluded),
            ignored_resolutions=sorted(ignored),
        ),
        warnings,
    )


def validate_result(result: MergeResult, team_row_numbers: set[int]) -> None:
    """Rules 1, 6 and 7 applied to the finished set."""
    bad_labels = sorted({label for _, label in result.entries if label not in CATEGORIES})
    if bad_labels:  # pragma: no cover - the readers reject these upstream
        raise LabellingError(f"internal error: non-canonical label(s) survived: {bad_labels}")

    missing = sorted(row for row, _ in result.entries if row not in team_row_numbers)
    if missing:
        raise LabellingError(
            f"{len(missing)} golden row(s) are not in data/team_rows.csv: "
            f"{missing[:20]}{' ...' if len(missing) > 20 else ''}. Only our team's "
            "1,000 rows may be used (brief, System Under Test, item 3)."
        )

    count = len(result.entries)
    if not BRIEF_MIN_GOLDEN <= count <= BRIEF_MAX_GOLDEN:
        if count < BRIEF_MIN_GOLDEN:
            remedy = (
                f"label {BRIEF_MIN_GOLDEN - count} more candidate(s), or exclude fewer "
                f"({len(result.excluded)} row(s) are currently excluded)"
            )
        else:
            remedy = f"exclude {count - BRIEF_MAX_GOLDEN} row(s), or sample fewer candidates"
        raise LabellingError(
            f"the golden set would hold {count} rows, outside the brief's "
            f"{BRIEF_MIN_GOLDEN}-{BRIEF_MAX_GOLDEN} range. To fix: {remedy}."
        )


# ---------------------------------------------------------------------------
# Freeze guard
# ---------------------------------------------------------------------------

def _git(*args: str) -> tuple[int, str]:
    """Run git in the repository root. Returns (exit code, stdout)."""
    try:
        completed = subprocess.run(
            ["git", "-C", str(REPO_ROOT), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return 127, ""
    return completed.returncode, completed.stdout.strip()


def is_git_tracked(path: Path) -> bool:
    """True if ``path`` is tracked by git."""
    code, _ = _git("ls-files", "--error-unmatch", str(path))
    return code == 0


def freeze_tag_exists() -> bool:
    """True if the ``golden-freeze`` tag exists in this repository."""
    code, _ = _git("rev-parse", "-q", "--verify", f"refs/tags/{FREEZE_TAG}^{{commit}}")
    return code == 0


def freeze_blockers(out_path: Path) -> list[str]:
    """Reasons to refuse to rebuild the golden set at ``out_path``."""
    blockers: list[str] = []
    if out_path.exists() and is_git_tracked(out_path):
        blockers.append(f"{out_path} already exists and is committed to git")
    if freeze_tag_exists():
        blockers.append(f"the {FREEZE_TAG} tag exists, so the golden set is frozen")
    return blockers


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_golden_set(path: Path, entries: Sequence[tuple[int, str]]) -> None:
    """Write ``row_number,label`` and nothing else."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(GOLDEN_COLUMNS)
        for row_number, label in entries:
            writer.writerow([row_number, label])


def print_summary(result: MergeResult, out_path: Path, total_pairs: int) -> list[str]:
    """Print the build summary. Returns any warnings it wants raised afterwards."""
    counts = {category: 0 for category in CATEGORIES}
    for _, label in result.entries:
        counts[label] += 1
    written = len(result.entries)

    print("Golden set built")
    print(f"  candidates labelled by both     {total_pairs}")
    print(f"  A and B agreed                  {result.agreements}")
    print(f"  disagreements resolved          {result.resolved}")
    print(f"  rows excluded by resolution     {len(result.excluded)}")
    if result.excluded:
        print(f"    excluded rows: {', '.join(str(row) for row in result.excluded)}")
    print(
        f"  rows written                    {written}"
        f"   (brief requires {BRIEF_MIN_GOLDEN}-{BRIEF_MAX_GOLDEN})"
    )
    print(f"  output                          {out_path}")
    print(f"  columns                         {','.join(GOLDEN_COLUMNS)}")
    print()
    print("Per-category counts in the finished golden set")
    header = f"    {'category':<27}{'rows':>6}{'share':>9}"
    print(header)
    print("    " + "-" * (len(header) - 4))
    for category in CATEGORIES:
        share = counts[category] / written if written else 0.0
        print(f"    {category:<27}{counts[category]:>6}{share:>9.3f}")
    print("    " + "-" * (len(header) - 4))
    print(f"    {'TOTAL':<27}{written:>6}{1.0:>9.3f}")
    print()

    warnings: list[str] = []
    empty = [category for category in CATEGORIES if counts[category] == 0]
    if empty:
        warnings.append(
            "no golden rows for: "
            + "; ".join(empty)
            + ". Per-category accuracy cannot be reported for a category with no "
            "golden rows, and the brief asks for accuracy per category."
        )
    thin = [category for category in CATEGORIES if 0 < counts[category] < 10]
    if thin:
        warnings.append(
            "fewer than 10 golden rows for: "
            + "; ".join(f"{category} ({counts[category]})" for category in thin)
            + ". Per-category accuracy on such a small denominator moves in large "
            "steps; say so when reporting it."
        )
    return warnings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Merge the two independent label sheets and the recorded resolutions into "
            "golden/golden_set.csv (row_number,label)."
        ),
        epilog=(
            "Refuses to rebuild a frozen golden set. After a successful build, commit "
            "golden/golden_set.csv with the prediction record and tag the commit "
            "golden-freeze; scripts/freeze_gate.py is what the benchmark scripts check."
        ),
    )
    parser.add_argument("--a", required=True, type=Path, help="Labeller A's completed sheet.")
    parser.add_argument("--b", required=True, type=Path, help="Labeller B's completed sheet.")
    parser.add_argument(
        "--resolutions",
        required=True,
        type=Path,
        help=(
            "labelling/resolutions.csv. Its sibling .md file is checked for consistency "
            "if it exists."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "golden" / "golden_set.csv",
        help="Output path (default: golden/golden_set.csv).",
    )
    parser.add_argument(
        "--team-rows",
        type=Path,
        default=REPO_ROOT / "data" / "team_rows.csv",
        help="Team slice every golden row must belong to (default: data/team_rows.csv).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Rebuild even though the golden set is already frozen. This invalidates the "
            "freeze evidence; only the team together should decide to do it."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Guard first, before any work: never compute a result we would refuse to write.
    if not args.force:
        blockers = freeze_blockers(args.out)
        if blockers:
            print(
                "REFUSING to rebuild the golden set:\n  "
                + "\n  ".join(blockers)
                + "\n\nThe golden set is frozen before any model sees it, and the commit "
                "history is\nthe evidence that our labels predate our measurements "
                "(brief, Step 1 and\nDeliverables). Rebuilding it destroys that "
                "evidence.\n\nIf the team has agreed to rebuild, re-run with --force and "
                "say why in the\ncommit message.",
                file=sys.stderr,
            )
            return 3

    try:
        pairs, sheet_warnings = load_pairs(args.a, args.b)
        resolutions = read_resolutions(args.resolutions)
        result, merge_warnings = merge(pairs, resolutions)
        team_rows = read_team_rows(args.team_rows)
        validate_result(result, {row.row_number for row in team_rows})
    except LabellingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 4

    warnings = list(sheet_warnings) + list(merge_warnings)

    # resolutions.md is the human record; resolutions.csv is what we just read.
    # They must describe the same rows.
    md_path = args.resolutions.with_suffix(".md")
    md_rows = read_resolution_md_rows(md_path)
    if md_rows is None:
        warnings.append(
            f"{md_path} not found. The brief requires the narrative record of the "
            "resolutions, and Slide 6 quotes one or two of them."
        )
    else:
        csv_rows = {resolution.row_number for resolution in resolutions}
        only_csv = sorted(csv_rows - md_rows)
        only_md = sorted(md_rows - csv_rows)
        if only_csv:
            warnings.append(
                f"{len(only_csv)} row(s) are resolved in {args.resolutions.name} but not "
                f"written up in {md_path.name}: {only_csv}. The .md is the record a "
                "marker reads."
            )
        if only_md:
            warnings.append(
                f"{len(only_md)} row(s) are written up in {md_path.name} but have no line "
                f"in {args.resolutions.name}: {only_md}. The .csv is what this script "
                "consumes, so those resolutions have had no effect."
            )

    write_golden_set(args.out, result.entries)
    warnings.extend(print_summary(result, args.out, total_pairs=len(pairs)))

    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    print("Next steps (the freeze):")
    print(f"  1. Commit {args.out}, the label sheets, the protocol, the resolutions and")
    print("     predictions/prediction_record.md in one commit.")
    print("  2. Tag that commit golden-freeze.")
    print("  3. Check the gate: python scripts/freeze_gate.py --json")
    print("  No benchmark run may happen before that gate passes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
