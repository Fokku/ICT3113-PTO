"""Shared helpers for the analysis scripts.

Every script in ``analysis/`` reads the same two kinds of evidence:

* **JMeter result files** (``results.jtl``) -- CSV, one row per sample, written
  by the run scripts with ``-Jsample_variables=request_id,source_row`` so the
  two headers the service echoes back are present as extra columns. This is
  what makes ``reconcile.py`` possible.
* **Service logs** (``service.jsonl``) -- one JSON object per request, schema
  fixed by :mod:`service.log_schema`.

Nothing in this module runs a model, and nothing here invents a value: every
function either reads a file or derives a statistic from what it read.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from service.categories import CATEGORIES, UNPARSEABLE  # noqa: F401  (re-export)
from service.log_schema import LOG_FIELDS, OLLAMA_TIMING_FIELDS  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Columns JMeter writes for a CSV .jtl at our save settings, plus the two
#: sample variables the run scripts request.
JTL_REQUIRED_COLUMNS: tuple[str, ...] = (
    "timeStamp",
    "elapsed",
    "label",
    "responseCode",
    "success",
)
JTL_SAMPLE_VARIABLES: tuple[str, ...] = ("request_id", "source_row")

#: ``results/runs/<stamp>_<model>_<plan>_<rate>_run<k>``
RUN_DIR_RE = re.compile(
    r"^(?P<stamp>\d{8}T\d{6}Z)"
    r"_(?P<model>.+?)"
    r"_(?P<plan>load_post_tickets|mixed_load|stress_ramp)"
    r"_(?P<rate>[^_]+)"
    r"_run(?P<run_index>\d+)$"
)


class AnalysisError(RuntimeError):
    """Raised when the evidence on disk is not usable. Always fail loudly."""


# ---------------------------------------------------------------------------
# matplotlib
# ---------------------------------------------------------------------------

def use_headless_matplotlib():
    """Select the Agg backend and return the ``pyplot`` module.

    Imported lazily so that scripts which only produce tables never pay for
    matplotlib, and so the analysis scripts run on a headless machine.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


# ---------------------------------------------------------------------------
# Naming
# ---------------------------------------------------------------------------

def sanitise_model_tag(tag: str) -> str:
    """Make an Ollama tag safe for a directory name: ``qwen2.5:1.5b`` -> ``qwen2.5-1.5b``."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", tag).strip("-")


@dataclass(frozen=True)
class RunDirInfo:
    """The fields encoded in a run directory's name."""

    path: Path
    stamp: str
    model: str
    plan: str
    rate: str
    run_index: int

    @property
    def config_key(self) -> tuple[str, str, str]:
        """The three-part key that the three repeat runs of one configuration share."""
        return (self.model, self.plan, self.rate)


def parse_run_dir_name(path: Path) -> RunDirInfo | None:
    """Parse a run directory name, or return ``None`` if it is not one."""
    match = RUN_DIR_RE.match(path.name)
    if not match:
        return None
    return RunDirInfo(
        path=path,
        stamp=match["stamp"],
        model=match["model"],
        plan=match["plan"],
        rate=match["rate"],
        run_index=int(match["run_index"]),
    )


def iter_run_dirs(root: Path) -> list[RunDirInfo]:
    """Every parseable run directory under ``root``, sorted by name.

    Raises if ``root`` does not exist, because silently analysing zero runs and
    reporting an empty table is exactly the failure mode we cannot afford.
    """
    if not root.is_dir():
        raise AnalysisError(f"No such results directory: {root}")
    found = [
        info
        for child in sorted(root.iterdir())
        if child.is_dir() and (info := parse_run_dir_name(child)) is not None
    ]
    if not found:
        raise AnalysisError(
            f"{root} contains no directories matching "
            f"<stamp>_<model>_<plan>_<rate>_run<k>. Nothing to analyse."
        )
    return found


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------

def load_metadata(run_dir: Path) -> dict:
    """Read ``metadata.json`` from a run directory."""
    path = run_dir / "metadata.json"
    if not path.is_file():
        raise AnalysisError(
            f"{path} is missing. Every run directory must carry its metadata; a "
            f"result without its model tag, freeze commit and prompt hash is not "
            f"evidence."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def read_jtl(path: Path) -> pd.DataFrame:
    """Read a JMeter CSV ``.jtl`` into a DataFrame with normalised dtypes.

    Adds two derived columns:

    * ``ts`` -- ``timeStamp`` (epoch ms, the moment the sample *started* minus
      nothing; JMeter records the start time) as a UTC ``datetime64``.
    * ``ok`` -- ``success`` coerced to a real boolean.
    """
    if not path.is_file():
        raise AnalysisError(f"No such .jtl file: {path}")
    frame = pd.read_csv(path)
    if frame.empty:
        raise AnalysisError(f"{path} has a header but no samples.")

    missing = [c for c in JTL_REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise AnalysisError(
            f"{path} is missing column(s) {missing}. Expected a CSV .jtl saved "
            f"with the default save settings. Found: {list(frame.columns)}"
        )

    frame["ts"] = pd.to_datetime(frame["timeStamp"], unit="ms", utc=True)
    frame["ok"] = frame["success"].astype(str).str.strip().str.lower().isin(
        {"true", "1", "yes"}
    )
    frame["elapsed"] = pd.to_numeric(frame["elapsed"], errors="coerce")
    for column in JTL_SAMPLE_VARIABLES:
        if column in frame.columns:
            frame[column] = frame[column].astype("string").fillna("")
    return frame


def read_service_log(paths: Path | Iterable[Path]) -> pd.DataFrame:
    """Read one or more ``.jsonl`` service logs into a DataFrame.

    Lines that are not valid JSON are reported rather than skipped silently:
    a truncated log means the run's evidence is incomplete and we must know.
    """
    if isinstance(paths, Path):
        paths = [paths]
    records: list[dict] = []
    bad: list[str] = []
    for path in paths:
        if not path.is_file():
            raise AnalysisError(f"No such service log: {path}")
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                bad.append(f"{path}:{lineno}: {exc}")
    if bad:
        raise AnalysisError(
            "Service log contains unparseable lines (the run's evidence is "
            "incomplete):\n  " + "\n  ".join(bad[:10])
        )
    if not records:
        raise AnalysisError(f"No log lines found in {[str(p) for p in paths]}.")

    frame = pd.DataFrame.from_records(records)
    unexpected = [c for c in frame.columns if c not in LOG_FIELDS]
    missing = [c for c in LOG_FIELDS if c not in frame.columns]
    if unexpected or missing:
        raise AnalysisError(
            "Service log does not match service/log_schema.py.\n"
            f"  unexpected fields: {unexpected}\n"
            f"  missing fields   : {missing}\n"
            "Were these lines written by a different version of the service?"
        )
    frame = frame[list(LOG_FIELDS)]
    frame["ts"] = pd.to_datetime(frame["ts"], format="ISO8601", utc=True)
    frame["warmup"] = frame["warmup"].fillna(False).astype(bool)
    frame["request_id"] = frame["request_id"].astype("string")
    frame["source_row"] = frame["source_row"].astype("string")
    return frame


def exclude_warmup(frame: pd.DataFrame) -> pd.DataFrame:
    """Drop warm-up samples.

    The first request after a model switch pays the model-load cost and would
    otherwise dominate p99. The run script flags it; analysis always drops it.
    """
    if "warmup" not in frame.columns:
        return frame
    return frame.loc[~frame["warmup"].astype(bool)].copy()


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def percentile(values: Sequence[float] | pd.Series, q: float) -> float:
    """Percentile with linear interpolation (numpy's default, 'linear' method).

    ``q`` is a fraction in [0, 1]. Stated explicitly because p95 computed with
    a different interpolation method differs on small samples, and our numbers
    have to be reproducible from the raw files by anyone.
    """
    series = pd.Series(values, dtype="float64").dropna()
    if series.empty:
        return float("nan")
    return float(series.quantile(q, interpolation="linear"))


def latency_percentiles(values: Sequence[float] | pd.Series) -> dict[str, float]:
    """p50/p95/p99 plus min/max/mean, as a flat dict."""
    series = pd.Series(values, dtype="float64").dropna()
    if series.empty:
        return {k: float("nan") for k in ("p50", "p95", "p99", "min", "max", "mean")}
    return {
        "p50": percentile(series, 0.50),
        "p95": percentile(series, 0.95),
        "p99": percentile(series, 0.99),
        "min": float(series.min()),
        "max": float(series.max()),
        "mean": float(series.mean()),
    }


def spread(values: Sequence[float] | pd.Series) -> dict[str, float]:
    """Mean, min, max and sample standard deviation across repeat runs.

    Sample SD (ddof=1) because three runs are a sample of the population of
    runs we could have done, not the population itself. With n=1 it is NaN and
    is reported as NaN rather than 0, so a single run never looks precise.
    """
    series = pd.Series(values, dtype="float64").dropna()
    if series.empty:
        return {"mean": float("nan"), "min": float("nan"), "max": float("nan"),
                "sd": float("nan"), "n": 0}
    return {
        "mean": float(series.mean()),
        "min": float(series.min()),
        "max": float(series.max()),
        "sd": float(series.std(ddof=1)) if len(series) > 1 else float("nan"),
        "n": int(len(series)),
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def to_markdown_table(frame: pd.DataFrame, float_format: str = "{:.1f}") -> str:
    """Render a DataFrame as a GitHub-flavoured Markdown table.

    Hand-rolled rather than ``DataFrame.to_markdown`` so we do not need the
    optional ``tabulate`` dependency on every teammate's machine.
    """
    if frame.empty:
        return "_(no rows)_\n"

    def cell(value) -> str:
        if isinstance(value, float):
            if pd.isna(value):
                return "n/a"
            return float_format.format(value)
        return "" if value is None else str(value)

    header = [str(c) for c in frame.columns]
    lines = ["| " + " | ".join(header) + " |",
             "|" + "|".join("---" for _ in header) + "|"]
    for _, row in frame.iterrows():
        lines.append("| " + " | ".join(cell(v) for v in row.tolist()) + " |")
    return "\n".join(lines) + "\n"


def write_table(frame: pd.DataFrame, out_dir: Path, stem: str,
                float_format: str = "{:.1f}") -> tuple[Path, Path]:
    """Write ``<stem>.csv`` and ``<stem>.md`` into ``out_dir``; return both paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"{stem}.csv"
    md_path = out_dir / f"{stem}.md"
    frame.to_csv(csv_path, index=False)
    md_path.write_text(to_markdown_table(frame, float_format), encoding="utf-8")
    return csv_path, md_path
