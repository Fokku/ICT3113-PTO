"""Classification accuracy of the baseline service, measured against the golden set.

Owner: Yeo Kai Yuan (Part 5 measurement tooling). Feeds **Slide 10 — Accuracy
Results**; ``misclassified.csv`` is the file Teammate B reads to write the
"where each model goes wrong" commentary.

What it reads
-------------
``--results`` points at ``results/accuracy/``, which holds one directory per
accuracy run named ``<sanitised-model-tag>_<UTCSTAMP>`` (see the results layout
contract). From each directory this script reads:

* ``service.jsonl`` -- the request log. **This is the evidence of record.** The
  brief requires every reported number to reconcile with the service log, so the
  predictions are taken from the log rather than from the convenience copy in
  ``responses.csv`` that ``scripts/run_accuracy.py`` also writes.
* ``metadata.json`` -- the model tag, the run mode and the freeze commit. A
  result directory without its metadata is not evidence, so a missing
  ``metadata.json`` is a hard error.

Joining
-------
The log line and the golden row are joined on **row number**: the service log
field ``source_row`` (a string, set from the ``X-Source-Row`` header that the
accuracy driver sends) against the golden set column ``row_number``. Only
``POST /tickets`` lines are considered, and warm-up lines are dropped.

Four join hazards are handled explicitly and reported rather than smoothed over:

1. **A golden row with no response.** The row is listed in
   ``missing_rows.csv``. It reduces coverage, and incomplete coverage fails the
   run (see "Exit codes"): an accuracy figure computed over part of the golden
   set is not the figure we said we would measure.
2. **A response with no golden row** (including a response whose ``source_row``
   is null or blank). Listed in ``unmatched_responses.csv`` and excluded. It
   usually means the driver was pointed at the wrong input CSV.
3. **More than one response for the same row.** All of them are listed in
   ``duplicates.csv`` and the **last by timestamp** is the one scored (ties
   broken by ``request_id`` so the choice is deterministic). Why the last: the
   accuracy driver sends each golden row exactly once, so a second response
   means either an operator re-sent a row after an error -- in which case the
   re-send is intended to supersede the failure -- or two passes were written
   into one directory, in which case the later pass is the current one. We never
   pick the *better* of the two, and we never average them; the duplicated row
   numbers are printed as a warning so a human can decide whether the directory
   should simply be re-run.
4. **A response with no usable prediction**, i.e. ``predicted_category`` is
   null. That is the model-failure path (HTTP 502, nothing stored). Those rows
   are listed in ``errored_responses.csv`` and are **not** scored -- scoring
   them as wrong would blame the model for an infrastructure timeout -- but they
   do count against coverage, because we have no classification for that golden
   row either way.

Metric definitions (stated in the output as well, because a confusion-matrix
discussion is only meaningful if the reader knows which figure is which)
--------------------------------------------------------------------------
* **Overall accuracy** = correct predictions / evaluated rows, where the
  evaluated rows are the golden rows that produced a prediction. ``UNPARSEABLE``
  is in the denominator and never in the numerator: the client gets no routing
  from an unparseable reply, so it is not a success.
* **Accuracy excluding UNPARSEABLE** is reported alongside it, over the
  parseable subset only, so the reader can separate "the model chose the wrong
  category" from "we could not read the model's answer".
* **Per-category accuracy is recall**: of the golden rows truly in category C,
  the fraction predicted C. This is the per-category figure the accuracy
  requirement is written against.
* **Precision** for category C: of the rows predicted C, the fraction truly C.
  Reported because recall alone hides a model that answers "Debt collection" to
  everything.
* **Support** for category C: the number of evaluated golden rows truly in C.
  A recall computed over a handful of rows is not worth much, and the reader
  must be able to see that.
* **Macro recall / macro precision**: the unweighted mean over the categories
  with non-zero support. Unweighted because the requirement is per category, so
  a category with few golden rows must not be allowed to disappear.
* ``UNPARSEABLE`` is counted separately throughout and is **never** folded into
  a specific category's error count. In the confusion matrix it is an extra
  **predicted-only column** (no golden row is ever labelled ``UNPARSEABLE``).

Outputs (under ``--out-dir``, one subdirectory per accuracy run)
---------------------------------------------------------------
``confusion_matrix.csv`` / ``.md`` / ``.png``, ``per_category.csv`` / ``.md``,
``overall.csv`` / ``.md``, ``misclassified.csv``, ``duplicates.csv``,
``missing_rows.csv``, ``unmatched_responses.csv``, ``errored_responses.csv``
and ``report.md``. At the top level: ``model_comparison.csv`` / ``.md`` (one row
per accuracy run, which is the per-model comparison when several models have
been measured) and ``accuracy_report.md``.

The confusion-matrix PNG uses a greyscale colour map on purpose: the deck and
the printed report must stay readable in black and white, and a cell is
annotated with its count so the reader never has to interpolate a colour.

Exit codes
----------
* ``0`` -- every accuracy run was scored over the complete golden set.
* ``1`` -- a sanity check failed: the golden set is missing or unusable, no
  responses were found, or coverage of the golden set is incomplete for at least
  one model. The tables and charts are still written first, so the operator can
  see *what* is missing, and then the run fails.

Development-time rule
---------------------
This script must not be run against real model output before the golden set and
the prediction record are frozen. Its tests run entirely on fabricated log
lines, and no example in this file contains a measured value.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:  # so `python analysis/accuracy.py` works
    sys.path.insert(0, str(_REPO_ROOT))

from analysis.common import (  # noqa: E402
    REPO_ROOT,
    CATEGORIES,
    UNPARSEABLE,
    AnalysisError,
    exclude_warmup,
    load_metadata,
    read_service_log,
    to_markdown_table,
    use_headless_matplotlib,
    write_table,
)
from service.categories import VALID_STORED_VALUES  # noqa: E402

# ``results/accuracy/<sanitised-model-tag>_<UTCSTAMP>``. The model tag is
# sanitised for the filesystem, so it may itself contain '_'; the stamp is
# anchored at the end, which makes the split unambiguous.
ACCURACY_DIR_RE = re.compile(r"^(?P<model>.+)_(?P<stamp>\d{8}T\d{6}Z)$")

#: Accepted spellings of the golden label column, in priority order. Part 1 owns
#: ``golden/golden_set.csv``; this script does not dictate its column name, but
#: it refuses to guess beyond this list.
GOLDEN_LABEL_COLUMNS: tuple[str, ...] = ("golden_label", "final_label", "label", "category")
#: Accepted spellings of an optional narrative column in the golden set.
GOLDEN_NARRATIVE_COLUMNS: tuple[str, ...] = ("narrative", "ticket", "text")

DEFAULT_RESULTS = REPO_ROOT / "results" / "accuracy"
DEFAULT_GOLDEN = REPO_ROOT / "golden" / "golden_set.csv"
DEFAULT_OUT_DIR = REPO_ROOT / "analysis" / "output" / "accuracy"
DEFAULT_TEAM_ROWS = REPO_ROOT / "data" / "team_rows.csv"

#: Columns of ``misclassified.csv``. Teammate B reads this file by hand, so the
#: order is "identify the row, then see the disagreement, then read the ticket".
MISCLASSIFIED_COLUMNS: tuple[str, ...] = (
    "row_number",
    "golden_label",
    "predicted_label",
    "raw_model_output",
    "narrative_prefix",
    "request_id",
    "ts",
)

_WHITESPACE_RE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------

def _flatten(text: object, limit: int | None = None) -> str:
    """Collapse whitespace (and optionally truncate) for a human-readable cell.

    The untouched value always remains in ``service.jsonl``; this is only so
    that a spreadsheet does not show one ticket across fifteen rows.
    """
    if text is None or (isinstance(text, float) and pd.isna(text)) or text is pd.NA:
        return ""
    flat = _WHITESPACE_RE.sub(" ", str(text)).strip()
    return flat if limit is None else flat[:limit]


def _format_ts(value: object) -> str:
    """Render a log timestamp back in the service's own format (ISO-8601, ms, Z).

    ``read_service_log`` parses ``ts`` into a pandas timestamp; printing that
    repr into a CSV would hand Teammate B a string that does not appear in
    ``service.jsonl``, which makes the row harder to trace back to its log line.
    """
    if value is None or value is pd.NA:
        return ""
    moment = pd.Timestamp(value)
    if pd.isna(moment):
        return ""
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def _sort_by_row_number(frame: pd.DataFrame, *extra: str) -> pd.DataFrame:
    """Sort by row number numerically where possible, then by ``extra`` columns.

    Row numbers are carried as strings everywhere (the log field is a string),
    so a plain lexicographic sort would put row 10100 before row 9999. Output
    ordering has to be deterministic because ``analysis/output/`` is committed.
    """
    if frame.empty:
        return frame
    keyed = frame.assign(_row_sort=pd.to_numeric(frame["row_number"], errors="coerce"))
    keyed = keyed.sort_values(
        ["_row_sort", "row_number", *extra], na_position="last", kind="stable"
    )
    return keyed.drop(columns="_row_sort").reset_index(drop=True)


def _pick_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    """First of ``candidates`` present in ``frame``, or ``None``."""
    for name in candidates:
        if name in frame.columns:
            return name
    return None


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AccuracyRun:
    """One ``results/accuracy/<model>_<stamp>`` directory and its metadata."""

    path: Path
    dir_model: str
    stamp: str
    model_tag: str
    mode: str
    freeze_commit: str | None

    @property
    def label(self) -> str:
        """Short human label used in tables and chart titles."""
        return f"{self.model_tag} @ {self.stamp}"


def parse_accuracy_dir_name(path: Path) -> tuple[str, str] | None:
    """Split ``<model>_<UTCSTAMP>`` into its two parts, or return ``None``."""
    match = ACCURACY_DIR_RE.match(path.name)
    if not match:
        return None
    return match["model"], match["stamp"]


def iter_accuracy_runs(root: Path) -> list[AccuracyRun]:
    """Every accuracy run directory under ``root``, sorted by directory name.

    Raises rather than returning an empty list: silently reporting "no models
    measured" as a successful run is the failure mode we cannot afford.
    """
    if not root.is_dir():
        raise AnalysisError(
            f"No such accuracy results directory: {root}. Run "
            f"scripts/run_accuracy.py first."
        )
    runs: list[AccuracyRun] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        parsed = parse_accuracy_dir_name(child)
        if parsed is None:
            continue
        dir_model, stamp = parsed
        meta = load_metadata(child)  # raises loudly when metadata.json is absent
        runs.append(
            AccuracyRun(
                path=child,
                dir_model=dir_model,
                stamp=stamp,
                # Prefer the real Ollama tag from metadata; the directory name is
                # sanitised for the filesystem and has lost ':' and '/'.
                model_tag=str(meta.get("model_tag") or dir_model),
                mode=str(meta.get("mode") or "unknown"),
                freeze_commit=meta.get("freeze_commit"),
            )
        )
    if not runs:
        raise AnalysisError(
            f"{root} contains no directories named <model>_<UTCSTAMP> "
            f"(for example testmodel-1b_20261001T090000Z). Nothing to analyse."
        )
    return runs


def load_golden_set(path: Path) -> pd.DataFrame:
    """Read the golden set into ``row_number`` / ``golden_label`` / ``narrative``.

    Everything is read as text: row numbers are compared as strings against the
    service log's ``source_row``, and pandas must not be allowed to turn a row
    number into a float or an empty narrative into ``NaN``.

    Golden labels must be exactly one of the seven canonical category names. The
    check is deliberately strict -- no case folding and no alias matching. A
    human label that does not match a canonical name is a defect in the
    labelling pipeline, and quietly repairing it here would mean this script,
    rather than Part 1, deciding what a labeller meant.
    """
    if not path.is_file():
        raise AnalysisError(
            f"Golden set not found: {path}. Accuracy cannot be measured without "
            f"it; build it with labelling/scripts/build_golden_set.py."
        )
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if frame.empty:
        raise AnalysisError(f"{path} has a header but no rows.")

    if "row_number" not in frame.columns:
        raise AnalysisError(
            f"{path} has no 'row_number' column (found {list(frame.columns)}). "
            f"The golden set must identify each ticket by its course CSV row."
        )
    label_column = _pick_column(frame, GOLDEN_LABEL_COLUMNS)
    if label_column is None:
        raise AnalysisError(
            f"{path} has no golden label column. Accepted names, in priority "
            f"order: {list(GOLDEN_LABEL_COLUMNS)}. Found: {list(frame.columns)}."
        )
    narrative_column = _pick_column(frame, GOLDEN_NARRATIVE_COLUMNS)

    golden = pd.DataFrame(
        {
            "row_number": frame["row_number"].astype("string").str.strip(),
            "golden_label": frame[label_column].astype("string").str.strip(),
            "narrative": (
                frame[narrative_column].astype("string").fillna("")
                if narrative_column
                else pd.Series([""] * len(frame), dtype="string")
            ),
        }
    )

    blank = golden["row_number"].isna() | (golden["row_number"] == "")
    if bool(blank.any()):
        raise AnalysisError(
            f"{path} has {int(blank.sum())} row(s) with an empty 'row_number'. "
            f"Every golden ticket must be identified by its row."
        )
    duplicated = golden.loc[golden["row_number"].duplicated(keep=False), "row_number"]
    if not duplicated.empty:
        raise AnalysisError(
            f"{path} labels the same row more than once: "
            f"{sorted(set(duplicated.tolist()))}. The golden set must hold one "
            f"agreed label per row."
        )
    unknown = sorted(set(golden.loc[~golden["golden_label"].isin(CATEGORIES), "golden_label"]))
    if unknown:
        raise AnalysisError(
            f"{path} contains label(s) that are not one of the seven canonical "
            f"categories: {unknown}. Expected exactly one of "
            f"{list(CATEGORIES)} (spelling and capitalisation included)."
        )
    return golden


def load_narratives(golden: pd.DataFrame, team_rows: Path) -> tuple[dict[str, str], str]:
    """Row number -> narrative text, for the ``misclassified.csv`` prefix column.

    The service log deliberately does not store the narrative (only its length),
    so the text has to come from the input data. Preference order:

    1. a narrative column in the golden set -- the frozen artefact, so it is the
       safest source;
    2. ``--team-rows`` (``data/team_rows.csv``), the CSV the driver posted from;
    3. nothing, in which case the column is left empty and the report says so
       rather than pretending the ticket text was unavailable for a good reason.
    """
    populated = golden.loc[golden["narrative"].fillna("") != ""]
    if not populated.empty:
        return dict(zip(populated["row_number"], populated["narrative"])), (
            "the golden set's own narrative column"
        )
    if team_rows.is_file():
        rows = pd.read_csv(team_rows, dtype=str, keep_default_na=False)
        if "row_number" in rows.columns and "narrative" in rows.columns:
            return (
                dict(
                    zip(
                        rows["row_number"].astype("string").str.strip(),
                        rows["narrative"].astype("string").fillna(""),
                    )
                ),
                str(team_rows),
            )
    return {}, "not available"


def load_responses(run_dir: Path) -> pd.DataFrame:
    """Every measured ``POST /tickets`` log line from one accuracy run.

    Returns the log frame with a ``row_number`` column (the stripped
    ``source_row``). Warm-up lines are excluded here as well as by the run
    script, because a warm-up ticket is not a golden ticket.
    """
    log_path = run_dir / "service.jsonl"
    frame = exclude_warmup(read_service_log(log_path))
    tickets = frame.loc[
        (frame["endpoint"] == "/tickets") & (frame["method"] == "POST")
    ].copy()
    if tickets.empty:
        raise AnalysisError(
            f"{log_path} holds no measured POST /tickets lines. The accuracy run "
            f"produced no responses to score."
        )
    tickets["row_number"] = tickets["source_row"].astype("string").str.strip()
    predicted = tickets["predicted_category"].astype("string")
    illegal = sorted(set(predicted.dropna()) - set(VALID_STORED_VALUES))
    if illegal:
        raise AnalysisError(
            f"{log_path} contains predicted_category value(s) the service should "
            f"never store: {illegal}. Expected one of the seven categories or "
            f"'{UNPARSEABLE}'."
        )
    tickets["predicted_label"] = predicted
    return tickets


# ---------------------------------------------------------------------------
# Join
# ---------------------------------------------------------------------------

@dataclass
class JoinOutcome:
    """The result of joining one run's responses to the golden set."""

    evaluated: pd.DataFrame
    duplicates: pd.DataFrame
    missing_rows: pd.DataFrame
    unmatched_responses: pd.DataFrame
    errored_responses: pd.DataFrame
    n_responses: int
    warnings: list[str] = field(default_factory=list)


def join_to_golden(golden: pd.DataFrame, responses: pd.DataFrame) -> JoinOutcome:
    """Join responses to golden rows on row number; see the module docstring."""
    warnings: list[str] = []
    golden_rows = set(golden["row_number"])

    has_row = responses["row_number"].notna() & (responses["row_number"] != "")
    no_row = responses.loc[~has_row]
    with_row = responses.loc[has_row].copy()

    in_golden = with_row["row_number"].isin(golden_rows)
    foreign = with_row.loc[~in_golden]
    matched = with_row.loc[in_golden].copy()

    unmatched_frame = pd.concat([no_row, foreign], ignore_index=True)
    unmatched = pd.DataFrame(
        {
            "row_number": unmatched_frame["row_number"].fillna("")
            if not unmatched_frame.empty
            else pd.Series(dtype="string"),
            "request_id": unmatched_frame["request_id"]
            if not unmatched_frame.empty
            else pd.Series(dtype="string"),
            "ts": unmatched_frame["ts"].map(_format_ts)
            if not unmatched_frame.empty
            else pd.Series(dtype="string"),
            "predicted_label": unmatched_frame["predicted_label"]
            if not unmatched_frame.empty
            else pd.Series(dtype="string"),
            "reason": (
                ["no source_row header"] * len(no_row)
                + ["source_row not in the golden set"] * len(foreign)
            ),
        }
    )
    if not no_row.empty:
        warnings.append(
            f"{len(no_row)} response(s) carried no source_row and could not be "
            f"joined to a golden row. Does the JMeter/driver header "
            f"X-Source-Row reach the service?"
        )
    if not foreign.empty:
        warnings.append(
            f"{len(foreign)} response(s) referenced row number(s) that are not in "
            f"the golden set (for example "
            f"{sorted(set(foreign['row_number']))[:5]}). They are excluded. Was "
            f"the driver pointed at the right input CSV?"
        )

    # Deterministic duplicate resolution: last by timestamp, then by request_id.
    matched = matched.sort_values(["row_number", "ts", "request_id"], kind="stable")
    counts = matched.groupby("row_number", sort=True).size()
    duplicated_rows = [row for row, n in counts.items() if n > 1]
    duplicate_records: list[dict[str, object]] = []
    for row in duplicated_rows:
        group = matched.loc[matched["row_number"] == row]
        kept = group.iloc[-1]
        duplicate_records.append(
            {
                "row_number": row,
                "n_responses": int(len(group)),
                "kept_request_id": str(kept["request_id"]),
                "kept_ts": _format_ts(kept["ts"]),
                "kept_predicted_label": _flatten(kept["predicted_label"]),
                "dropped_request_ids": " ".join(
                    str(v) for v in group["request_id"].tolist()[:-1]
                ),
                "dropped_predicted_labels": " | ".join(
                    _flatten(v) for v in group["predicted_label"].tolist()[:-1]
                ),
            }
        )
    duplicates = pd.DataFrame(
        duplicate_records,
        columns=[
            "row_number",
            "n_responses",
            "kept_request_id",
            "kept_ts",
            "kept_predicted_label",
            "dropped_request_ids",
            "dropped_predicted_labels",
        ],
    )
    if duplicated_rows:
        warnings.append(
            f"{len(duplicated_rows)} golden row(s) received more than one "
            f"response: {sorted(duplicated_rows)[:10]}. The LAST response by "
            f"timestamp was scored for each; see duplicates.csv. Consider "
            f"re-running the accuracy pass into a clean directory."
        )
    deduped = matched.drop_duplicates(subset="row_number", keep="last")

    joined = golden.merge(
        deduped[
            [
                "row_number",
                "request_id",
                "ts",
                "status",
                "predicted_label",
                "raw_model_output",
                "error",
            ]
        ],
        on="row_number",
        how="left",
    )

    responded = joined["request_id"].notna()
    missing = joined.loc[~responded]
    missing_rows = pd.DataFrame(
        {
            "row_number": missing["row_number"],
            "golden_label": missing["golden_label"],
            "reason": ["no response in this run's service log"] * len(missing),
        },
        columns=["row_number", "golden_label", "reason"],
    )
    if not missing.empty:
        warnings.append(
            f"{len(missing)} golden row(s) have no response at all in this run "
            f"(for example {sorted(missing['row_number'].tolist())[:5]}). "
            f"Coverage of the golden set is incomplete."
        )

    answered = joined.loc[responded].copy()
    has_prediction = answered["predicted_label"].notna()
    errored = answered.loc[~has_prediction]
    errored_responses = pd.DataFrame(
        {
            "row_number": errored["row_number"],
            "golden_label": errored["golden_label"],
            "request_id": errored["request_id"],
            "status": errored["status"],
            "error": (
                errored["error"].map(_flatten)
                if not errored.empty
                else pd.Series(dtype="string")
            ),
        },
        columns=["row_number", "golden_label", "request_id", "status", "error"],
    )
    if not errored.empty:
        warnings.append(
            f"{len(errored)} response(s) carried no predicted_category (the model "
            f"call failed). They are excluded from the accuracy figures -- an "
            f"Ollama timeout is not a wrong guess -- but they still count "
            f"against coverage; see errored_responses.csv."
        )

    evaluated = answered.loc[has_prediction].copy()
    evaluated["predicted_label"] = evaluated["predicted_label"].astype(str)
    evaluated["correct"] = evaluated["predicted_label"] == evaluated["golden_label"]

    return JoinOutcome(
        evaluated=_sort_by_row_number(evaluated),
        duplicates=duplicates,
        missing_rows=_sort_by_row_number(missing_rows),
        unmatched_responses=unmatched,
        errored_responses=_sort_by_row_number(errored_responses),
        n_responses=int(len(responses)),
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def build_confusion_matrix(evaluated: pd.DataFrame) -> pd.DataFrame:
    """Counts of golden label (rows) against predicted label (columns).

    Axis order is ``service.categories.CATEGORIES`` exactly, with
    ``UNPARSEABLE`` appended as a **predicted-only** column: no golden row can
    carry it, so it has no row of its own. Every cell is present even when zero,
    because a zero in a confusion matrix is information.
    """
    rows = list(CATEGORIES)
    columns = [*CATEGORIES, UNPARSEABLE]
    matrix = pd.DataFrame(0, index=rows, columns=columns, dtype=int)
    if not evaluated.empty:
        for (golden_label, predicted_label), count in (
            evaluated.groupby(["golden_label", "predicted_label"]).size().items()
        ):
            matrix.loc[golden_label, predicted_label] = int(count)
    matrix.index.name = "golden_label"
    return matrix


def per_category_metrics(matrix: pd.DataFrame) -> pd.DataFrame:
    """Recall, precision, F1, support and UNPARSEABLE count for each category.

    ``recall`` is the figure we call "per-category accuracy" in the deck; the
    column is named ``recall`` here so that nobody can mistake it for precision.
    Where a denominator is zero the cell is NaN, never 0.0: "no golden rows in
    this category" and "got every one of them wrong" are different findings.
    """
    records: list[dict[str, object]] = []
    for category in CATEGORIES:
        support = int(matrix.loc[category].sum())
        predicted_as = int(matrix[category].sum())
        correct = int(matrix.loc[category, category])
        unparseable = int(matrix.loc[category, UNPARSEABLE])
        recall = correct / support if support else float("nan")
        precision = correct / predicted_as if predicted_as else float("nan")
        if support and predicted_as and (recall + precision) > 0:
            f1 = 2 * recall * precision / (recall + precision)
        else:
            f1 = float("nan")
        records.append(
            {
                "category": category,
                "support": support,
                "predicted_as": predicted_as,
                "correct": correct,
                "recall": recall,
                "precision": precision,
                "f1": f1,
                "unparseable": unparseable,
            }
        )
    return pd.DataFrame(
        records,
        columns=[
            "category",
            "support",
            "predicted_as",
            "correct",
            "recall",
            "precision",
            "f1",
            "unparseable",
        ],
    )


def overall_metrics(
    run: AccuracyRun,
    golden: pd.DataFrame,
    outcome: JoinOutcome,
    matrix: pd.DataFrame,
    per_category: pd.DataFrame,
) -> dict[str, object]:
    """The one-row summary of a single accuracy run.

    ``macro_recall`` and ``macro_precision`` are unweighted means over the
    categories with non-zero support, and a NaN cell (a category nothing was
    predicted as has no precision) is skipped rather than counted as zero. The
    per-category table is the place to see which categories contributed.
    """
    golden_rows = int(len(golden))
    evaluated = int(matrix.to_numpy().sum())
    correct = int(sum(matrix.loc[c, c] for c in CATEGORIES))
    unparseable = int(matrix[UNPARSEABLE].sum())
    parseable = evaluated - unparseable
    scored = per_category.loc[per_category["support"] > 0]
    return {
        "model_tag": run.model_tag,
        "stamp": run.stamp,
        "mode": run.mode,
        "golden_rows": golden_rows,
        "responses": outcome.n_responses,
        "evaluated": evaluated,
        "coverage": (evaluated / golden_rows) if golden_rows else float("nan"),
        "correct": correct,
        "accuracy": (correct / evaluated) if evaluated else float("nan"),
        "unparseable": unparseable,
        "unparseable_rate": (unparseable / evaluated) if evaluated else float("nan"),
        "accuracy_excl_unparseable": (correct / parseable) if parseable else float("nan"),
        "macro_recall": float(scored["recall"].mean()) if not scored.empty else float("nan"),
        "macro_precision": (
            float(scored["precision"].mean()) if not scored.empty else float("nan")
        ),
        "missing_golden_rows": int(len(outcome.missing_rows)),
        "errored_responses": int(len(outcome.errored_responses)),
        "duplicate_rows": int(len(outcome.duplicates)),
        "unmatched_responses": int(len(outcome.unmatched_responses)),
    }


def build_misclassified(
    evaluated: pd.DataFrame, narratives: dict[str, str], narrative_chars: int
) -> pd.DataFrame:
    """Every evaluated row whose prediction is not the golden label.

    ``UNPARSEABLE`` rows are included and are visible as such in
    ``predicted_label``: they are the rows where the deck has to explain that
    the model's answer could not be read at all, which is a different story
    from a confusion between two categories.
    """
    wrong = evaluated.loc[~evaluated["correct"]].copy()
    if wrong.empty:
        return pd.DataFrame(columns=list(MISCLASSIFIED_COLUMNS))
    built = pd.DataFrame(
        {
            "row_number": wrong["row_number"].astype(str),
            "golden_label": wrong["golden_label"].astype(str),
            "predicted_label": wrong["predicted_label"].astype(str),
            "raw_model_output": [_flatten(v) for v in wrong["raw_model_output"]],
            "narrative_prefix": [
                _flatten(narratives.get(str(row), ""), narrative_chars)
                for row in wrong["row_number"]
            ],
            "request_id": wrong["request_id"].astype(str),
            "ts": [_format_ts(v) for v in wrong["ts"]],
        },
        columns=list(MISCLASSIFIED_COLUMNS),
    )
    # Group the file by golden label in canonical order so that a reader working
    # through one category's mistakes sees them together.
    order = {name: index for index, name in enumerate(CATEGORIES)}
    built = built.assign(_label_sort=built["golden_label"].map(order))
    built = built.assign(_row_sort=pd.to_numeric(built["row_number"], errors="coerce"))
    built = built.sort_values(
        ["_label_sort", "_row_sort", "row_number"], na_position="last", kind="stable"
    )
    return built.drop(columns=["_label_sort", "_row_sort"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def write_confusion_png(matrix: pd.DataFrame, out_path: Path, title: str) -> Path:
    """Write the confusion matrix as an annotated greyscale heatmap.

    Greyscale (``Greys``) because the slide deck and any printed copy must stay
    readable in black and white, and because a colour scale that encodes counts
    is useless without the counts: every cell carries its number, with the text
    switching to white on the darkest cells so it stays legible. A vertical rule
    separates the ``UNPARSEABLE`` column, which is predicted-only.
    """
    plt = use_headless_matplotlib()
    values = matrix.to_numpy(dtype=float)
    n_rows, n_columns = values.shape
    vmax = max(1.0, float(values.max()))

    fig, ax = plt.subplots(figsize=(1.05 * n_columns + 3.2, 0.72 * n_rows + 2.8))
    image = ax.imshow(values, cmap="Greys", vmin=0.0, vmax=vmax, aspect="auto")
    ax.set_xticks(range(n_columns), labels=list(matrix.columns), rotation=35, ha="right")
    ax.set_yticks(range(n_rows), labels=list(matrix.index))
    ax.set_xlabel("Predicted category (UNPARSEABLE is predicted-only)")
    ax.set_ylabel("Golden label")
    ax.set_title(title)
    for row in range(n_rows):
        for column in range(n_columns):
            count = int(values[row, column])
            ax.text(
                column,
                row,
                str(count),
                ha="center",
                va="center",
                fontsize=9,
                # Dark cells need light text; 0.6 of the scale is where the grey
                # map stops being readable with black text.
                color="white" if values[row, column] > 0.6 * vmax else "black",
            )
    ax.axvline(len(CATEGORIES) - 0.5, color="black", linewidth=1.4)
    fig.colorbar(image, ax=ax, label="tickets")
    fig.tight_layout()
    # metadata Date=None keeps the PNG byte-identical across runs with identical
    # inputs; analysis/output/ is committed and must not churn.
    fig.savefig(out_path, dpi=150, metadata={"Date": None})
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# Per-run analysis
# ---------------------------------------------------------------------------

@dataclass
class RunReport:
    """Everything one accuracy run produced, plus whether it passed its checks."""

    run: AccuracyRun
    overall: dict[str, object]
    per_category: pd.DataFrame
    matrix: pd.DataFrame
    misclassified: pd.DataFrame
    outcome: JoinOutcome
    out_dir: Path
    narrative_source: str
    failures: list[str] = field(default_factory=list)


def analyse_run(
    run: AccuracyRun,
    golden: pd.DataFrame,
    narratives: dict[str, str],
    narrative_source: str,
    out_root: Path,
    narrative_chars: int,
    make_charts: bool,
) -> RunReport:
    """Score one accuracy run and write all of its output files."""
    responses = load_responses(run.path)
    outcome = join_to_golden(golden, responses)
    matrix = build_confusion_matrix(outcome.evaluated)
    per_category = per_category_metrics(matrix)
    overall = overall_metrics(run, golden, outcome, matrix, per_category)
    misclassified = build_misclassified(outcome.evaluated, narratives, narrative_chars)

    out_dir = out_root / run.path.name
    out_dir.mkdir(parents=True, exist_ok=True)

    write_table(matrix.reset_index(), out_dir, "confusion_matrix", float_format="{:.0f}")
    write_table(per_category, out_dir, "per_category", float_format="{:.4f}")
    write_table(pd.DataFrame([overall]), out_dir, "overall", float_format="{:.4f}")
    misclassified.to_csv(out_dir / "misclassified.csv", index=False)
    outcome.duplicates.to_csv(out_dir / "duplicates.csv", index=False)
    outcome.missing_rows.to_csv(out_dir / "missing_rows.csv", index=False)
    outcome.unmatched_responses.to_csv(out_dir / "unmatched_responses.csv", index=False)
    outcome.errored_responses.to_csv(out_dir / "errored_responses.csv", index=False)
    if make_charts:
        write_confusion_png(
            matrix,
            out_dir / "confusion_matrix.png",
            f"Confusion matrix — {run.model_tag} ({run.stamp})",
        )

    failures: list[str] = []
    evaluated = int(overall["evaluated"])
    golden_rows = int(overall["golden_rows"])
    if evaluated < golden_rows:
        failures.append(
            f"{run.label}: only {evaluated} of {golden_rows} golden rows were "
            f"scored ({len(outcome.missing_rows)} with no response, "
            f"{len(outcome.errored_responses)} with a failed model call). An "
            f"accuracy figure over a subset of the golden set is not the figure "
            f"we said we would measure: re-send the missing rows and re-run."
        )
    if evaluated == 0:
        failures.append(f"{run.label}: no golden row produced a usable prediction.")

    report = RunReport(
        run=run,
        overall=overall,
        per_category=per_category,
        matrix=matrix,
        misclassified=misclassified,
        outcome=outcome,
        out_dir=out_dir,
        narrative_source=narrative_source,
        failures=failures,
    )
    (out_dir / "report.md").write_text(render_run_report(report), encoding="utf-8")
    return report


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

_DEFINITIONS_MD = f"""\
### How to read these figures

* **Overall accuracy** = correct / evaluated golden rows. `{UNPARSEABLE}` counts
  in the denominator and never in the numerator: an unreadable reply routes no
  ticket.
* **Accuracy excluding {UNPARSEABLE}** is the same figure over the parseable
  replies only. Quote both, so that a parsing problem is never presented as a
  classification problem.
* **Per-category accuracy is recall**: of the golden rows truly in category C,
  the fraction predicted C. This is the figure the per-category accuracy
  requirement is written against.
* **Precision** for C: of the rows predicted C, the fraction truly C.
* **Support**: evaluated golden rows truly in C. Read every recall next to its
  support.
* `{UNPARSEABLE}` is a **predicted-only** column of the confusion matrix. It is
  never attributed to a category the model did not name.
"""


def _fmt(value: object, digits: int = 4) -> str:
    """Format a metric for prose, showing ``n/a`` rather than a fake zero."""
    if isinstance(value, float):
        if pd.isna(value):
            return "n/a"
        return f"{value:.{digits}f}"
    return str(value)


def render_run_report(report: RunReport) -> str:
    """The per-run ``report.md``: the figures, the caveats, and what is next."""
    overall = report.overall
    lines: list[str] = [
        f"# Accuracy -- {report.run.model_tag} ({report.run.stamp})",
        "",
        f"* Accuracy run directory: `{report.run.path}`",
        f"* Run mode: `{report.run.mode}`",
        f"* Freeze commit: `{report.run.freeze_commit}`",
        f"* Narrative source for misclassified.csv: {report.narrative_source}",
        "",
    ]
    if report.run.mode == "dev":
        lines += [
            "> *** DEV MODE -- synthetic tickets only. Results are NOT evidence. ***",
            "",
        ]
    lines += [
        "## Overall",
        "",
        f"* Golden rows: {overall['golden_rows']}",
        f"* Evaluated (golden rows with a usable prediction): {overall['evaluated']}",
        f"* Coverage of the golden set: {_fmt(overall['coverage'])}",
        f"* Overall accuracy: {_fmt(overall['accuracy'])}",
        f"* Accuracy excluding {UNPARSEABLE}: "
        f"{_fmt(overall['accuracy_excl_unparseable'])}",
        f"* {UNPARSEABLE} replies: {overall['unparseable']} "
        f"(rate {_fmt(overall['unparseable_rate'])})",
        f"* Macro recall: {_fmt(overall['macro_recall'])}; "
        f"macro precision: {_fmt(overall['macro_precision'])}",
        "",
        _DEFINITIONS_MD,
        "## Per category",
        "",
        to_markdown_table(report.per_category, float_format="{:.4f}"),
        "## Confusion matrix",
        "",
        to_markdown_table(report.matrix.reset_index(), float_format="{:.0f}"),
        "See `confusion_matrix.png` for the annotated greyscale heatmap.",
        "",
        "## Data quality",
        "",
        f"* Responses in the service log: {overall['responses']}",
        f"* Golden rows with no response: {overall['missing_golden_rows']} "
        f"(`missing_rows.csv`)",
        f"* Responses with a failed model call: {overall['errored_responses']} "
        f"(`errored_responses.csv`)",
        f"* Golden rows with more than one response: {overall['duplicate_rows']} "
        f"(`duplicates.csv`; the last by timestamp was scored)",
        f"* Responses that could not be joined to a golden row: "
        f"{overall['unmatched_responses']} (`unmatched_responses.csv`)",
        "",
    ]
    if report.outcome.warnings:
        lines += ["### Warnings raised by this run", ""]
        lines += [f"* {warning}" for warning in report.outcome.warnings]
        lines += [""]
    if report.failures:
        lines += ["### Checks that failed", ""]
        lines += [f"* {failure}" for failure in report.failures]
        lines += [""]
    lines += [
        "## Interpretation still owed",
        "",
        "`misclassified.csv` lists every wrong row with the golden label, the "
        "predicted label, the raw model reply and the first characters of the "
        "ticket. It is the input to the Slide 10 commentary.",
        "",
        "TODO(Part 5 — Teammate B): read `misclassified.csv` and state, for "
        "this model, which category pairs it confuses and what the narratives "
        "in those pairs have in common. Name the two or three examples that go "
        "on Slide 10.",
        "",
        "TODO(Part 5 — Teammate B): say whether the per-category recall figures "
        "meet the per-category accuracy requirement from Part 4, category by "
        "category, and list every category that does not.",
        "",
        'TODO(Yeo Kai Yuan): replace "Teammate B" above with the real name.',
        "",
    ]
    return "\n".join(lines)


def build_comparison(reports: list[RunReport]) -> pd.DataFrame:
    """One row per accuracy run: the per-model comparison table.

    One row per *run directory* rather than per model, because two accuracy
    passes over the same model are two measurements and must not be silently
    merged into one figure.
    """
    frame = pd.DataFrame([report.overall for report in reports])
    return frame.sort_values(["model_tag", "stamp"], kind="stable").reset_index(drop=True)


def render_top_report(
    reports: list[RunReport],
    comparison: pd.DataFrame,
    golden_path: Path,
    results_root: Path,
) -> str:
    """The combined ``accuracy_report.md`` across every accuracy run found."""
    lines = [
        "# Accuracy results (all models)",
        "",
        f"* Golden set: `{golden_path}` ({int(reports[0].overall['golden_rows'])} rows)",
        f"* Accuracy runs read from: `{results_root}`",
        f"* Accuracy runs found: {len(reports)}",
        "",
        _DEFINITIONS_MD,
        "## Per-model comparison",
        "",
        to_markdown_table(comparison, float_format="{:.4f}"),
        "Per-model detail, including the confusion matrix and the list of "
        "misclassified rows, is in the subdirectory named after each run.",
        "",
    ]
    dev_runs = [r for r in reports if r.run.mode == "dev"]
    if dev_runs:
        lines += [
            "> *** DEV MODE runs are included in this table: "
            + ", ".join(r.run.path.name for r in dev_runs)
            + ". Synthetic tickets only. Results are NOT evidence. ***",
            "",
        ]
    lines += [
        "## Interpretation still owed",
        "",
        "TODO(Part 6 — Teammate B): state which model this table supports "
        "recommending on accuracy grounds, and whether any candidate fails the "
        "per-category accuracy requirement. Accuracy alone does not decide the "
        "recommendation: pair it with the latency and throughput results.",
        "",
        'TODO(Yeo Kai Yuan): replace "Teammate B" above with the real name.',
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line. See the module docstring for the semantics."""
    parser = argparse.ArgumentParser(
        prog="analysis/accuracy.py",
        description=(
            "Score the baseline service's classifications against the golden "
            "set: overall accuracy, per-category recall and precision, a "
            "confusion matrix (CSV and greyscale PNG) and a list of every "
            "misclassified row."
        ),
        epilog=(
            "Exit codes: 0 every run scored over the complete golden set; "
            "1 a sanity check failed (golden set missing or unusable, no "
            "responses found, or incomplete coverage of the golden set). The "
            "tables are written before the run fails, so the operator can see "
            "what is missing."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=DEFAULT_RESULTS,
        help="directory of <model>_<UTCSTAMP> accuracy run directories "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--golden",
        type=Path,
        default=DEFAULT_GOLDEN,
        help="the frozen golden set CSV (default: %(default)s)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="where tables, charts and reports are written (default: %(default)s)",
    )
    parser.add_argument(
        "--team-rows",
        type=Path,
        default=DEFAULT_TEAM_ROWS,
        help="fallback source of ticket narratives for misclassified.csv, used "
        "only when the golden set has no narrative column (default: %(default)s)",
    )
    parser.add_argument(
        "--narrative-chars",
        type=int,
        default=200,
        help="characters of the ticket narrative to include in "
        "misclassified.csv (default: %(default)s)",
    )
    parser.add_argument(
        "--no-charts",
        action="store_true",
        help="write tables only; skip the confusion-matrix PNG",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the accuracy analysis; return the process exit code."""
    args = parse_args(argv)
    try:
        golden = load_golden_set(args.golden)
        runs = iter_accuracy_runs(args.results)
        narratives, narrative_source = load_narratives(golden, args.team_rows)
        if not narratives:
            print(
                "WARNING: no ticket narratives available (the golden set has no "
                f"narrative column and {args.team_rows} was not readable). "
                "misclassified.csv will have an empty narrative_prefix column, "
                "which makes it much harder to interpret.",
                file=sys.stderr,
            )
        reports: list[RunReport] = []
        for run in runs:
            report = analyse_run(
                run=run,
                golden=golden,
                narratives=narratives,
                narrative_source=narrative_source,
                out_root=args.out_dir,
                narrative_chars=args.narrative_chars,
                make_charts=not args.no_charts,
            )
            reports.append(report)
            for warning in report.outcome.warnings:
                print(f"WARNING [{run.label}]: {warning}", file=sys.stderr)
            if run.mode == "dev":
                print(
                    f"*** DEV MODE -- synthetic tickets only. Results are NOT "
                    f"evidence. ({run.path.name}) ***",
                    file=sys.stderr,
                )
            print(
                f"{run.label}: accuracy {_fmt(report.overall['accuracy'])} over "
                f"{report.overall['evaluated']}/{report.overall['golden_rows']} "
                f"golden rows -> {report.out_dir}"
            )

        comparison = build_comparison(reports)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        write_table(comparison, args.out_dir, "model_comparison", float_format="{:.4f}")
        (args.out_dir / "accuracy_report.md").write_text(
            render_top_report(reports, comparison, args.golden, args.results),
            encoding="utf-8",
        )
        print(f"Wrote {args.out_dir / 'model_comparison.csv'}")
    except AnalysisError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    failures = [failure for report in reports for failure in report.failures]
    if failures:
        print("", file=sys.stderr)
        print("FAILED accuracy sanity checks:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
