#!/usr/bin/env python3
"""Send every golden-set ticket through POST /tickets, once, for one model.

Owner: Part 1 -- Yeo Kai Yuan (technical core).

What this script does
---------------------
It is the *driver* for the accuracy test, and only the driver. It posts each
golden-set narrative to the running service one at a time and records what came
back, row by row, into ``responses.csv``. It then copies the service's own log
lines for that window alongside, so that every later claim can be traced to two
independent records of the same request.

What this script must never do
------------------------------
It does not compute, print or summarise accuracy. It does not even READ the
golden labels: it reads the golden set's row numbers only, looks the narratives
up in ``data/team_rows.csv``, and posts them. Scoring is
``analysis/accuracy.py``'s job, run afterwards, against the frozen labels.
Keeping the driver blind to the labels makes it structurally impossible for this
step to be tuned towards a better score.

It also does not time anything. The service logs its own latencies; this script
reports counts.

Freeze gate
-----------
In real mode the freeze gate must pass before a single ticket is posted: the
golden set and the prediction record must be committed and tagged
``golden-freeze``. ``--dev`` bypasses the gate but is then restricted to the 28
hand-written tickets in ``data/dev/synthetic_tickets.csv``, writes only under
``results/dev/``, and stamps ``mode=dev`` so its output can never be mistaken
for evidence.

Usage
-----
    python scripts/run_accuracy.py --model llama3.2:1b-instruct-q4_K_M
    python scripts/run_accuracy.py --model llama3.2:1b-instruct-q4_K_M --dev        # pre-freeze

Exit codes: 0 done, 1 a failure that invalidates the run, 2 misuse, 3 the freeze
gate blocked the run.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent

# The repository root is importable so that service/log_schema.py -- the single
# definition of the log line -- can be asserted against, and the script's own
# directory so that the freeze gate is imported rather than re-implemented.
for candidate in (str(REPO_ROOT), str(SCRIPT_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import freeze_gate  # noqa: E402  (scripts/ is a directory of tools, not a package)

from service.log_schema import LOG_FIELDS  # noqa: E402

DEV_CSV_REL = "data/dev/synthetic_tickets.csv"
TEAM_ROWS_REL = "data/team_rows.csv"
GOLDEN_REL = "golden/golden_set.csv"
DEV_BANNER = "*** DEV MODE — synthetic tickets only. Results are NOT evidence. ***"

#: Dev output is confined to this subtree, which .gitignore excludes.
DEV_OUT_ROOT_REL = "results/dev/accuracy"
REAL_OUT_ROOT_REL = "results/accuracy"

#: Seconds to wait for one POST /tickets. CPU inference of a 2,000-character
#: ticket on a 7B-class model is slow, so this is generous. It is a timeout, not
#: a measurement: no elapsed time is recorded by this script.
DEFAULT_REQUEST_TIMEOUT_S = 300

#: Widen the service-log slice by this many seconds at each end, to absorb small
#: clock differences between this machine and the service host. The recorded
#: window in metadata.json is the true one.
DEFAULT_SLICE_MARGIN_S = 5

csv.field_size_limit(10 ** 9)          # narratives are long free text

MISUSE_EXIT = 2


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def utc_stamp(moment: datetime) -> str:
    """``YYYYmmddTHHMMSSZ`` -- the run-directory stamp format."""
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_ms(moment: datetime) -> str:
    """The service's own timestamp format: UTC, millisecond precision, ``Z``."""
    moment = moment.astimezone(timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def sanitise_model_tag(tag: str) -> str:
    """Directory-safe form of an Ollama tag.

    Delegated to :func:`analysis.common.sanitise_model_tag` so the rule lives in
    exactly one place. The import is late because ``analysis.common`` pulls in
    pandas, which is a development dependency: ``--help`` must work on a machine
    that only has the service's runtime requirements installed.
    """
    try:
        from analysis.common import sanitise_model_tag as _sanitise
    except ModuleNotFoundError as exc:      # pragma: no cover - environment issue
        raise SystemExit(
            f"cannot import analysis.common ({exc}). Install the development "
            f"requirements on this machine: pip install -r requirements-dev.txt"
        ) from exc
    return _sanitise(tag)


def git_state(repo: Path) -> tuple[str | None, bool | None]:
    """``(commit, dirty)`` for the repository, or ``(None, None)`` without git."""
    def run(*args: str) -> str | None:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, check=False,
        )
        return proc.stdout.strip() if proc.returncode == 0 else None

    commit = run("rev-parse", "HEAD")
    if commit is None:
        return None, None
    status = run("status", "--porcelain")
    return commit, bool(status)


def host_info() -> dict:
    """Facts about the machine this driver runs on. See docs/environment/ for hardware."""
    return {
        "hostname": socket.gethostname(),
        "platform": f"{os.uname().sysname} {os.uname().release} {os.uname().machine}",
        "python": sys.version.split()[0],
        "environment_capture": "docs/environment/<hostname>.txt (scripts/capture_env.sh)",
    }


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

def read_golden_row_numbers(path: Path) -> list[int]:
    """The golden set's row numbers, in file order. The LABELS ARE NOT READ.

    Only the first column is touched, so this script cannot be influenced by --
    or accused of having seen -- the frozen labels.
    """
    if not path.is_file():
        raise SystemExit(f"golden set not found: {path}")
    row_numbers: list[int] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for index, record in enumerate(csv.reader(handle)):
            if not record or not any(cell.strip() for cell in record):
                continue
            first = record[0].strip()
            if index == 0 and not first.isdigit():
                continue                    # header row
            if not first.isdigit():
                raise SystemExit(
                    f"{path}:{index + 1}: first column {first!r} is not a row number. "
                    f"The golden set's first column must be the course CSV row number."
                )
            row_numbers.append(int(first))
    if not row_numbers:
        raise SystemExit(f"{path} contains no rows.")
    duplicates = {n for n in row_numbers if row_numbers.count(n) > 1}
    if duplicates:
        raise SystemExit(
            f"{path} lists {len(duplicates)} row number(s) more than once "
            f"(e.g. {sorted(duplicates)[:5]}). Each golden row must appear once."
        )
    return row_numbers


def read_narratives(path: Path) -> dict[int, str]:
    """``{row_number: narrative}`` from a ``row_number,narrative,raw_label`` CSV."""
    if not path.is_file():
        raise SystemExit(f"narrative source not found: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        expected = ["row_number", "narrative", "raw_label"]
        if list(reader.fieldnames or []) != expected:
            raise SystemExit(
                f"{path} has columns {reader.fieldnames}; expected {expected}."
            )
        narratives: dict[int, str] = {}
        for record in reader:
            raw = (record.get("row_number") or "").strip()
            if not raw.isdigit():
                continue
            narratives[int(raw)] = record.get("narrative") or ""
    if not narratives:
        raise SystemExit(f"{path} contains no usable rows.")
    return narratives


def build_worklist(args: argparse.Namespace) -> tuple[list[tuple[int, str]], Path, Path]:
    """The ordered (row_number, narrative) list, plus the two input paths used."""
    if args.dev:
        dev_csv = REPO_ROOT / DEV_CSV_REL
        narratives = read_narratives(dev_csv)
        # Dev mode ignores golden/ entirely: the dev tickets are the worklist.
        return [(row, narratives[row]) for row in sorted(narratives)], dev_csv, dev_csv

    golden_path = args.golden if args.golden.is_absolute() else REPO_ROOT / args.golden
    team_rows_path = REPO_ROOT / TEAM_ROWS_REL
    row_numbers = read_golden_row_numbers(golden_path)
    narratives = read_narratives(team_rows_path)

    missing = [row for row in row_numbers if row not in narratives]
    if missing:
        preview = ", ".join(str(row) for row in missing[:10])
        raise SystemExit(
            f"{len(missing)} golden row number(s) are not present in {team_rows_path}: "
            f"{preview}{'...' if len(missing) > 10 else ''}\n"
            f"The golden set must be drawn from this team's 1,000 rows. Re-check "
            f"the sampler's --team-rows argument, or re-run "
            f"scripts/extract_team_rows.py."
        )
    empty = [row for row in row_numbers if not narratives[row].strip()]
    if empty:
        raise SystemExit(
            f"{len(empty)} golden row(s) have an empty narrative (e.g. {empty[:5]}). "
            f"An empty ticket cannot be classified and would silently distort the "
            f"accuracy denominator."
        )
    return [(row, narratives[row]) for row in row_numbers], golden_path, team_rows_path


# ---------------------------------------------------------------------------
# Service interaction
# ---------------------------------------------------------------------------

def fetch_health(base_url: str, timeout: float = 15.0) -> dict:
    """GET /health, or exit with advice. Never logged by the service."""
    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"GET {base_url}/health returned HTTP {exc.code}.")
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        raise SystemExit(
            f"cannot reach {base_url}/health ({exc}).\n"
            f"Start the stack first:  scripts/reset.sh --yes"
        )
    except json.JSONDecodeError as exc:
        raise SystemExit(f"GET {base_url}/health did not return JSON ({exc}).")


def require_model(health: dict, model_tag: str, base_url: str) -> None:
    """Refuse to run if the service is not serving the model we are labelling.

    Recording results under one model's name while the service was serving
    another is the single easiest way to produce numbers that cannot be
    defended, so it is a hard failure rather than a warning.
    """
    served = health.get("model_tag")
    if served != model_tag:
        raise SystemExit(
            f"the service at {base_url} is serving model_tag {served!r}, but this run "
            f"was asked for {model_tag!r}.\n"
            f"Switch the model first (recreate the triage container with "
            f"MODEL_TAG={model_tag}), then re-run:\n"
            f"    MODEL_TAG={model_tag} docker compose up -d --force-recreate triage"
        )
    if not health.get("ollama_reachable"):
        raise SystemExit(
            f"the service reports that Ollama is not reachable at "
            f"{health.get('ollama_base_url')!r}; every POST would return 502."
        )


def post_ticket(
    base_url: str, narrative: str, row_number: int, request_id: str, timeout: float
) -> tuple[int, str | None, str | None]:
    """POST one ticket. Returns ``(http_status, predicted_category, error)``.

    One request, one connection, nothing shared, nothing reused: this is the
    naive client the baseline deserves.

    # A2 candidate: post the golden set concurrently (a bounded thread pool, or
    # httpx.AsyncClient with a semaphore) and/or batch several narratives into
    # one model call, instead of this strictly sequential one-at-a-time loop.
    # A2 candidate: a single persistent HTTP connection (keep-alive) instead of
    # a new TCP connection per ticket.
    """
    body = json.dumps({"narrative": narrative}).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/tickets",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Request-ID": request_id,
            "X-Source-Row": str(row_number),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            returned_id = payload.get("request_id")
            if returned_id != request_id:
                # Without this the responses.csv could not be joined to the
                # service log at all, so it is an error, not a curiosity.
                return (
                    int(response.status),
                    payload.get("category"),
                    f"request_id_mismatch:{returned_id}",
                )
            return int(response.status), payload.get("category"), None
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:200]
        except OSError:
            pass
        slug = f"http_{exc.code}"
        if detail:
            slug = f"{slug}:{detail.replace(chr(10), ' ').strip()}"
        return int(exc.code), None, slug
    except (TimeoutError, socket.timeout):
        return 0, None, "client_timeout"
    except urllib.error.URLError as exc:
        return 0, None, f"client_connect_error:{exc.reason}"
    except json.JSONDecodeError as exc:
        return 0, None, f"client_bad_json:{exc}"


# ---------------------------------------------------------------------------
# Service log slice
# ---------------------------------------------------------------------------

def slice_service_log(
    log_dir: Path, start: datetime, end: datetime, margin_s: int
) -> tuple[list[dict], list[dict], list[str]]:
    """Return ``(measured, warmup, problems)`` log lines whose ``ts`` is in window.

    Warm-up lines are separated out so that ``service.jsonl`` holds only the
    requests this run actually posted.
    """
    window_start = start - timedelta(seconds=margin_s)
    window_end = end + timedelta(seconds=margin_s)
    measured: list[dict] = []
    warmup: list[dict] = []
    problems: list[str] = []

    if not log_dir.is_dir():
        return measured, warmup, [f"service log directory not found: {log_dir}"]

    for path in sorted(log_dir.glob("*.jsonl")):
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                problems.append(f"{path.name}:{lineno}: not valid JSON ({exc})")
                continue
            raw_ts = record.get("ts")
            if not isinstance(raw_ts, str):
                problems.append(f"{path.name}:{lineno}: missing a string 'ts'")
                continue
            try:
                moment = datetime.strptime(raw_ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                problems.append(f"{path.name}:{lineno}: ts {raw_ts!r} is not ISO-8601 UTC ms")
                continue
            if not (window_start <= moment <= window_end):
                continue
            if record.get("warmup"):
                warmup.append(record)
            else:
                measured.append(record)

    measured.sort(key=lambda record: record["ts"])
    warmup.sort(key=lambda record: record["ts"])
    return measured, warmup, problems


def sync_remote_logs(log_dir: Path) -> str | None:
    """Mirror the service host's logs/service into ``log_dir`` when SERVICE_SSH is set.

    Remote mode, the same contract as scripts/run_load_test.sh: the service runs on
    another machine, whose checkout is SERVICE_REPO (default ``ICT3113-PTO`` under
    its home directory), and its request log is copied here with rsync before it
    is sliced. Nothing is deleted on either side. Returns a problem string, or None.
    """
    target = os.environ.get("SERVICE_SSH", "")
    if not target:
        return None
    repo = os.environ.get("SERVICE_REPO", "ICT3113-PTO").rstrip("/")
    log_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            "rsync", "-a", "-e", "ssh -o BatchMode=yes -o ConnectTimeout=15",
            f"{target}:{repo}/logs/service/", f"{log_dir}/",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return f"rsync from {target}:{repo}/logs/service failed: {proc.stderr.strip()[:300]}"
    return None


def write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def sole_value(records: list[dict], field: str):
    """The single distinct value of ``field`` across records, else ``None``.

    Used for ``seed``, which /health does not report but every log line does. If
    the run somehow spans two configurations, ``None`` is recorded rather than an
    arbitrary choice: a metadata field must never be a guess.
    """
    values = {
        json.dumps(record.get(field), sort_keys=True)
        for record in records
        if field in record
    }
    if len(values) == 1:
        return json.loads(next(iter(values)))
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_accuracy.py",
        description=(
            "Post every golden-set ticket through POST /tickets once, for one "
            "model, and record what came back. Computes no accuracy: run "
            "analysis/accuracy.py afterwards."
        ),
        epilog=(
            "Environment variables: SERVICE_LOG_DIR (default logs/service), "
            "SERVICE_SSH and SERVICE_REPO (remote mode: mirror the service host's "
            "logs/service with rsync before slicing it), "
            "ACCURACY_TIMEOUT_S (default %d), SLICE_MARGIN_S (default %d), "
            "RUN_NOTES (free text copied into metadata.json)."
            % (DEFAULT_REQUEST_TIMEOUT_S, DEFAULT_SLICE_MARGIN_S)
        ),
    )
    parser.add_argument(
        "--model",
        required=True,
        help="The Ollama tag the service is currently serving, e.g. llama3.2:1b-instruct-q4_K_M. "
             "Refused if /health disagrees.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Service host (default 127.0.0.1).")
    parser.add_argument("--port", default="8000", help="Service port (default 8000).")
    parser.add_argument(
        "--golden",
        type=Path,
        default=Path(GOLDEN_REL),
        help=f"Golden set CSV (default {GOLDEN_REL}). Only its row numbers are read. "
             f"Ignored by --dev.",
    )
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
        help="Bypass the freeze gate and use data/dev/synthetic_tickets.csv instead. "
             "Writes only under results/dev/ and stamps mode=dev. Not evidence.",
    )
    return parser.parse_args(argv)


def refuse_real_data_in_dev(argv: list[str]) -> None:
    """Exit 2 if a dev-mode invocation names the team rows or the golden set.

    The raw argument list is inspected rather than the parsed values, so that a
    default (``--golden golden/golden_set.csv``) does not trip the check while an
    explicit request for real data does.
    """
    for raw in argv:
        lowered = raw.lower()
        if "team_rows.csv" in lowered or "golden/" in lowered or "golden_set" in lowered:
            raise SystemExit(
                MISUSE_EXIT_MESSAGE.format(argument=raw)
            )


MISUSE_EXIT_MESSAGE = (
    "run_accuracy.py: refusing: --dev was given together with {argument!r}, which "
    "names real team data. Dev mode exists precisely so that no model sees a team "
    "row or a golden-set row before the freeze. Drop --dev once the freeze gate "
    "passes."
)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parse_args(argv)

    if args.dev:
        try:
            refuse_real_data_in_dev(argv)
        except SystemExit as exc:
            print(exc, file=sys.stderr)
            return MISUSE_EXIT
        print(DEV_BANNER)

    base_url = f"http://{args.host}:{args.port}"

    # --- the freeze gate ---------------------------------------------------
    if args.dev:
        freeze_payload: dict = {
            "ok": False,
            "mode": "dev",
            "enforced": False,
            "reasons": [
                "dev mode: the freeze gate was bypassed, so this directory is not "
                "evidence and must never be cited."
            ],
        }
        freeze_commit = None
        freeze_tag = None
    else:
        status = freeze_gate.check_freeze(REPO_ROOT)
        if not status.ok:
            print(freeze_gate.explain(status), file=sys.stderr)
            return freeze_gate.GATE_BLOCKED_EXIT
        freeze_payload = status.to_payload()
        freeze_commit = status.freeze_commit
        freeze_tag = status.freeze_tag
        print(f"Freeze gate: PASS (commit {freeze_commit}, tag '{freeze_tag}').")

    # --- inputs ------------------------------------------------------------
    worklist, input_csv, narrative_source = build_worklist(args)

    out_root = args.out_root
    if out_root is None:
        out_root = Path(DEV_OUT_ROOT_REL if args.dev else REAL_OUT_ROOT_REL)
    if not out_root.is_absolute():
        out_root = REPO_ROOT / out_root
    if args.dev:
        dev_root = (REPO_ROOT / "results" / "dev").resolve()
        try:
            out_root.resolve().relative_to(dev_root)
        except ValueError:
            print(
                f"run_accuracy.py: refusing: --dev may only write under "
                f"{dev_root} (got {out_root}). Dev output is gitignored so that it "
                f"can never be mistaken for evidence.",
                file=sys.stderr,
            )
            return MISUSE_EXIT

    # --- the service -------------------------------------------------------
    health = fetch_health(base_url)
    require_model(health, args.model, base_url)

    log_dir = Path(os.environ.get("SERVICE_LOG_DIR", REPO_ROOT / "logs" / "service"))
    timeout = float(os.environ.get("ACCURACY_TIMEOUT_S", DEFAULT_REQUEST_TIMEOUT_S))
    margin_s = int(os.environ.get("SLICE_MARGIN_S", DEFAULT_SLICE_MARGIN_S))

    started = datetime.now(timezone.utc)
    stamp = utc_stamp(started)
    run_dir = out_root / f"{sanitise_model_tag(args.model)}_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)

    print(f"Model    : {args.model} (digest {health.get('model_digest')})")
    print(f"Service  : {base_url}")
    print(f"Input    : {input_csv.relative_to(REPO_ROOT) if input_csv.is_relative_to(REPO_ROOT) else input_csv}")
    print(f"Tickets  : {len(worklist)}")
    print(f"Output   : {run_dir}")
    print()

    # --- the sequential posting loop --------------------------------------
    responses_path = run_dir / "responses.csv"
    status_counts: dict[int, int] = {}
    error_count = 0
    # Written incrementally and flushed per row: if the run dies half way, the
    # rows already posted remain on disk as evidence of what happened.
    with responses_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["row_number", "request_id", "http_status", "predicted_category", "error"]
        )
        for index, (row_number, narrative) in enumerate(worklist, 1):
            request_id = str(uuid.uuid4())
            http_status, category, error = post_ticket(
                base_url, narrative, row_number, request_id, timeout
            )
            writer.writerow(
                [row_number, request_id, http_status, category or "", error or ""]
            )
            handle.flush()
            status_counts[http_status] = status_counts.get(http_status, 0) + 1
            if http_status != 200 or error:
                error_count += 1
            # Progress only: counts, never a latency and never a running score.
            if index == 1 or index % 10 == 0 or index == len(worklist):
                print(
                    f"  [{index:>4}/{len(worklist)}] posted; "
                    f"HTTP errors so far: {error_count}",
                    flush=True,
                )

    ended = datetime.now(timezone.utc)

    # --- the service's own record of the same requests --------------------
    if os.environ.get("SERVICE_SSH"):
        time.sleep(2)              # the last line is written as the response leaves
    sync_problem = sync_remote_logs(log_dir)
    measured, warmup, problems = slice_service_log(log_dir, started, ended, margin_s)
    if sync_problem:
        problems.insert(0, sync_problem)
    write_jsonl(run_dir / "service.jsonl", measured)
    if warmup:
        write_jsonl(run_dir / "warmup.jsonl", warmup)
    for problem in problems:
        print(f"  service log: {problem}", file=sys.stderr)

    off_schema = sorted(
        {key for record in measured for key in record if key not in LOG_FIELDS}
    )
    if off_schema:
        print(
            f"  service log: unexpected field(s) {off_schema} -- the service and "
            f"service/log_schema.py have diverged.",
            file=sys.stderr,
        )

    # --- metadata ----------------------------------------------------------
    commit, dirty = git_state(REPO_ROOT)
    notes = os.environ.get("RUN_NOTES", "")
    note_parts = [notes] if notes else []
    note_parts.append(f"narratives resolved from {narrative_source.name} by row_number")
    note_parts.append(f"posted={len(worklist)} status_counts={status_counts}")
    note_parts.append(f"service log lines captured={len(measured)}")
    if problems:
        note_parts.append(f"service log problems={len(problems)}")

    metadata = {
        "run_id": run_dir.name,
        "mode": "dev" if args.dev else "real",
        "plan": "accuracy",
        "plan_file": None,                 # no JMeter plan: this driver is the client
        "model_tag": args.model,
        "model_digest": health.get("model_digest"),
        "rate_per_min": None,              # sequential by design, not rate-driven
        "duration_s": None,                # not a timed test; see started/ended
        "run_index": 1,
        "runs_total": 1,                   # the golden set is posted once per model
        "started_at_utc": iso_ms(started),
        "ended_at_utc": iso_ms(ended),
        "git_commit": commit,
        "git_dirty": dirty,
        "freeze_commit": freeze_commit,
        "freeze_tag": freeze_tag,
        "prompt_hash": health.get("prompt_hash"),
        "num_ctx": health.get("num_ctx"),
        "seed": sole_value(measured, "seed"),
        "input_csv": str(
            input_csv.relative_to(REPO_ROOT)
            if input_csv.is_relative_to(REPO_ROOT)
            else input_csv
        ),
        "service_url": base_url,
        "service_host_info": {
            "target_url": base_url,
            "ollama_base_url": health.get("ollama_base_url"),
            "db_path": health.get("db_path"),
            "uvicorn_workers": health.get("uvicorn_workers"),
            "threadpool_size": health.get("threadpool_size"),
            "note": "hardware is recorded by scripts/capture_env.sh on the service host",
        },
        "load_generator_host_info": host_info(),
        "jmeter_version": None,            # JMeter is not involved in the accuracy test
        "ollama_num_parallel": os.environ.get("OLLAMA_NUM_PARALLEL", "default"),
        "ollama_max_loaded_models": os.environ.get("OLLAMA_MAX_LOADED_MODELS", "default"),
        "warmup_request_id": None,         # no warm-up: nothing here is timed
        "notes": "; ".join(note_parts),
    }
    (run_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    (run_dir / "freeze.json").write_text(
        json.dumps(freeze_payload, indent=2) + "\n", encoding="utf-8"
    )

    # --- summary: counts only ---------------------------------------------
    print()
    print(f"Wrote {run_dir}")
    print(f"  responses.csv : {len(worklist)} rows")
    print(f"  service.jsonl : {len(measured)} log lines"
          + (f" (+{len(warmup)} warm-up lines separated out)" if warmup else ""))
    print(f"  HTTP status counts: {dict(sorted(status_counts.items()))}")
    if error_count:
        print(
            f"  {error_count} request(s) did not return HTTP 200. Those rows carry an "
            f"error in responses.csv and must be explained, not dropped silently.",
            file=sys.stderr,
        )
    if len(measured) != len(worklist):
        print(
            f"  WARNING: {len(worklist)} tickets posted but {len(measured)} service log "
            f"lines captured in the window. analysis/reconcile.py exists to chase this; "
            f"check SERVICE_LOG_DIR ({log_dir}) and the clocks on both machines.",
            file=sys.stderr,
        )
    print()
    print("No accuracy was computed here, by design. Score the run with:")
    print(f"    python analysis/accuracy.py --results {out_root.relative_to(REPO_ROOT) if out_root.is_relative_to(REPO_ROOT) else out_root}")
    if args.dev:
        print()
        print(DEV_BANNER)
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
