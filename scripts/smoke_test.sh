#!/usr/bin/env bash
#
# smoke_test.sh -- the pre-freeze smoke test for the triage service.
#
# Owner: Part 1 -- Yeo Kai Yuan (technical core).
#
# What this proves
#   The service is wired up end to end: /health answers, POST /tickets returns
#   200 with a category we recognise and the request id we sent, and a
#   well-formed log line lands in logs/service/ with all 24 contracted fields.
#
# What this deliberately does NOT do
#   It does not print, compute, compare or summarise any latency, and it does
#   not check whether the category is *correct*. Both would be measuring the
#   model before the golden set is frozen, which is precisely what the freeze
#   exists to prevent. If you want to know how fast or how accurate a model is,
#   freeze the golden set first and then run scripts/run_load_test.sh and
#   scripts/run_accuracy.py.
#
# It reads data/dev/synthetic_tickets.csv and nothing else, ever: those 28
# tickets are hand-written, so no real team row and no golden-set row can reach
# a model through this script. Pointing it at another file is refused (exit 2).
#
# Usage:
#   scripts/smoke_test.sh [--host HOST] [--port PORT] [--count N]
#
# Exit codes:
#   0  every check passed
#   1  a check failed (the service is not behaving to contract)
#   2  misuse: bad arguments, or an attempt to read anything but the dev file
#
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
export REPO_ROOT

HOST="127.0.0.1"
PORT="8000"
COUNT="3"

#: The ONLY input this script will ever read.
DEV_CSV="${REPO_ROOT}/data/dev/synthetic_tickets.csv"

#: Where the service's JSONL request log lands. Override when the service runs
#: on another machine and its log directory is mounted or synced elsewhere.
SERVICE_LOG_DIR="${SERVICE_LOG_DIR:-${REPO_ROOT}/logs/service}"

#: curl timeout per request. CPU inference is slow, so this is generous; it is a
#: timeout, not a measurement, and no elapsed time is ever reported.
SMOKE_TIMEOUT_S="${SMOKE_TIMEOUT_S:-180}"

#: How many times to re-read the log directory while looking for a request's log
#: line. The service flushes inside the handler, but a network hop can still put
#: the response ahead of the file write on a loaded machine.
LOG_LOOKUP_ATTEMPTS=15

usage() {
    cat <<'USAGE'
smoke_test.sh -- pre-freeze smoke test: /health, POST /tickets, and the log line.

Usage:
  scripts/smoke_test.sh [--host HOST] [--port PORT] [--count N]

Options:
  --host HOST   Service host (default 127.0.0.1).
  --port PORT   Service port (default 8000).
  --count N     How many of the dev tickets to post (default 3, max 28).
  -h, --help    Print this help and exit.

Input is fixed to data/dev/synthetic_tickets.csv -- hand-written synthetic
tickets. This script refuses (exit 2) to read data/team_rows.csv or anything
under golden/, because no model may see a real ticket before the freeze.

Checks, per posted ticket:
  * HTTP 200
  * the returned category is one of the seven, or UNPARSEABLE
  * the returned request_id is exactly the X-Request-ID that was sent
  * a log line with that request_id exists in the service log and carries all
    24 fields of service/log_schema.py, with the values that line must have

No latency is measured, printed or implied, and accuracy is not assessed.

Environment variables:
  SERVICE_LOG_DIR   Where to look for <date>.jsonl (default logs/service).
  SMOKE_TIMEOUT_S   Per-request curl timeout in seconds (default 180).
USAGE
}

die_usage() { printf 'smoke_test.sh: %s\n' "$*" >&2; exit 2; }
die_fail()  { printf 'smoke_test.sh: FAIL: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Refuse real data before doing anything else. The check is on the raw argument
# list, so even an argument this script would otherwise ignore cannot smuggle a
# path to team rows or to the golden set into a pre-freeze model call.
# ---------------------------------------------------------------------------
for raw in "$@"; do
    case "$raw" in
        *team_rows.csv*|*golden/*|*golden_set*)
            die_usage "refusing: '$raw' names real team data. This script only ever reads data/dev/synthetic_tickets.csv (no model may see a team row before the freeze)."
            ;;
    esac
done
if [[ -n "${SMOKE_INPUT_CSV:-}" && "${SMOKE_INPUT_CSV}" != "${DEV_CSV}" ]]; then
    die_usage "refusing: SMOKE_INPUT_CSV is set to '${SMOKE_INPUT_CSV}'. The input is fixed to ${DEV_CSV}."
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host) [[ $# -ge 2 ]] || die_usage "--host needs a value"; HOST="$2"; shift 2 ;;
        --host=*) HOST="${1#*=}"; shift ;;
        --port) [[ $# -ge 2 ]] || die_usage "--port needs a value"; PORT="$2"; shift 2 ;;
        --port=*) PORT="${1#*=}"; shift ;;
        --count) [[ $# -ge 2 ]] || die_usage "--count needs a value"; COUNT="$2"; shift 2 ;;
        --count=*) COUNT="${1#*=}"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die_usage "unknown argument: $1" ;;
    esac
done

[[ "$COUNT" =~ ^[0-9]+$ && "$COUNT" -ge 1 ]] || die_usage "--count must be a positive integer (got '$COUNT')"
[[ "$PORT" =~ ^[0-9]+$ ]] || die_usage "--port must be a number (got '$PORT')"

command -v curl >/dev/null 2>&1 || die_usage "curl is not installed; this smoke test is curl-based."

# The repository virtualenv is used for the JSON checks so that the same
# service/log_schema.py the service writes against is the one we assert against.
PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
    PYTHON_BIN="$(command -v python3 || true)"
    [[ -n "$PYTHON_BIN" ]] || die_usage "neither .venv/bin/python nor python3 is available"
    printf 'NOTE: .venv/bin/python not found; falling back to %s\n' "$PYTHON_BIN" >&2
fi

[[ -f "$DEV_CSV" ]] || die_usage "missing $DEV_CSV"
BASE_URL="http://${HOST}:${PORT}"

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/smoke_test.XXXXXX")"
cleanup() { rm -rf "$WORK_DIR"; }
trap cleanup EXIT

echo '*** DEV MODE — synthetic tickets only. Results are NOT evidence. ***'
echo "Smoke test against ${BASE_URL} using ${COUNT} of the hand-written dev tickets."
echo

# ---------------------------------------------------------------------------
# 1. GET /health
# ---------------------------------------------------------------------------
echo "[1/3] GET /health"
health_body="${WORK_DIR}/health.json"
health_code="$(curl -sS -o "$health_body" -w '%{http_code}' --max-time 15 "${BASE_URL}/health" || true)"
health_code="${health_code:-000}"
[[ "$health_code" == "200" ]] || die_fail "GET /health returned HTTP ${health_code}. Is the service running? Try: scripts/reset.sh --yes"

"$PYTHON_BIN" - "$health_body" <<'PY_HEALTH' || die_fail "/health did not satisfy the contract (see above)"
"""Validate /health against the configuration contract. Prints configuration
facts only -- never a timing or an accuracy figure."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["REPO_ROOT"])
from service.categories import CATEGORIES            # noqa: E402

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
required = (
    "status", "model_tag", "model_digest", "num_ctx", "ollama_base_url",
    "ollama_reachable", "prompt_hash", "uvicorn_workers", "threadpool_size",
    "db_path", "categories",
)
missing = [key for key in required if key not in payload]
if missing:
    print(f"  /health is missing field(s): {missing}", file=sys.stderr)
    raise SystemExit(1)

if list(payload["categories"]) != list(CATEGORIES):
    print("  /health reports a different category list (or a different order)", file=sys.stderr)
    print(f"    service: {payload['categories']}", file=sys.stderr)
    print(f"    contract: {list(CATEGORIES)}", file=sys.stderr)
    raise SystemExit(1)

for key in ("model_tag", "model_digest", "num_ctx", "prompt_hash",
            "uvicorn_workers", "threadpool_size", "db_path", "ollama_base_url"):
    print(f"      {key:16}: {payload[key]}")

if not payload["ollama_reachable"]:
    print("  Ollama is not reachable from the service, so POST /tickets cannot "
          "classify anything.", file=sys.stderr)
    print(f"    the service is looking at {payload['ollama_base_url']}", file=sys.stderr)
    raise SystemExit(1)
if payload["status"] != "ok":
    print(f"  /health reports status={payload['status']!r}", file=sys.stderr)
    raise SystemExit(1)
PY_HEALTH
echo "      /health: ok"
echo

# ---------------------------------------------------------------------------
# 2. Prepare the request bodies from the dev CSV.
#    Done in Python because a narrative contains commas, quotes and newlines,
#    and because the JSON body must be correctly escaped.
# ---------------------------------------------------------------------------
LIST_FILE="${WORK_DIR}/tickets.tsv"
"$PYTHON_BIN" - "$DEV_CSV" "$COUNT" "$WORK_DIR" > "$LIST_FILE" <<'PY_PREPARE' || die_usage "could not read the dev tickets (see above)"
"""Write the first N dev narratives as JSON request bodies.

Emits one '<row_number>\t<body file>' line per ticket. Also enforces, in code,
that the file being read really is the synthetic dev file: this script must be
incapable of sending a real team row to a model before the freeze.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

csv.field_size_limit(10 ** 9)          # narratives are long free text

source = Path(sys.argv[1]).resolve()
count = int(sys.argv[2])
out_dir = Path(sys.argv[3])

expected = (Path(os.environ["REPO_ROOT"]) / "data" / "dev" / "synthetic_tickets.csv").resolve()
if source != expected:
    print(f"  refusing to read {source}; the only permitted input is {expected}", file=sys.stderr)
    raise SystemExit(2)

with source.open(newline="", encoding="utf-8") as handle:
    reader = csv.DictReader(handle)
    if list(reader.fieldnames or []) != ["row_number", "narrative", "raw_label"]:
        print(f"  {source} has unexpected columns: {reader.fieldnames}", file=sys.stderr)
        raise SystemExit(2)
    rows = list(reader)

if count > len(rows):
    print(f"  --count {count} exceeds the {len(rows)} tickets in {source.name}", file=sys.stderr)
    raise SystemExit(2)

for index, row in enumerate(rows[:count]):
    body_path = out_dir / f"body_{index:03d}.json"
    body_path.write_text(
        json.dumps({"narrative": row["narrative"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"{row['row_number']}\t{body_path}")
PY_PREPARE

# ---------------------------------------------------------------------------
# 3. POST each ticket and verify the response and the log line.
# ---------------------------------------------------------------------------
verify_one() {
    # verify_one <response body file> <http code> <request id> <source row>
    SERVICE_LOG_DIR="$SERVICE_LOG_DIR" LOG_LOOKUP_ATTEMPTS="$LOG_LOOKUP_ATTEMPTS" \
    "$PYTHON_BIN" - "$1" "$2" "$3" "$4" <<'PY_VERIFY'
"""Verify one POST /tickets response and its service log line.

Checked here (and nothing else):
  * HTTP 200
  * body has id / category / request_id
  * category is one of the seven canonical names, or UNPARSEABLE
  * request_id echoes exactly what was sent
  * a log line with that request_id exists and has EXACTLY the 24 fields of
    service/log_schema.LOG_FIELDS, with the values that line must carry

Deliberately NOT checked, and deliberately not printed: any timing field, and
whether the category is the right one. Both are measurements that may not
happen before the golden set is frozen.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.environ["REPO_ROOT"])
from service.categories import CATEGORIES, UNPARSEABLE        # noqa: E402
from service.log_schema import LOG_FIELDS                     # noqa: E402

body_path, http_code, request_id, source_row = sys.argv[1:5]
problems: list[str] = []

if http_code != "200":
    print(f"  HTTP {http_code} (expected 200)", file=sys.stderr)
    body_text = Path(body_path).read_text(encoding="utf-8", errors="replace")[:500]
    print(f"  response body: {body_text}", file=sys.stderr)
    raise SystemExit(1)

try:
    payload = json.loads(Path(body_path).read_text(encoding="utf-8"))
except json.JSONDecodeError as exc:
    print(f"  response is not JSON: {exc}", file=sys.stderr)
    raise SystemExit(1)

for key in ("id", "category", "request_id"):
    if key not in payload:
        problems.append(f"response is missing {key!r}")

category = payload.get("category")
if category is not None and category not in set(CATEGORIES) | {UNPARSEABLE}:
    problems.append(
        f"category {category!r} is neither one of the seven canonical names nor {UNPARSEABLE!r}"
    )
if payload.get("request_id") != request_id:
    problems.append(
        f"request_id came back as {payload.get('request_id')!r}, sent {request_id!r}"
    )

# --- find the log line -----------------------------------------------------
log_dir = Path(os.environ["SERVICE_LOG_DIR"])
attempts = int(os.environ.get("LOG_LOOKUP_ATTEMPTS", "15"))
record: dict | None = None
for attempt in range(attempts):
    for path in sorted(log_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or request_id not in line:
                continue
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError as exc:
                problems.append(f"{path.name} contains a line that is not valid JSON: {exc}")
                continue
            if candidate.get("request_id") == request_id:
                record = candidate
                break
        if record is not None:
            break
    if record is not None:
        break
    time.sleep(0.2)          # the write may trail the response over a network hop

if record is None:
    problems.append(
        f"no log line with request_id {request_id} in {log_dir} "
        f"(is LOG_DIR bind-mounted to ./logs/service?)"
    )
else:
    keys = list(record)
    if keys != list(LOG_FIELDS):
        extra = [k for k in keys if k not in LOG_FIELDS]
        missing = [k for k in LOG_FIELDS if k not in keys]
        if extra or missing:
            problems.append(
                f"log line does not match the {len(LOG_FIELDS)}-field schema: "
                f"unexpected={extra} missing={missing}"
            )
        else:
            problems.append("log line has the right fields in the wrong order")
    expectations = {
        "endpoint": "/tickets",
        "method": "POST",
        "status": 200,
        "source_row": source_row,
        "warmup": False,
        "error": None,
    }
    for key, want in expectations.items():
        if key in record and record[key] != want:
            problems.append(f"log line {key}={record[key]!r}, expected {want!r}")
    if record.get("predicted_category") != category:
        problems.append(
            f"log line predicted_category={record.get('predicted_category')!r} "
            f"but the response said {category!r}"
        )
    if not isinstance(record.get("ticket_chars"), int) or record.get("ticket_chars", 0) <= 0:
        problems.append(f"log line ticket_chars={record.get('ticket_chars')!r} is not a positive int")
    ts = str(record.get("ts", ""))
    if not (ts.endswith("Z") and len(ts) == 24 and ts[10] == "T"):
        problems.append(f"log line ts={ts!r} is not ISO-8601 UTC with millisecond precision")

if problems:
    for problem in problems:
        print(f"  {problem}", file=sys.stderr)
    raise SystemExit(1)

# One line of output per ticket: identity and outcome only.
print(f"      row {source_row}: HTTP 200, category={category!r}, log line complete ({len(LOG_FIELDS)} fields)")
PY_VERIFY
}

echo "[2/3] POST /tickets x ${COUNT}"
posted=0
while IFS=$'\t' read -r row_number payload_file; do
    [[ -n "$row_number" ]] || continue
    request_id="smoke-$("$PYTHON_BIN" -c 'import uuid; print(uuid.uuid4())')"
    response_file="${WORK_DIR}/response_${row_number}.json"

    # A2 candidate: reuse one connection for every request (curl --keepalive /
    # a single session) instead of a fresh TCP + TLS-free connection per ticket.
    # Left naive: the smoke test's job is correctness, and the baseline is naive
    # by design.
    http_code="$(curl -sS -o "$response_file" -w '%{http_code}' \
        --max-time "$SMOKE_TIMEOUT_S" \
        -X POST "${BASE_URL}/tickets" \
        -H 'Content-Type: application/json' \
        -H "X-Request-ID: ${request_id}" \
        -H "X-Source-Row: ${row_number}" \
        --data-binary "@${payload_file}" || true)"
    http_code="${http_code:-000}"

    if ! verify_one "$response_file" "$http_code" "$request_id" "$row_number"; then
        die_fail "ticket from dev row ${row_number} (request_id ${request_id}) did not satisfy the contract."
    fi
    posted=$((posted + 1))
done < "$LIST_FILE"

[[ "$posted" -eq "$COUNT" ]] || die_fail "posted ${posted} tickets but expected ${COUNT}"
echo

# ---------------------------------------------------------------------------
# 4. GET /stats and GET /search must answer. No counts are asserted against a
#    model's behaviour -- only that the endpoints exist and answer.
# ---------------------------------------------------------------------------
echo "[3/3] GET /stats and GET /search"
stats_code="$(curl -sS -o "${WORK_DIR}/stats.json" -w '%{http_code}' --max-time 30 "${BASE_URL}/stats" || true)"
stats_code="${stats_code:-000}"
[[ "$stats_code" == "200" ]] || die_fail "GET /stats returned HTTP ${stats_code}"
search_code="$(curl -sS -o "${WORK_DIR}/search.json" -w '%{http_code}' --max-time 30 \
    --get --data-urlencode 'q=account' --data 'limit=50' "${BASE_URL}/search" || true)"
search_code="${search_code:-000}"
[[ "$search_code" == "200" ]] || die_fail "GET /search returned HTTP ${search_code}"

"$PYTHON_BIN" - "${WORK_DIR}/stats.json" "${WORK_DIR}/search.json" "$posted" <<'PY_TAIL' || die_fail "/stats or /search did not satisfy the contract (see above)"
"""Shape checks for /stats and /search. No accuracy, no timing."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["REPO_ROOT"])
from service.categories import CATEGORIES, UNPARSEABLE        # noqa: E402

stats = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
search = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
posted = int(sys.argv[3])

problems = []
if "total" not in stats or "counts" not in stats:
    problems.append(f"/stats must have 'total' and 'counts'; got keys {sorted(stats)}")
else:
    want_keys = list(CATEGORIES) + [UNPARSEABLE]
    if list(stats["counts"]) != want_keys:
        problems.append(
            "/stats counts must list the seven categories in canonical order plus "
            f"{UNPARSEABLE}; got {list(stats['counts'])}"
        )
    if stats["total"] < posted:
        problems.append(
            f"/stats total={stats['total']} is fewer than the {posted} tickets just posted"
        )
if not isinstance(search, (list, dict)):
    problems.append(f"/search returned {type(search).__name__}, expected a JSON array or object")

for problem in problems:
    print(f"  {problem}", file=sys.stderr)
raise SystemExit(1 if problems else 0)
PY_TAIL
echo "      /stats and /search answered and are shaped to contract"
echo

echo "SMOKE TEST PASSED: ${posted}/${COUNT} tickets classified, ${posted}/${COUNT} log lines complete."
echo "No latency and no accuracy was measured. Synthetic tickets only; this is not evidence."
