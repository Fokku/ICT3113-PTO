"""Tests for the team-row extractor.

Owner: Part 1 -- Yeo Kai Yuan (technical core).

``scripts/extract_team_rows.py`` has already been run once to produce the
committed ``data/team_rows.csv``, which every later step depends on: the golden
set is sampled from it, the load tests read narratives from it, and the accuracy
run looks up narratives in it by row number. If the extractor picked the wrong
1,000 rows, or mangled a narrative containing a comma or a newline, every number
we later report would be about the wrong data -- silently.

So these tests pin the three properties that matter (the right rows, the exact
column order, a lossless round trip) and the three ways it must fail loudly (a
gap in the range, a bad team number, a missing file).

The tests never touch the real course CSV: each builds a small synthetic source
file in ``tmp_path`` whose row numbers bracket one team's range.
"""

from __future__ import annotations

import csv
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "extract_team_rows.py"

#: The extractor's source-CSV column names (the course extract's own header).
SOURCE_COLUMNS = ["row", "source_label", "narrative"]

#: The output column order the rest of the repository relies on.
EXPECTED_OUTPUT_COLUMNS = ["row_number", "narrative", "raw_label"]

TEAM = 10
TEAM_FIRST_ROW = TEAM * 1000
TEAM_LAST_ROW = TEAM_FIRST_ROW + 999


def _load_extractor():
    """Import ``scripts/extract_team_rows.py`` by path (``scripts`` is not a package)."""
    spec = importlib.util.spec_from_file_location("extract_team_rows_under_test", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


extract_team_rows = _load_extractor()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def write_source(
    path: Path,
    *,
    first: int = TEAM_FIRST_ROW - 10,
    last: int = TEAM_LAST_ROW + 10,
    skip: set[int] | None = None,
    special: dict[int, str] | None = None,
) -> Path:
    """Write a synthetic course-extract CSV covering ``first``..``last``.

    ``skip`` omits row numbers entirely (to simulate a gap in the extract);
    ``special`` replaces a row's narrative with awkward text.
    """
    skip = skip or set()
    special = special or {}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SOURCE_COLUMNS)
        writer.writeheader()
        for row_number in range(first, last + 1):
            if row_number in skip:
                continue
            writer.writerow(
                {
                    "row": str(row_number),
                    "source_label": "Mortgage",
                    "narrative": special.get(row_number, f"narrative for row {row_number}"),
                }
            )
    return path


def read_output(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Return the output file's header order and its rows."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        return header, list(reader)


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
        check=False,
    )


# ---------------------------------------------------------------------------
# The right rows
# ---------------------------------------------------------------------------

def test_selects_exactly_the_teams_thousand_rows(tmp_path: Path) -> None:
    source = write_source(tmp_path / "source.csv")
    out = tmp_path / "team_rows.csv"

    summary = extract_team_rows.extract(source, TEAM, out)

    assert summary["written"] == 1000
    assert summary["range"] == (TEAM_FIRST_ROW, TEAM_LAST_ROW)
    assert summary["missing_row_numbers"] == []

    _, rows = read_output(out)
    row_numbers = [int(row["row_number"]) for row in rows]
    assert len(row_numbers) == 1000
    assert row_numbers == sorted(row_numbers), "rows must be written in row order"
    assert row_numbers[0] == TEAM_FIRST_ROW
    assert row_numbers[-1] == TEAM_LAST_ROW
    # The bracketing rows either side of the range must not leak in.
    assert TEAM_FIRST_ROW - 1 not in row_numbers
    assert TEAM_LAST_ROW + 1 not in row_numbers


def test_a_different_team_gets_a_different_slice(tmp_path: Path) -> None:
    """Team n owns rows n*1000..n*1000+999 -- the slices must not overlap."""
    source = write_source(tmp_path / "source.csv", first=0, last=3999)

    out_one = tmp_path / "team1.csv"
    out_two = tmp_path / "team2.csv"
    extract_team_rows.extract(source, 1, out_one)
    extract_team_rows.extract(source, 2, out_two)

    _, rows_one = read_output(out_one)
    _, rows_two = read_output(out_two)
    numbers_one = {int(row["row_number"]) for row in rows_one}
    numbers_two = {int(row["row_number"]) for row in rows_two}

    assert numbers_one == set(range(1000, 2000))
    assert numbers_two == set(range(2000, 3000))
    assert not numbers_one & numbers_two


def test_column_order_is_exactly_row_number_narrative_raw_label(tmp_path: Path) -> None:
    """Pinned because analysis and the JMeter CSV Data Set Config both assume it.

    ``variableNames=row_number,narrative,raw_label`` in the .jmx maps columns by
    position, so a reordering here would quietly post the wrong field as the
    ticket narrative.
    """
    source = write_source(tmp_path / "source.csv", first=TEAM_FIRST_ROW, last=TEAM_LAST_ROW)
    out = tmp_path / "team_rows.csv"
    extract_team_rows.extract(source, TEAM, out)

    header, _ = read_output(out)
    assert header == EXPECTED_OUTPUT_COLUMNS
    assert extract_team_rows.OUTPUT_COLUMNS == EXPECTED_OUTPUT_COLUMNS
    # The raw label travels through under its new name, unchanged in value.
    first_physical_line = out.read_text(encoding="utf-8").splitlines()[0]
    assert first_physical_line == ",".join(EXPECTED_OUTPUT_COLUMNS)


# ---------------------------------------------------------------------------
# Lossless round trip
# ---------------------------------------------------------------------------

AWKWARD_NARRATIVE = (
    'The agent said "we will refund the fee", then closed the case.\n'
    "It was a charge of 1,250.00, applied twice, on 3 January.\n"
    "\tI still have the letter, reference A,B-99.\n"
    "Final line with a trailing comma,"
)


def test_narratives_with_newlines_and_commas_survive_the_round_trip(tmp_path: Path) -> None:
    target = TEAM_FIRST_ROW + 7
    source = write_source(
        tmp_path / "source.csv",
        first=TEAM_FIRST_ROW,
        last=TEAM_FIRST_ROW + 20,
        special={target: AWKWARD_NARRATIVE},
    )
    out = tmp_path / "team_rows.csv"
    extract_team_rows.extract(source, TEAM, out)

    _, rows = read_output(out)
    by_row = {int(row["row_number"]): row for row in rows}
    assert by_row[target]["narrative"] == AWKWARD_NARRATIVE
    # The quoted field spans physical lines, so the file has more lines than rows;
    # that is correct CSV and every reader in the repository uses the csv module.
    assert len(out.read_text(encoding="utf-8").splitlines()) > len(rows) + 1
    # Neighbouring rows are unaffected by the quoting.
    assert by_row[target + 1]["narrative"] == f"narrative for row {target + 1}"


def test_narrative_values_are_not_stripped_or_altered(tmp_path: Path) -> None:
    """Ticket length is a reported figure, so the text must be byte-for-byte intact."""
    target = TEAM_FIRST_ROW + 1
    padded = "  leading and trailing spaces matter for ticket_chars  "
    source = write_source(
        tmp_path / "source.csv",
        first=TEAM_FIRST_ROW,
        last=TEAM_FIRST_ROW + 3,
        special={target: padded},
    )
    out = tmp_path / "team_rows.csv"
    extract_team_rows.extract(source, TEAM, out)

    _, rows = read_output(out)
    narratives = {int(row["row_number"]): row["narrative"] for row in rows}
    assert narratives[target] == padded


# ---------------------------------------------------------------------------
# Loud failures
# ---------------------------------------------------------------------------

def test_a_missing_row_number_is_reported(tmp_path: Path) -> None:
    missing = {TEAM_FIRST_ROW + 500, TEAM_LAST_ROW}
    source = write_source(tmp_path / "source.csv", skip=missing)
    out = tmp_path / "team_rows.csv"

    summary = extract_team_rows.extract(source, TEAM, out)

    assert summary["written"] == 1000 - len(missing)
    assert summary["missing_row_numbers"] == sorted(missing)


def test_cli_reports_missing_rows_on_stderr_and_exits_non_zero(tmp_path: Path) -> None:
    """A short slice is not an error we may discover later from a chart."""
    missing = TEAM_FIRST_ROW + 123
    source = write_source(tmp_path / "source.csv", skip={missing})
    out = tmp_path / "team_rows.csv"

    proc = run_cli("--csv", str(source), "--team", str(TEAM), "--out", str(out))

    assert proc.returncode != 0
    assert str(missing) in proc.stderr
    assert "WARNING" in proc.stderr


def test_no_rows_in_range_is_fatal(tmp_path: Path) -> None:
    source = write_source(tmp_path / "source.csv", first=0, last=99)
    proc = run_cli("--csv", str(source), "--team", str(TEAM), "--out", str(tmp_path / "o.csv"))

    assert proc.returncode != 0
    assert "No rows found in range" in (proc.stderr + proc.stdout)
    assert not (tmp_path / "o.csv").exists()


def test_a_negative_team_number_exits_non_zero(tmp_path: Path) -> None:
    source = write_source(tmp_path / "source.csv", first=0, last=50)
    proc = run_cli("--csv", str(source), "--team", "-1", "--out", str(tmp_path / "o.csv"))
    assert proc.returncode != 0
    assert "non-negative" in (proc.stderr + proc.stdout)


def test_a_non_numeric_team_number_exits_non_zero(tmp_path: Path) -> None:
    source = write_source(tmp_path / "source.csv", first=0, last=50)
    proc = run_cli("--csv", str(source), "--team", "ten", "--out", str(tmp_path / "o.csv"))
    assert proc.returncode != 0
    assert "invalid int value" in proc.stderr


def test_a_missing_source_file_exits_non_zero(tmp_path: Path) -> None:
    proc = run_cli(
        "--csv", str(tmp_path / "absent.csv"),
        "--team", str(TEAM),
        "--out", str(tmp_path / "o.csv"),
    )
    assert proc.returncode != 0
    assert "not found" in (proc.stderr + proc.stdout)


def test_a_source_file_with_the_wrong_columns_exits_non_zero(tmp_path: Path) -> None:
    source = tmp_path / "wrong.csv"
    source.write_text("id,label,text\n10000,Mortgage,hello\n", encoding="utf-8")
    proc = run_cli("--csv", str(source), "--team", str(TEAM), "--out", str(tmp_path / "o.csv"))
    assert proc.returncode != 0
    assert "missing expected column" in (proc.stderr + proc.stdout)


def test_missing_required_arguments_exit_non_zero() -> None:
    assert run_cli().returncode != 0
    assert run_cli("--team", str(TEAM)).returncode != 0


def test_help_works_without_any_data() -> None:
    proc = run_cli("--help")
    assert proc.returncode == 0
    assert "--team" in proc.stdout and "--csv" in proc.stdout


# ---------------------------------------------------------------------------
# The committed artefact
# ---------------------------------------------------------------------------

def test_the_committed_team_rows_file_matches_the_contract(repo_root: Path) -> None:
    """The file every later step reads must have the shape we promised.

    This is a guard on the artefact, not on the extractor: if someone hand-edits
    data/team_rows.csv, the golden-set sampler and the load tests would be
    reading something we never verified.
    """
    team_rows = repo_root / "data" / "team_rows.csv"
    if not team_rows.is_file():
        pytest.skip("data/team_rows.csv is not present in this checkout")

    header, rows = read_output(team_rows)
    assert header == EXPECTED_OUTPUT_COLUMNS
    assert len(rows) == 1000
    row_numbers = [int(row["row_number"]) for row in rows]
    assert row_numbers == sorted(row_numbers)
    assert len(set(row_numbers)) == 1000
    # A 1,000-row slice must sit inside exactly one team's block of 1,000.
    assert row_numbers[0] // 1000 == row_numbers[-1] // 1000
    assert row_numbers[0] % 1000 == 0
    assert all(row["narrative"].strip() for row in rows), "no empty narratives"
