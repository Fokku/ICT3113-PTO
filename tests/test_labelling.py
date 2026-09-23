"""Tests for the golden-set labelling toolchain.

Covers all three scripts in ``labelling/scripts``:
``sample_golden_candidates.py``, ``agreement.py`` and ``build_golden_set.py``.

Everything is exercised against **fabricated** team rows and label sheets built
in ``tmp_path``.  Two fabricated things only are checked against the real
repository: that ``data/team_rows.csv`` still allocates the way our report says
it does, and that the shipped ``labelling/resolutions.csv`` template still parses.
No model is involved anywhere in this file, and nothing here touches
``golden/golden_set.csv``.

The kappa tests carry their arithmetic in comments.  The point of computing
Cohen's kappa from first principles is that the figure can be checked by hand;
a test that only compares the code against itself would defeat that.

Owner: Yeo Kai Yuan.  TODO(Yeo Kai Yuan): replace with real name.
"""

from __future__ import annotations

import csv
import importlib
import sys
from pathlib import Path
from typing import Iterable, Sequence

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "labelling" / "scripts"
for _path in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from service.categories import CATEGORIES  # noqa: E402

# Imported under their real module names, so that build_golden_set.py's own
# ``from agreement import ...`` and ``from sample_golden_candidates import ...``
# resolve to these same module objects. Loading them under aliased names would
# give us two copies of LabellingError and every ``except`` clause would miss.
sampler = importlib.import_module("sample_golden_candidates")
agreement = importlib.import_module("agreement")
build = importlib.import_module("build_golden_set")

CR, DC, MO, CC, BA, CL, MT = CATEGORIES


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def write_team_rows(path: Path, rows: Sequence[tuple[int, str, str]]) -> Path:
    """Write a fabricated ``data/team_rows.csv``."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(sampler.TEAM_ROW_COLUMNS)
        writer.writerows(rows)
    return path


def fabricate_team_rows(
    per_category: int = 30,
    start: int = 10000,
    categories: Sequence[str] = CATEGORIES,
) -> list[tuple[int, str, str]]:
    """``per_category`` rows for each category, with distinct narratives."""
    rows: list[tuple[int, str, str]] = []
    row_number = start
    for category in categories:
        for index in range(per_category):
            rows.append(
                (
                    row_number,
                    f"fabricated narrative {index} for {category}",
                    category,
                )
            )
            row_number += 1
    return rows


def write_sheet(path: Path, rows: Iterable[Sequence[object]]) -> Path:
    """Write a label sheet: rows of (row_number, narrative, label, confidence, notes)."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(sampler.SHEET_COLUMNS)
        writer.writerows(rows)
    return path


def write_paired_sheets(
    directory: Path,
    labels: Sequence[tuple[int, str, str]],
    confidences: Sequence[tuple[str, str]] | None = None,
) -> tuple[Path, Path]:
    """Write both sheets from ``(row_number, label_a, label_b)`` triples."""
    confidences = confidences or [("high", "high")] * len(labels)
    rows_a = []
    rows_b = []
    for (row_number, label_a, label_b), (conf_a, conf_b) in zip(labels, confidences):
        narrative = f"fabricated narrative for row {row_number}"
        rows_a.append((row_number, narrative, label_a, conf_a, f"note A {row_number}"))
        rows_b.append((row_number, narrative, label_b, conf_b, f"note B {row_number}"))
    return (
        write_sheet(directory / "labeller_A.csv", rows_a),
        write_sheet(directory / "labeller_B.csv", rows_b),
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def header_of(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return next(csv.reader(handle))


def write_resolutions(path: Path, rows: Iterable[Sequence[object]], comment: bool = True) -> Path:
    """Write a resolutions.csv, optionally with a comment line as the template has."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(build.RESOLUTION_COLUMNS)
        if comment:
            handle.write("# a comment line, as in the shipped template\n")
        writer.writerows(rows)
    return path


@pytest.fixture(autouse=True)
def _unfrozen(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralise the freeze guard's view of the *real* repository.

    ``build_golden_set.freeze_blockers`` asks git about the working repository,
    not about ``tmp_path``.  Without this fixture the whole build-script suite
    would begin failing the day the team creates the ``golden-freeze`` tag --
    a test failure that says nothing about the code.  The guard itself is tested
    explicitly in :func:`test_build_refuses_when_frozen`.
    """
    monkeypatch.setattr(build, "is_git_tracked", lambda path: False)
    monkeypatch.setattr(build, "freeze_tag_exists", lambda: False)


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------

def test_allocation_matches_hand_computation() -> None:
    """Largest-remainder allocation, checked by hand.

    available = {Credit reporting: 10, Debt collection: 7, Mortgage: 3}, total 20
    n = 10

        quota(Credit reporting) = 10 * 10 / 20 = 5.0  -> floor 5, remainder 0.0
        quota(Debt collection)  = 10 *  7 / 20 = 3.5  -> floor 3, remainder 0.5
        quota(Mortgage)         = 10 *  3 / 20 = 1.5  -> floor 1, remainder 0.5

    floors sum to 9, so one place is left over.  The two largest remainders tie
    at 0.5; the tie is broken by canonical category order, and Debt collection
    (index 1) precedes Mortgage (index 2), so Debt collection takes it.

        Credit reporting 5, Debt collection 4, Mortgage 1  -> 10
    """
    available = {CR: 10, DC: 7, MO: 3}
    assert sampler.allocate(available, 10) == {CR: 5, DC: 4, MO: 1}


def test_allocation_gives_every_stratum_at_least_one_row() -> None:
    """Repair pass (b): a stratum too small for a quota place still gets one."""
    # available total 100, n = 5. Mortgage's quota is 5 * 1 / 100 = 0.05, which
    # floors to 0 and loses the remainder race, so the minimum pass must lift it
    # to 1 by taking a place from the largest stratum.
    available = {CR: 60, DC: 39, MO: 1}
    allocation = sampler.allocate(available, 5)
    assert allocation[MO] >= sampler.MIN_PER_STRATUM
    assert sum(allocation.values()) == 5


def test_allocation_never_exceeds_available_rows() -> None:
    available = {CR: 4, DC: 4, MO: 2}
    allocation = sampler.allocate(available, 10)
    assert allocation == available  # n equals the total, so everything is drawn


def test_allocation_rejects_impossible_n() -> None:
    with pytest.raises(sampler.LabellingError):
        sampler.allocate({CR: 3, DC: 2}, 6)


def test_real_team_rows_allocate_to_the_reported_plan() -> None:
    """Guard the stratum sizes the report quotes.

    These are the numbers ``sample_golden_candidates.py`` printed when the sample
    was drawn, and they are quoted on Slide 6. If ``data/team_rows.csv`` ever
    changes, this test must fail: the drawn sample, and therefore the golden set,
    would no longer be the one we reported.
    """
    rows = sampler.read_team_rows(REPO_ROOT / "data" / "team_rows.csv")
    available = sampler.stratum_counts(rows)
    allocation = sampler.allocate(available, 200)
    assert allocation == {
        CR: 32,
        DC: 30,
        MO: 30,
        CC: 26,
        BA: 29,
        CL: 27,
        MT: 26,
    }
    assert sum(allocation.values()) == 200
    assert all(count >= 1 for count in allocation.values())


def test_unexpected_raw_label_is_an_error() -> None:
    rows = [sampler.TeamRow(10000, "narrative", "Payday loan")]
    with pytest.raises(sampler.LabellingError, match="not in service.categories"):
        sampler.stratum_counts(rows)


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------

def test_sampling_is_reproducible_for_a_given_seed(tmp_path: Path) -> None:
    rows = sampler.read_team_rows(write_team_rows(tmp_path / "team.csv", fabricate_team_rows()))
    first, _ = sampler.build_candidates(rows, 70, 3113)
    second, _ = sampler.build_candidates(rows, 70, 3113)
    assert [row.row_number for row in first] == [row.row_number for row in second]


def test_sampling_differs_for_another_seed(tmp_path: Path) -> None:
    rows = sampler.read_team_rows(write_team_rows(tmp_path / "team.csv", fabricate_team_rows()))
    # 10 of 30 rows drawn per stratum, so two seeds agreeing everywhere is
    # astronomically unlikely; a failure here means the seed is being ignored.
    with_default, _ = sampler.build_candidates(rows, 70, 3113)
    with_other, _ = sampler.build_candidates(rows, 70, 999)
    assert [r.row_number for r in with_default] != [r.row_number for r in with_other]


def test_sampling_ignores_input_order(tmp_path: Path) -> None:
    rows = sampler.read_team_rows(write_team_rows(tmp_path / "team.csv", fabricate_team_rows()))
    shuffled = list(reversed(rows))
    drawn, _ = sampler.build_candidates(rows, 70, 3113)
    drawn_shuffled, _ = sampler.build_candidates(shuffled, 70, 3113)
    assert [r.row_number for r in drawn] == [r.row_number for r in drawn_shuffled]


def test_stratification_covers_every_category_present(tmp_path: Path) -> None:
    rows = sampler.read_team_rows(write_team_rows(tmp_path / "team.csv", fabricate_team_rows()))
    drawn, strata = sampler.build_candidates(rows, 70, 3113)
    drawn_per_category: dict[str, int] = {}
    for row in drawn:
        drawn_per_category[row.raw_label] = drawn_per_category.get(row.raw_label, 0) + 1
    assert set(drawn_per_category) == set(CATEGORIES)
    assert all(count >= 1 for count in drawn_per_category.values())
    # The printed plan must agree with what was actually drawn, or the method
    # block in the report describes a sample we did not take.
    assert {stratum.category: stratum.drawn for stratum in strata} == drawn_per_category


def test_sampler_writes_sheets_without_raw_label(tmp_path: Path) -> None:
    team = write_team_rows(tmp_path / "team.csv", fabricate_team_rows())
    out = tmp_path / "labelling"
    code = sampler.main(["--team-rows", str(team), "--n", "70", "--out-dir", str(out)])
    assert code == 0

    sheet_a, sheet_b = out / "labeller_A.csv", out / "labeller_B.csv"
    candidates = out / "golden_candidates.csv"
    assert header_of(sheet_a) == list(sampler.SHEET_COLUMNS)
    assert header_of(sheet_b) == list(sampler.SHEET_COLUMNS)
    assert "raw_label" not in header_of(sheet_a)
    assert "raw_label" not in header_of(sheet_b)
    # The audit trail, by contrast, must carry raw_label.
    assert header_of(candidates) == list(sampler.CANDIDATE_COLUMNS)

    rows_a, rows_b = read_csv(sheet_a), read_csv(sheet_b)
    assert len(rows_a) == len(rows_b) == 70
    # Same rows, same order, so the two sheets can be paired by position or by
    # row number and a labeller never has to hunt for a row.
    assert [r["row_number"] for r in rows_a] == [r["row_number"] for r in rows_b]
    assert all(r["narrative"] for r in rows_a)
    assert all(
        r["label"] == "" and r["confidence"] == "" and r["notes"] == ""
        for r in rows_a + rows_b
    )
    assert {r["row_number"] for r in rows_a} == {r["row_number"] for r in read_csv(candidates)}


def test_sampler_is_byte_identical_on_a_second_run(tmp_path: Path) -> None:
    team = write_team_rows(tmp_path / "team.csv", fabricate_team_rows())
    out = tmp_path / "labelling"
    argv = ["--team-rows", str(team), "--n", "70", "--out-dir", str(out)]
    assert sampler.main(argv) == 0
    before = {p.name: p.read_bytes() for p in sorted(out.glob("*.csv"))}
    assert sampler.main(argv) == 0  # blank sheets carry no work, so no --force needed
    after = {p.name: p.read_bytes() for p in sorted(out.glob("*.csv"))}
    assert before == after


def test_sampler_refuses_to_overwrite_a_started_sheet(tmp_path: Path) -> None:
    team = write_team_rows(tmp_path / "team.csv", fabricate_team_rows())
    out = tmp_path / "labelling"
    argv = ["--team-rows", str(team), "--n", "70", "--out-dir", str(out)]
    assert sampler.main(argv) == 0

    # Simulate a labeller who has started work on sheet A.
    sheet_a = out / "labeller_A.csv"
    rows = read_csv(sheet_a)
    rows[0]["label"] = CR
    rows[0]["confidence"] = "high"
    write_sheet(sheet_a, [[r[c] for c in sampler.SHEET_COLUMNS] for r in rows])
    started = sheet_a.read_bytes()

    assert sampler.main(argv) == 3
    assert sheet_a.read_bytes() == started  # the work is still there
    assert sampler.main(argv + ["--force"]) == 0
    assert sheet_a.read_bytes() != started  # --force really does overwrite


def test_sampler_warns_when_n_is_outside_the_brief_range(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    team = write_team_rows(tmp_path / "team.csv", fabricate_team_rows())
    assert sampler.main(
        ["--team-rows", str(team), "--n", "70", "--out-dir", str(tmp_path / "out")]
    ) == 0
    assert "outside the brief's 150-200" in capsys.readouterr().err


def test_sampler_prints_its_method(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The printed method block is what the report quotes, so it must be there."""
    team = write_team_rows(tmp_path / "team.csv", fabricate_team_rows())
    sampler.main(["--team-rows", str(team), "--n", "70", "--out-dir", str(tmp_path / "out")])
    out = capsys.readouterr().out
    for expected in ("Sampling method", "largest-remainder", "random.Random(3113)", "quota"):
        assert expected in out


# ---------------------------------------------------------------------------
# Label validation shared by the toolchain
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value, expected",
    [
        ("Credit card", CC),
        ("credit card", CC),  # case-insensitive exact match is accepted
        ("  Money transfer or service  ", MT),  # surrounding whitespace is ignored
        ("creditcard", None),  # no aliasing: a typo is reported, not guessed
        ("Credit", None),
        ("UNPARSEABLE", None),  # a model-output value, never a human label
        ("", None),
        (None, None),
    ],
)
def test_canonical_label(value: str | None, expected: str | None) -> None:
    assert sampler.canonical_label(value) == expected


def test_confidence_rank_orders_low_first() -> None:
    ranks = [sampler.confidence_rank(v) for v in ("low", "medium", "high", "", "wobbly")]
    assert ranks[0] < ranks[1] < ranks[2]
    assert ranks[3] == ranks[4] > ranks[2]  # blank and unrecognised sort last


def test_sheet_with_changed_header_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "sheet.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["row_number", "narrative", "label", "confidence"])  # notes missing
        writer.writerow([10000, "narrative", CR, "high"])
    with pytest.raises(sampler.LabellingError, match="must be exactly"):
        sampler.read_label_sheet(path)


# ---------------------------------------------------------------------------
# Cohen's kappa
# ---------------------------------------------------------------------------

#: The worked example used by the kappa tests. Ten rows, three categories.
#:
#:   row  A                  B
#:   1    Credit reporting   Credit reporting   agree
#:   2    Credit reporting   Credit reporting   agree
#:   3    Credit reporting   Credit reporting   agree
#:   4    Credit reporting   Credit reporting   agree
#:   5    Credit reporting   Debt collection    disagree
#:   6    Credit reporting   Mortgage           disagree
#:   7    Debt collection    Debt collection    agree
#:   8    Debt collection    Debt collection    agree
#:   9    Mortgage           Mortgage           agree
#:   10   Mortgage           Credit reporting   disagree
WORKED_EXAMPLE: tuple[tuple[int, str, str], ...] = (
    (10001, CR, CR),
    (10002, CR, CR),
    (10003, CR, CR),
    (10004, CR, CR),
    (10005, CR, DC),
    (10006, CR, MO),
    (10007, DC, DC),
    (10008, DC, DC),
    (10009, MO, MO),
    (10010, MO, CR),
)
WORKED_CONFIDENCE: tuple[tuple[str, str], ...] = (
    ("high", "high"),
    ("high", "high"),
    ("high", "high"),
    ("high", "high"),
    ("low", "medium"),     # row 10005: least confident disagreement
    ("medium", "low"),     # row 10006: next least confident
    ("high", "high"),
    ("high", "high"),
    ("high", "high"),
    ("high", "high"),      # row 10010: a confident disagreement, so last
)


def pairs_from(labels: Sequence[tuple[int, str, str]]) -> list[agreement.Pair]:
    return [
        agreement.Pair(
            row_number=row_number,
            label_a=label_a,
            label_b=label_b,
            confidence_a="high",
            confidence_b="high",
            notes_a="",
            notes_b="",
            narrative=f"narrative {row_number}",
        )
        for row_number, label_a, label_b in labels
    ]


def test_kappa_matches_the_hand_computed_value() -> None:
    """Cohen's kappa on the worked example above, computed by hand.

    N = 10, agreements = 7 (rows 1, 2, 3, 4, 7, 8, 9)

        Po = 7 / 10 = 0.7

    Marginals
        A: Credit reporting 6, Debt collection 2, Mortgage 2
        B: Credit reporting 5, Debt collection 3, Mortgage 2
        (the other four categories are unused, contributing 0 to Pe)

        Pe = (6/10)(5/10) + (2/10)(3/10) + (2/10)(2/10)
           = 0.30 + 0.06 + 0.04
           = 0.40

        kappa = (Po - Pe) / (1 - Pe) = (0.7 - 0.4) / (1 - 0.4)
              = 0.3 / 0.6
              = 0.5
    """
    result = agreement.cohen_kappa(pairs_from(WORKED_EXAMPLE))
    assert result.n == 10
    assert result.n_agree == 7
    assert result.po == pytest.approx(0.7)
    assert result.pe == pytest.approx(0.4)
    assert result.kappa == pytest.approx(0.5)
    assert result.marginals_a[CR] == 6
    assert result.marginals_b[CR] == 5
    assert agreement.interpret(result.kappa) == "moderate"


def test_per_category_kappa_matches_the_hand_computed_value() -> None:
    """One-vs-rest kappa for "Credit reporting" on the same worked example.

    Collapse to "Credit reporting or not":

        in A and in B (rows 1-4)          = 4
        in A only     (rows 5, 6)         = 2
        in B only     (row 10)            = 1
        in neither    (rows 7, 8, 9)      = 3

        n_A = 6, n_B = 5, N = 10
        Po = (4 + 3) / 10 = 0.7
        Pe = (6/10)(5/10) + (4/10)(5/10) = 0.30 + 0.20 = 0.50
        kappa = (0.7 - 0.5) / (1 - 0.5) = 0.2 / 0.5 = 0.4
    """
    entry = agreement.category_agreement(pairs_from(WORKED_EXAMPLE), CR)
    assert (entry.n_a, entry.n_b, entry.both, entry.neither) == (6, 5, 4, 3)
    assert entry.po == pytest.approx(0.7)
    assert entry.pe == pytest.approx(0.5)
    assert entry.kappa == pytest.approx(0.4)


def test_per_category_kappa_is_not_available_for_an_unused_category() -> None:
    entry = agreement.category_agreement(pairs_from(WORKED_EXAMPLE), MT)
    assert entry.kappa is None
    assert entry.reason == "neither labeller used this category"


def test_kappa_of_perfect_agreement_is_one() -> None:
    # Both labellers use several categories and always agree: Po = 1, and Pe < 1
    # because no single category dominates, so kappa = (1 - Pe)/(1 - Pe) = 1.
    labels = [(10000 + i, category, category) for i, category in enumerate(CATEGORIES)]
    result = agreement.cohen_kappa(pairs_from(labels))
    assert result.po == pytest.approx(1.0)
    assert result.kappa == pytest.approx(1.0)
    assert agreement.interpret(result.kappa) == "almost perfect"


def test_kappa_of_chance_agreement_is_zero() -> None:
    """Agreement exactly at the chance level gives kappa = 0.

        row  A                 B
        1    Credit reporting  Credit reporting   agree
        2    Credit reporting  Debt collection
        3    Debt collection   Credit reporting
        4    Debt collection   Debt collection    agree

        Po = 2/4 = 0.5
        Pe = (2/4)(2/4) + (2/4)(2/4) = 0.25 + 0.25 = 0.5
        kappa = (0.5 - 0.5) / (1 - 0.5) = 0.0
    """
    labels = [(10001, CR, CR), (10002, CR, DC), (10003, DC, CR), (10004, DC, DC)]
    result = agreement.cohen_kappa(pairs_from(labels))
    assert result.po == pytest.approx(0.5)
    assert result.pe == pytest.approx(0.5)
    assert result.kappa == pytest.approx(0.0, abs=1e-12)


def test_kappa_is_undefined_when_both_labellers_use_one_category(tmp_path: Path) -> None:
    labels = [(10000 + i, CR, CR) for i in range(5)]
    result = agreement.cohen_kappa(pairs_from(labels))
    assert result.pe == pytest.approx(1.0)
    assert result.degenerate and result.kappa is None

    sheet_a, sheet_b = write_paired_sheets(tmp_path, labels)
    code = agreement.main(
        ["--a", str(sheet_a), "--b", str(sheet_b), "--out-dir", str(tmp_path)]
    )
    assert code == 4  # no statistic to report, so do not exit 0


def test_confusion_matrix_counts_the_worked_example() -> None:
    matrix = agreement.confusion_matrix(pairs_from(WORKED_EXAMPLE))
    assert matrix[CR][CR] == 4
    assert matrix[CR][DC] == 1
    assert matrix[CR][MO] == 1
    assert matrix[MO][CR] == 1
    assert sum(sum(row.values()) for row in matrix.values()) == 10


def test_agreement_refuses_blank_labels(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    labels = list(WORKED_EXAMPLE)
    sheet_a, sheet_b = write_paired_sheets(tmp_path, labels)
    # Blank one cell in each sheet, on different rows.
    rows_a = read_csv(sheet_a)
    rows_a[2]["label"] = ""
    write_sheet(sheet_a, [[r[c] for c in sampler.SHEET_COLUMNS] for r in rows_a])
    rows_b = read_csv(sheet_b)
    rows_b[8]["label"] = "   "
    write_sheet(sheet_b, [[r[c] for c in sampler.SHEET_COLUMNS] for r in rows_b])

    code = agreement.main(
        ["--a", str(sheet_a), "--b", str(sheet_b), "--out-dir", str(tmp_path)]
    )
    assert code == 4
    err = capsys.readouterr().err
    assert "incomplete" in err
    assert "10003" in err and "10009" in err  # it says WHICH rows are blank
    assert not (tmp_path / "disagreements.csv").exists()  # no partial output


def test_agreement_refuses_an_invalid_label(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    labels = list(WORKED_EXAMPLE)
    sheet_a, sheet_b = write_paired_sheets(tmp_path, labels)
    rows_a = read_csv(sheet_a)
    rows_a[0]["label"] = "Credit cards and reporting"
    write_sheet(sheet_a, [[r[c] for c in sampler.SHEET_COLUMNS] for r in rows_a])

    assert agreement.main(
        ["--a", str(sheet_a), "--b", str(sheet_b), "--out-dir", str(tmp_path)]
    ) == 4
    err = capsys.readouterr().err
    assert "not one of the seven categories" in err
    assert "10001" in err


def test_agreement_refuses_sheets_covering_different_rows(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sheet_a, sheet_b = write_paired_sheets(tmp_path, list(WORKED_EXAMPLE))
    rows_b = read_csv(sheet_b)
    rows_b[0]["row_number"] = "19999"
    write_sheet(sheet_b, [[r[c] for c in sampler.SHEET_COLUMNS] for r in rows_b])

    assert agreement.main(
        ["--a", str(sheet_a), "--b", str(sheet_b), "--out-dir", str(tmp_path)]
    ) == 4
    assert "do not cover the same rows" in capsys.readouterr().err


def test_disagreements_csv_content_and_order(tmp_path: Path) -> None:
    sheet_a, sheet_b = write_paired_sheets(
        tmp_path, list(WORKED_EXAMPLE), list(WORKED_CONFIDENCE)
    )
    assert agreement.main(
        ["--a", str(sheet_a), "--b", str(sheet_b), "--out-dir", str(tmp_path)]
    ) == 0

    out = tmp_path / "disagreements.csv"
    assert header_of(out) == list(agreement.DISAGREEMENT_COLUMNS)
    rows = read_csv(out)
    assert len(rows) == 3  # rows 10005, 10006, 10010 of the worked example
    # Ordered by the LOWER of the two confidences: 10005 (low/medium) then
    # 10006 (medium/low) then 10010 (high/high).
    assert [r["row_number"] for r in rows] == ["10005", "10006", "10010"]
    first = rows[0]
    assert first["label_A"] == CR and first["label_B"] == DC
    assert first["confidence_A"] == "low" and first["confidence_B"] == "medium"
    assert first["notes_A"] == "note A 10005" and first["notes_B"] == "note B 10005"
    assert first["narrative_prefix"] == "fabricated narrative for row 10005"


def test_narrative_prefix_collapses_whitespace_and_truncates() -> None:
    text = "line one\n\nline   two\ttabbed " + ("x" * 500)
    prefix = agreement.narrative_prefix(text, limit=20)
    assert "\n" not in prefix and "  " not in prefix
    assert prefix.startswith("line one line two")
    assert prefix.endswith("...")
    assert len(prefix) == 23  # 20 characters plus the ellipsis


# ---------------------------------------------------------------------------
# build_golden_set
# ---------------------------------------------------------------------------

GOLDEN_SIZE = 160


def golden_fixture(
    tmp_path: Path,
    *,
    size: int = GOLDEN_SIZE,
    disagree_rows: Sequence[int] = (10003, 10007),
) -> tuple[Path, Path, Path]:
    """Team rows plus two sheets that agree everywhere except ``disagree_rows``."""
    rows = [
        (10000 + index, f"fabricated narrative {index}", CATEGORIES[index % len(CATEGORIES)])
        for index in range(size)
    ]
    team = write_team_rows(tmp_path / "team_rows.csv", rows)
    labels: list[tuple[int, str, str]] = []
    for row_number, _, category in rows:
        other = CATEGORIES[(CATEGORIES.index(category) + 1) % len(CATEGORIES)]
        labels.append(
            (row_number, category, other if row_number in disagree_rows else category)
        )
    sheet_a, sheet_b = write_paired_sheets(tmp_path, labels)
    return team, sheet_a, sheet_b


def build_argv(tmp_path: Path, team: Path, a: Path, b: Path, resolutions: Path) -> list[str]:
    return [
        "--a", str(a),
        "--b", str(b),
        "--resolutions", str(resolutions),
        "--out", str(tmp_path / "golden_set.csv"),
        "--team-rows", str(team),
    ]


def test_build_happy_path(tmp_path: Path) -> None:
    team, sheet_a, sheet_b = golden_fixture(tmp_path)
    resolutions = write_resolutions(
        tmp_path / "resolutions.csv",
        [
            (10003, CC, "fabricated fixture: E1 applies", "none"),
            (10007, "EXCLUDE", "fabricated fixture: E2 applies", "R2"),
        ],
    )
    (tmp_path / "resolutions.md").write_text(
        "- **Row number:** 10003\n- **Row number:** 10007\n", encoding="utf-8"
    )
    assert build.main(build_argv(tmp_path, team, sheet_a, sheet_b, resolutions)) == 0

    out = tmp_path / "golden_set.csv"
    rows = read_csv(out)
    assert len(rows) == GOLDEN_SIZE - 1  # one row excluded by resolution
    assert dict(zip([r["row_number"] for r in rows], [r["label"] for r in rows]))["10003"] == CC
    assert "10007" not in {r["row_number"] for r in rows}
    # Row numbers ascending, so the file is diffable and checkable by eye.
    numbers = [int(r["row_number"]) for r in rows]
    assert numbers == sorted(numbers)


def test_golden_set_has_exactly_two_columns(tmp_path: Path) -> None:
    team, sheet_a, sheet_b = golden_fixture(tmp_path, disagree_rows=())
    resolutions = write_resolutions(tmp_path / "resolutions.csv", [])
    assert build.main(build_argv(tmp_path, team, sheet_a, sheet_b, resolutions)) == 0
    assert header_of(tmp_path / "golden_set.csv") == ["row_number", "label"]
    assert list(build.GOLDEN_COLUMNS) == ["row_number", "label"]


def test_build_rejects_unresolved_disagreements(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    team, sheet_a, sheet_b = golden_fixture(tmp_path)
    resolutions = write_resolutions(
        tmp_path / "resolutions.csv",
        [(10003, CC, "only one of the two is resolved", "none")],
    )
    assert build.main(build_argv(tmp_path, team, sheet_a, sheet_b, resolutions)) == 4
    err = capsys.readouterr().err
    assert "no entry in resolutions.csv" in err
    assert "10007" in err  # it names the unresolved row
    assert not (tmp_path / "golden_set.csv").exists()


def test_build_rejects_an_invalid_resolution_label(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    team, sheet_a, sheet_b = golden_fixture(tmp_path, disagree_rows=(10003,))
    resolutions = write_resolutions(
        tmp_path / "resolutions.csv",
        [(10003, "UNPARSEABLE", "a model value, not a human label", "none")],
    )
    assert build.main(build_argv(tmp_path, team, sheet_a, sheet_b, resolutions)) == 4
    err = capsys.readouterr().err
    assert "is not one of the seven categories" in err
    assert "model-output value" in err


def test_build_rejects_an_empty_resolution_note(tmp_path: Path) -> None:
    team, sheet_a, sheet_b = golden_fixture(tmp_path, disagree_rows=(10003,))
    resolutions = write_resolutions(tmp_path / "resolutions.csv", [(10003, CC, "", "none")])
    assert build.main(build_argv(tmp_path, team, sheet_a, sheet_b, resolutions)) == 4


def test_build_rejects_a_row_outside_the_team_slice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    team, sheet_a, sheet_b = golden_fixture(tmp_path, disagree_rows=())
    # Both labellers labelled a row that is not in the team slice at all.
    for sheet in (sheet_a, sheet_b):
        rows = read_csv(sheet)
        rows.append(
            {
                "row_number": "99999",
                "narrative": "a row from somebody else's slice",
                "label": CR,
                "confidence": "high",
                "notes": "",
            }
        )
        write_sheet(sheet, [[r[c] for c in sampler.SHEET_COLUMNS] for r in rows])
    resolutions = write_resolutions(tmp_path / "resolutions.csv", [])
    assert build.main(build_argv(tmp_path, team, sheet_a, sheet_b, resolutions)) == 4
    assert "not in data/team_rows.csv" in capsys.readouterr().err


def test_build_rejects_an_out_of_range_size(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    team, sheet_a, sheet_b = golden_fixture(tmp_path, size=10, disagree_rows=())
    resolutions = write_resolutions(tmp_path / "resolutions.csv", [])
    assert build.main(build_argv(tmp_path, team, sheet_a, sheet_b, resolutions)) == 4
    err = capsys.readouterr().err
    assert "outside the brief's 150-200 range" in err
    assert "would hold 10 rows" in err


def test_build_rejects_a_resolution_for_an_unknown_row(tmp_path: Path) -> None:
    team, sheet_a, sheet_b = golden_fixture(tmp_path, disagree_rows=())
    resolutions = write_resolutions(
        tmp_path / "resolutions.csv", [(88888, CR, "not a sampled row", "none")]
    )
    assert build.main(build_argv(tmp_path, team, sheet_a, sheet_b, resolutions)) == 4


def test_build_ignores_a_resolution_where_the_labellers_agreed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    team, sheet_a, sheet_b = golden_fixture(tmp_path, disagree_rows=())
    agreed_label = read_csv(sheet_a)[0]["label"]
    resolutions = write_resolutions(
        tmp_path / "resolutions.csv",
        [(10000, MT, "an override that the merge rules do not allow", "none")],
    )
    assert build.main(build_argv(tmp_path, team, sheet_a, sheet_b, resolutions)) == 0
    rows = read_csv(tmp_path / "golden_set.csv")
    assert rows[0]["row_number"] == "10000"
    assert rows[0]["label"] == agreed_label  # the agreed label stands
    assert "IGNORED" in capsys.readouterr().err


def test_build_excludes_an_agreed_row_when_asked(tmp_path: Path) -> None:
    team, sheet_a, sheet_b = golden_fixture(tmp_path, disagree_rows=())
    resolutions = write_resolutions(
        tmp_path / "resolutions.csv",
        [(10000, "EXCLUDE", "E2: the protocol says this row cannot be labelled", "R3")],
    )
    assert build.main(build_argv(tmp_path, team, sheet_a, sheet_b, resolutions)) == 0
    rows = read_csv(tmp_path / "golden_set.csv")
    assert len(rows) == GOLDEN_SIZE - 1
    assert "10000" not in {r["row_number"] for r in rows}


def test_build_warns_when_the_md_and_csv_records_disagree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    team, sheet_a, sheet_b = golden_fixture(tmp_path, disagree_rows=(10003,))
    resolutions = write_resolutions(
        tmp_path / "resolutions.csv", [(10003, CC, "resolved in the csv only", "none")]
    )
    # The .md writes up a different row, and omits the one that was resolved.
    (tmp_path / "resolutions.md").write_text("- **Row number:** 10011\n", encoding="utf-8")
    assert build.main(build_argv(tmp_path, team, sheet_a, sheet_b, resolutions)) == 0
    err = capsys.readouterr().err
    assert "not written up in resolutions.md" in err
    assert "no line in resolutions.csv" in err


def test_build_warns_when_the_md_record_is_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    team, sheet_a, sheet_b = golden_fixture(tmp_path, disagree_rows=())
    resolutions = write_resolutions(tmp_path / "resolutions.csv", [])
    assert build.main(build_argv(tmp_path, team, sheet_a, sheet_b, resolutions)) == 0
    assert "resolutions.md not found" in capsys.readouterr().err


def test_build_refuses_when_frozen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    team, sheet_a, sheet_b = golden_fixture(tmp_path, disagree_rows=())
    resolutions = write_resolutions(tmp_path / "resolutions.csv", [])
    argv = build_argv(tmp_path, team, sheet_a, sheet_b, resolutions)

    monkeypatch.setattr(build, "freeze_tag_exists", lambda: True)
    assert build.main(argv) == 3
    assert "REFUSING to rebuild" in capsys.readouterr().err
    assert not (tmp_path / "golden_set.csv").exists()

    assert build.main(argv + ["--force"]) == 0
    assert (tmp_path / "golden_set.csv").exists()


def test_build_refuses_when_the_output_is_committed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    team, sheet_a, sheet_b = golden_fixture(tmp_path, disagree_rows=())
    resolutions = write_resolutions(tmp_path / "resolutions.csv", [])
    out = tmp_path / "golden_set.csv"
    out.write_text("row_number,label\n10000,Mortgage\n", encoding="utf-8")
    monkeypatch.setattr(build, "is_git_tracked", lambda path: True)
    assert build.main(build_argv(tmp_path, team, sheet_a, sheet_b, resolutions)) == 3
    # The committed file is untouched.
    assert out.read_text(encoding="utf-8") == "row_number,label\n10000,Mortgage\n"


def test_shipped_resolutions_template_parses_to_no_resolutions() -> None:
    """The committed template must be readable and must resolve nothing yet."""
    csv_path = REPO_ROOT / "labelling" / "resolutions.csv"
    assert build.read_resolutions(csv_path) == []
    md_path = REPO_ROOT / "labelling" / "resolutions.md"
    assert build.read_resolution_md_rows(md_path) == set()


def test_resolutions_md_row_pattern_matches_the_documented_shape() -> None:
    """build_golden_set and resolutions.md must agree on this one line shape."""
    text = "- **Row number:** 10123\n* **Row number:**  10456 \n- **Row number:** TODO\n"
    assert build.MD_ROW_RE.findall(text) == ["10123", "10456"]


# ---------------------------------------------------------------------------
# CLI contract
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module", [sampler, agreement, build], ids=lambda m: m.__name__)
def test_help_works_without_network_or_data(module: object) -> None:
    """--help must work from an import alone: no files read, no network."""
    with pytest.raises(SystemExit) as excinfo:
        module.main(["--help"])  # type: ignore[attr-defined]
    assert excinfo.value.code == 0
