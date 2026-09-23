"""Measure the ticket length distribution of our own team rows.

Owner: Part 4 -- Teammate C (workload model).
Written by: Part 1 -- Yeo Kai Yuan (tooling only; the interpretation is Part 4's).

Why this script exists
----------------------
The workload model (Step 3 of the brief, Slide 3) has to state the "expected
distribution of ticket lengths". Every other figure in that model -- ticket
volume, search rate, peak factor -- is an *estimate* about the client and must
be cited or its estimation method stated. The length distribution is different:
we hold the actual narratives the load generator will post, so this one figure
is **measured from our own data** and needs no external source. This script is
the only legitimate producer of it.

It reads ``data/team_rows.csv`` (or any CSV with the same columns) and reports,
for characters, words and *approximate* tokens:

* the percentiles min, p5, p25, p50, p75, p90, p95, p99, max,
* the mean and the sample standard deviation,
* a histogram PNG (shape of the distribution) and an empirical-CDF PNG
  (the chart you actually read a percentile off),
* the number of rows whose approximate prompt length would exceed ``NUM_CTX``,
  which is the silent-truncation risk the service configuration comment refers
  to.

No model is run and no tokeniser is called
------------------------------------------
Token counts here are an **approximation** from character counts (see
:data:`CHARS_PER_APPROX_TOKEN`). The true count is tokeniser-specific, so it
differs per candidate model, and we deliberately do not import a tokeniser: it
would add a dependency, and it would still be the wrong tokeniser for at least
some of the candidates. The authoritative figure arrives for free once
benchmarks run -- Ollama returns it and the service logs it as
``prompt_eval_count`` (see ``../../service/log_schema.py``). Treat the numbers
here as a sizing aid for ``NUM_CTX``, not as evidence about tokens.

Nothing in this script touches a model, so running it on ``data/team_rows.csv``
before the freeze is allowed: the freeze gate exists to stop a *model* seeing
team rows, not to stop us measuring our own text.

Charts: one hue per chart because each chart carries a single series, a
recessive grid, and no legend (the title names the series). The only second
colour is the ``num_ctx`` limit line, which is a threshold rather than a series.

Usage
-----
    python workload/scripts/ticket_length_stats.py \
        [--input data/team_rows.csv] [--out-dir workload/output] \
        [--num-ctx 4096] [--prompt-overhead-chars N] \
        [--reserve-output-tokens N] [--bins N] [--no-charts]

Exit codes: ``0`` success, ``2`` the input or the arguments are unusable (a
clear message on stderr, never a traceback).
"""

from __future__ import annotations

import argparse
import hashlib
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# The repository root has to be importable so that ``analysis.common`` (our
# shared percentile/table helpers) resolves when this file is run directly as
# ``python workload/scripts/ticket_length_stats.py``, in which case sys.path[0]
# is workload/scripts rather than the repository root.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis.common import (  # noqa: E402  (deliberately after the sys.path fix)
    AnalysisError,
    percentile,
    to_markdown_table,
    use_headless_matplotlib,
    write_table,
)

# ---------------------------------------------------------------------------
# Documented constants. These are rules and defaults, not measurements.
# ---------------------------------------------------------------------------

#: The token approximation rule, stated once: approximate tokens =
#: ceil(characters / CHARS_PER_APPROX_TOKEN). Four characters per token is the
#: usual rule of thumb for English prose with byte-pair encodings. It is an
#: approximation and is labelled as one in every output this script writes.
CHARS_PER_APPROX_TOKEN = 4

#: Default context window, matching the ``NUM_CTX`` default in the
#: configuration contract (``.env.example``). The value that actually applied to
#: a run is recorded per request in the service log's ``num_ctx`` field; prefer
#: that when reporting.
DEFAULT_NUM_CTX = 4096

#: Fewest data rows we will summarise. One row is not a distribution: the sample
#: standard deviation is undefined and every percentile collapses onto the same
#: number, which would look like a finding on a slide. Refuse instead.
MIN_ROWS = 2

#: Default number of histogram bins. A chart parameter, not a statistic.
DEFAULT_BINS = 30

#: Percentiles reported, in this order. ``min`` and ``max`` are exact counts and
#: are reported separately; these are the interpolated ones.
PERCENTILE_POINTS: tuple[tuple[str, float], ...] = (
    ("p5", 0.05),
    ("p25", 0.25),
    ("p50", 0.50),
    ("p75", 0.75),
    ("p90", 0.90),
    ("p95", 0.95),
    ("p99", 0.99),
)

#: Column order of the per-row measurements CSV. Fixed so that a diff of two
#: runs of this script shows changed data, not reordered columns.
PER_ROW_COLUMNS: tuple[str, ...] = ("row_number", "chars", "words", "approx_tokens")

#: Column order of the distribution table.
DISTRIBUTION_COLUMNS: tuple[str, ...] = (
    ("metric", "unit", "n", "min")
    + tuple(name for name, _ in PERCENTILE_POINTS)
    + ("max", "mean", "sd")
)

#: Column order of the truncation-risk table. A key/value shape, because these
#: are settings and one derived count rather than a series.
TRUNCATION_COLUMNS: tuple[str, ...] = ("quantity", "value", "unit", "how it was obtained")

#: The three things we measure, and the unit each is reported in.
METRIC_UNITS: tuple[tuple[str, str], ...] = (
    ("chars", "characters"),
    ("words", "words"),
    ("approx_tokens", "approximate tokens"),
)

# Output file names, so the tests and the workload documents can name them.
STEM_DISTRIBUTION = "length_distribution"
STEM_TRUNCATION = "truncation_risk"
PER_ROW_CSV = "ticket_lengths_per_row.csv"
HISTOGRAM_PNG = "length_histogram.png"
CDF_PNG = "length_cdf.png"
REPORT_MD = "ticket_length_stats.md"

# Chart colours, taken from a validated categorical palette. One series per
# chart, so only the first slot is used; red marks the num_ctx threshold.
COLOUR_SERIES = "#2a78d6"
COLOUR_LIMIT = "#e34948"
COLOUR_GUIDE = "#9a9a94"


# ---------------------------------------------------------------------------
# Measurement rules
# ---------------------------------------------------------------------------

def count_characters(narrative: str) -> int:
    """Characters in a narrative: ``len()`` of the string as it was read.

    This is deliberately the same rule the service uses for the log line's
    ``ticket_chars`` field, so the distribution measured here and the lengths
    recorded during a benchmark run are directly comparable.
    """
    return len(narrative)


def count_words(narrative: str) -> int:
    """Words in a narrative.

    Rule, stated once and tested: split on any run of whitespace (so repeated
    spaces, tabs and the newlines that appear inside quoted CSV narratives do
    not inflate the count), then keep only the tokens containing at least one
    alphanumeric character.

    That last clause is why a stray ``--`` or a lone ``*`` is not a word, while
    punctuation attached to a word (``world!``, ``it's``, ``XX/XX/XXXX``) leaves
    the count alone. Hyphenated and slashed forms therefore count once. The rule
    is simple on purpose: any cleverer tokenisation would need justifying on a
    slide, and words are only ever a readability aid here -- the figure that
    drives ``num_ctx`` is tokens.
    """
    return sum(
        1
        for token in narrative.split()
        if any(character.isalnum() for character in token)
    )


def approx_token_count(n_chars: int) -> int:
    """Approximate tokens for a text of ``n_chars`` characters.

    Exactly ``ceil(n_chars / CHARS_PER_APPROX_TOKEN)``. Rounded up because a
    partial token still occupies a slot in the context window, so rounding down
    would understate the truncation risk -- and if this figure is wrong we want
    it wrong on the cautious side.
    """
    if n_chars < 0:  # defensive: a negative length is a programming error
        raise AnalysisError(f"Negative character count: {n_chars}")
    return math.ceil(n_chars / CHARS_PER_APPROX_TOKEN)


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

def read_narratives(path: Path) -> pd.DataFrame:
    """Read a tickets CSV into a frame with ``row_number`` and ``narrative``.

    Accepts any CSV carrying a ``narrative`` column -- ``data/team_rows.csv``,
    ``data/dev/synthetic_tickets.csv`` or a subset cut from either. Raises
    :class:`AnalysisError` with an actionable message rather than letting a
    pandas traceback escape, because Part 4 will run this from a shell and a
    traceback is not a usable error message.

    ``row_number`` is optional: if the column is absent, the 1-based position of
    the data row is substituted so that the per-row output can still be joined
    back to the input by eye.
    """
    if not path.is_file():
        raise AnalysisError(
            f"No such input CSV: {path}\n"
            f"Expected a CSV with a 'narrative' column, for example "
            f"data/team_rows.csv or data/dev/synthetic_tickets.csv."
        )

    try:
        # keep_default_na=False so a narrative that happens to read "NA" or
        # "null" stays a string instead of becoming a missing value.
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    except Exception as exc:  # pragma: no cover - depends on the broken file
        raise AnalysisError(f"{path} could not be parsed as CSV: {exc}") from exc

    if "narrative" not in frame.columns:
        raise AnalysisError(
            f"{path} has no 'narrative' column. Found: {list(frame.columns)}. "
            f"Expected the team-rows layout 'row_number,narrative,raw_label'."
        )

    if frame.empty:
        raise AnalysisError(
            f"{path} has a header but no data rows. There is no distribution to "
            f"report, so nothing was written."
        )

    if len(frame) < MIN_ROWS:
        raise AnalysisError(
            f"{path} has only {len(frame)} data row(s); at least {MIN_ROWS} are "
            f"needed. A single row has no spread -- its standard deviation is "
            f"undefined and every percentile is the same number -- and reporting "
            f"it as a distribution would be misleading. Pass a larger --input."
        )

    if "row_number" in frame.columns:
        row_numbers = frame["row_number"].astype(str).str.strip()
    else:
        # Documented substitute, so the output is still joinable by position.
        row_numbers = pd.Series(
            [str(i) for i in range(1, len(frame) + 1)], index=frame.index
        )

    narratives = frame["narrative"].astype(str)
    blank = [
        row_numbers.iloc[i]
        for i in range(len(narratives))
        if not narratives.iloc[i].strip()
    ]
    if blank:
        raise AnalysisError(
            f"{path} contains {len(blank)} row(s) with an empty narrative "
            f"(row_number {', '.join(blank[:10])}"
            f"{', ...' if len(blank) > 10 else ''}). An empty ticket would drag "
            f"the percentiles down and cannot be posted to /tickets, so fix or "
            f"drop those rows before reporting a distribution."
        )

    return pd.DataFrame({"row_number": row_numbers, "narrative": narratives})


def measure(frame: pd.DataFrame) -> pd.DataFrame:
    """Per-row measurements: characters, words and approximate tokens."""
    chars = frame["narrative"].map(count_characters)
    return pd.DataFrame(
        {
            "row_number": frame["row_number"],
            "chars": chars,
            "words": frame["narrative"].map(count_words),
            "approx_tokens": chars.map(approx_token_count),
        }
    )[list(PER_ROW_COLUMNS)]


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def distribution_table(measurements: pd.DataFrame) -> pd.DataFrame:
    """One row per metric: n, min, the percentiles, max, mean and sample SD.

    Percentiles come from ``analysis.common.percentile`` (linear interpolation)
    so that a percentile in the workload model is computed exactly the same way
    as a latency percentile in the load-test analysis. A percentile computed
    with a different interpolation rule differs on small samples, and anyone
    must be able to reproduce ours from the CSV.
    """
    rows: list[dict[str, object]] = []
    for metric, unit in METRIC_UNITS:
        series = measurements[metric].astype("float64")
        row: dict[str, object] = {
            "metric": metric,
            "unit": unit,
            "n": int(series.count()),
            "min": int(series.min()),
        }
        for name, q in PERCENTILE_POINTS:
            row[name] = percentile(series, q)
        row["max"] = int(series.max())
        row["mean"] = float(series.mean())
        # ddof=1: our rows are a sample of the client's traffic, not the
        # population of it. MIN_ROWS guarantees this is defined.
        row["sd"] = float(series.std(ddof=1))
        rows.append(row)
    return pd.DataFrame(rows)[list(DISTRIBUTION_COLUMNS)]


@dataclass(frozen=True)
class PromptOverhead:
    """How many characters the fixed prompt adds around a narrative.

    ``chars`` is ``None`` when we could not establish it honestly; ``source``
    always explains where the value came from, or why there is none, and that
    string is copied into the output tables.
    """

    chars: int | None
    source: str


def resolve_prompt_overhead(explicit: int | None) -> PromptOverhead:
    """Establish the prompt overhead, preferring the real prompt module.

    Order of preference:

    1. ``--prompt-overhead-chars`` if given -- an explicit, documented argument.
    2. Measured from ``service.prompt`` by rendering the real template around an
       empty narrative. This is the honest figure, because it is the prompt the
       service actually sends.
    3. Nothing. We then report the truncation risk as "not computed" and say
       why, rather than inventing an overhead. A made-up overhead would produce
       a made-up truncation count, and no number in this repository may be
       invented.

    The introspection in step 2 is deliberately tolerant about the name of the
    prompt builder, because ``service/prompt.py`` only promises a template and a
    hash. If it cannot find one, that is step 3, not an error.
    """
    if explicit is not None:
        if explicit < 0:
            raise AnalysisError("--prompt-overhead-chars cannot be negative.")
        return PromptOverhead(
            chars=explicit,
            source="supplied with --prompt-overhead-chars",
        )

    try:
        from service import prompt as prompt_module  # noqa: PLC0415 (optional)
    except Exception as exc:
        return PromptOverhead(
            chars=None,
            source=(
                f"not established: service/prompt.py could not be imported "
                f"({type(exc).__name__}) and --prompt-overhead-chars was not given"
            ),
        )

    for builder_name in ("build_prompt", "render_prompt", "make_prompt", "format_prompt"):
        builder = getattr(prompt_module, builder_name, None)
        if callable(builder):
            try:
                rendered = builder("")
            except Exception:  # wrong signature: try the next candidate
                continue
            if isinstance(rendered, str):
                return PromptOverhead(
                    chars=len(rendered),
                    source=f"measured: len(service.prompt.{builder_name}('')), the prompt the service sends",
                )

    template = getattr(prompt_module, "PROMPT_TEMPLATE", None)
    if isinstance(template, str):
        for rule_name, render in (
            ("str.format(narrative='')", lambda t: t.format(narrative="")),
            ("%-formatting with an empty narrative", lambda t: t % ("",)),
            ("template with the {narrative} placeholder removed",
             lambda t: t.replace("{narrative}", "")),
        ):
            try:
                rendered = render(template)
            except Exception:
                continue
            return PromptOverhead(
                chars=len(rendered),
                source=f"measured from service.prompt.PROMPT_TEMPLATE via {rule_name}",
            )

    return PromptOverhead(
        chars=None,
        source=(
            "not established: service/prompt.py exposes neither a prompt builder "
            "nor a usable PROMPT_TEMPLATE, and --prompt-overhead-chars was not given"
        ),
    )


@dataclass(frozen=True)
class TruncationRisk:
    """The ``num_ctx`` sizing result for one input and one set of settings."""

    num_ctx: int
    prompt_overhead_chars: int
    reserve_output_tokens: int
    rows_total: int
    rows_at_risk: int
    max_prompt_tokens: int
    p99_prompt_tokens: float

    @property
    def share_at_risk_pct(self) -> float:
        """Rows at risk as a percentage of rows measured."""
        return 100.0 * self.rows_at_risk / self.rows_total

    @property
    def headroom_tokens(self) -> int:
        """Spare context at the longest row. Negative means it would not fit."""
        return self.num_ctx - (self.max_prompt_tokens + self.reserve_output_tokens)


def truncation_risk(
    measurements: pd.DataFrame,
    *,
    prompt_overhead_chars: int,
    num_ctx: int,
    reserve_output_tokens: int,
) -> TruncationRisk:
    """Count the rows whose approximate prompt would not fit in ``num_ctx``.

    The arithmetic, stated once so the count is reproducible by hand:

        approx_prompt_tokens(row) = ceil((chars + prompt_overhead_chars) / 4)
        at risk  <=>  approx_prompt_tokens + reserve_output_tokens > num_ctx

    The overhead is added in *characters* before the division, because that is
    how the prompt is actually assembled -- rounding the narrative and the
    instructions up separately would double-count a partial token.

    Ollama's ``num_ctx`` bounds the prompt and the generated reply together.
    Our reply is a category name, a handful of tokens, so
    ``--reserve-output-tokens`` defaults to 0 and is there for whoever wants to
    be stricter; it is never guessed on their behalf.
    """
    if num_ctx <= 0:
        raise AnalysisError("--num-ctx must be a positive number of tokens.")
    if reserve_output_tokens < 0:
        raise AnalysisError("--reserve-output-tokens cannot be negative.")

    prompt_tokens = (measurements["chars"] + prompt_overhead_chars).map(approx_token_count)
    at_risk = prompt_tokens + reserve_output_tokens > num_ctx
    return TruncationRisk(
        num_ctx=num_ctx,
        prompt_overhead_chars=prompt_overhead_chars,
        reserve_output_tokens=reserve_output_tokens,
        rows_total=int(len(prompt_tokens)),
        rows_at_risk=int(at_risk.sum()),
        max_prompt_tokens=int(prompt_tokens.max()),
        p99_prompt_tokens=percentile(prompt_tokens.astype("float64"), 0.99),
    )


def truncation_table(
    risk: TruncationRisk | None,
    overhead: PromptOverhead,
    *,
    num_ctx: int,
    reserve_output_tokens: int,
    rows_total: int,
) -> pd.DataFrame:
    """Render the truncation-risk result (or its absence) as a stable table."""
    rule = f"ceil((characters + prompt overhead) / {CHARS_PER_APPROX_TOKEN})"
    rows: list[dict[str, object]] = [
        {
            "quantity": "num_ctx",
            "value": num_ctx,
            "unit": "tokens",
            "how it was obtained": "--num-ctx (configuration contract NUM_CTX)",
        },
        {
            "quantity": "prompt overhead",
            "value": "not established" if overhead.chars is None else overhead.chars,
            "unit": "characters",
            "how it was obtained": overhead.source,
        },
        {
            "quantity": "output tokens reserved",
            "value": reserve_output_tokens,
            "unit": "tokens",
            "how it was obtained": "--reserve-output-tokens (default 0; the reply is a category name)",
        },
        {
            "quantity": "rows measured",
            "value": rows_total,
            "unit": "rows",
            "how it was obtained": "counted from the input CSV",
        },
    ]

    if risk is None:
        rows.append(
            {
                "quantity": "rows at truncation risk",
                "value": "not computed",
                "unit": "rows",
                "how it was obtained": (
                    "blocked: the prompt overhead is not established. Re-run with "
                    "--prompt-overhead-chars N, or once service/prompt.py is importable."
                ),
            }
        )
        return _value_column_as_objects(rows)

    rows.extend(
        [
            {
                "quantity": "approximate prompt tokens, p99",
                "value": risk.p99_prompt_tokens,
                "unit": "approximate tokens",
                "how it was obtained": f"approximation {rule}, linear-interpolated p99",
            },
            {
                "quantity": "approximate prompt tokens, longest row",
                "value": risk.max_prompt_tokens,
                "unit": "approximate tokens",
                "how it was obtained": f"approximation {rule}",
            },
            {
                "quantity": "context headroom at the longest row",
                "value": risk.headroom_tokens,
                "unit": "approximate tokens",
                "how it was obtained": "num_ctx - (longest prompt + reserved output); negative means it would not fit",
            },
            {
                "quantity": "rows at truncation risk",
                "value": risk.rows_at_risk,
                "unit": "rows",
                "how it was obtained": f"count of rows where {rule} + reserved output > num_ctx",
            },
            {
                "quantity": "share of rows at truncation risk",
                "value": risk.share_at_risk_pct,
                "unit": "% of rows measured",
                "how it was obtained": "rows at risk / rows measured",
            },
        ]
    )
    return _value_column_as_objects(rows)


def _value_column_as_objects(rows: list[dict[str, object]]) -> pd.DataFrame:
    """Build the truncation table keeping each value's own type.

    ``DataFrame(list_of_dicts)`` promotes a column of mixed ints and floats to
    float64, which would render a token count as ``4096.00``. The column mixes
    settings, counts and one percentage on purpose, so it is held as ``object``
    and each value keeps the type it was computed with.
    """
    table = pd.DataFrame(rows)[list(TRUNCATION_COLUMNS)]
    table["value"] = pd.Series([row["value"] for row in rows], dtype=object)
    return table


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def _style_axes(axes) -> None:
    """Recessive grid and spines, so the data is the most prominent thing."""
    axes.grid(axis="y", color=COLOUR_GUIDE, alpha=0.35, linewidth=0.6)
    axes.set_axisbelow(True)
    for side in ("top", "right"):
        axes.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axes.spines[side].set_color(COLOUR_GUIDE)


def write_histogram(measurements: pd.DataFrame, out_path: Path, bins: int) -> Path:
    """Three panels -- characters, words, approximate tokens -- as histograms.

    A histogram answers "what shape is this", which is what Slide 3 needs
    alongside the percentile table. Each panel is a single series, so it needs
    no legend; the panel title names it.
    """
    plt = use_headless_matplotlib()
    figure, axes_list = plt.subplots(1, 3, figsize=(12.0, 3.6))
    for axes, (metric, unit) in zip(axes_list, METRIC_UNITS):
        axes.hist(measurements[metric], bins=bins, color=COLOUR_SERIES, edgecolor="white",
                  linewidth=0.8)
        axes.set_title(f"Ticket length in {unit}", fontsize=10)
        axes.set_xlabel(unit)
        axes.set_ylabel("tickets")
        _style_axes(axes)
    figure.suptitle(
        "Distribution of ticket length, measured from our own team rows "
        "(tokens are approximate)",
        fontsize=11,
    )
    figure.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out_path, dpi=150)
    plt.close(figure)
    return out_path


def write_cdf(
    measurements: pd.DataFrame,
    out_path: Path,
    *,
    risk: TruncationRisk | None,
    num_ctx: int,
) -> Path:
    """Two empirical CDFs: characters, and approximate prompt tokens.

    The CDF is the chart a percentile is actually read off -- "x% of tickets are
    at most this long" -- which is why it is here as well as the histogram. The
    right-hand panel carries the ``num_ctx`` line when the prompt overhead is
    known, because the crossing point of the curve and that line *is* the
    truncation risk.
    """
    plt = use_headless_matplotlib()
    figure, (axes_chars, axes_tokens) = plt.subplots(1, 2, figsize=(10.0, 4.0))

    def ecdf(axes, values: pd.Series, xlabel: str, title: str) -> None:
        ordered = values.sort_values().to_numpy()
        # Fraction of the sample at or below each observed value.
        share = [(i + 1) / len(ordered) for i in range(len(ordered))]
        axes.step(ordered, share, where="post", color=COLOUR_SERIES, linewidth=2.0)
        axes.set_xlabel(xlabel)
        axes.set_ylabel("share of tickets at or below")
        axes.set_ylim(0.0, 1.02)
        axes.set_title(title, fontsize=10)
        _style_axes(axes)
        # Direct labels on the percentiles a requirement is likely to quote,
        # rather than a number on every point.
        # The y offsets are staggered because p95 and p99 sit close together at
        # the top of the curve and their labels would otherwise overlap.
        for name, q, y_offset in (("p50", 0.50, -12), ("p95", 0.95, -12), ("p99", 0.99, 5)):
            x = percentile(values.astype("float64"), q)
            axes.axhline(q, color=COLOUR_GUIDE, linewidth=0.8, linestyle=":")
            axes.annotate(
                f"{name} = {x:,.0f}",
                xy=(x, q),
                xytext=(4, y_offset),
                textcoords="offset points",
                fontsize=8,
                color="#52514e",
            )

    ecdf(axes_chars, measurements["chars"], "characters", "Characters per ticket")

    if risk is not None:
        prompt_tokens = (measurements["chars"] + risk.prompt_overhead_chars).map(
            approx_token_count
        )
        token_label = "approximate tokens (narrative + prompt)"
    else:
        prompt_tokens = measurements["approx_tokens"]
        token_label = "approximate tokens (narrative only; prompt overhead unknown)"
    ecdf(axes_tokens, prompt_tokens, token_label, "Approximate tokens per request")
    if risk is not None:
        axes_tokens.axvline(num_ctx, color=COLOUR_LIMIT, linewidth=1.6)
        axes_tokens.annotate(
            f"num_ctx = {num_ctx:,}",
            xy=(num_ctx, 0.5),
            xytext=(-6, 0),
            textcoords="offset points",
            rotation=90,
            ha="right",
            va="center",
            fontsize=8,
            color=COLOUR_LIMIT,
        )

    figure.suptitle(
        "Empirical CDF of ticket length (read percentiles off these curves)",
        fontsize=11,
    )
    figure.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out_path, dpi=150)
    plt.close(figure)
    return out_path


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def write_report(
    out_dir: Path,
    *,
    input_path: Path,
    input_sha256: str,
    distribution: pd.DataFrame,
    truncation: pd.DataFrame,
    charts_written: list[Path],
) -> Path:
    """Write the human-readable Markdown report that ties the tables together.

    Deliberately carries no timestamp: the same input must produce byte-identical
    output, so that a re-run proves the numbers rather than churning the diff.
    """
    lines = [
        "# Ticket length distribution (measured)",
        "",
        f"Produced by `workload/scripts/ticket_length_stats.py` from `{input_path}`.",
        "",
        f"- Input SHA-256: `{input_sha256}`",
        "- These figures are **measured from our own team rows**, not estimated, so",
        "  the workload model records them with `Estimate? = N` and cites this script",
        "  and the input file as the source.",
        "- Token counts are an **approximation**: "
        f"`ceil(characters / {CHARS_PER_APPROX_TOKEN})`. The true count is",
        "  tokeniser-specific and therefore differs per candidate model. The",
        "  authoritative per-request figure is `prompt_eval_count` in the service log",
        "  (`service/log_schema.py`), available once benchmarks run. Do not report the",
        "  approximation as a token measurement.",
        "",
        "## Length distribution",
        "",
        to_markdown_table(distribution),
        "## Context-window (num_ctx) sizing",
        "",
        to_markdown_table(truncation, float_format="{:.2f}"),
        "## Charts",
        "",
    ]
    for chart in charts_written:
        lines.append(f"- `{chart.name}`")
    if not charts_written:
        lines.append("- none (run without `--no-charts` to produce them)")
    lines += [
        "",
        "## What Part 4 must still do with this",
        "",
        "TODO(Part 4 — Teammate C): decide and write down, in",
        "`../workload_model.md`, whether the client's real complaint traffic would",
        "resemble this distribution. These narratives are CFPB complaints filed",
        "through a regulator's web form; the client's own intake channel may differ",
        "in length, and if it does, say so and say which direction.",
        "",
        "TODO(Part 4 — Teammate C): if any row is at truncation risk, raise it with",
        "Part 1 -- Yeo Kai Yuan before the benchmark runs. A silently truncated",
        "prompt is a classification error we would otherwise blame on the model.",
        "",
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / REPORT_MD
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """The argument parser. Kept in its own function so the tests can use it."""
    parser = argparse.ArgumentParser(
        prog="ticket_length_stats.py",
        description=(
            "Measure the character, word and approximate-token length "
            "distribution of our own ticket narratives, and report how many "
            "rows risk silent truncation at a given num_ctx. Runs no model and "
            "calls no tokeniser."
        ),
        epilog=(
            "Approximate tokens are ceil(characters / "
            f"{CHARS_PER_APPROX_TOKEN}); the true count is model-specific and is "
            "logged as prompt_eval_count once benchmarks run."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        "--team-rows",  # the name used in the CLI contract; same destination
        dest="input",
        type=Path,
        default=REPO_ROOT / "data" / "team_rows.csv",
        help=(
            "CSV with a 'narrative' column: the team rows, the dev synthetic "
            "tickets, or a subset of either. --team-rows is an accepted alias."
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "workload" / "output",
        help="Directory for the tables, the report and the charts.",
    )
    parser.add_argument(
        "--num-ctx",
        type=int,
        default=DEFAULT_NUM_CTX,
        help="Context window to test rows against (configuration contract NUM_CTX).",
    )
    parser.add_argument(
        "--prompt-overhead-chars",
        type=int,
        default=None,
        help=(
            "Characters the fixed prompt adds around a narrative. Omit to measure "
            "it from service/prompt.py; if that is not importable the truncation "
            "risk is reported as 'not computed' rather than guessed."
        ),
    )
    parser.add_argument(
        "--reserve-output-tokens",
        type=int,
        default=0,
        help=(
            "Tokens to reserve inside num_ctx for the model's reply. The reply is "
            "a category name, so 0 by default; raise it to be stricter."
        ),
    )
    parser.add_argument(
        "--bins",
        type=int,
        default=DEFAULT_BINS,
        help="Histogram bins. A chart parameter; it changes no statistic.",
    )
    parser.add_argument(
        "--no-charts",
        action="store_true",
        help="Write the tables only. Useful when re-checking numbers quickly.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code; never raises AnalysisError."""
    args = build_parser().parse_args(argv)

    try:
        if args.bins < 1:
            raise AnalysisError("--bins must be at least 1.")

        input_path: Path = args.input
        frame = read_narratives(input_path)
        measurements = measure(frame)
        distribution = distribution_table(measurements)

        overhead = resolve_prompt_overhead(args.prompt_overhead_chars)
        risk: TruncationRisk | None = None
        if overhead.chars is not None:
            risk = truncation_risk(
                measurements,
                prompt_overhead_chars=overhead.chars,
                num_ctx=args.num_ctx,
                reserve_output_tokens=args.reserve_output_tokens,
            )
        else:
            # Loud on stderr, and visible in the table: a missing input, not a
            # zero. Not fatal, because the length distribution itself is fine.
            print(
                "warning: prompt overhead not established, so the truncation "
                f"risk was not computed ({overhead.source}).",
                file=sys.stderr,
            )

        truncation = truncation_table(
            risk,
            overhead,
            num_ctx=args.num_ctx,
            reserve_output_tokens=args.reserve_output_tokens,
            rows_total=int(len(measurements)),
        )

        out_dir: Path = args.out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        per_row_path = out_dir / PER_ROW_CSV
        measurements.to_csv(per_row_path, index=False)
        dist_csv, dist_md = write_table(distribution, out_dir, STEM_DISTRIBUTION)
        trunc_csv, trunc_md = write_table(
            truncation, out_dir, STEM_TRUNCATION, float_format="{:.2f}"
        )

        charts: list[Path] = []
        if not args.no_charts:
            charts.append(write_histogram(measurements, out_dir / HISTOGRAM_PNG, args.bins))
            charts.append(
                write_cdf(measurements, out_dir / CDF_PNG, risk=risk, num_ctx=args.num_ctx)
            )

        input_sha256 = hashlib.sha256(input_path.read_bytes()).hexdigest()
        report_path = write_report(
            out_dir,
            input_path=input_path,
            input_sha256=input_sha256,
            distribution=distribution,
            truncation=truncation,
            charts_written=charts,
        )
    except AnalysisError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    written = [per_row_path, dist_csv, dist_md, trunc_csv, trunc_md, *charts, report_path]
    print(f"Measured {len(measurements)} ticket narratives from {input_path}")
    for path in written:
        print(f"  wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
