#!/usr/bin/env bash
#
# run_load_test.sh -- run one JMeter load test configuration, three times, and
#                     keep everything needed to defend the numbers afterwards.
#
# Owner: Part 1 -- Yeo Kai Yuan (technical core).
#
# The brief is strict about what counts as a measurement: open-loop arrivals,
# three runs per configuration, raw .jtl files kept, and every reported number
# reconcilable with the service log. This script is the only sanctioned way to
# produce a benchmark result, and it refuses to produce one at all until the
# golden set and the prediction record are committed and tagged (the freeze
# gate). Everything it writes into a run directory is evidence; nothing it
# writes is derived, summarised or interpreted -- that is the analysis scripts'
# job, deliberately separated so that a result cannot be quietly re-shaped while
# it is being produced.
#
# Order of operations per run (do not reorder: each step exists because the
# previous one would otherwise contaminate the measurement)
#   1. Freeze gate.       Refuse to measure before the labels and predictions
#                         are frozen. Its JSON verdict is copied into the run
#                         directory as freeze.json.
#   2. Reset and switch.  scripts/reset.sh --yes wipes stored tickets so every
#                         run starts from an empty database (GET /search scans
#                         the table, so a leftover table changes what we
#                         measure), then the triage container is recreated with
#                         MODEL_TAG set and we wait for /health to confirm the
#                         requested model and a reachable Ollama.
#   3. Warm up.           ONE POST /tickets from the dev tickets, flagged
#                         X-Warmup: 1, so that the first-request model load cost
#                         is paid before measurement. Its log line goes to
#                         warmup.jsonl and is excluded from analysis.
#   4. Measure.           JMeter in non-GUI mode, open model thread group, with
#                         -Jsample_variables=request_id,source_row so the CSV
#                         .jtl carries the two headers the service echoes back.
#   5. Slice the log.     The service log lines inside the measured window are
#                         copied into service.jsonl, so the run directory is
#                         self-contained.
#   6. Record.            metadata.json, with the exact keys the repository's
#                         contract specifies.
#
# Usage:
#   scripts/run_load_test.sh --plan load_post_tickets --model llama3.2:1b \
#        --rate 60 --duration 300 [--runs 3] [--host H] [--port P] \
#        [--search-rate N] [--jmeter-home PATH] [--out-root results/runs] \
#        [--dev] [--yes]
#
# Exit codes: 0 all runs completed; 1 a run failed or its evidence is incomplete;
#             2 misuse (bad arguments, JMeter missing, dev-mode violation);
#             3 the freeze gate blocked the run.
#
# A2 candidate: none of the tuning knobs below (worker counts, connection reuse,
# Ollama parallelism) are touched by this script. The baseline is measured as
# built; changing the system to make it faster is Assignment 2.
#
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"

# --- defaults --------------------------------------------------------------
PLAN=""
MODEL=""
RATE=""
DURATION=""
RUNS=3
HOST="127.0.0.1"
PORT="8000"
SEARCH_RATE=""
JMETER_HOME_ARG=""
OUT_ROOT_ARG=""
DEV=0
ASSUME_YES=0

DEV_CSV_REL="data/dev/synthetic_tickets.csv"
TEAM_ROWS_REL="data/team_rows.csv"
SEARCH_TERMS_REL="data/search_terms.txt"
DEV_BANNER='*** DEV MODE — synthetic tickets only. Results are NOT evidence. ***'

# --- environment overrides (documented in usage) ---------------------------
# The CLI is fixed by the repository contract, so machine-specific plumbing is
# configured through the environment rather than by adding flags.
COMPOSE_FILE="${COMPOSE_FILE:-${REPO_ROOT}/docker-compose.yml}"
TRIAGE_SERVICE="${TRIAGE_SERVICE:-triage}"
OLLAMA_SERVICE="${OLLAMA_SERVICE:-ollama}"
SERVICE_LOG_DIR="${SERVICE_LOG_DIR:-${REPO_ROOT}/logs/service}"
SERVICE_SSH="${SERVICE_SSH:-}"
SERVICE_REPO="${SERVICE_REPO:-ICT3113-PTO}"
HEALTH_TIMEOUT_S="${HEALTH_TIMEOUT_S:-240}"
WARMUP_TIMEOUT_S="${WARMUP_TIMEOUT_S:-600}"
SLICE_MARGIN_S="${SLICE_MARGIN_S:-5}"
SETTLE_S="${SETTLE_S:-5}"
DRAIN_S="${DRAIN_S:-150}"
RUN_NOTES="${RUN_NOTES:-}"

usage() {
    cat <<'USAGE'
run_load_test.sh -- one load-test configuration, repeated, with its evidence.

Usage:
  scripts/run_load_test.sh --plan PLAN --model TAG --rate N --duration S
                           [--runs 3] [--host HOST] [--port PORT]
                           [--search-rate N] [--jmeter-home PATH]
                           [--out-root results/runs] [--dev] [--yes]

Required:
  --plan PLAN        load_post_tickets | mixed_load | stress_ramp
                     (the .jmx of the same name in jmeter/)
  --model TAG        Ollama tag to serve, e.g. llama3.2:1b. The triage container
                     is recreated with MODEL_TAG set to this, and /health must
                     confirm it before anything is measured.
  --rate N           Arrival rate in requests per minute (open loop). For
                     stress_ramp this is the FIRST step's rate.
  --duration S       Measured duration in seconds per run.

Optional:
  --runs N           Repeats of the whole reset/switch/warm-up/measure cycle
                     (default 3). The brief requires three: a single run is not
                     a measurement.
  --host HOST        Service host (default 127.0.0.1).
  --port PORT        Service port (default 8000).
  --search-rate N    GET /search arrivals per minute; only used by mixed_load.
                     Omitted means the plan's own default applies.
  --jmeter-home PATH JMeter installation directory (uses PATH otherwise).
  --out-root DIR     Where run directories are created (default results/runs).
  --dev              Pre-freeze rehearsal: bypasses the freeze gate, forces the
                     input to data/dev/synthetic_tickets.csv, writes only under
                     results/dev/runs, stamps mode=dev and freeze_commit=null.
                     Refuses (exit 2) if any argument names real team data.
  --yes              Do not ask for confirmation. Each run calls
                     scripts/reset.sh --yes, which DESTROYS the stored tickets.
  -h, --help         Print this help and exit.

Output, per run, in <out-root>/<UTCSTAMP>_<model>_<plan>_<rate>_run<k>/ :
  metadata.json  freeze.json  results.jtl  jmeter.log  jmeter_stdout.txt
  service.jsonl  warmup.jsonl

Environment variables:
  COMPOSE_FILE            docker compose file (default ./docker-compose.yml)
  COMPOSE_PROJECT_NAME    passed to docker compose as -p when set
  TRIAGE_SERVICE          compose service name of the web service (default triage)
  OLLAMA_SERVICE          compose service name of the model backend (default ollama)
  DOCKER_HOST             set this (e.g. ssh://user@service-host) when the load
                          generator is a different machine from the service --
                          which the brief requires
  SERVICE_SSH             user@service-host. Remote mode: docker compose and
                          scripts/reset.sh run in the service host's own
                          checkout over ssh (so its bind mounts resolve on that
                          machine), and its logs/service is mirrored into
                          SERVICE_LOG_DIR with rsync before every read. The
                          remote checkout must be at the same commit as this one.
  SERVICE_REPO            the service host's checkout, relative to its home
                          directory or absolute (default ICT3113-PTO)
  SERVICE_LOG_DIR         where <date>.jsonl is readable (default logs/service)
  HEALTH_TIMEOUT_S        wait for /health after a model switch (default 240)
  WARMUP_TIMEOUT_S        curl timeout for the single warm-up POST (default 600)
  SLICE_MARGIN_S          widen the service-log slice at each end, to absorb
                          clock skew between machines (default 5)
  SETTLE_S                pause between the warm-up and the measured window
                          (default 5)
  DRAIN_S                 seconds after the last arrival during which no new
                          request is sent but those in flight may finish
                          (default 150, longer than the service's 120 s model
                          timeout). Without it JMeter interrupts every request
                          still in flight when the schedule ends and records it
                          as a failure, cutting the slowest tail off the
                          percentiles; the stress plan gets it as ramp_drain_s
  RAMP_START_PER_MIN, RAMP_STEP_PER_MIN, RAMP_STEPS, RAMP_STEP_DURATION_S
                          passed to stress_ramp.jmx when set; otherwise the
                          plan's own documented defaults apply
  OLLAMA_NUM_PARALLEL, OLLAMA_MAX_LOADED_MODELS
                          recorded in metadata.json (recorded only -- this
                          script never tunes Ollama)
  RUN_NOTES               free text copied into metadata.json's notes field
USAGE
}

log()  { printf '%s\n' "$*"; }
step() { printf '\n== %s\n' "$*"; }
warn() { printf 'run_load_test.sh: WARNING: %s\n' "$*" >&2; }
die_usage() { printf 'run_load_test.sh: %s\n' "$*" >&2; exit 2; }
die_fail()  { printf 'run_load_test.sh: FAIL: %s\n' "$*" >&2; exit 1; }

# The raw arguments are kept so the dev-mode refusal can inspect exactly what the
# operator typed, including arguments this script would otherwise not use.
RAW_ARGS=("$@")

while [[ $# -gt 0 ]]; do
    case "$1" in
        --plan)        [[ $# -ge 2 ]] || die_usage "--plan needs a value";        PLAN="$2"; shift 2 ;;
        --plan=*)      PLAN="${1#*=}"; shift ;;
        --model)       [[ $# -ge 2 ]] || die_usage "--model needs a value";       MODEL="$2"; shift 2 ;;
        --model=*)     MODEL="${1#*=}"; shift ;;
        --rate)        [[ $# -ge 2 ]] || die_usage "--rate needs a value";        RATE="$2"; shift 2 ;;
        --rate=*)      RATE="${1#*=}"; shift ;;
        --duration)    [[ $# -ge 2 ]] || die_usage "--duration needs a value";    DURATION="$2"; shift 2 ;;
        --duration=*)  DURATION="${1#*=}"; shift ;;
        --runs)        [[ $# -ge 2 ]] || die_usage "--runs needs a value";        RUNS="$2"; shift 2 ;;
        --runs=*)      RUNS="${1#*=}"; shift ;;
        --host)        [[ $# -ge 2 ]] || die_usage "--host needs a value";        HOST="$2"; shift 2 ;;
        --host=*)      HOST="${1#*=}"; shift ;;
        --port)        [[ $# -ge 2 ]] || die_usage "--port needs a value";        PORT="$2"; shift 2 ;;
        --port=*)      PORT="${1#*=}"; shift ;;
        --search-rate) [[ $# -ge 2 ]] || die_usage "--search-rate needs a value"; SEARCH_RATE="$2"; shift 2 ;;
        --search-rate=*) SEARCH_RATE="${1#*=}"; shift ;;
        --jmeter-home) [[ $# -ge 2 ]] || die_usage "--jmeter-home needs a value"; JMETER_HOME_ARG="$2"; shift 2 ;;
        --jmeter-home=*) JMETER_HOME_ARG="${1#*=}"; shift ;;
        --out-root)    [[ $# -ge 2 ]] || die_usage "--out-root needs a value";    OUT_ROOT_ARG="$2"; shift 2 ;;
        --out-root=*)  OUT_ROOT_ARG="${1#*=}"; shift ;;
        --dev)         DEV=1; shift ;;
        --yes|-y)      ASSUME_YES=1; shift ;;
        -h|--help)     usage; exit 0 ;;
        *) usage >&2; die_usage "unknown argument: $1" ;;
    esac
done

# ---------------------------------------------------------------------------
# Validation. Nothing below this point has touched the filesystem or the
# service, so --help and a bad argument set are both harmless.
# ---------------------------------------------------------------------------
[[ -n "$PLAN" ]]     || die_usage "--plan is required (load_post_tickets|mixed_load|stress_ramp)"
[[ -n "$MODEL" ]]    || die_usage "--model is required (an Ollama tag, e.g. llama3.2:1b)"
[[ -n "$RATE" ]]     || die_usage "--rate is required (requests per minute)"
[[ -n "$DURATION" ]] || die_usage "--duration is required (seconds)"

case "$PLAN" in
    load_post_tickets|mixed_load|stress_ramp) : ;;
    *) die_usage "--plan must be load_post_tickets, mixed_load or stress_ramp (got '$PLAN')" ;;
esac
[[ "$RATE" =~ ^[0-9]+$ && "$RATE" -ge 1 ]]         || die_usage "--rate must be a positive integer (got '$RATE')"
[[ "$DURATION" =~ ^[0-9]+$ && "$DURATION" -ge 1 ]] || die_usage "--duration must be a positive integer (got '$DURATION')"
[[ "$RUNS" =~ ^[0-9]+$ && "$RUNS" -ge 1 ]]         || die_usage "--runs must be a positive integer (got '$RUNS')"
[[ "$PORT" =~ ^[0-9]+$ ]]                          || die_usage "--port must be a number (got '$PORT')"
if [[ -n "$SEARCH_RATE" ]]; then
    [[ "$SEARCH_RATE" =~ ^[0-9]+$ && "$SEARCH_RATE" -ge 1 ]] || die_usage "--search-rate must be a positive integer"
    [[ "$PLAN" == "mixed_load" ]] || warn "--search-rate is only used by mixed_load; ignoring it for plan '$PLAN'."
fi

# --- dev mode may not so much as name real data ---------------------------
if (( DEV )); then
    for raw in ${RAW_ARGS+"${RAW_ARGS[@]}"}; do
        case "$raw" in
            *team_rows.csv*|*golden/*|*golden_set*)
                die_usage "refusing: --dev was given together with '$raw', which names real team data. Dev mode exists so that no model sees a team row or a golden-set row before the freeze."
                ;;
        esac
    done
fi

# --- tools ----------------------------------------------------------------
PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
    PYTHON_BIN="$(command -v python3 || true)"
    [[ -n "$PYTHON_BIN" ]] || die_usage "neither .venv/bin/python nor python3 is available"
fi
command -v curl >/dev/null 2>&1 || die_usage "curl is not installed (needed for /health and the warm-up POST)"

JMETER_BIN=""
if [[ -n "$JMETER_HOME_ARG" ]]; then
    if [[ -x "${JMETER_HOME_ARG}/bin/jmeter" ]]; then
        JMETER_BIN="${JMETER_HOME_ARG}/bin/jmeter"
    elif [[ -x "$JMETER_HOME_ARG" ]]; then
        JMETER_BIN="$JMETER_HOME_ARG"
    else
        die_usage "--jmeter-home '$JMETER_HOME_ARG' does not contain bin/jmeter"
    fi
elif command -v jmeter >/dev/null 2>&1; then
    JMETER_BIN="$(command -v jmeter)"
elif [[ -n "${JMETER_HOME:-}" && -x "${JMETER_HOME}/bin/jmeter" ]]; then
    JMETER_BIN="${JMETER_HOME}/bin/jmeter"
else
    die_usage "JMeter not found. Install Apache JMeter 5.6+ and either put jmeter on PATH or pass --jmeter-home /path/to/apache-jmeter-5.6.3."
fi

if [[ -n "$SERVICE_SSH" ]]; then
    command -v ssh   >/dev/null 2>&1 || die_usage "ssh not found (needed because SERVICE_SSH is set)"
    command -v rsync >/dev/null 2>&1 || die_usage "rsync not found (needed to mirror the service host's logs/service)"
else
    command -v docker >/dev/null 2>&1 || die_usage "docker not found. The model switch recreates the triage container; run this on the service host, set SERVICE_SSH=user@service-host, or set DOCKER_HOST (e.g. ssh://user@service-host)."
fi

# --- paths ----------------------------------------------------------------
PLAN_FILE="${REPO_ROOT}/jmeter/${PLAN}.jmx"
[[ -f "$PLAN_FILE" ]] || die_usage "missing plan file $PLAN_FILE"
RESET_SCRIPT="${REPO_ROOT}/scripts/reset.sh"
[[ -x "$RESET_SCRIPT" ]] || die_usage "missing or non-executable $RESET_SCRIPT (each run must start from an empty database)"
[[ -f "$COMPOSE_FILE" ]] || die_usage "missing compose file $COMPOSE_FILE (set COMPOSE_FILE if it lives elsewhere)"

if (( DEV )); then
    INPUT_CSV="${REPO_ROOT}/${DEV_CSV_REL}"
    INPUT_CSV_REL="$DEV_CSV_REL"
    MODE="dev"
else
    INPUT_CSV="${REPO_ROOT}/${TEAM_ROWS_REL}"
    INPUT_CSV_REL="$TEAM_ROWS_REL"
    MODE="real"
fi
[[ -f "$INPUT_CSV" ]] || die_usage "missing input CSV $INPUT_CSV"

# The warm-up always uses the hand-written dev tickets, even in a real run: the
# warm-up is not a measured sample, and there is no reason to spend a team row
# (or a golden row) on it.
WARMUP_CSV="${REPO_ROOT}/${DEV_CSV_REL}"
[[ -f "$WARMUP_CSV" ]] || die_usage "missing $WARMUP_CSV (used for the warm-up request)"

SEARCH_TERMS_FILE="${REPO_ROOT}/${SEARCH_TERMS_REL}"
if [[ "$PLAN" == "mixed_load" && ! -f "$SEARCH_TERMS_FILE" ]]; then
    die_usage "plan mixed_load needs $SEARCH_TERMS_FILE (one search term per line)"
fi

if [[ -n "$OUT_ROOT_ARG" ]]; then
    case "$OUT_ROOT_ARG" in
        /*) OUT_ROOT="$OUT_ROOT_ARG" ;;
        *)  OUT_ROOT="${REPO_ROOT}/${OUT_ROOT_ARG}" ;;
    esac
elif (( DEV )); then
    OUT_ROOT="${REPO_ROOT}/results/dev/runs"
else
    OUT_ROOT="${REPO_ROOT}/results/runs"
fi

if (( DEV )); then
    # results/dev/ is gitignored precisely so a rehearsal can never be cited.
    case "$OUT_ROOT" in
        "${REPO_ROOT}/results/dev"|"${REPO_ROOT}/results/dev/"*) : ;;
        *) die_usage "refusing: --dev may only write under ${REPO_ROOT}/results/dev (got $OUT_ROOT)" ;;
    esac
fi

if [[ -n "$SERVICE_SSH" ]]; then
    # Remote mode: SERVICE_LOG_DIR is a local mirror that rsync fills.
    mkdir -p "$SERVICE_LOG_DIR"
elif [[ ! -d "$SERVICE_LOG_DIR" ]]; then
    die_usage "service log directory $SERVICE_LOG_DIR does not exist. The run directory must contain the service's own record of every request. Run this on the service host, set SERVICE_SSH so the log is mirrored, or mount/sync its ./logs/service and set SERVICE_LOG_DIR."
fi

# The model tag, made safe for a directory name. This mirrors
# analysis/common.sanitise_model_tag() exactly (same character class, same
# collapsing of runs, same trimming); it is repeated in shell so that the load
# generator needs no Python packages installed.
MODEL_SAFE="$(printf '%s' "$MODEL" | sed -e 's/[^A-Za-z0-9._-]\{1,\}/-/g' -e 's/^-*//' -e 's/-*$//')"
[[ -n "$MODEL_SAFE" ]] || die_usage "--model '$MODEL' contains no usable characters for a directory name"

# <rate> in the directory name: 'ramp' for the stepped stress plan, whose rate
# changes during the run and so cannot be labelled with one number.
if [[ "$PLAN" == "stress_ramp" ]]; then
    RATE_LABEL="ramp"
else
    RATE_LABEL="${RATE}pm"
fi

SERVICE_URL="http://${HOST}:${PORT}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# remote <command words...> -- run one command inside the service host's checkout.
# Each word is quoted locally, so narratives, tags and paths survive the remote
# shell unchanged.
remote() {
    ssh -o BatchMode=yes -o ConnectTimeout=15 "$SERVICE_SSH" \
        "cd $(printf '%q' "$SERVICE_REPO") && $(printf '%q ' "$@")"
}

compose() {
    if [[ -n "$SERVICE_SSH" ]]; then
        # The compose file is the service host's own copy, so ./logs/service and
        # the build context resolve on that machine, not on this one.
        local -a remote_cmd=(env "MODEL_TAG=${MODEL_TAG:-}" docker compose -f docker-compose.yml)
        if [[ -n "${COMPOSE_PROJECT_NAME:-}" ]]; then
            remote_cmd+=(-p "$COMPOSE_PROJECT_NAME")
        fi
        remote "${remote_cmd[@]}" "$@"
        return
    fi
    local -a cmd=(docker compose -f "$COMPOSE_FILE")
    if [[ -n "${COMPOSE_PROJECT_NAME:-}" ]]; then
        cmd+=(-p "$COMPOSE_PROJECT_NAME")
    fi
    "${cmd[@]}" "$@"
}

# reset_service -- empty the database and bring triage back up on MODEL_TAG.
reset_service() {
    if [[ -n "$SERVICE_SSH" ]]; then
        remote env "MODEL_TAG=${MODEL_TAG:-}" scripts/reset.sh --yes
    else
        "$RESET_SCRIPT" --yes
    fi
}

# sync_service_logs -- in remote mode, mirror the service host's logs/service into
# SERVICE_LOG_DIR. Never deletes anything on either side: the logs are evidence.
sync_service_logs() {
    [[ -n "$SERVICE_SSH" ]] || return 0
    rsync -a -e "ssh -o BatchMode=yes -o ConnectTimeout=15" \
        "${SERVICE_SSH}:${SERVICE_REPO%/}/logs/service/" "${SERVICE_LOG_DIR%/}/"
}

# wait_for_log_line <request id> -- in remote mode, re-sync until the line has
# arrived (the service writes it as the response is sent, so it can trail).
wait_for_log_line() {
    [[ -n "$SERVICE_SSH" ]] || return 0
    local attempt
    for attempt in 1 2 3 4 5 6 7 8 9 10; do
        sync_service_logs || true
        if grep -qs -- "$1" "${SERVICE_LOG_DIR%/}"/*.jsonl; then
            return 0
        fi
        sleep 2
    done
    return 1
}

now_iso_ms() {
    # Millisecond ISO-8601 in UTC, matching the service's own 'ts' format.
    # Done in Python because date(1)'s %3N is GNU-only and a teammate's load
    # generator may be a Mac.
    "$PYTHON_BIN" -c 'import datetime as d; n = d.datetime.now(d.timezone.utc); print(n.strftime("%Y-%m-%dT%H:%M:%S.") + f"{n.microsecond // 1000:03d}Z")'
}

new_uuid() { "$PYTHON_BIN" -c 'import uuid; print(uuid.uuid4())'; }

# check_health <health json file> <expected model tag> [verbose]
# Exit 0 when the service is serving the model we asked for and can reach Ollama.
check_health() {
    "$PYTHON_BIN" - "$1" "$2" "${3:-quiet}" <<'PY_HEALTH_CHECK'
"""Is the service ready to be measured with the model we asked for?

Checks configuration only. It never reports a timing: readiness is a
configuration fact, and latency is the measurement itself.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

path, wanted, verbosity = sys.argv[1], sys.argv[2], sys.argv[3]
verbose = verbosity == "verbose"

def complain(message: str) -> None:
    if verbose:
        print(f"  {message}", file=sys.stderr)

try:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    complain(f"/health did not return usable JSON: {exc}")
    raise SystemExit(1)

served = payload.get("model_tag")
if served != wanted:
    complain(f"/health reports model_tag={served!r}, waiting for {wanted!r}")
    raise SystemExit(1)
if not payload.get("ollama_reachable"):
    complain(
        f"/health reports ollama_reachable=false "
        f"(base url {payload.get('ollama_base_url')!r})"
    )
    raise SystemExit(1)
if payload.get("status") != "ok":
    complain(f"/health reports status={payload.get('status')!r}")
    raise SystemExit(1)
PY_HEALTH_CHECK
}

# fetch_health <out file> -- HTTP status on stdout, body written to the file.
fetch_health() {
    local out="$1" code
    code="$(curl -sS -o "$out" -w '%{http_code}' --max-time 15 "${SERVICE_URL}/health" 2>/dev/null || true)"
    printf '%s' "${code:-000}"
}

# wait_for_health <model> <health json file>
wait_for_health() {
    local model="$1" health_file="$2"
    local deadline=$(( $(date +%s) + HEALTH_TIMEOUT_S )) code
    while [[ $(date +%s) -lt $deadline ]]; do
        code="$(fetch_health "$health_file")"
        if [[ "$code" == "200" ]] && check_health "$health_file" "$model"; then
            return 0
        fi
        sleep 2
    done
    printf 'run_load_test.sh: /health did not report model %s within %ss.\n' \
        "$model" "$HEALTH_TIMEOUT_S" >&2
    code="$(fetch_health "$health_file")"
    printf '  last HTTP status: %s\n' "$code" >&2
    if [[ -s "$health_file" ]]; then
        printf '  last body: %s\n' "$(head -c 800 "$health_file")" >&2
    fi
    check_health "$health_file" "$model" verbose || true
    return 1
}

# write_warmup_body <csv> <out json file> -- prints the source row number.
write_warmup_body() {
    "$PYTHON_BIN" - "$1" "$2" <<'PY_WARMUP_BODY'
"""Build the warm-up request body from the FIRST data row of a tickets CSV.

Python rather than awk/cut because a narrative contains commas, quotes and
newlines, and because the JSON body has to be escaped correctly.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

csv.field_size_limit(10 ** 9)

source, out_path = Path(sys.argv[1]), Path(sys.argv[2])
with source.open(newline="", encoding="utf-8") as handle:
    reader = csv.DictReader(handle)
    expected = ["row_number", "narrative", "raw_label"]
    if list(reader.fieldnames or []) != expected:
        print(f"  {source} has columns {reader.fieldnames}; expected {expected}",
              file=sys.stderr)
        raise SystemExit(2)
    row = next(reader, None)
if row is None:
    print(f"  {source} has no data rows", file=sys.stderr)
    raise SystemExit(2)

out_path.write_text(
    json.dumps({"narrative": row["narrative"]}, ensure_ascii=False), encoding="utf-8"
)
print(row["row_number"])
PY_WARMUP_BODY
}

# collect_warmup_log <log dir> <request id> <out jsonl>
collect_warmup_log() {
    SERVICE_LOG_DIR="$1" "$PYTHON_BIN" - "$2" "$3" <<'PY_WARMUP_LOG'
"""Copy the warm-up request's log line(s) out of the service log.

The warm-up pays the model-load cost, so its line must be kept (it is evidence
that the cost was paid before measurement) and must be kept OUT of
service.jsonl, where analysis would otherwise let it dominate p99.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

request_id, out_path = sys.argv[1], Path(sys.argv[2])
log_dir = Path(os.environ["SERVICE_LOG_DIR"])

found: list[dict] = []
for _ in range(25):                       # the write can trail the response
    found = []
    for path in sorted(log_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or request_id not in line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("request_id") == request_id:
                found.append(record)
    if found:
        break
    time.sleep(0.4)

with out_path.open("w", encoding="utf-8") as handle:
    for record in found:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")

if not found:
    print(f"  no log line found for warm-up request {request_id} in {log_dir}",
          file=sys.stderr)
    raise SystemExit(1)
if not any(record.get("warmup") for record in found):
    print(f"  the warm-up log line for {request_id} does not carry warmup=true; "
          f"analysis would treat it as a measured sample", file=sys.stderr)
    raise SystemExit(1)
print(f"      warm-up log line captured ({len(found)} line(s), warmup=true)")
PY_WARMUP_LOG
}

# slice_service_log <log dir> <start iso> <end iso> <margin s> <service.jsonl> <warmup.jsonl>
slice_service_log() {
    SERVICE_LOG_DIR="$1" "$PYTHON_BIN" - "$2" "$3" "$4" "$5" "$6" <<'PY_SLICE'
"""Copy the service log lines of the measured window into the run directory.

Timestamp comparison is done here rather than in awk because 'ts' is an ISO-8601
string with a millisecond fraction and a Z suffix: comparing those correctly
means parsing them, and a string comparison would silently mis-handle a run that
crosses midnight into a second log file.

Warm-up lines are appended to warmup.jsonl instead of service.jsonl, so that
service.jsonl holds exactly the measured samples.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

start_s, end_s, margin_s, out_measured, out_warmup = sys.argv[1:6]
log_dir = Path(os.environ["SERVICE_LOG_DIR"])


def parse(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


margin = timedelta(seconds=int(margin_s))
window_start = parse(start_s) - margin
window_end = parse(end_s) + margin

measured: list[tuple[str, dict]] = []
warmup: list[tuple[str, dict]] = []
problems: list[str] = []

for path in sorted(log_dir.glob("*.jsonl")):
    for lineno, raw in enumerate(
        path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
    ):
        raw = raw.strip()
        if not raw:
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            problems.append(f"{path.name}:{lineno}: not valid JSON ({exc})")
            continue
        ts = record.get("ts")
        if not isinstance(ts, str):
            problems.append(f"{path.name}:{lineno}: no string 'ts'")
            continue
        try:
            moment = parse(ts)
        except ValueError:
            problems.append(f"{path.name}:{lineno}: ts {ts!r} is not ISO-8601 UTC ms")
            continue
        if not (window_start <= moment <= window_end):
            continue
        (warmup if record.get("warmup") else measured).append((ts, record))

measured.sort(key=lambda item: item[0])
warmup.sort(key=lambda item: item[0])

with Path(out_measured).open("w", encoding="utf-8") as handle:
    for _, record in measured:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")

# Append, rather than overwrite: the warm-up request's own line was already
# collected into this file before the window opened. Anything already recorded
# there is skipped so the file cannot end up holding the same request twice.
already = set()
warmup_path = Path(out_warmup)
if warmup_path.is_file():
    for line in warmup_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            already.add(json.loads(line).get("request_id"))
        except json.JSONDecodeError:
            continue

appended = 0
with warmup_path.open("a", encoding="utf-8") as handle:
    for _, record in warmup:
        if record.get("request_id") in already:
            continue
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        appended += 1

for problem in problems:
    print(f"      service log: {problem}", file=sys.stderr)
print(f"      service.jsonl: {len(measured)} measured line(s); "
      f"warmup.jsonl: +{appended} warm-up line(s) added "
      f"({len(warmup)} found in window)")
if not measured:
    raise SystemExit(1)
PY_SLICE
}

# write_metadata <out file> -- reads META_* from the environment.
write_metadata() {
    "$PYTHON_BIN" - "$1" <<'PY_METADATA'
"""Write metadata.json with exactly the keys the repository contract lists.

Every value is either something the operator asked for, something the service
reported about itself (/health, or its own log lines), or a fact about this
machine. Nothing here is estimated, and nothing is derived from the results --
if a value is unknown it is written as null rather than guessed, because a
metadata field that might be a guess makes the whole run undefendable.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

out_path = Path(sys.argv[1])
env = os.environ


def text(name: str) -> str | None:
    value = env.get(name, "")
    return value if value != "" else None


def number(name: str) -> int | None:
    value = env.get(name, "")
    return int(value) if value.isdigit() else None


def read_json(name: str) -> dict:
    path = env.get(name, "")
    if not path or not Path(path).is_file():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def git(*args: str) -> str | None:
    proc = subprocess.run(
        ["git", "-C", env["META_REPO"], *args], capture_output=True, text=True, check=False
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def sole_seed(path_name: str):
    """The one seed value the service logged during the window, else None.

    /health does not report the seed, but every log line does, so the value is
    taken from the service's own record rather than from our assumption about
    the .env file.
    """
    path = env.get(path_name, "")
    if not path or not Path(path).is_file():
        return None
    seeds = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            seeds.add(json.loads(line).get("seed"))
        except json.JSONDecodeError:
            continue
    return seeds.pop() if len(seeds) == 1 else None


health = read_json("META_HEALTH_JSON")
commit = git("rev-parse", "HEAD")
dirty = None
if commit is not None:
    dirty = bool(git("status", "--porcelain"))

uname = os.uname()
metadata = {
    "run_id": text("META_RUN_ID"),
    "mode": text("META_MODE"),
    "plan": text("META_PLAN"),
    "plan_file": text("META_PLAN_FILE"),
    "model_tag": text("META_MODEL_TAG"),
    "model_digest": health.get("model_digest"),
    "rate_per_min": number("META_RATE"),
    "duration_s": number("META_DURATION"),
    "run_index": number("META_RUN_INDEX"),
    "runs_total": number("META_RUNS_TOTAL"),
    "started_at_utc": text("META_STARTED"),
    "ended_at_utc": text("META_ENDED"),
    "git_commit": commit,
    "git_dirty": dirty,
    "freeze_commit": text("META_FREEZE_COMMIT"),
    "freeze_tag": text("META_FREEZE_TAG"),
    "prompt_hash": health.get("prompt_hash"),
    "num_ctx": health.get("num_ctx"),
    "seed": sole_seed("META_SERVICE_JSONL"),
    "input_csv": text("META_INPUT_CSV"),
    "service_url": text("META_SERVICE_URL"),
    "service_host_info": {
        "target_url": text("META_SERVICE_URL"),
        "ollama_base_url": health.get("ollama_base_url"),
        "db_path": health.get("db_path"),
        "uvicorn_workers": health.get("uvicorn_workers"),
        "threadpool_size": health.get("threadpool_size"),
        "note": "hardware is recorded by scripts/capture_env.sh on the service host",
    },
    "load_generator_host_info": {
        "hostname": socket.gethostname(),
        "platform": f"{uname.sysname} {uname.release} {uname.machine}",
        "note": "hardware is recorded by scripts/capture_env.sh --role loadgen",
    },
    "jmeter_version": text("META_JMETER_VERSION"),
    "ollama_num_parallel": env.get("OLLAMA_NUM_PARALLEL", "default"),
    "ollama_max_loaded_models": env.get("OLLAMA_MAX_LOADED_MODELS", "default"),
    "warmup_request_id": text("META_WARMUP_REQUEST_ID"),
    "notes": env.get("META_NOTES", ""),
}

out_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
PY_METADATA
}

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
if (( DEV )); then
    log "$DEV_BANNER"
    log ""
fi

case "$HOST" in
    127.0.0.1|localhost|::1|0.0.0.0)
        if (( ! DEV )); then
            warn "the service is being addressed at '$HOST', which means the load generator is on the same machine as the system under test. The brief does not accept latency measured that way: a co-hosted generator steals CPU from the service. Pass --host <service machine>."
        fi
        ;;
esac

JMETER_VERSION="$("$JMETER_BIN" --version 2>&1 | grep -Eo '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -n 1 || true)"
[[ -n "$JMETER_VERSION" ]] || JMETER_VERSION="unknown"

log "Plan          : $PLAN  ($PLAN_FILE)"
log "Model         : $MODEL"
log "Arrival rate  : ${RATE}/min$( [[ "$PLAN" == "stress_ramp" ]] && printf ' (first ramp step)' )"
log "Duration      : ${DURATION}s per run"
log "Runs          : $RUNS"
log "Service       : $SERVICE_URL"
log "Input CSV     : $INPUT_CSV_REL"
log "Mode          : $MODE"
log "Output root   : $OUT_ROOT"
log "JMeter        : $JMETER_BIN (version $JMETER_VERSION)"
log "Service log   : $SERVICE_LOG_DIR"

if [[ -n "$SERVICE_SSH" ]]; then
    log "Service host  : $SERVICE_SSH (checkout $SERVICE_REPO; compose and reset run there)"
    REMOTE_HEAD="$(remote git rev-parse HEAD 2>/dev/null || true)"
    [[ -n "$REMOTE_HEAD" ]] || die_usage "cannot run git in $SERVICE_REPO on $SERVICE_SSH (check ssh access and SERVICE_REPO)"
    LOCAL_HEAD="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || true)"
    if [[ "$REMOTE_HEAD" != "$LOCAL_HEAD" ]]; then
        # metadata.json records THIS checkout's commit, so the service host must
        # be running the same code or the record would be wrong.
        if (( DEV )); then
            warn "service host checkout is at ${REMOTE_HEAD:0:12}, this checkout at ${LOCAL_HEAD:0:12}"
        else
            die_usage "service host checkout is at ${REMOTE_HEAD:0:12} but this checkout is at ${LOCAL_HEAD:0:12}. Push, then 'git pull' on the service host and rebuild (docker compose build triage) before measuring."
        fi
    fi
fi

if (( ! ASSUME_YES )); then
    log ""
    log "Each run calls scripts/reset.sh --yes, which DESTROYS every ticket stored in"
    log "the service's database, then recreates the triage container with"
    log "MODEL_TAG=$MODEL."
    if [[ ! -t 0 ]]; then
        die_usage "not an interactive terminal and --yes was not given; refusing to reset the service without confirmation"
    fi
    printf 'Proceed with %d run(s)? [y/N] ' "$RUNS"
    read -r reply
    case "$reply" in
        y|Y|yes|YES) : ;;
        *) log "Aborted; nothing was changed."; exit 0 ;;
    esac
fi

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/run_load_test.XXXXXX")"
cleanup() { rm -rf "$WORK_DIR"; }
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Step 1: the freeze gate (once per invocation; its verdict is copied per run)
# ---------------------------------------------------------------------------
step "Step 1: freeze gate"
FREEZE_JSON="${WORK_DIR}/freeze.json"
FREEZE_COMMIT=""
FREEZE_TAG=""
if (( DEV )); then
    cat > "$FREEZE_JSON" <<'DEV_FREEZE_JSON'
{
  "ok": false,
  "mode": "dev",
  "enforced": false,
  "reasons": [
    "dev mode: the freeze gate was bypassed, so this run directory is a rehearsal and not evidence. It must never be cited."
  ]
}
DEV_FREEZE_JSON
    log "  bypassed (--dev). freeze_commit will be recorded as null."
else
    if ! "$PYTHON_BIN" "${REPO_ROOT}/scripts/freeze_gate.py" --json --repo "$REPO_ROOT" > "$FREEZE_JSON"; then
        # freeze_gate.py has already explained itself on stderr, in detail.
        exit 3
    fi
    FREEZE_COMMIT="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1]))["freeze_commit"])' "$FREEZE_JSON")"
    FREEZE_TAG="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1]))["freeze_tag"])' "$FREEZE_JSON")"
    log "  PASS: frozen at $FREEZE_COMMIT (tag '$FREEZE_TAG')"
    if [[ -n "$(git -C "$REPO_ROOT" status --porcelain 2>/dev/null || true)" ]]; then
        warn "the working tree has uncommitted changes. Results are traceable only to a commit; commit before measuring."
    fi
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FAILED_RUNS=()

# The stress plan's step rates are not visible in the .jtl, so the effective
# staircase is written into metadata.json for analysis/stress_summary.py
# (scripts/run_analysis.sh reads it back). Defaults are the plan's own:
# ramp_start_per_min falls back to --rate, the others to the .jmx defaults.
RAMP_NOTE=""
if [[ "$PLAN" == "stress_ramp" ]]; then
    RAMP_NOTE="ramp_start_per_min=${RAMP_START_PER_MIN:-$RATE}; ramp_step_per_min=${RAMP_STEP_PER_MIN:-30}; ramp_steps=6; ramp_step_duration_s=${RAMP_STEP_DURATION_S:-120}; "
fi

# ---------------------------------------------------------------------------
# Steps 2-6, once per run
# ---------------------------------------------------------------------------
for (( RUN_INDEX = 1; RUN_INDEX <= RUNS; RUN_INDEX++ )); do
    RUN_ID="${STAMP}_${MODEL_SAFE}_${PLAN}_${RATE_LABEL}_run${RUN_INDEX}"
    RUN_DIR="${OUT_ROOT}/${RUN_ID}"
    step "Run ${RUN_INDEX} of ${RUNS}: ${RUN_ID}"
    mkdir -p "$RUN_DIR"
    cp "$FREEZE_JSON" "${RUN_DIR}/freeze.json"
    RUN_NOTE_EXTRA=""

    # --- Step 2: reset the service and switch the model --------------------
    log "  [2/6] reset and switch model"
    # MODEL_TAG is exported BEFORE reset.sh runs, because reset.sh brings the
    # triage container back up itself: exporting first means it starts on the
    # model we asked for rather than on the compose file's default, and the
    # forced recreate below is then only a guarantee rather than a correction.
    export MODEL_TAG="$MODEL"
    reset_service
    # The backend is brought up but NOT force-recreated: recreating Ollama would
    # throw away an already-resident model for no benefit, and the warm-up below
    # pays the load cost deliberately.
    compose up -d "$OLLAMA_SERVICE"
    compose up -d --force-recreate --no-deps "$TRIAGE_SERVICE"

    HEALTH_FILE="${WORK_DIR}/health_run${RUN_INDEX}.json"
    if ! wait_for_health "$MODEL" "$HEALTH_FILE"; then
        die_fail "the service never reported model '$MODEL' with Ollama reachable. Nothing was measured. Check: compose logs $TRIAGE_SERVICE"
    fi
    log "      /health: model $MODEL, Ollama reachable"

    # --- Step 3: one warm-up request --------------------------------------
    log "  [3/6] warm-up request (excluded from analysis)"
    WARMUP_BODY="${WORK_DIR}/warmup_body_run${RUN_INDEX}.json"
    WARMUP_ROW="$(write_warmup_body "$WARMUP_CSV" "$WARMUP_BODY")" \
        || die_fail "could not build the warm-up request body from $WARMUP_CSV"
    WARMUP_REQUEST_ID="warmup-$(new_uuid)"
    WARMUP_RESPONSE="${WORK_DIR}/warmup_response_run${RUN_INDEX}.json"
    WARMUP_CODE="$(curl -sS -o "$WARMUP_RESPONSE" -w '%{http_code}' \
        --max-time "$WARMUP_TIMEOUT_S" \
        -X POST "${SERVICE_URL}/tickets" \
        -H 'Content-Type: application/json' \
        -H "X-Request-ID: ${WARMUP_REQUEST_ID}" \
        -H "X-Source-Row: ${WARMUP_ROW}" \
        -H 'X-Warmup: 1' \
        --data-binary "@${WARMUP_BODY}" 2>/dev/null || true)"
    WARMUP_CODE="${WARMUP_CODE:-000}"
    if [[ "$WARMUP_CODE" != "200" ]]; then
        die_fail "the warm-up POST returned HTTP ${WARMUP_CODE}. Measuring now would charge the first sample with the model-load cost. Response: $(head -c 400 "$WARMUP_RESPONSE" 2>/dev/null || true)"
    fi
    log "      warm-up request_id ${WARMUP_REQUEST_ID} (dev row ${WARMUP_ROW}), HTTP 200"
    wait_for_log_line "$WARMUP_REQUEST_ID" || warn "the warm-up log line has not reached the mirror in $SERVICE_LOG_DIR yet"
    if ! collect_warmup_log "$SERVICE_LOG_DIR" "$WARMUP_REQUEST_ID" "${RUN_DIR}/warmup.jsonl"; then
        die_fail "the warm-up request produced no usable log line; the service log is not readable at $SERVICE_LOG_DIR"
    fi
    # A short settle so the model-load work is finished and the window below
    # contains only measured traffic.
    sleep "$SETTLE_S"

    # --- Step 4: JMeter ----------------------------------------------------
    log "  [4/6] JMeter (non-GUI, open model arrivals)"
    JMETER_PROPS=(
        # These two sample variables become extra columns in the CSV .jtl, which
        # is what lets analysis/reconcile.py join JMeter's samples to the
        # service's own log lines by request_id.
        "-Jsample_variables=request_id,source_row"
        "-Jhost=${HOST}"
        "-Jport=${PORT}"
        "-Jrate_per_min=${RATE}"
        "-Jduration_s=${DURATION}"
        "-Jinput_csv=${INPUT_CSV}"
        "-Jsearch_terms_file=${SEARCH_TERMS_FILE}"
        "-Jdrain_s=${DRAIN_S}"
    )
    if [[ -n "$SEARCH_RATE" ]]; then
        JMETER_PROPS+=("-Jsearch_rate_per_min=${SEARCH_RATE}")
    fi
    # Ramp properties are passed only when the operator set them, so that the
    # plan's own documented defaults (and the step boundaries recorded in the
    # stress-test playbook) remain the single source of truth otherwise.
    if [[ "$PLAN" == "stress_ramp" ]]; then
        JMETER_PROPS+=("-Jramp_start_per_min=${RAMP_START_PER_MIN:-$RATE}")
        [[ -n "${RAMP_STEP_PER_MIN:-}" ]]      && JMETER_PROPS+=("-Jramp_step_per_min=${RAMP_STEP_PER_MIN}")
        [[ -n "${RAMP_STEPS:-}" ]]             && JMETER_PROPS+=("-Jramp_steps=${RAMP_STEPS}")
        [[ -n "${RAMP_STEP_DURATION_S:-}" ]]   && JMETER_PROPS+=("-Jramp_step_duration_s=${RAMP_STEP_DURATION_S}")
        JMETER_PROPS+=("-Jramp_drain_s=${DRAIN_S}")
    fi

    STARTED_AT="$(now_iso_ms)"
    set +e
    # -q jmeter/user.properties fixes the .jtl column set and turns off
    # HttpClient retries, so the file does not depend on this machine's JMeter
    # install (see jmeter/README.md).
    "$JMETER_BIN" -n \
        -q "${REPO_ROOT}/jmeter/user.properties" \
        -t "$PLAN_FILE" \
        -l "${RUN_DIR}/results.jtl" \
        -j "${RUN_DIR}/jmeter.log" \
        "${JMETER_PROPS[@]}" \
        > "${RUN_DIR}/jmeter_stdout.txt" 2>&1
    JMETER_STATUS=$?
    set -e
    ENDED_AT="$(now_iso_ms)"

    if [[ $JMETER_STATUS -ne 0 ]]; then
        warn "JMeter exited ${JMETER_STATUS} for ${RUN_ID}; see ${RUN_DIR}/jmeter_stdout.txt"
        RUN_NOTE_EXTRA="${RUN_NOTE_EXTRA}jmeter exit status ${JMETER_STATUS}; "
        FAILED_RUNS+=("$RUN_ID")
    fi

    # The .jtl must be CSV and must carry the two sample-variable columns, or the
    # run cannot be reconciled and is not evidence.
    if [[ -s "${RUN_DIR}/results.jtl" ]]; then
        # JMeter 5.6 writes the sample_variables column names quoted
        # ("request_id","source_row"); CSV readers strip the quotes, so this
        # check does too.
        JTL_HEADER="$(head -n 1 "${RUN_DIR}/results.jtl" | tr -d '"')"
        case "$JTL_HEADER" in
            timeStamp,*) : ;;
            *) warn "${RUN_ID}: results.jtl does not start with a CSV header ('${JTL_HEADER:0:40}'). Check jmeter.save.saveservice.output_format in jmeter.properties."
               RUN_NOTE_EXTRA="${RUN_NOTE_EXTRA}jtl not CSV; "
               FAILED_RUNS+=("$RUN_ID") ;;
        esac
        for column in request_id source_row; do
            case ",$JTL_HEADER," in
                *",$column,"*) : ;;
                *) warn "${RUN_ID}: results.jtl has no '$column' column, so analysis/reconcile.py cannot join it to the service log. Does the plan set the '$column' variable in a User Parameters pre-processor?"
                   RUN_NOTE_EXTRA="${RUN_NOTE_EXTRA}jtl missing $column column; "
                   FAILED_RUNS+=("$RUN_ID") ;;
            esac
        done
        JTL_SAMPLES=$(( $(wc -l < "${RUN_DIR}/results.jtl") - 1 ))
        log "      results.jtl: ${JTL_SAMPLES} sample line(s)"
    else
        warn "${RUN_ID}: results.jtl is empty. Nothing was measured."
        RUN_NOTE_EXTRA="${RUN_NOTE_EXTRA}empty jtl; "
        FAILED_RUNS+=("$RUN_ID")
    fi

    # --- Step 5: the service's own record of the same window --------------
    log "  [5/6] slice the service log into the run directory"
    if [[ -n "$SERVICE_SSH" ]]; then
        sleep 2
        sync_service_logs || warn "${RUN_ID}: rsync of the service host's logs/service failed"
    fi
    if ! slice_service_log "$SERVICE_LOG_DIR" "$STARTED_AT" "$ENDED_AT" "$SLICE_MARGIN_S" \
            "${RUN_DIR}/service.jsonl" "${RUN_DIR}/warmup.jsonl"; then
        warn "${RUN_ID}: no service log lines fall inside the measured window. Check SERVICE_LOG_DIR and that both machines' clocks are in sync (NTP)."
        RUN_NOTE_EXTRA="${RUN_NOTE_EXTRA}service log slice empty; "
        FAILED_RUNS+=("$RUN_ID")
    fi

    # --- Step 6: metadata -------------------------------------------------
    log "  [6/6] write metadata.json"
    META_RUN_ID="$RUN_ID" \
    META_MODE="$MODE" \
    META_PLAN="$PLAN" \
    META_PLAN_FILE="jmeter/${PLAN}.jmx" \
    META_MODEL_TAG="$MODEL" \
    META_RATE="$RATE" \
    META_DURATION="$DURATION" \
    META_RUN_INDEX="$RUN_INDEX" \
    META_RUNS_TOTAL="$RUNS" \
    META_STARTED="$STARTED_AT" \
    META_ENDED="$ENDED_AT" \
    META_FREEZE_COMMIT="$FREEZE_COMMIT" \
    META_FREEZE_TAG="$FREEZE_TAG" \
    META_INPUT_CSV="$INPUT_CSV_REL" \
    META_SERVICE_URL="$SERVICE_URL" \
    META_JMETER_VERSION="$JMETER_VERSION" \
    META_WARMUP_REQUEST_ID="$WARMUP_REQUEST_ID" \
    META_HEALTH_JSON="$HEALTH_FILE" \
    META_SERVICE_JSONL="${RUN_DIR}/service.jsonl" \
    META_REPO="$REPO_ROOT" \
    META_NOTES="${RUN_NOTES:+${RUN_NOTES}; }${RUN_NOTE_EXTRA}${RAMP_NOTE}drain_s=${DRAIN_S}; rate label=${RATE_LABEL}; warm-up excluded from service.jsonl; slice margin ${SLICE_MARGIN_S}s" \
        write_metadata "${RUN_DIR}/metadata.json"
    log "      ${RUN_DIR}/metadata.json"
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
step "Summary"
log "Wrote ${RUNS} run directory/ies under ${OUT_ROOT}"
if (( ${#FAILED_RUNS[@]} )); then
    # Deduplicate: one run can accumulate several complaints.
    printf 'run_load_test.sh: %d run(s) have incomplete or failed evidence:\n' \
        "$(printf '%s\n' "${FAILED_RUNS[@]}" | sort -u | wc -l)" >&2
    printf '%s\n' "${FAILED_RUNS[@]}" | sort -u | sed 's/^/  /' >&2
    printf 'Do not report a run that is listed above until you have explained it.\n' >&2
    exit 1
fi
log "Next: python analysis/reconcile.py --run-dir <run dir>   (prove .jtl and service log agree)"
log "      python analysis/summarise_load.py --runs ${OUT_ROOT}"
if (( DEV )); then
    log ""
    log "$DEV_BANNER"
fi
