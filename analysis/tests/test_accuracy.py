"""Tests for ``analysis/accuracy.py``.

Every fixture here is fabricated with the builders in ``conftest.py``: no model
runs, and none of these numbers is ever reported. The arithmetic is checked
against a confusion matrix small enough to verify by hand (see
:func:`_hand_checked_records`), so a change in the metric definitions cannot pass
unnoticed.
"""

from __future__ import annotations

import csv
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

from conftest import BASE_TIME, iso_ms, make_log_line, make_metadata, write_service_log

from analysis import accuracy
from service.categories import CATEGORIES, UNPARSEABLE

import json

CREDIT_REPORTING, DEBT_COLLECTION, MORTGAGE, CREDIT_CARD = CATEGORIES[:4]


# ---------------------------------------------------------------------------
# Local builders (an accuracy run directory is not a load-test run directory, so
# conftest's build_run_dir does not apply; everything inside it still comes from
# conftest's builders).
# ---------------------------------------------------------------------------

def build_accuracy_dir(
    root: Path,
    records: list[dict],
    *,
    model: str = "testmodel-1b",
    stamp: str = "20261001T090000Z",
    model_tag: str = "testmodel:1b",
    mode: str = "real",
    write_metadata: bool = True,
) -> Path:
    """Write one ``results/accuracy/<model>_<stamp>`` directory."""
    run_dir = root / f"{model}_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    write_service_log(run_dir / "service.jsonl", records)
    if write_metadata:
        meta = make_metadata(model_tag=model_tag, mode=mode, plan="accuracy")
        (run_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return run_dir


def response(
    row_number: str,
    predicted: str | None,
    *,
    seconds: int = 0,
    request_id: str | None = None,
    raw: str | None = None,
    error: str | None = None,
    status: int = 200,
    **overrides,
) -> dict:
    """One ``POST /tickets`` log line for the golden row ``row_number``."""
    return make_log_line(
        ts=iso_ms(BASE_TIME + timedelta(seconds=seconds)),
        request_id=request_id or f"req-{row_number}-{seconds}",
        source_row=row_number,
        status=status,
        predicted_category=predicted,
        raw_model_output=raw if raw is not None else predicted,
        error=error,
        **overrides,
    )


def _hand_checked_records() -> tuple[list[tuple[str, str]], list[dict]]:
    """Ten golden rows and their predictions, with figures checkable by hand.

    Confusion matrix (rows golden, columns predicted):

    =======================  ==  ==  ==  ===========
    golden \\ predicted      CR  DC  MO  UNPARSEABLE
    =======================  ==  ==  ==  ===========
    Credit reporting (4)      2   1   0            1
    Debt collection  (3)      1   2   0            0
    Mortgage         (3)      0   0   3            0
    =======================  ==  ==  ==  ===========

    So: evaluated 10, correct 7, accuracy 0.7, one UNPARSEABLE, accuracy over the
    parseable nine 7/9; recall 0.5 / 2-3 / 1.0 and precision 2-3 / 2-3 / 1.0.
    """
    golden = (
        [(f"1000{i}", CREDIT_REPORTING) for i in range(4)]
        + [(f"2000{i}", DEBT_COLLECTION) for i in range(3)]
        + [(f"3000{i}", MORTGAGE) for i in range(3)]
    )
    predictions = [
        CREDIT_REPORTING, CREDIT_REPORTING, DEBT_COLLECTION, UNPARSEABLE,
        DEBT_COLLECTION, DEBT_COLLECTION, CREDIT_REPORTING,
        MORTGAGE, MORTGAGE, MORTGAGE,
    ]
    records = [
        response(row, predicted, seconds=index)
        for index, ((row, _), predicted) in enumerate(zip(golden, predictions))
    ]
    return golden, records


def read_csv(path: Path) -> pd.DataFrame:
    """Read an output CSV as text, so nothing is coerced on the way in."""
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def overall_row(out_dir: Path, run_name: str) -> dict[str, str]:
    """The single row of one run's ``overall.csv``."""
    frame = read_csv(out_dir / run_name / "overall.csv")
    assert len(frame) == 1
    return frame.iloc[0].to_dict()


# ---------------------------------------------------------------------------
# The clean case
# ---------------------------------------------------------------------------

def test_clean_run_scores_every_row_and_exits_zero(tmp_path, golden_csv):
    pairs = [("10000", CREDIT_REPORTING), ("10001", MORTGAGE), ("10002", CREDIT_CARD)]
    golden = golden_csv(pairs)
    results = tmp_path / "results" / "accuracy"
    run_dir = build_accuracy_dir(
        results,
        [response(row, label, seconds=index) for index, (row, label) in enumerate(pairs)],
    )
    out_dir = tmp_path / "out"

    code = accuracy.main(
        [
            "--results", str(results),
            "--golden", str(golden),
            "--out-dir", str(out_dir),
            "--no-charts",
        ]
    )

    assert code == 0
    row = overall_row(out_dir, run_dir.name)
    assert row["golden_rows"] == "3"
    assert row["evaluated"] == "3"
    assert float(row["coverage"]) == 1.0
    assert float(row["accuracy"]) == 1.0
    assert row["unparseable"] == "0"
    for name in (
        "confusion_matrix.csv", "confusion_matrix.md", "per_category.csv",
        "overall.csv", "misclassified.csv", "duplicates.csv", "missing_rows.csv",
        "unmatched_responses.csv", "errored_responses.csv", "report.md",
    ):
        assert (out_dir / run_dir.name / name).is_file(), name
    assert (out_dir / "model_comparison.csv").is_file()
    assert (out_dir / "accuracy_report.md").is_file()
    # Nothing was wrong, so the file a human reads has a header and no rows.
    assert read_csv(out_dir / run_dir.name / "misclassified.csv").empty


def test_hand_checked_matrix_recall_precision_and_support(tmp_path, golden_csv):
    pairs, records = _hand_checked_records()
    golden = golden_csv(pairs)
    results = tmp_path / "results" / "accuracy"
    run_dir = build_accuracy_dir(results, records)
    out_dir = tmp_path / "out"

    assert accuracy.main(
        ["--results", str(results), "--golden", str(golden),
         "--out-dir", str(out_dir), "--no-charts"]
    ) == 0

    row = overall_row(out_dir, run_dir.name)
    assert row["evaluated"] == "10"
    assert row["correct"] == "7"
    assert float(row["accuracy"]) == pytest.approx(0.7)
    assert row["unparseable"] == "1"
    assert float(row["unparseable_rate"]) == pytest.approx(0.1)
    assert float(row["accuracy_excl_unparseable"]) == pytest.approx(7 / 9)
    assert float(row["macro_recall"]) == pytest.approx((0.5 + 2 / 3 + 1.0) / 3)
    assert float(row["macro_precision"]) == pytest.approx((2 / 3 + 2 / 3 + 1.0) / 3)

    per_category = read_csv(out_dir / run_dir.name / "per_category.csv").set_index("category")
    assert per_category.loc[CREDIT_REPORTING, "support"] == "4"
    assert per_category.loc[CREDIT_REPORTING, "predicted_as"] == "3"
    assert float(per_category.loc[CREDIT_REPORTING, "recall"]) == pytest.approx(0.5)
    assert float(per_category.loc[CREDIT_REPORTING, "precision"]) == pytest.approx(2 / 3)
    assert per_category.loc[CREDIT_REPORTING, "unparseable"] == "1"
    assert float(per_category.loc[DEBT_COLLECTION, "recall"]) == pytest.approx(2 / 3)
    assert float(per_category.loc[DEBT_COLLECTION, "precision"]) == pytest.approx(2 / 3)
    assert float(per_category.loc[MORTGAGE, "recall"]) == pytest.approx(1.0)
    assert float(per_category.loc[MORTGAGE, "precision"]) == pytest.approx(1.0)
    # A category with no golden rows must not be reported as 0.0 recall: "we did
    # not test it" and "we got it all wrong" are different findings.
    assert per_category.loc[CREDIT_CARD, "support"] == "0"
    assert per_category.loc[CREDIT_CARD, "recall"] == ""


def test_confusion_matrix_axes_and_unparseable_column(tmp_path, golden_csv):
    pairs, records = _hand_checked_records()
    golden = golden_csv(pairs)
    results = tmp_path / "results" / "accuracy"
    run_dir = build_accuracy_dir(results, records)
    out_dir = tmp_path / "out"

    assert accuracy.main(
        ["--results", str(results), "--golden", str(golden),
         "--out-dir", str(out_dir), "--no-charts"]
    ) == 0

    matrix = read_csv(out_dir / run_dir.name / "confusion_matrix.csv")
    # Axes in service.categories order, with UNPARSEABLE appended as a
    # predicted-only column and never as a row.
    assert list(matrix.columns) == ["golden_label", *CATEGORIES, UNPARSEABLE]
    assert list(matrix["golden_label"]) == list(CATEGORIES)
    indexed = matrix.set_index("golden_label")
    assert indexed.loc[CREDIT_REPORTING, UNPARSEABLE] == "1"
    assert indexed.loc[CREDIT_REPORTING, DEBT_COLLECTION] == "1"
    assert indexed.loc[DEBT_COLLECTION, CREDIT_REPORTING] == "1"
    assert indexed.loc[MORTGAGE, MORTGAGE] == "3"
    # The UNPARSEABLE reply is not attributed to any category the model did not
    # name: every other cell of that golden row is accounted for.
    assert indexed.loc[CREDIT_REPORTING, CREDIT_REPORTING] == "2"
    assert indexed.loc[CREDIT_REPORTING, MORTGAGE] == "0"


def test_confusion_matrix_png_is_written(tmp_path, golden_csv):
    pairs, records = _hand_checked_records()
    golden = golden_csv(pairs)
    results = tmp_path / "results" / "accuracy"
    run_dir = build_accuracy_dir(results, records)
    out_dir = tmp_path / "out"

    assert accuracy.main(
        ["--results", str(results), "--golden", str(golden), "--out-dir", str(out_dir)]
    ) == 0

    png = out_dir / run_dir.name / "confusion_matrix.png"
    assert png.is_file()
    payload = png.read_bytes()
    assert payload[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(payload) > 5_000


# ---------------------------------------------------------------------------
# Join hazards
# ---------------------------------------------------------------------------

def test_missing_golden_rows_fail_the_run(tmp_path, golden_csv, capsys):
    pairs = [("10000", CREDIT_REPORTING), ("10001", MORTGAGE), ("10002", MORTGAGE)]
    golden = golden_csv(pairs)
    results = tmp_path / "results" / "accuracy"
    run_dir = build_accuracy_dir(
        results,
        [response("10000", CREDIT_REPORTING), response("10001", MORTGAGE, seconds=1)],
    )
    out_dir = tmp_path / "out"

    code = accuracy.main(
        ["--results", str(results), "--golden", str(golden),
         "--out-dir", str(out_dir), "--no-charts"]
    )

    assert code == 1
    captured = capsys.readouterr()
    assert "Coverage of the golden set is incomplete" in captured.err
    assert "subset of the golden set" in captured.err
    missing = read_csv(out_dir / run_dir.name / "missing_rows.csv")
    assert list(missing["row_number"]) == ["10002"]
    row = overall_row(out_dir, run_dir.name)
    assert row["evaluated"] == "2"
    assert float(row["coverage"]) == pytest.approx(2 / 3)
    # The accuracy figure is still written, so the operator can see what the
    # incomplete run said -- but the run has failed.
    assert float(row["accuracy"]) == 1.0


def test_extra_responses_are_reported_and_excluded(tmp_path, golden_csv, capsys):
    pairs = [("10000", CREDIT_REPORTING)]
    golden = golden_csv(pairs)
    results = tmp_path / "results" / "accuracy"
    run_dir = build_accuracy_dir(
        results,
        [
            response("10000", CREDIT_REPORTING),
            response("99999", MORTGAGE, seconds=1),  # not a golden row at all
        ],
    )
    out_dir = tmp_path / "out"

    code = accuracy.main(
        ["--results", str(results), "--golden", str(golden),
         "--out-dir", str(out_dir), "--no-charts"]
    )

    assert code == 0
    assert "not in the golden set" in capsys.readouterr().err
    unmatched = read_csv(out_dir / run_dir.name / "unmatched_responses.csv")
    assert list(unmatched["row_number"]) == ["99999"]
    assert unmatched.loc[0, "reason"] == "source_row not in the golden set"
    row = overall_row(out_dir, run_dir.name)
    assert row["evaluated"] == "1"
    assert row["responses"] == "2"
    assert row["unmatched_responses"] == "1"


def test_response_without_a_source_row_is_reported(tmp_path, golden_csv, capsys):
    pairs = [("10000", CREDIT_REPORTING)]
    golden = golden_csv(pairs)
    results = tmp_path / "results" / "accuracy"
    run_dir = build_accuracy_dir(
        results,
        [
            response("10000", CREDIT_REPORTING),
            make_log_line(  # the driver forgot the X-Source-Row header
                ts=iso_ms(BASE_TIME + timedelta(seconds=1)),
                request_id="req-headerless",
                source_row=None,
            ),
        ],
    )
    out_dir = tmp_path / "out"

    assert accuracy.main(
        ["--results", str(results), "--golden", str(golden),
         "--out-dir", str(out_dir), "--no-charts"]
    ) == 0

    assert "carried no source_row" in capsys.readouterr().err
    unmatched = read_csv(out_dir / run_dir.name / "unmatched_responses.csv")
    assert list(unmatched["reason"]) == ["no source_row header"]
    assert list(unmatched["request_id"]) == ["req-headerless"]


def test_duplicate_responses_use_the_last_by_timestamp(tmp_path, golden_csv, capsys):
    pairs = [("10000", CREDIT_REPORTING)]
    golden = golden_csv(pairs)
    results = tmp_path / "results" / "accuracy"
    run_dir = build_accuracy_dir(
        results,
        [
            # The earlier attempt was right; the later one was not. The later one
            # is what we score, and both are reported.
            response("10000", CREDIT_REPORTING, seconds=0, request_id="first"),
            response("10000", MORTGAGE, seconds=5, request_id="second"),
        ],
    )
    out_dir = tmp_path / "out"

    code = accuracy.main(
        ["--results", str(results), "--golden", str(golden),
         "--out-dir", str(out_dir), "--no-charts"]
    )

    assert code == 0
    assert "more than one response" in capsys.readouterr().err
    duplicates = read_csv(out_dir / run_dir.name / "duplicates.csv")
    assert list(duplicates["row_number"]) == ["10000"]
    assert duplicates.loc[0, "n_responses"] == "2"
    assert duplicates.loc[0, "kept_request_id"] == "second"
    assert duplicates.loc[0, "dropped_request_ids"] == "first"
    assert duplicates.loc[0, "kept_predicted_label"] == MORTGAGE
    row = overall_row(out_dir, run_dir.name)
    assert row["evaluated"] == "1"
    assert row["duplicate_rows"] == "1"
    assert float(row["accuracy"]) == 0.0  # the later, wrong answer was scored
    misclassified = read_csv(out_dir / run_dir.name / "misclassified.csv")
    assert list(misclassified["request_id"]) == ["second"]


def test_errored_response_is_excluded_and_fails_coverage(tmp_path, golden_csv, capsys):
    pairs = [("10000", CREDIT_REPORTING), ("10001", MORTGAGE)]
    golden = golden_csv(pairs)
    results = tmp_path / "results" / "accuracy"
    run_dir = build_accuracy_dir(
        results,
        [
            response("10000", CREDIT_REPORTING),
            response(
                "10001", None, seconds=1, status=502, error="ollama_timeout",
                raw=None, total_duration=None, eval_count=None,
            ),
        ],
    )
    out_dir = tmp_path / "out"

    code = accuracy.main(
        ["--results", str(results), "--golden", str(golden),
         "--out-dir", str(out_dir), "--no-charts"]
    )

    assert code == 1
    assert "carried no predicted_category" in capsys.readouterr().err
    errored = read_csv(out_dir / run_dir.name / "errored_responses.csv")
    assert list(errored["row_number"]) == ["10001"]
    assert list(errored["error"]) == ["ollama_timeout"]
    row = overall_row(out_dir, run_dir.name)
    # A timeout is not a wrong guess: it is out of the accuracy denominator, but
    # it still means the golden set was not fully covered.
    assert row["evaluated"] == "1"
    assert float(row["accuracy"]) == 1.0
    assert row["errored_responses"] == "1"
    assert float(row["coverage"]) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# misclassified.csv -- the file Jolie Ngai Ning Li reads
# ---------------------------------------------------------------------------

def test_misclassified_csv_contents_and_narrative_prefix(tmp_path, golden_csv):
    pairs = [
        ("10000", CREDIT_REPORTING),   # right
        ("10001", MORTGAGE),           # confused with another category
        ("10002", CREDIT_CARD),        # unreadable reply
    ]
    golden = golden_csv(pairs)
    # No narrative column in the golden set, so the narrative must come from the
    # team rows CSV instead.
    team_rows = tmp_path / "team_rows.csv"
    with team_rows.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["row_number", "narrative", "raw_label"])
        writer.writerow(["10001", "MORTGAGE TICKET " + "y" * 400, "Mortgage"])
        writer.writerow(["10002", "CARD TICKET\nsecond line " + "z" * 400, "Credit card"])
    results = tmp_path / "results" / "accuracy"
    run_dir = build_accuracy_dir(
        results,
        [
            response("10000", CREDIT_REPORTING),
            response("10001", DEBT_COLLECTION, seconds=1, raw="Debt collection"),
            response("10002", UNPARSEABLE, seconds=2, raw="I think this is a card?"),
        ],
    )
    out_dir = tmp_path / "out"

    assert accuracy.main(
        ["--results", str(results), "--golden", str(golden),
         "--team-rows", str(team_rows), "--out-dir", str(out_dir), "--no-charts"]
    ) == 0

    misclassified = read_csv(out_dir / run_dir.name / "misclassified.csv")
    assert list(misclassified.columns) == list(accuracy.MISCLASSIFIED_COLUMNS)
    assert list(misclassified["row_number"]) == ["10001", "10002"]
    assert list(misclassified["golden_label"]) == [MORTGAGE, CREDIT_CARD]
    # The unreadable reply appears as UNPARSEABLE, not as a guessed category.
    assert list(misclassified["predicted_label"]) == [DEBT_COLLECTION, UNPARSEABLE]
    assert misclassified.loc[1, "raw_model_output"] == "I think this is a card?"
    prefixes = list(misclassified["narrative_prefix"])
    assert all(len(prefix) == 200 for prefix in prefixes)
    assert prefixes[0].startswith("MORTGAGE TICKET ")
    # Newlines are collapsed so the file stays readable in a spreadsheet.
    assert "\n" not in prefixes[1]
    assert prefixes[1].startswith("CARD TICKET second line ")
    # The timestamp is written back in the service's own format, so the row can
    # be found in service.jsonl.
    assert misclassified.loc[0, "ts"].endswith("Z")


def test_narrative_comes_from_the_golden_set_when_it_has_one(tmp_path):
    # Written by hand rather than with the golden_csv fixture because this test
    # is specifically about a golden set that carries its own narrative column.
    golden = tmp_path / "golden_set.csv"
    with golden.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["row_number", "golden_label", "narrative"])
        writer.writerow(["10000", MORTGAGE, "FROM GOLDEN SET " + "q" * 300])
    results = tmp_path / "results" / "accuracy"
    run_dir = build_accuracy_dir(results, [response("10000", CREDIT_REPORTING)])
    out_dir = tmp_path / "out"

    assert accuracy.main(
        ["--results", str(results), "--golden", str(golden),
         "--team-rows", str(tmp_path / "does-not-exist.csv"),
         "--out-dir", str(out_dir), "--narrative-chars", "40", "--no-charts"]
    ) == 0

    misclassified = read_csv(out_dir / run_dir.name / "misclassified.csv")
    prefix = misclassified.loc[0, "narrative_prefix"]
    assert prefix.startswith("FROM GOLDEN SET ")
    assert len(prefix) == 40
    assert "golden set's own narrative column" in (
        out_dir / run_dir.name / "report.md"
    ).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Unusable evidence
# ---------------------------------------------------------------------------

def test_missing_golden_set_exits_non_zero(tmp_path, capsys):
    results = tmp_path / "results" / "accuracy"
    build_accuracy_dir(results, [response("10000", CREDIT_REPORTING)])

    code = accuracy.main(
        ["--results", str(results), "--golden", str(tmp_path / "nope.csv"),
         "--out-dir", str(tmp_path / "out"), "--no-charts"]
    )

    assert code == 1
    assert "Golden set not found" in capsys.readouterr().err


def test_non_canonical_golden_label_exits_non_zero(tmp_path, golden_csv, capsys):
    golden = golden_csv([("10000", "credit reporting")])  # wrong capitalisation
    results = tmp_path / "results" / "accuracy"
    build_accuracy_dir(results, [response("10000", CREDIT_REPORTING)])

    code = accuracy.main(
        ["--results", str(results), "--golden", str(golden),
         "--out-dir", str(tmp_path / "out"), "--no-charts"]
    )

    assert code == 1
    assert "not one of the seven canonical" in capsys.readouterr().err


def test_duplicated_golden_row_exits_non_zero(tmp_path, golden_csv, capsys):
    golden = golden_csv([("10000", CREDIT_REPORTING), ("10000", MORTGAGE)])
    results = tmp_path / "results" / "accuracy"
    build_accuracy_dir(results, [response("10000", CREDIT_REPORTING)])

    code = accuracy.main(
        ["--results", str(results), "--golden", str(golden),
         "--out-dir", str(tmp_path / "out"), "--no-charts"]
    )

    assert code == 1
    assert "labels the same row more than once" in capsys.readouterr().err


def test_no_responses_exits_non_zero(tmp_path, golden_csv, capsys):
    golden = golden_csv([("10000", CREDIT_REPORTING)])
    results = tmp_path / "results" / "accuracy"
    # A log with lines in it, but no POST /tickets line: nothing to score.
    build_accuracy_dir(
        results,
        [make_log_line(endpoint="/stats", method="GET", ticket_chars=None,
                       predicted_category=None, raw_model_output=None)],
    )

    code = accuracy.main(
        ["--results", str(results), "--golden", str(golden),
         "--out-dir", str(tmp_path / "out"), "--no-charts"]
    )

    assert code == 1
    assert "no measured POST /tickets lines" in capsys.readouterr().err


def test_no_accuracy_run_directories_exits_non_zero(tmp_path, golden_csv, capsys):
    golden = golden_csv([("10000", CREDIT_REPORTING)])
    empty = tmp_path / "results" / "accuracy"
    empty.mkdir(parents=True)

    code = accuracy.main(
        ["--results", str(empty), "--golden", str(golden),
         "--out-dir", str(tmp_path / "out"), "--no-charts"]
    )

    assert code == 1
    assert "no directories named <model>_<UTCSTAMP>" in capsys.readouterr().err


def test_missing_metadata_exits_non_zero(tmp_path, golden_csv, capsys):
    golden = golden_csv([("10000", CREDIT_REPORTING)])
    results = tmp_path / "results" / "accuracy"
    build_accuracy_dir(
        results, [response("10000", CREDIT_REPORTING)], write_metadata=False
    )

    code = accuracy.main(
        ["--results", str(results), "--golden", str(golden),
         "--out-dir", str(tmp_path / "out"), "--no-charts"]
    )

    assert code == 1
    assert "metadata.json is missing" in capsys.readouterr().err


def test_illegal_predicted_category_exits_non_zero(tmp_path, golden_csv, capsys):
    golden = golden_csv([("10000", CREDIT_REPORTING)])
    results = tmp_path / "results" / "accuracy"
    build_accuracy_dir(results, [response("10000", "Bananas")])

    code = accuracy.main(
        ["--results", str(results), "--golden", str(golden),
         "--out-dir", str(tmp_path / "out"), "--no-charts"]
    )

    assert code == 1
    assert "should never store" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Several models, dev mode, CLI
# ---------------------------------------------------------------------------

def test_per_model_comparison_table_lists_every_run(tmp_path, golden_csv):
    pairs = [("10000", CREDIT_REPORTING), ("10001", MORTGAGE)]
    golden = golden_csv(pairs)
    results = tmp_path / "results" / "accuracy"
    build_accuracy_dir(
        results,
        [response("10000", CREDIT_REPORTING), response("10001", MORTGAGE, seconds=1)],
        model="small-1b", model_tag="small:1b",
    )
    build_accuracy_dir(
        results,
        [response("10000", MORTGAGE), response("10001", MORTGAGE, seconds=1)],
        model="large-8b", model_tag="large:8b", stamp="20261001T100000Z",
    )
    out_dir = tmp_path / "out"

    assert accuracy.main(
        ["--results", str(results), "--golden", str(golden),
         "--out-dir", str(out_dir), "--no-charts"]
    ) == 0

    comparison = read_csv(out_dir / "model_comparison.csv")
    assert list(comparison["model_tag"]) == ["large:8b", "small:1b"]
    accuracies = dict(zip(comparison["model_tag"], comparison["accuracy"]))
    assert float(accuracies["small:1b"]) == 1.0
    assert float(accuracies["large:8b"]) == 0.5
    assert "Per-model comparison" in (out_dir / "accuracy_report.md").read_text(
        encoding="utf-8"
    )


def test_dev_mode_run_is_flagged_loudly(tmp_path, golden_csv, capsys):
    golden = golden_csv([("10000", CREDIT_REPORTING)])
    results = tmp_path / "results" / "accuracy"
    run_dir = build_accuracy_dir(
        results, [response("10000", CREDIT_REPORTING)], mode="dev"
    )
    out_dir = tmp_path / "out"

    assert accuracy.main(
        ["--results", str(results), "--golden", str(golden),
         "--out-dir", str(out_dir), "--no-charts"]
    ) == 0

    assert "DEV MODE" in capsys.readouterr().err
    assert "NOT evidence" in (out_dir / run_dir.name / "report.md").read_text(
        encoding="utf-8"
    )


def test_help_is_available_without_any_evidence():
    # The contract requires --help to work with no network and no data on disk.
    with pytest.raises(SystemExit) as raised:
        accuracy.parse_args(["--help"])
    assert raised.value.code == 0


def test_defaults_point_at_the_committed_layout():
    args = accuracy.parse_args([])
    assert args.results == accuracy.REPO_ROOT / "results" / "accuracy"
    assert args.golden == accuracy.REPO_ROOT / "golden" / "golden_set.csv"
    assert args.out_dir == accuracy.REPO_ROOT / "analysis" / "output" / "accuracy"
    assert args.narrative_chars == 200
