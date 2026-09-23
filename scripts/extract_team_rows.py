#!/usr/bin/env python3
"""Extract this team's 1,000 rows from the course complaint CSV.

Per the assignment brief, team ``n`` owns rows ``n * 1000`` through
``n * 1000 + 999`` (inclusive) of the course extract.  Those 1,000 rows are the
ONLY rows that may ever be used for labelling or for test traffic.

The full course CSV is gitignored (it is large and is distributed via xSiTe).
The extracted slice -- ``data/team_rows.csv`` -- IS committed, so that every
number we report can be traced back to a specific, version-controlled input.

Output columns (exactly, in this order):

    row_number   the row identifier from the course CSV (int)
    narrative    the complaint narrative text
    raw_label    the consumer-selected category from the course CSV

``raw_label`` is the NOISY consumer-submitted label.  It is retained here only
so that the golden-set sampler can stratify across categories and so that we
can talk about label noise.  It is NOT ground truth and must never be used to
score a model -- accuracy is measured against ``golden/golden_set.csv`` only.

Usage:
    python scripts/extract_team_rows.py --csv ict3113_tickets.csv --team 10

No model is involved in this script.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Narratives are long free text; the stdlib default field-size limit is too
# small for some rows.
csv.field_size_limit(10 ** 9)

ROWS_PER_TEAM = 1000
OUTPUT_COLUMNS = ["row_number", "narrative", "raw_label"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Extract one team's 1,000-row slice of the course CSV.",
    )
    p.add_argument(
        "--csv",
        required=True,
        type=Path,
        help="Path to the full course CSV (e.g. ict3113_tickets.csv).",
    )
    p.add_argument(
        "--team",
        required=True,
        type=int,
        help="Registered team number n. Rows n*1000 .. n*1000+999 are extracted.",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("data/team_rows.csv"),
        help="Output path (default: data/team_rows.csv).",
    )
    p.add_argument(
        "--row-column",
        default="row",
        help="Name of the row-number column in the source CSV (default: row).",
    )
    p.add_argument(
        "--narrative-column",
        default="narrative",
        help="Name of the narrative column in the source CSV (default: narrative).",
    )
    p.add_argument(
        "--label-column",
        default="source_label",
        help="Name of the raw label column in the source CSV (default: source_label).",
    )
    return p.parse_args(argv)


def extract(
    source: Path,
    team: int,
    out_path: Path,
    row_column: str = "row",
    narrative_column: str = "narrative",
    label_column: str = "source_label",
) -> dict:
    """Write the team's slice to ``out_path`` and return a small summary dict."""
    if team < 0:
        raise SystemExit(f"Team number must be non-negative, got {team}.")

    lo = team * ROWS_PER_TEAM
    hi = lo + ROWS_PER_TEAM - 1

    if not source.is_file():
        raise SystemExit(f"Source CSV not found: {source}")

    wanted: dict[int, dict[str, str]] = {}
    seen_rows = 0

    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [
            c
            for c in (row_column, narrative_column, label_column)
            if c not in (reader.fieldnames or [])
        ]
        if missing:
            raise SystemExit(
                f"Source CSV is missing expected column(s): {', '.join(missing)}. "
                f"Found: {reader.fieldnames}"
            )

        for record in reader:
            seen_rows += 1
            raw_row = (record.get(row_column) or "").strip()
            try:
                row_number = int(raw_row)
            except ValueError:
                # A row without a usable identifier cannot be traced back to the
                # source, so it cannot be used as evidence. Skip loudly later.
                continue
            if lo <= row_number <= hi:
                wanted[row_number] = {
                    "row_number": str(row_number),
                    "narrative": record.get(narrative_column) or "",
                    "raw_label": (record.get(label_column) or "").strip(),
                }

    if not wanted:
        raise SystemExit(
            f"No rows found in range {lo}..{hi}. The source CSV held {seen_rows} "
            f"records. Is --team {team} correct for this extract?"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row_number in sorted(wanted):
            writer.writerow(wanted[row_number])

    expected = set(range(lo, hi + 1))
    found = set(wanted)
    summary = {
        "team": team,
        "range": (lo, hi),
        "source_records": seen_rows,
        "written": len(wanted),
        "missing_row_numbers": sorted(expected - found),
        "out": str(out_path),
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = extract(
        source=args.csv,
        team=args.team,
        out_path=args.out,
        row_column=args.row_column,
        narrative_column=args.narrative_column,
        label_column=args.label_column,
    )
    lo, hi = summary["range"]
    print(f"Team {summary['team']}: rows {lo}..{hi}")
    print(f"Source records scanned : {summary['source_records']}")
    print(f"Rows written           : {summary['written']} -> {summary['out']}")
    if summary["missing_row_numbers"]:
        miss = summary["missing_row_numbers"]
        preview = ", ".join(str(m) for m in miss[:10])
        more = f" (+{len(miss) - 10} more)" if len(miss) > 10 else ""
        print(
            f"WARNING: {len(miss)} row number(s) in range were not present in the "
            f"source CSV: {preview}{more}",
            file=sys.stderr,
        )
        return 1
    print(f"Complete: all {ROWS_PER_TEAM} rows present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
