#!/usr/bin/env python3
"""Assignment 2 accuracy test: post the test-set tickets through POST /tickets, once, for one configuration.

Owner: Part 1 -- Yeo Kai Yuan (technical core). TODO_A2.md §1.3 (the
run_accuracy bullet) and §1.5.

What this script does
---------------------
It is the Assignment 2 *driver* for the accuracy test, and only the driver --
the same job ``scripts/run_accuracy.py`` did for Assignment 1, whose helpers it
imports rather than copies. For one configuration (a single model, or the
cascade at Setting A or Setting B) it:

1. reads the row numbers of one half of the golden-set split,
   ``golden/split_a2.csv`` -- ``test`` by default (brief, Step 1: "Use the test
   set for every accuracy number you report") or ``tuning`` on request;
2. looks each narrative up in ``data/team_rows.csv`` by row number;
3. posts them one at a time, in row-number order, once each, and writes what
   came back to ``responses.csv`` row by row;
4. copies the service's own log lines for that window into ``service.jsonl``,
   and joins them back to the posted tickets on ``request_id`` into
   ``routing.csv``: which model answered each ticket and whether it was
   escalated. The brief: the escalation fraction "must be reported from the
   service logs", so it comes from there, never from the HTTP response (which
   cannot tell, by design).

What this script must never do
------------------------------
* **Read a golden label.** From ``golden/split_a2.csv`` it reads exactly the two
  columns ``row_number,set`` and refuses a file with any other column. It never
  opens the frozen golden-set labels file at all. Scoring is
  ``analysis/accuracy.py``'s job, afterwards (Part 3, TODO_A2.md §3.1).
* **Compute, print or summarise accuracy**, or time anything. It prints counts.
* **Cache or retry.** Every ticket gets one real POST, and therefore one real
  model call (guardrail 3). An errored ticket is recorded as errored, with its
  HTTP status and error, and counts as wrong later (TODO_A2.md §1.5); it is
  never re-sent.
* **Post concurrently.** One ticket at a time, one configuration per run.

The A2 gate
-----------
In real mode ``scripts/a2_gate.py`` must pass before a single ticket is posted
(TODO_A2.md guardrail 15): the prediction record, the escalation rule and the
split must be committed and tagged ``a2-predictions-freeze``. Its payload is
stored verbatim as ``gate.json`` in the run directory. Exit 3 otherwise.

``--dev`` bypasses the gate, but then reads only
``data/dev/synthetic_tickets.csv`` (selecting ``--rows`` by row-number parity,
even = test, odd = tuning, the rule ``golden/split_a2.csv`` was generated
with), writes only under ``results/dev/accuracy_a2/`` (gitignored), stamps
``"mode": "dev"``, and refuses any argument naming the team rows or the golden
directory. Dev output is never evidence and must never appear on a slide.

Output (``<out-root>/<config>_<UTCSTAMP>/``)
--------------------------------------------
``responses.csv``  exactly Assignment 1's columns, so analysis/accuracy.py reads
                   the directory unchanged.
``service.jsonl``  the service-log slice for the run window (+ ``warmup.jsonl``).
``routing.csv``    one row per posted ticket, joined to ``service.jsonl``.
``metadata.json``  Assignment 1's keys plus the Assignment 2 configuration.
``gate.json``      the A2 gate payload.

Usage
-----
    python scripts/run_accuracy_a2.py --config cascade-A
    python scripts/run_accuracy_a2.py --config granite4:3b --rows test
    python scripts/run_accuracy_a2.py --config cascade-B --rows tuning     # shown, never decides pass/fail
    python scripts/run_accuracy_a2.py --config cascade-A --dev             # before the gate

Exit codes: 0 clean; 1 a ticket did not return HTTP 200, a service log line is
missing (or names another configuration), or the service is not serving
``--config``; 2 misuse; 3 the A2 gate blocked the run.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent

# Same pattern as scripts/run_accuracy.py: the repository root is importable for
# service/log_schema.py, and scripts/ (a directory of tools, not a package) so
# that the gate and the Assignment 1 driver's helpers are imported, not copied.
for _candidate in (str(REPO_ROOT), str(SCRIPT_DIR)):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

import a2_gate  # noqa: E402
import run_accuracy as a1  # noqa: E402  (Assignment 1 driver; reused, never edited)

from service.log_schema import LOG_FIELDS  # noqa: E402

PROG = "run_accuracy_a2.py"

# --- inputs ----------------------------------------------------------------
#: The gated tuning/test split. Only ``row_number`` and ``set`` are read.
SPLIT_REL = a2_gate.SPLIT_PATH                      # "golden/split_a2.csv"
SPLIT_PATH = REPO_ROOT / SPLIT_REL
SPLIT_COLUMNS = ["row_number", "set"]
ROW_SETS = ("test", "tuning")
TEAM_ROWS_PATH = REPO_ROOT / a1.TEAM_ROWS_REL       # narratives, by row number
DEV_CSV_PATH = REPO_ROOT / a1.DEV_CSV_REL           # the only dev-mode input

# --- outputs ---------------------------------------------------------------
REAL_OUT_ROOT_REL = "results/accuracy_a2"
DEV_OUT_ROOT_REL = "results/dev/accuracy_a2"
#: Dev output is confined to this subtree (gitignored with results/dev/).
DEV_OUT_ROOT = REPO_ROOT / DEV_OUT_ROOT_REL
#: Where Part 3's scoring should write. Never accuracy.py's default, which is
#: Assignment 1's analysis/output/accuracy/ and would be overwritten.
ANALYSIS_OUT_DIR_REL = "analysis/output/accuracy_a2"

#: Exactly Assignment 1's responses.csv header (scripts/run_accuracy.py).
RESPONSES_COLUMNS: tuple[str, ...] = (
    "row_number", "request_id", "http_status", "predicted_category", "error",
)
ROUTING_COLUMNS: tuple[str, ...] = (
    "row_number", "request_id", "http_status", "predicted_category",
    "model_tag", "escalated", "cascade_setting", "small_model_tag",
    "small_model_category",
)
#: routing.csv columns that are blank for a single-model configuration.
ROUTING_CASCADE_COLUMNS: tuple[str, ...] = (
    "escalated", "cascade_setting", "small_model_tag", "small_model_category",
)

CASCADE_CONFIGS = {"cascade-a": "A", "cascade-b": "B"}
MISUSE_EXIT = a1.MISUSE_EXIT                         # 2
GATE_BLOCKED_EXIT = a2_gate.GATE_BLOCKED_EXIT        # 3

TUNING_NOTE = (
    "NOTE: --rows tuning. Tuning-set results may be shown beside the test-set "
    "results (brief, Step 4), but they are NEVER used to decide pass/fail: only "
    "the test-set results decide whether a configuration passes."
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Config:
    """What ``--config`` asked for: one model tag, or cascade Setting A/B."""

    label: str                  # "granite4:3b" | "cascade-A" | "cascade-B"
    setting: str | None = None  # "A" | "B" for a cascade, else None

    @property
    def is_cascade(self) -> bool:
        return self.setting is not None

    @property
    def dir_name(self) -> str:
        """``<config_safe>`` in the run-directory name."""
        return self.label if self.is_cascade else a1.sanitise_model_tag(self.label)


def parse_config(raw: str) -> Config:
    """``cascade-A`` / ``cascade-B`` (any case) or a model tag; ValueError otherwise."""
    value = (raw or "").strip()
    if not value:
        raise ValueError("--config is empty; give a model tag or cascade-A / cascade-B.")
    lowered = value.lower()
    if lowered in CASCADE_CONFIGS:
        setting = CASCADE_CONFIGS[lowered]
        return Config(label=f"cascade-{setting}", setting=setting)
    if lowered.startswith("cascade"):
        raise ValueError(
            f"--config {value!r}: the cascade has exactly two settings, "
            f"cascade-A and cascade-B (\"Setting A\" / \"Setting B\")."
        )
    return Config(label=value)


def switch_command(config: Config, health: dict) -> str:
    """The exact ``docker compose`` command that makes the service serve ``config``."""
    if config.is_cascade:
        small = health.get("cascade_small_model_tag") or "<small model tag, cascade/escalation_rule.md>"
        large = health.get("cascade_large_model_tag") or "<large model tag, cascade/escalation_rule.md>"
        env = [
            ("SERVICE_MODE", "cascade"),
            ("CASCADE_SETTING", config.setting or ""),
            ("CASCADE_SMALL_MODEL_TAG", small),
            ("MODEL_TAG", large),
        ]
    else:
        env = [("SERVICE_MODE", "single"), ("MODEL_TAG", config.label)]
    assignments = " ".join(
        f"{name}={value if value.startswith('<') else shlex.quote(value)}"
        for name, value in env
    )
    command = f"{assignments} docker compose up -d --force-recreate triage"
    if "<" in assignments:
        command += "\n    (replace each <...> with the tag pair in cascade/escalation_rule.md)"
    return command


def require_config(health: dict, config: Config, base_url: str) -> None:
    """Refuse (SystemExit -> exit 1) unless ``/health`` says the service serves ``config``.

    The Assignment 1 rule (``require_model``), extended to the cascade:
    recording one configuration's results under another's name is the easiest
    way to produce numbers that cannot be defended.
    """
    mode = health.get("service_mode")
    if config.is_cascade:
        matches = mode == "cascade" and health.get("cascade_setting") == config.setting
        served = f"service_mode={mode!r}, cascade_setting={health.get('cascade_setting')!r}"
    else:
        matches = mode == "single" and health.get("model_tag") == config.label
        served = f"service_mode={mode!r}, model_tag={health.get('model_tag')!r}"
    if not matches:
        raise SystemExit(
            f"the service at {base_url} is serving {served}, but this run was asked "
            f"for --config {config.label}.\n"
            f"Switch the configuration first, then re-run:\n"
            f"    {switch_command(config, health)}"
        )
    if config.is_cascade:
        rule = health.get("cascade_rule")
        if not rule or str(rule).startswith("NOT CONFIGURED"):
            raise SystemExit(
                f"the service at {base_url} reports cascade_rule {rule!r}: Setting "
                f"{config.setting} has no escalation rule configured in "
                f"service/cascade.py, so there is nothing to measure."
            )
    if not health.get("ollama_reachable"):
        raise SystemExit(
            f"the service reports that Ollama is not reachable at "
            f"{health.get('ollama_base_url')!r}; every POST would return 502."
        )


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

def read_split(path: Path) -> dict[int, str]:
    """``{row_number: set}`` from the split file. NO OTHER COLUMN IS READ.

    The header must be exactly ``row_number,set`` (the shared interface,
    TODO_A2.md §B). A file carrying any further column -- a label, say -- is
    refused rather than read around, so this driver cannot be handed a label.
    """
    if not path.is_file():
        raise SystemExit(f"split file not found: {path}")
    split: dict[int, str] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = [cell.strip() for cell in next(reader, [])]
        if header != SPLIT_COLUMNS:
            raise SystemExit(
                f"{path} has columns {header}; expected exactly {SPLIT_COLUMNS}. "
                f"The split file carries row numbers and set names, nothing else."
            )
        for lineno, record in enumerate(reader, start=2):
            if not record or not any(cell.strip() for cell in record):
                continue
            if len(record) != len(SPLIT_COLUMNS):
                raise SystemExit(f"{path}:{lineno}: expected 2 fields, got {len(record)}.")
            raw_row, raw_set = (cell.strip() for cell in record)
            if not raw_row.isdigit():
                raise SystemExit(f"{path}:{lineno}: row_number {raw_row!r} is not a row number.")
            if raw_set not in ROW_SETS:
                raise SystemExit(
                    f"{path}:{lineno}: set {raw_set!r} is not one of {list(ROW_SETS)}."
                )
            row = int(raw_row)
            if row in split:
                raise SystemExit(f"{path}:{lineno}: row {row} is listed more than once.")
            split[row] = raw_set
    if not split:
        raise SystemExit(f"{path} contains no rows.")
    return split


def select_rows(split: dict[int, str], rows_set: str) -> list[int]:
    """The row numbers in ``rows_set``, in row-number order."""
    rows = sorted(row for row, which in split.items() if which == rows_set)
    if not rows:
        raise SystemExit(f"the split has no {rows_set!r} rows.")
    return rows


def build_worklist(
    rows_set: str,
    *,
    dev: bool,
    split_path: Path,
    team_rows_path: Path,
    dev_csv_path: Path,
) -> tuple[list[tuple[int, str]], Path, int | None]:
    """``(worklist, narrative_source, split_total)``.

    ``worklist`` is the ordered ``(row_number, narrative)`` list to post.
    ``split_total`` is the number of rows in the whole split (None in dev mode,
    which never opens it).
    """
    if dev:
        narratives = a1.read_narratives(dev_csv_path)
        want_even = rows_set == "test"
        rows = sorted(row for row in narratives if (row % 2 == 0) == want_even)
        source, split_total = dev_csv_path, None
    else:
        split = read_split(split_path)
        rows = select_rows(split, rows_set)
        narratives = a1.read_narratives(team_rows_path)
        source, split_total = team_rows_path, len(split)

    missing = [row for row in rows if row not in narratives]
    if missing:
        preview = ", ".join(str(row) for row in missing[:10])
        raise SystemExit(
            f"{len(missing)} {rows_set} row number(s) are not present in {source}: "
            f"{preview}{'...' if len(missing) > 10 else ''}"
        )
    empty = [row for row in rows if not narratives[row].strip()]
    if empty:
        raise SystemExit(
            f"{len(empty)} {rows_set} row(s) have an empty narrative in {source} "
            f"(e.g. {empty[:5]}). An empty ticket cannot be classified and would "
            f"silently distort the accuracy denominator."
        )
    if not rows:
        raise SystemExit(f"no {rows_set} rows to post from {source}.")
    return [(row, narratives[row]) for row in rows], source, split_total


def refused_dev_argument(argv: list[str]) -> str | None:
    """The first raw argument that names real team data, or None.

    The raw list is inspected (as Assignment 1 does) so a default never trips
    the check while an explicit request for real data does.
    """
    for raw in argv:
        lowered = raw.lower()
        if "team_rows.csv" in lowered or "golden/" in lowered or "golden_set" in lowered:
            return raw
    return None


# ---------------------------------------------------------------------------
# Routing: join each posted ticket to its service log line
# ---------------------------------------------------------------------------

@dataclass
class RoutingSummary:
    missing_log_lines: int = 0
    duplicate_log_lines: int = 0
    config_mismatch_lines: int = 0
    category_mismatches: int = 0
    escalated_count: int | None = None
    escalation_denominator: int | None = None

    @property
    def escalation_fraction(self) -> float | None:
        if not self.escalation_denominator or self.escalated_count is None:
            return None
        return self.escalated_count / self.escalation_denominator


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build_routing(
    posted: list[dict], log_records: list[dict], config: Config
) -> tuple[list[dict], RoutingSummary]:
    """One routing row per posted ticket, joined to its log line on ``request_id``.

    ``http_status`` and ``predicted_category`` are what the caller received;
    ``model_tag`` and the cascade columns are what the service logged. A
    ticket with no log line keeps its row, with the logged columns blank, and
    is counted in ``missing_log_lines``. For a single-model configuration the
    cascade columns are always blank and there is no escalation figure.
    """
    summary = RoutingSummary()
    by_id: dict[str, dict] = {}
    for record in log_records:            # already sorted by ts: the last one wins
        if record.get("endpoint") != "/tickets" or record.get("method") != "POST":
            continue
        request_id = record.get("request_id")
        if request_id in by_id:
            summary.duplicate_log_lines += 1
        by_id[request_id] = record

    rows: list[dict] = []
    escalated = known = 0
    for ticket in posted:
        row = {
            "row_number": ticket["row_number"],
            "request_id": ticket["request_id"],
            "http_status": ticket["http_status"],
            "predicted_category": ticket.get("predicted_category") or "",
            **{name: "" for name in ROUTING_COLUMNS[4:]},
        }
        record = by_id.get(ticket["request_id"])
        if record is None:
            summary.missing_log_lines += 1
            rows.append(row)
            continue
        row["model_tag"] = _cell(record.get("model_tag"))
        if config.is_cascade:
            for name in ROUTING_CASCADE_COLUMNS:
                row[name] = _cell(record.get(name))
            if record.get("cascade_setting") != config.setting:
                summary.config_mismatch_lines += 1
            if isinstance(record.get("escalated"), bool):
                known += 1
                escalated += record["escalated"]
        elif record.get("model_tag") != config.label or record.get("escalated") is not None:
            summary.config_mismatch_lines += 1
        if (
            ticket["http_status"] == 200
            and (record.get("predicted_category") or "") != row["predicted_category"]
        ):
            summary.category_mismatches += 1
        rows.append(row)

    if config.is_cascade:
        summary.escalated_count = escalated
        summary.escalation_denominator = known
    return rows, summary


def write_csv(path: Path, columns: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


def _rel(path: Path) -> str:
    """``path`` relative to the repository when it is inside it."""
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "Assignment 2 accuracy test: post the test-set (or tuning-set) "
            "tickets from golden/split_a2.csv through POST /tickets once, for "
            "one configuration, and record what came back and which model "
            "answered. Computes no accuracy: run analysis/accuracy.py afterwards."
        ),
        epilog=(
            "Environment variables, as for scripts/run_accuracy.py: SERVICE_LOG_DIR "
            "(default logs/service), SERVICE_SSH and SERVICE_REPO (remote mode: "
            "mirror the service host's logs/service with rsync before slicing), "
            "ACCURACY_TIMEOUT_S (default %d), SLICE_MARGIN_S (default %d), "
            "RUN_NOTES (free text copied into metadata.json). Exit codes: 0 clean, "
            "1 a ticket errored / a log line is missing / wrong service "
            "configuration, 2 misuse, 3 the A2 gate blocked the run."
            % (a1.DEFAULT_REQUEST_TIMEOUT_S, a1.DEFAULT_SLICE_MARGIN_S)
        ),
    )
    parser.add_argument(
        "--config",
        required=True,
        help="A model tag (single model, e.g. granite4:3b) or cascade-A / cascade-B. "
             "Refused unless GET /health shows the service serving exactly that.",
    )
    parser.add_argument(
        "--rows",
        choices=ROW_SETS,
        default="test",
        help="Which half of golden/split_a2.csv to post (default: test). Tuning-set "
             "results are never used to decide pass/fail.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Service host (default 127.0.0.1).")
    parser.add_argument("--port", default="8000", help="Service port (default 8000).")
    parser.add_argument(
        "--out-root",
        type=Path,
        default=None,
        help=f"Where the run directory is created (default {REAL_OUT_ROOT_REL}, or "
             f"{DEV_OUT_ROOT_REL} with --dev).",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Bypass the A2 gate and post data/dev/synthetic_tickets.csv instead "
             "(--rows by row-number parity). Writes only under "
             f"{DEV_OUT_ROOT_REL} and stamps mode=dev. Not evidence.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the driver; return the exit code. A string SystemExit becomes exit 1."""
    try:
        return _main(list(sys.argv[1:] if argv is None else argv))
    except SystemExit as exc:
        if isinstance(exc.code, str):
            print(f"{PROG}: {exc.code}", file=sys.stderr)
            return 1
        return 0 if exc.code is None else int(exc.code)


def _main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        config = parse_config(args.config)
    except ValueError as exc:
        print(f"{PROG}: {exc}", file=sys.stderr)
        return MISUSE_EXIT

    if args.dev:
        offending = refused_dev_argument(argv)
        if offending is not None:
            print(
                f"{PROG}: refusing: --dev was given together with {offending!r}, which "
                f"names real team data. Dev mode exists so that no model sees a team "
                f"row or a golden-set row before the A2 gate. Drop --dev once "
                f"python scripts/a2_gate.py passes.",
                file=sys.stderr,
            )
            return MISUSE_EXIT
        print(a1.DEV_BANNER)

    # --- the A2 gate, before anything else is read or posted ---------------
    if args.dev:
        gate_payload: dict = {
            "ok": False,
            "mode": "dev",
            "enforced": False,
            "reasons": [
                "dev mode: the A2 gate was bypassed, so this directory is not "
                "evidence and must never be cited."
            ],
        }
        gate_commit = gate_tag = None
    else:
        status = a2_gate.check_gate(REPO_ROOT)
        if not status.ok:
            print(a2_gate.explain(status), file=sys.stderr)
            return GATE_BLOCKED_EXIT
        gate_payload = status.to_payload()
        gate_commit, gate_tag = status.gate_commit, status.gate_tag
        print(f"A2 gate: PASS (commit {gate_commit}, tag '{gate_tag}').")

    # --- where the run goes ------------------------------------------------
    out_root = args.out_root
    if out_root is None:
        out_root = DEV_OUT_ROOT if args.dev else REPO_ROOT / REAL_OUT_ROOT_REL
    if not out_root.is_absolute():
        out_root = REPO_ROOT / out_root
    if args.dev:
        dev_root = DEV_OUT_ROOT.resolve()
        try:
            out_root.resolve().relative_to(dev_root)
        except ValueError:
            print(
                f"{PROG}: refusing: --dev may only write under {dev_root} (got "
                f"{out_root}). Dev output is gitignored so that it can never be "
                f"mistaken for evidence.",
                file=sys.stderr,
            )
            return MISUSE_EXIT

    # --- inputs: row numbers from the split, narratives from the team rows -
    worklist, narrative_source, split_total = build_worklist(
        args.rows,
        dev=args.dev,
        split_path=SPLIT_PATH,
        team_rows_path=TEAM_ROWS_PATH,
        dev_csv_path=DEV_CSV_PATH,
    )

    # --- the service must be serving exactly this configuration ------------
    base_url = f"http://{args.host}:{args.port}"
    health = a1.fetch_health(base_url)
    require_config(health, config, base_url)

    log_dir = Path(os.environ.get("SERVICE_LOG_DIR", REPO_ROOT / "logs" / "service"))
    timeout = float(os.environ.get("ACCURACY_TIMEOUT_S", a1.DEFAULT_REQUEST_TIMEOUT_S))
    margin_s = int(os.environ.get("SLICE_MARGIN_S", a1.DEFAULT_SLICE_MARGIN_S))

    started = datetime.now(timezone.utc)
    run_dir = out_root / f"{config.dir_name}_{a1.utc_stamp(started)}"
    run_dir.mkdir(parents=True, exist_ok=False)

    rows_desc = (
        f"{args.rows} (dev: synthetic tickets with an {'even' if args.rows == 'test' else 'odd'} row number)"
        if args.dev
        else f"{args.rows} set of {SPLIT_REL}"
    )
    if config.is_cascade:
        print(
            f"Config   : {config.label} (small {health.get('cascade_small_model_tag')}, "
            f"large {health.get('cascade_large_model_tag')})"
        )
        print(f"Rule     : {health.get('cascade_rule')}")
    else:
        print(f"Config   : {config.label} (digest {health.get('model_digest')})")
    print(f"Service  : {base_url}")
    print(f"Rows     : {rows_desc}")
    print(f"Input    : narratives from {_rel(narrative_source)}")
    print(f"Tickets  : {len(worklist)}")
    print(f"Output   : {run_dir}")
    if args.rows == "tuning":
        print(TUNING_NOTE)
    print()

    # --- the sequential posting loop: one ticket at a time, once each ------
    posted: list[dict] = []
    status_counts: dict[int, int] = {}
    error_count = 0
    # Written incrementally and flushed per row: if the run dies half way, the
    # rows already posted remain on disk as evidence of what happened.
    with (run_dir / "responses.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(RESPONSES_COLUMNS)
        for index, (row_number, narrative) in enumerate(worklist, 1):
            request_id = str(uuid.uuid4())
            http_status, category, error = a1.post_ticket(
                base_url, narrative, row_number, request_id, timeout
            )
            # No retry, whatever came back: an errored ticket counts as wrong.
            writer.writerow([row_number, request_id, http_status, category or "", error or ""])
            handle.flush()
            posted.append(
                {
                    "row_number": row_number,
                    "request_id": request_id,
                    "http_status": http_status,
                    "predicted_category": category,
                }
            )
            status_counts[http_status] = status_counts.get(http_status, 0) + 1
            if http_status != 200 or error:
                error_count += 1
            # Progress only: counts, never a latency and never a running score.
            if index == 1 or index % 10 == 0 or index == len(worklist):
                print(
                    f"  [{index:>4}/{len(worklist)}] posted; HTTP errors so far: {error_count}",
                    flush=True,
                )

    ended = datetime.now(timezone.utc)

    # --- the service's own record of the same requests ---------------------
    if os.environ.get("SERVICE_SSH"):
        time.sleep(2)              # the last line is written as the response leaves
    sync_problem = a1.sync_remote_logs(log_dir)
    measured, warmup, problems = a1.slice_service_log(log_dir, started, ended, margin_s)
    if sync_problem:
        problems.insert(0, sync_problem)
    a1.write_jsonl(run_dir / "service.jsonl", measured)
    if warmup:
        a1.write_jsonl(run_dir / "warmup.jsonl", warmup)
    for problem in problems:
        print(f"  service log: {problem}", file=sys.stderr)
    off_schema = sorted({key for record in measured for key in record if key not in LOG_FIELDS})
    if off_schema:
        print(
            f"  service log: unexpected field(s) {off_schema} -- the service and "
            f"service/log_schema.py have diverged.",
            file=sys.stderr,
        )

    # --- routing.csv: which model answered, from the log -------------------
    routing_rows, routing = build_routing(posted, measured, config)
    write_csv(run_dir / "routing.csv", ROUTING_COLUMNS, routing_rows)

    # --- metadata ----------------------------------------------------------
    commit, dirty = a1.git_state(REPO_ROOT)
    notes = os.environ.get("RUN_NOTES", "")
    note_parts = [notes] if notes else []
    note_parts.append(f"rows_set={args.rows}")
    if args.rows == "tuning":
        note_parts.append("tuning-set run: never used to decide pass/fail")
    note_parts.append(f"narratives resolved from {narrative_source.name} by row_number")
    note_parts.append(f"posted={len(worklist)} status_counts={status_counts}")
    note_parts.append(f"service log lines captured={len(measured)}")
    note_parts.append(f"routing missing log lines={routing.missing_log_lines}")
    if routing.duplicate_log_lines:
        note_parts.append(f"routing duplicate log lines={routing.duplicate_log_lines}")
    if routing.config_mismatch_lines:
        note_parts.append(f"log lines naming another configuration={routing.config_mismatch_lines}")
    if routing.category_mismatches:
        note_parts.append(f"response/log category mismatches={routing.category_mismatches}")
    if problems:
        note_parts.append(f"service log problems={len(problems)}")

    metadata = {
        # --- Assignment 1's keys (scripts/run_accuracy.py), same meaning ---
        "run_id": run_dir.name,
        "mode": "dev" if args.dev else "real",
        "plan": "accuracy_a2",
        "plan_file": None,                 # no JMeter plan: this driver is the client
        # A cascade is labelled by its configuration so analysis/accuracy.py's
        # tables can never show it under the large model's tag; its two models
        # are in the cascade_* keys below.
        "model_tag": config.label,
        "model_digest": None if config.is_cascade else health.get("model_digest"),
        "rate_per_min": None,              # sequential by design, not rate-driven
        "duration_s": None,                # not a timed test; see started/ended
        "run_index": 1,
        "runs_total": 1,                   # each configuration is posted once
        "started_at_utc": a1.iso_ms(started),
        "ended_at_utc": a1.iso_ms(ended),
        "git_commit": commit,
        "git_dirty": dirty,
        "freeze_commit": None,             # Assignment 2 is gated by gate_commit
        "freeze_tag": None,
        "prompt_hash": health.get("prompt_hash"),
        "num_ctx": health.get("num_ctx"),
        "seed": a1.sole_value(measured, "seed"),
        "input_csv": _rel(narrative_source),
        "service_url": base_url,
        "service_host_info": {
            "target_url": base_url,
            "ollama_base_url": health.get("ollama_base_url"),
            "db_path": health.get("db_path"),
            "uvicorn_workers": health.get("uvicorn_workers"),
            "threadpool_size": health.get("threadpool_size"),
            "note": "hardware is recorded by scripts/capture_env.sh on the service host",
        },
        "load_generator_host_info": a1.host_info(),
        "jmeter_version": None,            # JMeter is not involved in the accuracy test
        "ollama_num_parallel": os.environ.get("OLLAMA_NUM_PARALLEL", "default"),
        "ollama_max_loaded_models": os.environ.get("OLLAMA_MAX_LOADED_MODELS", "default"),
        "warmup_request_id": None,         # no warm-up: nothing here is timed
        "notes": "; ".join(note_parts),
        # --- Assignment 2 -------------------------------------------------
        "assignment": "A2",
        "config": config.label,
        "rows_set": args.rows,
        "n_rows": len(worklist),
        "gate_commit": gate_commit,
        "gate_tag": gate_tag,
        "service_mode": health.get("service_mode"),
        "cascade_setting": health.get("cascade_setting"),
        "cascade_small_model_tag": health.get("cascade_small_model_tag"),
        "cascade_small_model_digest": health.get("cascade_small_model_digest"),
        "cascade_large_model_tag": health.get("cascade_large_model_tag"),
        # In cascade mode /health's model_digest is the large model's.
        "cascade_large_model_digest": health.get("model_digest") if config.is_cascade else None,
        "cascade_rule": health.get("cascade_rule"),
        "split_file": None if args.dev else SPLIT_REL,   # dev never opens the split
        "escalated_count": routing.escalated_count,
        "escalation_denominator": routing.escalation_denominator,
        "escalation_fraction": routing.escalation_fraction,
        "routing_missing_log_lines": routing.missing_log_lines,
    }
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    (run_dir / "gate.json").write_text(json.dumps(gate_payload, indent=2) + "\n", encoding="utf-8")

    # --- summary: counts only ----------------------------------------------
    print()
    print(f"Wrote {run_dir}")
    print(f"  responses.csv : {len(worklist)} rows")
    print(
        f"  service.jsonl : {len(measured)} log lines"
        + (f" (+{len(warmup)} warm-up lines separated out)" if warmup else "")
    )
    print(
        f"  routing.csv   : {len(routing_rows)} rows, "
        f"{routing.missing_log_lines} without a log line"
    )
    if config.is_cascade:
        print(
            f"  escalated     : {routing.escalated_count} of "
            f"{routing.escalation_denominator} tickets with a log line"
        )
    print(f"  HTTP status counts: {dict(sorted(status_counts.items()))}")
    if args.rows == "tuning":
        print(f"  {TUNING_NOTE}")
    if error_count:
        print(
            f"  {error_count} request(s) did not return HTTP 200. Those rows carry an "
            f"error in responses.csv, were NOT retried, and count as wrong.",
            file=sys.stderr,
        )
    if routing.missing_log_lines:
        print(
            f"  WARNING: {routing.missing_log_lines} posted ticket(s) have no service log "
            f"line, so which model answered them is unknown (blank in routing.csv). "
            f"Check SERVICE_LOG_DIR ({log_dir}), SERVICE_SSH and the clocks on both machines.",
            file=sys.stderr,
        )
    if routing.duplicate_log_lines:
        print(
            f"  WARNING: {routing.duplicate_log_lines} request_id(s) appear on more than "
            f"one log line; routing.csv uses the last.",
            file=sys.stderr,
        )
    if routing.config_mismatch_lines:
        print(
            f"  WARNING: {routing.config_mismatch_lines} log line(s) do not match "
            f"--config {config.label}: the service configuration changed during the "
            f"run. The run is invalid.",
            file=sys.stderr,
        )
    if routing.category_mismatches:
        print(
            f"  WARNING: {routing.category_mismatches} ticket(s) returned a category "
            f"different from the one logged. analysis/reconcile.py exists to chase this.",
            file=sys.stderr,
        )

    print()
    print("No accuracy was computed here, by design.")
    if args.dev:
        print(
            "Dev runs are plumbing checks only: the synthetic tickets are not golden "
            "rows, so there is nothing for analysis/accuracy.py to score. Inspect "
            "responses.csv and routing.csv directly."
        )
        print()
        print(a1.DEV_BANNER)
    else:
        others = (split_total or 0) - len(worklist)
        print("Score it (Part 3, TODO_A2.md §3.1) with:")
        print(
            f"    python analysis/accuracy.py --results {_rel(out_root)} "
            f"--out-dir {ANALYSIS_OUT_DIR_REL}"
        )
        print(
            "  Keep --out-dir: accuracy.py's default is Assignment 1's "
            "analysis/output/accuracy/, which it would overwrite."
        )
        print(
            f"  Only the {len(worklist)} {args.rows}-set rows were posted, so the other "
            f"{others} golden rows appear in missing_rows.csv and accuracy.py reports "
            f"incomplete coverage (exit 1). That is expected for this run: Part 3 scores "
            f"the test-set rows only."
        )
        print(
            "  An errored ticket counts as wrong (TODO_A2.md §1.5); accuracy.py lists "
            "it in errored_responses.csv rather than scoring it."
        )
    invalid = error_count or routing.missing_log_lines or routing.config_mismatch_lines
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
