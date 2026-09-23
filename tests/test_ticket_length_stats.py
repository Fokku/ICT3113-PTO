"""Tests for ``workload/scripts/ticket_length_stats.py``.

Owner: Part 1 -- Yeo Kai Yuan.

Every test here builds its own tiny CSV in ``tmp_path``. Nothing reads
``data/team_rows.csv`` and nothing runs a model: the point of the script is that
it turns text into arithmetic, so the arithmetic is what is pinned down here,
on inputs whose answers can be worked out by hand.

Three of these tests exist because of a specific way the workload model could go
wrong:

* the percentile test, because a percentile computed with a different
  interpolation rule quietly disagrees with the latency percentiles in
  ``analysis/`` and nobody would notice;
* the token-approximation test, because the ``num_ctx`` decision rests on that
  one documented rule and a change to it must be deliberate;
* the column-order tests, because the tables are committed and cited on a
  slide, so a re-run must produce a diff of changed numbers, not of moved
  columns.
"""

from __future__ import annotations

import csv
import importlib.util
import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "workload" / "scripts" / "ticket_length_stats.py"

# workload/scripts is not an importable package (it holds one standalone CLI
# script), so the module is loaded from its path rather than imported by name.
_spec = importlib.util.spec_from_file_location("workload_ticket_length_stats", MODULE_PATH)
assert _spec is not None and _spec.loader is not None, f"cannot load {MODULE_PATH}"
stats = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = stats
_spec.loader.exec_module(stats)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_tickets(
    path: Path,
    narratives: list[str],
    *,
    include_row_number: bool = True,
    columns: list[str] | None = None,
) -> Path:
    """Write a tickets CSV in the ``row_number,narrative,raw_label`` layout.

    ``columns`` overrides the header entirely, which is how the "missing
    narrative column" case is built.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if columns is not None:
            writer.writerow(columns)
            for index, narrative in enumerate(narratives):
                writer.writerow([str(10000 + index), narrative][: len(columns)])
            return path
        header = (["row_number"] if include_row_number else []) + ["narrative", "raw_label"]
        writer.writerow(header)
        for index, narrative in enumerate(narratives):
            row = [narrative, "Mortgage"]
            if include_row_number:
                row = [str(10000 + index)] + row
            writer.writerow(row)
    return path


def narratives_of_length(lengths: list[int]) -> list[str]:
    """Narratives of exactly the given character lengths, so maths is checkable."""
    return ["x" * length for length in lengths]


def read_header(path: Path) -> list[str]:
    """First row of a CSV, as a list."""
    with path.open(newline="", encoding="utf-8") as handle:
        return next(csv.reader(handle))


# ---------------------------------------------------------------------------
# Measurement rules
# ---------------------------------------------------------------------------

class TestWordCounting:
    """The documented rule: whitespace-split, keep tokens containing alphanumerics."""

    def test_multiple_spaces_do_not_inflate_the_count(self) -> None:
        assert stats.count_words("alpha   beta     gamma") == 3

    def test_tabs_and_newlines_are_whitespace(self) -> None:
        # Team-row narratives really do contain newlines inside quoted fields.
        assert stats.count_words("alpha\tbeta\n\ngamma\r\ndelta") == 4

    def test_attached_punctuation_does_not_split_a_word(self) -> None:
        assert stats.count_words("Hello,  world!!  it's   fine.") == 4

    def test_standalone_punctuation_is_not_a_word(self) -> None:
        # "--" and "***" carry no alphanumeric character, so they do not count.
        assert stats.count_words("alpha -- beta *** gamma") == 3

    def test_redacted_tokens_count_once(self) -> None:
        # The CFPB extract redacts with runs of X and dates as XX/XX/XXXX.
        # paid | on | XX/XX/XXXX | to | XXXX | XXXX -- the slashed date is one word.
        assert stats.count_words("paid on XX/XX/XXXX to XXXX XXXX") == 6

    def test_leading_and_trailing_whitespace_is_ignored(self) -> None:
        assert stats.count_words("   alpha beta   ") == 2

    def test_whitespace_only_text_has_no_words(self) -> None:
        assert stats.count_words("   \t\n ") == 0


class TestTokenApproximation:
    """The approximation must be exactly ceil(characters / CHARS_PER_APPROX_TOKEN)."""

    def test_the_documented_divisor_is_four(self) -> None:
        # If this ever changes it must be a deliberate, documented decision: the
        # num_ctx sizing in the workload model is derived from it.
        assert stats.CHARS_PER_APPROX_TOKEN == 4

    @pytest.mark.parametrize(
        ("chars", "expected"),
        [(0, 0), (1, 1), (3, 1), (4, 1), (5, 2), (8, 2), (9, 3), (201, 51), (1999, 500)],
    )
    def test_known_values(self, chars: int, expected: int) -> None:
        assert stats.approx_token_count(chars) == expected

    def test_matches_ceiling_division_everywhere(self) -> None:
        for chars in range(0, 500):
            assert stats.approx_token_count(chars) == math.ceil(
                chars / stats.CHARS_PER_APPROX_TOKEN
            )

    def test_rounds_up_rather_than_down(self) -> None:
        # Rounding down would understate the truncation risk.
        assert stats.approx_token_count(5) == 2

    def test_negative_length_is_rejected(self) -> None:
        with pytest.raises(stats.AnalysisError):
            stats.approx_token_count(-1)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

class TestDistributionArithmetic:
    """Percentiles, mean and sample SD on a set whose answers are known."""

    @pytest.fixture()
    def table(self, tmp_path: Path):
        # Ten narratives of 100, 200, ... 1000 characters. With linear
        # interpolation over n = 10, the percentile at fraction q sits at index
        # q * (n - 1) = 9q of the sorted values, which makes every expectation
        # below checkable by hand.
        path = write_tickets(tmp_path / "known.csv", narratives_of_length(list(range(100, 1100, 100))))
        measurements = stats.measure(stats.read_narratives(path))
        frame = stats.distribution_table(measurements)
        return frame.set_index("metric").loc["chars"]

    def test_count_min_and_max(self, table) -> None:
        assert table["n"] == 10
        assert table["min"] == 100
        assert table["max"] == 1000

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("p5", 145.0),    # index 0.45 -> 100 + 0.45 * 100
            ("p25", 325.0),   # index 2.25 -> 300 + 0.25 * 100
            ("p50", 550.0),   # index 4.50 -> 500 + 0.50 * 100
            ("p75", 775.0),   # index 6.75 -> 700 + 0.75 * 100
            ("p90", 910.0),   # index 8.10 -> 900 + 0.10 * 100
            ("p95", 955.0),   # index 8.55 -> 900 + 0.55 * 100
            ("p99", 991.0),   # index 8.91 -> 900 + 0.91 * 100
        ],
    )
    def test_percentiles_use_linear_interpolation(self, table, name: str, expected: float) -> None:
        assert table[name] == pytest.approx(expected)

    def test_mean_and_sample_standard_deviation(self, table) -> None:
        assert table["mean"] == pytest.approx(550.0)
        # ddof = 1: sum of squared deviations 825000 over 9 degrees of freedom.
        assert table["sd"] == pytest.approx(math.sqrt(825000.0 / 9.0))

    def test_every_metric_is_reported(self, tmp_path: Path) -> None:
        path = write_tickets(tmp_path / "metrics.csv", narratives_of_length([100, 200, 300]))
        frame = stats.distribution_table(stats.measure(stats.read_narratives(path)))
        assert list(frame["metric"]) == ["chars", "words", "approx_tokens"]


class TestTruncationRisk:
    """The count of rows that would not fit in num_ctx."""

    @pytest.fixture()
    def measurements(self, tmp_path: Path):
        # Characters 100, 400, 1000, 2000. With an overhead of 100 characters
        # the approximate prompt lengths are 50, 125, 275 and 525 tokens.
        path = write_tickets(tmp_path / "risk.csv", narratives_of_length([100, 400, 1000, 2000]))
        return stats.measure(stats.read_narratives(path))

    def test_counts_only_the_rows_over_the_limit(self, measurements) -> None:
        risk = stats.truncation_risk(
            measurements, prompt_overhead_chars=100, num_ctx=300, reserve_output_tokens=0
        )
        assert risk.rows_total == 4
        assert risk.rows_at_risk == 1          # only the 525-token row exceeds 300
        assert risk.max_prompt_tokens == 525
        assert risk.headroom_tokens == -225    # negative: the longest row would not fit
        assert risk.share_at_risk_pct == pytest.approx(25.0)

    def test_reserved_output_tokens_tighten_the_limit(self, measurements) -> None:
        # 275 + 30 = 305 > 300, so the third row now joins the fourth.
        risk = stats.truncation_risk(
            measurements, prompt_overhead_chars=100, num_ctx=300, reserve_output_tokens=30
        )
        assert risk.rows_at_risk == 2

    def test_a_large_context_puts_nothing_at_risk(self, measurements) -> None:
        risk = stats.truncation_risk(
            measurements, prompt_overhead_chars=100, num_ctx=4096, reserve_output_tokens=0
        )
        assert risk.rows_at_risk == 0
        assert risk.headroom_tokens == 4096 - 525

    def test_the_boundary_is_strictly_greater_than(self, measurements) -> None:
        # A prompt of exactly num_ctx tokens fits, so it is not at risk.
        risk = stats.truncation_risk(
            measurements, prompt_overhead_chars=100, num_ctx=525, reserve_output_tokens=0
        )
        assert risk.rows_at_risk == 0

    def test_a_non_positive_context_is_rejected(self, measurements) -> None:
        with pytest.raises(stats.AnalysisError):
            stats.truncation_risk(
                measurements, prompt_overhead_chars=100, num_ctx=0, reserve_output_tokens=0
            )


class TestPromptOverhead:
    """Where the prompt overhead comes from, and what happens when it does not."""

    def test_an_explicit_value_is_used_verbatim(self) -> None:
        overhead = stats.resolve_prompt_overhead(120)
        assert overhead.chars == 120
        assert "--prompt-overhead-chars" in overhead.source

    def test_a_negative_explicit_value_is_rejected(self) -> None:
        with pytest.raises(stats.AnalysisError):
            stats.resolve_prompt_overhead(-1)

    def test_without_an_explicit_value_the_source_is_always_stated(self) -> None:
        # Whether service/prompt.py is importable or not, the result must say
        # where the number came from, or why there is none. It must never be a
        # bare number of unknown provenance.
        overhead = stats.resolve_prompt_overhead(None)
        assert overhead.source
        if overhead.chars is None:
            assert "not established" in overhead.source
        else:
            assert "measured" in overhead.source


# ---------------------------------------------------------------------------
# Input handling: clear errors, never a traceback
# ---------------------------------------------------------------------------

class TestInputErrors:
    """Bad input must exit 2 with an explanation Part 4 can act on."""

    def test_empty_input(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        path = write_tickets(tmp_path / "empty.csv", [])
        exit_code = stats.main(["--input", str(path), "--out-dir", str(tmp_path / "out")])
        captured = capsys.readouterr()
        assert exit_code == 2
        assert captured.err.startswith("error: ")
        assert "no data rows" in captured.err
        assert "Traceback" not in captured.err

    def test_single_row_input(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        path = write_tickets(tmp_path / "one.csv", narratives_of_length([500]))
        exit_code = stats.main(["--input", str(path), "--out-dir", str(tmp_path / "out")])
        captured = capsys.readouterr()
        assert exit_code == 2
        assert "only 1 data row" in captured.err
        assert str(stats.MIN_ROWS) in captured.err
        assert "Traceback" not in captured.err

    def test_two_rows_are_enough(self, tmp_path: Path) -> None:
        # The boundary on the other side: MIN_ROWS rows must succeed.
        path = write_tickets(tmp_path / "two.csv", narratives_of_length([400, 800]))
        assert stats.main(
            ["--input", str(path), "--out-dir", str(tmp_path / "out"),
             "--prompt-overhead-chars", "100", "--no-charts"]
        ) == 0

    def test_missing_file(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = stats.main(
            ["--input", str(tmp_path / "absent.csv"), "--out-dir", str(tmp_path / "out")]
        )
        assert exit_code == 2
        assert "No such input CSV" in capsys.readouterr().err

    def test_missing_narrative_column(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        path = write_tickets(
            tmp_path / "wrong.csv", ["ignored"], columns=["row_number", "text"]
        )
        exit_code = stats.main(["--input", str(path), "--out-dir", str(tmp_path / "out")])
        captured = capsys.readouterr()
        assert exit_code == 2
        assert "no 'narrative' column" in captured.err

    def test_blank_narrative_is_reported_with_its_row_number(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = write_tickets(tmp_path / "blank.csv", ["a valid narrative", "   ", "another"])
        exit_code = stats.main(["--input", str(path), "--out-dir", str(tmp_path / "out")])
        captured = capsys.readouterr()
        assert exit_code == 2
        assert "empty narrative" in captured.err
        assert "10001" in captured.err       # the offending row is named

    def test_row_number_column_is_optional(self, tmp_path: Path) -> None:
        path = write_tickets(
            tmp_path / "norow.csv", narratives_of_length([300, 600]), include_row_number=False
        )
        measurements = stats.measure(stats.read_narratives(path))
        # Falls back to the 1-based position of the data row.
        assert list(measurements["row_number"]) == ["1", "2"]

    def test_bins_must_be_positive(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        path = write_tickets(tmp_path / "bins.csv", narratives_of_length([300, 600]))
        exit_code = stats.main(
            ["--input", str(path), "--out-dir", str(tmp_path / "out"), "--bins", "0"]
        )
        assert exit_code == 2
        assert "--bins" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

class TestOutputs:
    """What lands in --out-dir, and in what shape."""

    @pytest.fixture()
    def out_dir(self, tmp_path: Path) -> Path:
        path = write_tickets(
            tmp_path / "tickets.csv",
            narratives_of_length([200, 400, 600, 800, 1000, 1200]),
        )
        out_dir = tmp_path / "output"
        exit_code = stats.main(
            ["--input", str(path), "--out-dir", str(out_dir),
             "--prompt-overhead-chars", "100", "--num-ctx", "300"]
        )
        assert exit_code == 0
        return out_dir

    def test_every_expected_file_is_written(self, out_dir: Path) -> None:
        for name in (
            stats.PER_ROW_CSV,
            f"{stats.STEM_DISTRIBUTION}.csv",
            f"{stats.STEM_DISTRIBUTION}.md",
            f"{stats.STEM_TRUNCATION}.csv",
            f"{stats.STEM_TRUNCATION}.md",
            stats.REPORT_MD,
        ):
            assert (out_dir / name).is_file(), f"{name} was not written"

    def test_png_charts_are_created(self, out_dir: Path) -> None:
        for name in (stats.HISTOGRAM_PNG, stats.CDF_PNG):
            path = out_dir / name
            assert path.is_file(), f"{name} was not written"
            # Real PNG, not an empty file left behind by a failed save.
            assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
            assert path.stat().st_size > 1000

    def test_no_charts_flag_skips_the_pngs(self, tmp_path: Path) -> None:
        path = write_tickets(tmp_path / "t.csv", narratives_of_length([200, 400]))
        out_dir = tmp_path / "tables-only"
        assert stats.main(
            ["--input", str(path), "--out-dir", str(out_dir),
             "--prompt-overhead-chars", "100", "--no-charts"]
        ) == 0
        assert not (out_dir / stats.HISTOGRAM_PNG).exists()
        assert (out_dir / f"{stats.STEM_DISTRIBUTION}.csv").is_file()

    def test_distribution_table_column_order_is_stable(self, out_dir: Path) -> None:
        expected = [
            "metric", "unit", "n", "min",
            "p5", "p25", "p50", "p75", "p90", "p95", "p99",
            "max", "mean", "sd",
        ]
        assert list(stats.DISTRIBUTION_COLUMNS) == expected
        assert read_header(out_dir / f"{stats.STEM_DISTRIBUTION}.csv") == expected

    def test_truncation_table_column_order_is_stable(self, out_dir: Path) -> None:
        expected = ["quantity", "value", "unit", "how it was obtained"]
        assert list(stats.TRUNCATION_COLUMNS) == expected
        assert read_header(out_dir / f"{stats.STEM_TRUNCATION}.csv") == expected

    def test_per_row_column_order_is_stable(self, out_dir: Path) -> None:
        expected = ["row_number", "chars", "words", "approx_tokens"]
        assert list(stats.PER_ROW_COLUMNS) == expected
        assert read_header(out_dir / stats.PER_ROW_CSV) == expected

    def test_markdown_tables_carry_the_same_columns_in_the_same_order(self, out_dir: Path) -> None:
        header = (out_dir / f"{stats.STEM_DISTRIBUTION}.md").read_text(encoding="utf-8").splitlines()[0]
        cells = [cell.strip() for cell in header.strip("|").split("|")]
        assert cells == list(stats.DISTRIBUTION_COLUMNS)

    def test_per_row_measurements_cover_every_input_row(self, out_dir: Path) -> None:
        with (out_dir / stats.PER_ROW_CSV).open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        assert len(rows) == 6
        assert rows[0]["chars"] == "200"
        assert rows[0]["approx_tokens"] == "50"

    def test_truncation_row_is_present_and_counted(self, out_dir: Path) -> None:
        with (out_dir / f"{stats.STEM_TRUNCATION}.csv").open(newline="", encoding="utf-8") as handle:
            values = {row["quantity"]: row["value"] for row in csv.DictReader(handle)}
        # Characters 200..1200 plus 100 of overhead give 75..325 tokens; with
        # num_ctx = 300 only the 1200-character row exceeds it.
        assert values["rows at truncation risk"] == "1"
        assert values["num_ctx"] == "300"
        assert values["prompt overhead"] == "100"

    def test_report_labels_the_token_figure_as_an_approximation(self, out_dir: Path) -> None:
        report = (out_dir / stats.REPORT_MD).read_text(encoding="utf-8")
        assert "approximation" in report.lower()
        assert "prompt_eval_count" in report      # points at the authoritative figure
        assert "TODO(Part 4 \u2014 Teammate C)" in report

    def test_output_is_deterministic(self, tmp_path: Path) -> None:
        # The tables are committed and cited on a slide, so a re-run over the
        # same input must produce identical bytes rather than churn the diff.
        path = write_tickets(tmp_path / "det.csv", narratives_of_length([250, 500, 750]))
        first, second = tmp_path / "run1", tmp_path / "run2"
        for out_dir in (first, second):
            assert stats.main(
                ["--input", str(path), "--out-dir", str(out_dir),
                 "--prompt-overhead-chars", "100", "--no-charts"]
            ) == 0
        for name in (f"{stats.STEM_DISTRIBUTION}.md", f"{stats.STEM_TRUNCATION}.csv",
                     stats.REPORT_MD, stats.PER_ROW_CSV):
            assert (first / name).read_bytes() == (second / name).read_bytes()


class TestCommandLine:
    """The CLI surface the workload documents tell Part 4 to type."""

    def test_team_rows_alias_is_accepted(self, tmp_path: Path) -> None:
        # The CLI contract in the build contract spells this flag --team-rows.
        path = write_tickets(tmp_path / "alias.csv", narratives_of_length([300, 600]))
        args = stats.build_parser().parse_args(["--team-rows", str(path)])
        assert args.input == path

    def test_defaults_point_at_the_team_rows_and_workload_output(self) -> None:
        args = stats.build_parser().parse_args([])
        assert args.input.name == "team_rows.csv"
        assert args.out_dir.name == "output"
        assert args.num_ctx == stats.DEFAULT_NUM_CTX
        assert args.prompt_overhead_chars is None   # never guessed
        assert args.reserve_output_tokens == 0

    def test_help_mentions_the_approximation_rule(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            stats.build_parser().parse_args(["--help"])
        assert exc.value.code == 0
        assert "ceil(characters / 4)" in capsys.readouterr().out
