#!/usr/bin/env bash
#
# run_load_test_a2.sh -- the Assignment 2 speed test: one configuration (a
#                        single model, or the cascade at Setting A or Setting
#                        B), three runs, and everything needed to defend the
#                        numbers afterwards.
#
# Owner: Part 1 -- Yeo Kai Yuan (technical core).
#
# The Assignment 2 counterpart of scripts/run_load_test.sh, which is Assignment 1
# evidence and is NOT edited. Same structure, same remote (SERVICE_SSH) mode,
# same rsync log mirroring, same log slicing and metadata, same dev-mode rules,
# same exit codes. What changes is what the A2 brief (Step 4, "Set-up" and
# "Each run") changes, and the procedure in docs/playbooks/cascade-test.md:
#
#   * the A2 gate (scripts/a2_gate.py, tag a2-predictions-freeze) instead of the
#     A1 freeze gate; its verdict goes into every run directory as gate.json;
#   * the arrival rate, run length, response timeout and trailing pause come
#     from S (docs/a2/arrival_rate.json), not from the A1 workload model;
#   * the fixed 100-ticket workload (data/speed_test_tickets_a2.csv, rows in
#     workload/speed_test_rows_a2.txt), each ticket sent at most once per run
#     (jmeter/speed_test_a2.jmx, recycle off);
#   * software versions, digests and Ollama settings are checked against the
#     recorded baseline before every configuration;
#   * every run restarts the Ollama container (clearing its prompt cache), sends
#     THREE fixed warm-up tickets, and for the cascade makes sure the large model
#     is loaded too and that `ollama ps` lists both models before measuring;
#   * GET /stats before and after the measured window.
#
# Order of operations (do not reorder: each step exists because the previous one
# would otherwise contaminate the measurement)
#   A. Gate.             Refuse to measure before the A2 prediction record,
#                        escalation rule and golden split are committed and
#                        tagged. Its JSON verdict becomes gate.json.
#   B. Environment.      Once per configuration, before run 1: the Ollama
#                        container's environment, the Ollama version, model
#                        digests, service settings and JMeter version are
#                        compared with docs/a2/env_baseline.json by
#                        scripts/a2_env_snapshot.py. A change stops the
#                        configuration before anything is measured.
#   C. Per run:
#       1. restart the Ollama container and wait until it answers;
#       2. reset the database and recreate triage in this configuration;
#       3. wait for /health to confirm the configuration (health.json);
#       4. three fixed warm-up tickets (warmup.jsonl), and for the cascade a
#          direct call to the large model if no warm-up ticket escalated;
#       5. residency: `ollama ps` must list every expected model, or the run is
#          not measured (real mode);
#       6. GET /stats (stats_before.json);
#       7. JMeter, non-GUI, open model (results.jtl);
#       8. GET /stats (stats_after.json);
#       9. slice the service log window (service.jsonl, warmup.jsonl);
#      10. residency after the run (ollama_ps_after.*);
#      11. metadata.json.
#
# Hard rules this script keeps (TODO_A2.md, "Guardrails"): it never changes an
# Ollama inference setting (OLLAMA_NUM_PARALLEL, OLLAMA_MAX_LOADED_MODELS,
# threads, context) -- it only records them; it caches nothing; it never reads a
# golden label; it only runs models pinned in models/models.yaml; it never
# touches service/prompt.py (the large-model warm-up imports its build_prompt()
# so that the warm-up prompt is the service's own).
#
# Usage:
#   scripts/run_load_test_a2.sh --config qwen2.5:7b [--runs 3] --host <service host> --yes
#   scripts/run_load_test_a2.sh --config cascade-A --small-model granite4:3b \
#        [--large-model qwen2.5:7b] --host <service host> --yes
#
# Exit codes: 0 all runs completed; 1 a run failed or its evidence is incomplete
#             (including: the environment changed, a model was not resident);
#             2 misuse (bad arguments, JMeter missing, dev-mode violation,
#             missing arrival file or environment baseline);
#             3 the A2 gate blocked the run.
#
set -euo pipefail

SCRIPT_NAME="run_load_test_a2.sh"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"

# --- defaults --------------------------------------------------------------
CONFIG=""
SMALL_MODEL=""
LARGE_MODEL="qwen2.5:7b"
LARGE_MODEL_GIVEN=0
RUNS=3
HOST="127.0.0.1"
PORT="8000"
OLLAMA_PORT_ARG="${OLLAMA_PORT:-11434}"
ARRIVAL_FILE_ARG="docs/a2/arrival_rate.json"
ENV_BASELINE_ARG="docs/a2/env_baseline.json"
RATE=""
DURATION=""
TIMEOUT_MS=""
PAUSE_S=""
JMETER_HOME_ARG=""
OUT_ROOT_ARG=""
DEV=0
ASSUME_YES=0

PLAN_NAME="speed_a2"
PLAN_REL="jmeter/speed_test_a2.jmx"
DEV_CSV_REL="data/dev/synthetic_tickets.csv"
A2_CSV_REL="data/speed_test_tickets_a2.csv"
TICKET_LIST_REL="workload/speed_test_rows_a2.txt"
MODELS_YAML_REL="models/models.yaml"
WARMUP_COUNT=3
DEV_BANNER='*** DEV MODE — synthetic tickets only. Results are NOT evidence. ***'

# Brief, Step 4: response timeout 10 x S and at least 5 minutes; trailing pause
# longer than the timeout by at least one minute; run length S minutes, at least 5.
MIN_TIMEOUT_MS=300000
MIN_PAUSE_MARGIN_S=60
MIN_DURATION_S=300

# --- environment overrides (documented in usage) ---------------------------
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
RUN_NOTES="${RUN_NOTES:-}"

usage() {
    cat <<'USAGE'
run_load_test_a2.sh -- one Assignment 2 speed-test configuration, three runs, with its evidence.

Usage:
  scripts/run_load_test_a2.sh --config CONFIG [--small-model TAG] [--large-model TAG]
                              [--runs 3] [--host HOST] [--port PORT] [--ollama-port PORT]
                              [--arrival-file docs/a2/arrival_rate.json]
                              [--env-baseline docs/a2/env_baseline.json]
                              [--rate N] [--duration S] [--timeout-ms MS] [--pause-s S]
                              [--jmeter-home PATH] [--out-root results/runs] [--dev] [--yes]

Required:
  --config CONFIG    One of:
                       <model tag>   a single model alone, e.g. qwen2.5:7b. The triage
                                     container runs SERVICE_MODE=single, MODEL_TAG=<tag>.
                       cascade-A     the cascade at Setting A of cascade/escalation_rule.md
                       cascade-B     the cascade at Setting B
                     (cascade-a / cascade-b are accepted and recorded as cascade-A / -B.)
  --small-model TAG  Required for cascade-A/B: the cascade's small model
                     (CASCADE_SMALL_MODEL_TAG). Not allowed for a single model.

Optional:
  --large-model TAG  The cascade's large model (MODEL_TAG in cascade mode; default
                     qwen2.5:7b). Not allowed for a single model.
  --runs N           Repeats of the whole restart/reset/warm-up/measure cycle
                     (default 3; the brief requires three).
  --host HOST        Service host (default 127.0.0.1, which the brief does not accept
                     for a real run: the load generator must be a separate machine).
  --port PORT        Service port (default 8000).
  --ollama-port P    Ollama's published port on the service host (default
                     $OLLAMA_PORT or 11434). Ollama is reached at http://HOST:P for
                     the readiness check, `ollama ps` (/api/ps) and the large-model
                     warm-up.
  --arrival-file F   S and everything derived from it (default
                     docs/a2/arrival_rate.json; keys s_seconds, s_rows, s_timings_s,
                     rate_per_min, duration_s, response_timeout_ms, pause_s,
                     measured_at_utc, top_model_tag). Written by scripts/measure_s_a2.py.
  --rate N           Arrival rate per minute (may be a decimal with up to two places,
                     e.g. 13.04). Overrides the arrival file.
  --duration S       Arrivals last S seconds per run. Overrides the arrival file.
  --timeout-ms MS    HTTP response timeout. Overrides the arrival file.
  --pause-s S        Trailing pause after the last arrival. Overrides the arrival file.
                     In a real run the arrival file must exist unless all four of
                     --rate/--duration/--timeout-ms/--pause-s are given, and the
                     brief's rules are enforced: timeout >= max(10 x S, 5 min),
                     pause >= timeout + 1 min, duration >= max(S min, 5 min).
  --env-baseline F   The recorded environment (default docs/a2/env_baseline.json,
                     written once by `python scripts/a2_env_snapshot.py record ...`).
  --jmeter-home PATH JMeter installation directory (uses PATH otherwise).
  --out-root DIR     Where run directories are created (default results/runs).
  --dev              Rehearsal: bypasses the A2 gate, forces the input to
                     data/dev/synthetic_tickets.csv, writes only under
                     results/dev/runs, stamps mode=dev and gate_commit=null, and
                     only warns where a real run would stop. Refuses (exit 2) if any
                     argument names real team data.
  --yes              Do not ask for confirmation. Each run RESTARTS the Ollama
                     container and calls scripts/reset.sh --yes, which DESTROYS the
                     stored tickets.
  -h, --help         Print this help and exit.

Output, per run, in <out-root>/<UTCSTAMP>_<config>_speed_a2_<rate>pm_run<k>/ :
  metadata.json  gate.json  env_check.json  ollama_env.txt  health.json
  warmup.jsonl  [large_model_warmup.json]  ollama_ps_before.txt  ollama_ps_before.json
  stats_before.json  results.jtl  jmeter.log  jmeter_stdout.txt  stats_after.json
  service.jsonl  stats_calls.jsonl  ollama_ps_after.txt  ollama_ps_after.json
  <config> is the sanitised model tag, or cascade-A / cascade-B.

Environment variables (machine plumbing, as in scripts/run_load_test.sh):
  COMPOSE_FILE            docker compose file (default ./docker-compose.yml)
  COMPOSE_PROJECT_NAME    passed to docker compose as -p when set
  TRIAGE_SERVICE          compose service name of the web service (default triage)
  OLLAMA_SERVICE          compose service name of the model backend (default ollama)
  DOCKER_HOST             e.g. ssh://user@service-host, when the load generator is a
                          different machine from the service (the brief requires it)
  SERVICE_SSH             user@service-host. Remote mode: docker compose and
                          scripts/reset.sh run in the service host's own checkout over
                          ssh, with MODEL_TAG, SERVICE_MODE, CASCADE_SETTING and
                          CASCADE_SMALL_MODEL_TAG passed through, and its logs/service is
                          mirrored into SERVICE_LOG_DIR with rsync before every read.
                          The remote checkout must be at the same commit as this one.
  SERVICE_REPO            the service host's checkout (default ICT3113-PTO)
  SERVICE_LOG_DIR         where <date>.jsonl is readable (default logs/service)
  HEALTH_TIMEOUT_S        wait for Ollama after a restart, and for /health (default 240)
  WARMUP_TIMEOUT_S        curl timeout for each warm-up call (default 600)
  SLICE_MARGIN_S          widen the service-log slice at each end (default 5)
  SETTLE_S                pause between the warm-up and the measured window (default 5)
  RUN_NOTES               free text copied into metadata.json's notes field
USAGE
}

log()  { printf '%s\n' "$*"; }
step() { printf '\n== %s\n' "$*"; }
warn() { printf '%s: WARNING: %s\n' "$SCRIPT_NAME" "$*" >&2; }
die_usage() { printf '%s: %s\n' "$SCRIPT_NAME" "$*" >&2; exit 2; }
die_fail()  { printf '%s: FAIL: %s\n' "$SCRIPT_NAME" "$*" >&2; exit 1; }

# The raw arguments are kept so the dev-mode refusal can inspect exactly what the
# operator typed, including arguments this script would otherwise not use.
RAW_ARGS=("$@")

RATE_GIVEN=0; DURATION_GIVEN=0; TIMEOUT_GIVEN=0; PAUSE_GIVEN=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)        [[ $# -ge 2 ]] || die_usage "--config needs a value";        CONFIG="$2"; shift 2 ;;
        --config=*)      CONFIG="${1#*=}"; shift ;;
        --small-model)   [[ $# -ge 2 ]] || die_usage "--small-model needs a value";   SMALL_MODEL="$2"; shift 2 ;;
        --small-model=*) SMALL_MODEL="${1#*=}"; shift ;;
        --large-model)   [[ $# -ge 2 ]] || die_usage "--large-model needs a value";   LARGE_MODEL="$2"; LARGE_MODEL_GIVEN=1; shift 2 ;;
        --large-model=*) LARGE_MODEL="${1#*=}"; LARGE_MODEL_GIVEN=1; shift ;;
        --runs)          [[ $# -ge 2 ]] || die_usage "--runs needs a value";          RUNS="$2"; shift 2 ;;
        --runs=*)        RUNS="${1#*=}"; shift ;;
        --host)          [[ $# -ge 2 ]] || die_usage "--host needs a value";          HOST="$2"; shift 2 ;;
        --host=*)        HOST="${1#*=}"; shift ;;
        --port)          [[ $# -ge 2 ]] || die_usage "--port needs a value";          PORT="$2"; shift 2 ;;
        --port=*)        PORT="${1#*=}"; shift ;;
        --ollama-port)   [[ $# -ge 2 ]] || die_usage "--ollama-port needs a value";   OLLAMA_PORT_ARG="$2"; shift 2 ;;
        --ollama-port=*) OLLAMA_PORT_ARG="${1#*=}"; shift ;;
        --arrival-file)  [[ $# -ge 2 ]] || die_usage "--arrival-file needs a value";  ARRIVAL_FILE_ARG="$2"; shift 2 ;;
        --arrival-file=*) ARRIVAL_FILE_ARG="${1#*=}"; shift ;;
        --env-baseline)  [[ $# -ge 2 ]] || die_usage "--env-baseline needs a value";  ENV_BASELINE_ARG="$2"; shift 2 ;;
        --env-baseline=*) ENV_BASELINE_ARG="${1#*=}"; shift ;;
        --rate)          [[ $# -ge 2 ]] || die_usage "--rate needs a value";          RATE="$2"; RATE_GIVEN=1; shift 2 ;;
        --rate=*)        RATE="${1#*=}"; RATE_GIVEN=1; shift ;;
        --duration)      [[ $# -ge 2 ]] || die_usage "--duration needs a value";      DURATION="$2"; DURATION_GIVEN=1; shift 2 ;;
        --duration=*)    DURATION="${1#*=}"; DURATION_GIVEN=1; shift ;;
        --timeout-ms)    [[ $# -ge 2 ]] || die_usage "--timeout-ms needs a value";    TIMEOUT_MS="$2"; TIMEOUT_GIVEN=1; shift 2 ;;
        --timeout-ms=*)  TIMEOUT_MS="${1#*=}"; TIMEOUT_GIVEN=1; shift ;;
        --pause-s)       [[ $# -ge 2 ]] || die_usage "--pause-s needs a value";       PAUSE_S="$2"; PAUSE_GIVEN=1; shift 2 ;;
        --pause-s=*)     PAUSE_S="${1#*=}"; PAUSE_GIVEN=1; shift ;;
        --jmeter-home)   [[ $# -ge 2 ]] || die_usage "--jmeter-home needs a value";   JMETER_HOME_ARG="$2"; shift 2 ;;
        --jmeter-home=*) JMETER_HOME_ARG="${1#*=}"; shift ;;
        --out-root)      [[ $# -ge 2 ]] || die_usage "--out-root needs a value";      OUT_ROOT_ARG="$2"; shift 2 ;;
        --out-root=*)    OUT_ROOT_ARG="${1#*=}"; shift ;;
        --dev)           DEV=1; shift ;;
        --yes|-y)        ASSUME_YES=1; shift ;;
        -h|--help)       usage; exit 0 ;;
        *) usage >&2; die_usage "unknown argument: $1" ;;
    esac
done

# ---------------------------------------------------------------------------
# Validation. Nothing below this point touches the service or writes a file
# until the confirmation prompt, so --help and a bad argument set are harmless.
# ---------------------------------------------------------------------------
[[ -n "$CONFIG" ]] || die_usage "--config is required (a model tag, cascade-A or cascade-B)"

CONFIG_LOWER="$(printf '%s' "$CONFIG" | tr '[:upper:]' '[:lower:]')"
case "$CONFIG_LOWER" in
    cascade-a|cascade-b)
        WANT_MODE="cascade"
        WANT_SETTING="$(printf '%s' "${CONFIG_LOWER#cascade-}" | tr '[:lower:]' '[:upper:]')"
        CONFIG="cascade-${WANT_SETTING}"
        [[ -n "$SMALL_MODEL" ]] || die_usage "--config $CONFIG needs --small-model TAG (the cascade's small model)"
        [[ -n "$LARGE_MODEL" ]] || die_usage "--large-model must not be empty"
        [[ "$SMALL_MODEL" != "$LARGE_MODEL" ]] || die_usage "--small-model and --large-model are both '$SMALL_MODEL'; a cascade needs two different models"
        # In cascade mode MODEL_TAG is the LARGE model (docker-compose.yml).
        WANT_MODEL="$LARGE_MODEL"
        WANT_SMALL="$SMALL_MODEL"
        EXPECTED_MODELS=("$SMALL_MODEL" "$LARGE_MODEL")
        CONFIG_SAFE="$CONFIG"
        ;;
    cascade*)
        die_usage "unknown cascade configuration '$CONFIG': use cascade-A or cascade-B (the only two settings, TODO_A2.md shared interfaces)"
        ;;
    *)
        WANT_MODE="single"
        WANT_SETTING=""
        WANT_SMALL=""
        [[ -z "$SMALL_MODEL" ]] || die_usage "--small-model is only for cascade-A/cascade-B; --config '$CONFIG' is a single model"
        (( ! LARGE_MODEL_GIVEN )) || die_usage "--large-model is only for cascade-A/cascade-B; --config '$CONFIG' is a single model"
        WANT_MODEL="$CONFIG"
        EXPECTED_MODELS=("$CONFIG")
        # The model tag, made safe for a directory name. This mirrors
        # analysis/common.sanitise_model_tag() exactly, as in run_load_test.sh.
        CONFIG_SAFE="$(printf '%s' "$CONFIG" | sed -e 's/[^A-Za-z0-9._-]\{1,\}/-/g' -e 's/^-*//' -e 's/-*$//')"
        [[ -n "$CONFIG_SAFE" ]] || die_usage "--config '$CONFIG' contains no usable characters for a directory name"
        ;;
esac

[[ "$RUNS" =~ ^[0-9]+$ && "$RUNS" -ge 1 ]] || die_usage "--runs must be a positive integer (got '$RUNS')"
[[ "$PORT" =~ ^[0-9]+$ ]]                  || die_usage "--port must be a number (got '$PORT')"
[[ "$OLLAMA_PORT_ARG" =~ ^[0-9]+$ ]]       || die_usage "--ollama-port must be a number (got '$OLLAMA_PORT_ARG')"

# --- dev mode may not so much as name real data ---------------------------
if (( DEV )); then
    for raw in ${RAW_ARGS+"${RAW_ARGS[@]}"}; do
        case "$raw" in
            *team_rows.csv*|*golden/*|*golden_set*|*speed_test_tickets_a2*)
                die_usage "refusing: --dev was given together with '$raw', which names real team data. Dev mode exists so that no model sees a team row or a golden-set row before the A2 gate."
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
command -v curl >/dev/null 2>&1 || die_usage "curl is not installed (needed for /health, /stats, the warm-up POSTs and Ollama's /api/ps)"

# a2py <subcommand> [args...] -- the script's embedded Python helpers.
#
# One heredoc rather than one per helper, so that the whole of the script's
# Python is in one place and can be extracted and tested on its own. Standard
# library only, Python 3.8+: the load generator needs no packages installed
# (the large-model warm-up additionally imports service/prompt.py from this
# checkout, which is standard-library only too).
a2py() {
    "$PYTHON_BIN" - "$@" <<'PY_A2'
"""Embedded helpers for scripts/run_load_test_a2.sh.

Every helper reports configuration facts, copies evidence, or checks a rule.
None of them computes a latency or summarises a result: that is the analysis
scripts' job (analysis/reconcile.py, analysis/summarise_load_a2.py), kept apart
so that a result cannot be quietly re-shaped while it is being produced.
"""
from __future__ import annotations

import csv
import json
import math
import os
import socket
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

csv.field_size_limit(min(sys.maxsize, 10 ** 9))

TICKET_COLUMNS = ["row_number", "narrative", "raw_label"]


def err(message: str) -> None:
    print(f"  {message}", file=sys.stderr)


def read_json(path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_tickets(path) -> list:
    """Rows of a row_number,narrative,raw_label CSV. raw_label is never used."""
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if list(reader.fieldnames or []) != TICKET_COLUMNS:
            raise ValueError(
                f"{path} has columns {reader.fieldnames}; expected {TICKET_COLUMNS}"
            )
        return list(reader)


def read_row_list(path) -> list:
    """Row numbers from workload/speed_test_rows_a2.txt, in file order.

    Comment lines start with '#'; each other line is row_number[,more,...].
    """
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rows.append(line.split(",")[0].strip())
    return rows


def split_list(value: str) -> list:
    return [item.strip() for item in value.split(",") if item.strip()]


def norm_tag(tag: str) -> str:
    """Ollama lists an untagged model as name:latest."""
    tag = (tag or "").strip()
    return tag if ":" in tag or not tag else tag + ":latest"


# --- json-get FILE KEY --------------------------------------------------------
def cmd_json_get(args: list) -> int:
    """Print one value (dotted key) from a JSON file; '' for missing or null."""
    path, key = args
    try:
        value = read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        err(f"{path}: not readable JSON ({exc})")
        return 1
    for part in key.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    if value is None:
        print("")
    elif isinstance(value, bool):
        print("true" if value else "false")
    elif isinstance(value, (list, tuple)):
        print(",".join(str(item) for item in value))
    elif isinstance(value, dict):
        print(json.dumps(value, sort_keys=True))
    else:
        print(value)
    return 0


# --- rate-label RATE ----------------------------------------------------------
def rate_label(raw: str) -> str:
    """13.04 -> '13.04pm', 5.00 -> '5pm', 12.50 -> '12.5pm'.

    Must stay parseable by analysis/summarise_load.parse_rate() and match the
    <rate> group of analysis/common.RUN_DIR_RE ([^_]+).
    """
    text = f"{float(raw):.2f}".rstrip("0").rstrip(".")
    return f"{text}pm"


def cmd_rate_label(args: list) -> int:
    print(rate_label(args[0]))
    return 0


# --- expected RATE DURATION ---------------------------------------------------
def cmd_expected(args: list) -> int:
    """Expected arrivals per run, and the safe upper bound expected + 3 sqrt(expected)."""
    rate, duration = float(args[0]), float(args[1])
    expected = rate * duration / 60.0
    upper = expected + 3.0 * math.sqrt(expected)
    print(f"{expected:.1f} {upper:.1f}")
    return 0


# --- candidate-tags MODELS_YAML -----------------------------------------------
def cmd_candidate_tags(args: list) -> int:
    """The tags under `candidates:` in models/models.yaml (not `substitutes:`).

    A line-based reader, because the load generator has no PyYAML: the file's
    format note fixes the `  - tag: "..."` shape.
    """
    in_candidates = False
    tags = []
    for line in Path(args[0]).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line[:1].isspace():
            in_candidates = stripped == "candidates:"
            continue
        if in_candidates and stripped.startswith("- tag:"):
            tags.append(stripped[len("- tag:"):].strip().strip('"').strip("'"))
    for tag in tags:
        print(tag)
    return 0 if tags else 1


# --- workload-check MODE INPUT_CSV LIST_TXT WARMUP_CSV WARMUP_N S_ROWS ---------
def cmd_workload_check(args: list) -> int:
    """Check the fixed ticket list before anything is sent; print its size.

    Real mode: the JMeter input must be exactly the committed row list, in the
    same order, with no repeated ticket; the warm-up tickets must be neither
    workload tickets nor S tickets (a shared prompt would be answered from
    Ollama's cache). In dev mode the input IS the warm-up file, so the overlap
    is expected and only noted.
    """
    mode, input_csv, list_txt, warmup_csv, warmup_n, s_rows = args
    problems, notes = [], []
    try:
        rows = read_tickets(input_csv)
        warm_rows = read_tickets(warmup_csv)[: int(warmup_n)]
    except (OSError, ValueError, csv.Error) as exc:
        err(str(exc))
        return 2
    numbers = [row["row_number"].strip() for row in rows]
    if not numbers:
        problems.append(f"{input_csv} has no data rows")
    repeated = sorted(n for n, c in Counter(numbers).items() if c > 1)
    if repeated:
        problems.append(f"{input_csv} lists row(s) {repeated} more than once; a run would repeat a ticket")
    if list_txt:
        try:
            listed = read_row_list(list_txt)
        except OSError as exc:
            err(f"cannot read {list_txt}: {exc}")
            return 2
        if listed != numbers:
            first = next(
                (i for i, (a, b) in enumerate(zip(listed, numbers)) if a != b),
                min(len(listed), len(numbers)),
            )
            problems.append(
                f"{input_csv} ({len(numbers)} rows) does not match {list_txt} "
                f"({len(listed)} rows) row for row; first difference at position {first + 1}. "
                f"The committed list is the workload: regenerate the CSV from it."
            )
    warm = [row["row_number"].strip() for row in warm_rows]
    if len(warm) < int(warmup_n):
        problems.append(f"{warmup_csv} has fewer than {warmup_n} data rows for the warm-up")
    in_workload = sorted(set(warm) & set(numbers))
    if in_workload:
        message = f"warm-up row(s) {in_workload} are also workload tickets"
        (notes if mode == "dev" else problems).append(message)
    s_list = split_list(s_rows)
    if set(warm) & set(s_list):
        problems.append(f"warm-up row(s) {sorted(set(warm) & set(s_list))} are also S-measurement tickets")
    if set(s_list) & set(numbers):
        notes.append(
            f"S-measurement row(s) {sorted(set(s_list) & set(numbers))} are also workload tickets "
            f"(docs/a2/arrival-rate.md says they should not be)"
        )
    for note in notes:
        err(f"note: {note}")
    for problem in problems:
        err(problem)
    if problems:
        return 2
    print(len(numbers))
    return 0


# --- warmup-bodies WARMUP_CSV OUT_DIR N ---------------------------------------
def cmd_warmup_bodies(args: list) -> int:
    """Write the JSON bodies of the first N rows; print their row numbers.

    Python rather than awk/cut because a narrative contains commas, quotes and
    newlines, and because the JSON body has to be escaped correctly.
    """
    source, out_dir, count = Path(args[0]), Path(args[1]), int(args[2])
    try:
        rows = read_tickets(source)[:count]
    except (OSError, ValueError, csv.Error) as exc:
        err(str(exc))
        return 2
    if len(rows) < count:
        err(f"{source} has {len(rows)} data row(s); the warm-up needs {count}")
        return 2
    for index, row in enumerate(rows, 1):
        (out_dir / f"warmup_body_{index}.json").write_text(
            json.dumps({"narrative": row["narrative"]}, ensure_ascii=False),
            encoding="utf-8",
        )
        print(row["row_number"].strip())
    return 0


# --- check-health FILE MODEL MODE SETTING SMALL VERBOSITY ---------------------
def cmd_check_health(args: list) -> int:
    """Is the service serving exactly the configuration we asked for?

    Checks configuration only. It never reports a timing: readiness is a
    configuration fact, and latency is the measurement itself.
    """
    path, want_model, want_mode, want_setting, want_small, verbosity = args
    verbose = verbosity == "verbose"

    def complain(message: str) -> int:
        if verbose:
            err(message)
        return 1

    try:
        payload = read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return complain(f"/health did not return usable JSON: {exc}")
    if not isinstance(payload, dict):
        return complain("/health did not return a JSON object")
    if payload.get("model_tag") != want_model:
        return complain(f"/health reports model_tag={payload.get('model_tag')!r}, waiting for {want_model!r}")
    if payload.get("service_mode") != want_mode:
        return complain(f"/health reports service_mode={payload.get('service_mode')!r}, waiting for {want_mode!r}")
    if want_mode == "cascade":
        if payload.get("cascade_setting") != want_setting:
            return complain(f"/health reports cascade_setting={payload.get('cascade_setting')!r}, waiting for {want_setting!r}")
        if payload.get("cascade_small_model_tag") != want_small:
            return complain(
                f"/health reports cascade_small_model_tag={payload.get('cascade_small_model_tag')!r}, "
                f"waiting for {want_small!r}"
            )
        rule = payload.get("cascade_rule")
        if not rule or str(rule).startswith("NOT CONFIGURED"):
            return complain(
                f"/health reports cascade_rule={rule!r}: Setting {want_setting} of the "
                f"escalation rule is not configured in service/cascade.py"
            )
    elif payload.get("cascade_setting") is not None:
        return complain(f"/health reports cascade_setting={payload.get('cascade_setting')!r} for a single-model service")
    if not payload.get("ollama_reachable"):
        return complain(f"/health reports ollama_reachable=false (base url {payload.get('ollama_base_url')!r})")
    if payload.get("status") != "ok":
        return complain(f"/health reports status={payload.get('status')!r}")
    return 0


# --- collect-warmup LOG_DIR OUT_JSONL ID [ID...] ------------------------------
def cmd_collect_warmup(args: list) -> int:
    """Copy the warm-up requests' log lines out of the service log.

    The warm-up pays the model-load cost, so its lines must be kept (evidence
    that the cost was paid before measurement) and kept OUT of service.jsonl.
    """
    log_dir, out_path, ids = Path(args[0]), Path(args[1]), args[2:]
    wanted = set(ids)
    found: dict = {}
    for _ in range(25):                       # the write can trail the response
        found = {}
        for path in sorted(log_dir.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or not any(rid in line for rid in wanted):
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("request_id") in wanted:
                    found.setdefault(record["request_id"], []).append(record)
        if set(found) == wanted:
            break
        time.sleep(0.4)

    with out_path.open("w", encoding="utf-8") as handle:
        for rid in ids:                       # in the order they were sent
            for record in found.get(rid, []):
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    missing = [rid for rid in ids if rid not in found]
    if missing:
        err(f"no log line found for warm-up request(s) {missing} in {log_dir}")
        return 1
    unflagged = [rid for rid in ids if not any(r.get("warmup") for r in found[rid])]
    if unflagged:
        err(f"the warm-up log line(s) for {unflagged} do not carry warmup=true; "
            f"analysis would treat them as measured samples")
        return 1
    escalated = sum(1 for rid in ids for r in found[rid] if r.get("escalated") is True)
    lines = sum(len(found[rid]) for rid in ids)
    print(f"      warm-up log lines captured ({lines} line(s) for {len(ids)} request(s), "
          f"all warmup=true; escalated: {escalated})")
    return 0


# --- any-escalated JSONL ------------------------------------------------------
def cmd_any_escalated(args: list) -> int:
    """Exit 0 when some line has "escalated": true (the large model was called)."""
    try:
        text = Path(args[0]).read_text(encoding="utf-8")
    except OSError:
        return 1
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            if json.loads(line).get("escalated") is True:
                return 0
        except (json.JSONDecodeError, AttributeError):
            continue
    return 1


# --- large-warmup-body REPO WARMUP_CSV MODEL SEED NUM_CTX OUT_JSON -------------
def cmd_large_warmup_body(args: list) -> int:
    """The /api/generate body for loading the cascade's large model directly.

    The prompt is built by the service's own, unchanged service.prompt.build_prompt()
    from the first warm-up narrative, and the options are exactly the service's
    (temperature 0, its seed, its num_ctx). num_ctx matters most: a different
    context size would make Ollama reload the model on the next service call.
    """
    repo, warmup_csv, model, seed, num_ctx, out_path = args
    sys.path.insert(0, repo)
    from service.prompt import build_prompt  # noqa: E402  (this checkout's prompt)

    try:
        rows = read_tickets(warmup_csv)
    except (OSError, ValueError, csv.Error) as exc:
        err(str(exc))
        return 2
    if not rows:
        err(f"{warmup_csv} has no data rows")
        return 2
    body = {
        "model": model,
        "prompt": build_prompt(rows[0]["narrative"]),
        "stream": False,
        "options": {"temperature": 0, "seed": int(seed), "num_ctx": int(num_ctx)},
    }
    Path(out_path).write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    print(rows[0]["row_number"].strip())
    return 0


# --- strip-context IN OUT -----------------------------------------------------
def cmd_strip_context(args: list) -> int:
    """Keep Ollama's /api/generate reply as evidence, minus the token 'context' array."""
    source, dest = Path(args[0]), Path(args[1])
    try:
        payload = read_json(source)
    except (OSError, json.JSONDecodeError):
        dest.write_bytes(source.read_bytes() if source.is_file() else b"")
        return 1
    if isinstance(payload, dict):
        payload.pop("context", None)
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


# --- residency PS_JSON OUT_JSON EXPECTED [EXPECTED...] -------------------------
def cmd_residency(args: list) -> int:
    """Which models does Ollama's /api/ps list, and are all the expected ones there?

    Exit 0 only when every expected tag is listed (by "name" or "model").
    """
    ps_json, out_json, expected = args[0], Path(args[1]), args[2:]
    resident, listed, error = [], set(), None
    try:
        payload = read_json(ps_json)
        models = (payload.get("models") or []) if isinstance(payload, dict) else None
        if models is None or not isinstance(models, list):
            raise ValueError("no 'models' list in the /api/ps reply")
        for model in models:
            name = model.get("name") or model.get("model") or ""
            resident.append(name)
            listed.add(norm_tag(model.get("name") or ""))
            listed.add(norm_tag(model.get("model") or ""))
    except (OSError, json.JSONDecodeError, ValueError, AttributeError) as exc:
        error = f"{ps_json}: {exc}"
    missing = [tag for tag in expected if norm_tag(tag) not in listed]
    result = {
        "expected": list(expected),
        "resident": resident,
        "missing": missing,
        "all_expected_resident": error is None and not missing,
        "error": error,
    }
    out_json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(", ".join(resident) if resident else "(none)")
    if error:
        err(error)
    return 0 if result["all_expected_resident"] else 1


# --- jtl-summary JTL ----------------------------------------------------------
def cmd_jtl_summary(args: list) -> int:
    """Print '<samples> <distinct source rows> <repeated rows or ->'.

    Counted with a CSV reader rather than wc -l, because a quoted failure message
    can span lines. A repeated source_row means a ticket was sent twice in one
    run, which the plan is built never to do (recycle off).
    """
    with open(args[0], newline="", encoding="utf-8", errors="replace") as handle:
        rows = list(csv.DictReader(handle))
    sources = [(row.get("source_row") or "").strip() for row in rows]
    present = [s for s in sources if s]
    repeated = sorted(s for s, c in Counter(present).items() if c > 1)
    print(f"{len(rows)} {len(set(present))} {','.join(repeated) if repeated else '-'}")
    return 0


# --- ollama-env IN OUT --------------------------------------------------------
def cmd_ollama_env(args: list) -> int:
    """Keep only the OLLAMA_* lines of the container's printenv, sorted."""
    lines = Path(args[0]).read_text(encoding="utf-8", errors="replace").splitlines()
    kept = sorted(line for line in lines if line.startswith("OLLAMA_"))
    Path(args[1]).write_text("".join(line + "\n" for line in kept), encoding="utf-8")
    return 0


# --- slice LOG_DIR START END MARGIN OUT_MEASURED OUT_WARMUP OUT_BOOK BOOK_IDS CLAIMED
def cmd_slice(args: list) -> int:
    """Copy the service log lines of the measured window into the run directory.

    As in run_load_test.sh: timestamps are parsed, not string-compared, so a run
    crossing midnight into a second log file is handled; warm-up lines go to
    warmup.jsonl, never to service.jsonl. New for A2:

    * this script's own GET /stats calls (identified by the request ids it gave
      them, BOOK_IDS) go to stats_calls.jsonl, because the before/after /stats
      calls fall inside the slice margin and analysis/reconcile.py would
      otherwise report them as requests the load generator never sent;
    * a line whose request_id is listed in CLAIMED -- already filed in an
      earlier run directory of this same invocation -- is skipped, so that a
      short gap between two runs cannot let one run's lines (inside the slice
      margin) be copied into the next run's evidence as well. This run's own
      ids are appended to CLAIMED afterwards.

    Nothing else is filtered out: an unexpected line still lands in
    service.jsonl, where reconcile will see it.
    """
    log_dir = Path(args[0])
    start_s, end_s, margin_s, out_measured, out_warmup, out_book, book_ids, claimed_path = args[1:9]
    bookkeeping = set(split_list(book_ids))
    claimed_file = Path(claimed_path)
    claimed = set()
    if claimed_file.is_file():
        claimed = {line.strip() for line in claimed_file.read_text(encoding="utf-8").splitlines() if line.strip()}
    skipped = 0

    def parse(value: str) -> datetime:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)

    margin = timedelta(seconds=int(margin_s))
    window_start = parse(start_s) - margin
    window_end = parse(end_s) + margin

    measured, warmup, book, problems = [], [], [], []
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
            if record.get("request_id") in claimed:
                skipped += 1
                continue
            if record.get("request_id") in bookkeeping:
                book.append((ts, record))
            elif record.get("warmup"):
                warmup.append((ts, record))
            else:
                measured.append((ts, record))

    for bucket in (measured, warmup, book):
        bucket.sort(key=lambda item: item[0])

    with Path(out_measured).open("w", encoding="utf-8") as handle:
        for _, record in measured:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    with Path(out_book).open("w", encoding="utf-8") as handle:
        for _, record in book:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    # Append to warmup.jsonl rather than overwrite: the warm-up requests' own
    # lines were collected into it before the window opened. Anything already
    # there is skipped so the file cannot hold the same request twice.
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

    with claimed_file.open("a", encoding="utf-8") as handle:
        for _, record in measured + warmup + book:
            if record.get("request_id"):
                handle.write(f"{record['request_id']}\n")

    for problem in problems:
        print(f"      service log: {problem}", file=sys.stderr)
    print(f"      service.jsonl: {len(measured)} measured line(s); "
          f"warmup.jsonl: +{appended} warm-up line(s) added ({len(warmup)} found in window); "
          f"stats_calls.jsonl: {len(book)} line(s)"
          + (f"; {skipped} line(s) of an earlier run of this invocation skipped" if skipped else ""))
    return 0 if measured else 1


# --- metadata OUT -------------------------------------------------------------
def cmd_metadata(args: list) -> int:
    """Write metadata.json: every Assignment 1 key, plus the Assignment 2 keys.

    Every value is either something the operator asked for, something the
    service or Ollama reported about itself (/health, /api/ps, the container's
    environment, the service's own log lines), or a fact about this machine.
    Nothing is estimated and nothing is derived from the results: an unknown
    value is written as null rather than guessed.
    """
    out_path = Path(args[0])
    env = os.environ

    def text(name):
        value = env.get(name, "")
        return value if value != "" else None

    def integer(name):
        try:
            return int(env.get(name, "").strip())
        except ValueError:
            return None

    def number(name):
        try:
            value = float(env.get(name, "").strip())
        except ValueError:
            return None
        return int(value) if value.is_integer() else value

    def flag(name):
        value = env.get(name, "").strip().lower()
        if value in ("1", "true"):
            return True
        if value in ("0", "false"):
            return False
        return None

    def listing(name):
        return split_list(env.get(name, ""))

    def row_numbers(name):
        return [int(v) if v.isdigit() else v for v in listing(name)]

    def json_file(name):
        path = env.get(name, "")
        if not path or not Path(path).is_file():
            return None
        try:
            return read_json(path)
        except (OSError, json.JSONDecodeError):
            return None

    def git(*git_args):
        proc = subprocess.run(
            ["git", "-C", env["META_REPO"], *git_args],
            capture_output=True, text=True, check=False,
        )
        return proc.stdout.strip() if proc.returncode == 0 else None

    def sole_seed(name):
        """The one seed the service logged during the window, else None."""
        path = env.get(name, "")
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

    def stats_total(name):
        payload = json_file(name)
        total = payload.get("total") if isinstance(payload, dict) else None
        return total if isinstance(total, int) and not isinstance(total, bool) else None

    def container_env(name):
        """The Ollama container's own environment, or None if it was not captured."""
        path = env.get(name, "")
        if not path or not Path(path).is_file() or Path(path).stat().st_size == 0:
            return None
        values = {}
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            key, sep, value = line.partition("=")
            if sep:
                values[key] = value
        return values

    health = json_file("META_HEALTH_JSON") or {}
    gate = json_file("META_GATE_JSON") or {}
    before = json_file("META_RESIDENCY_BEFORE")
    after = json_file("META_RESIDENCY_AFTER")
    ollama_env = container_env("META_OLLAMA_ENV_FILE")

    def ollama_setting(key):
        # "default" when the container does not set it (Ollama's built-in value
        # applies), null when the environment could not be captured at all.
        if ollama_env is None:
            return None
        return ollama_env.get(key, "default")

    commit = git("rev-parse", "HEAD")
    dirty = bool(git("status", "--porcelain")) if commit is not None else None
    warmup_ids = listing("META_WARMUP_IDS")
    uname = os.uname()

    metadata = {
        # --- every key Assignment 1's run_load_test.sh writes -------------
        "run_id": text("META_RUN_ID"),
        "mode": text("META_MODE"),
        "plan": text("META_PLAN"),
        "plan_file": text("META_PLAN_FILE"),
        "model_tag": health.get("model_tag") or text("META_MODEL_TAG"),
        "model_digest": health.get("model_digest"),
        "rate_per_min": number("META_RATE"),
        "duration_s": integer("META_DURATION"),
        "run_index": integer("META_RUN_INDEX"),
        "runs_total": integer("META_RUNS_TOTAL"),
        "started_at_utc": text("META_STARTED"),
        "ended_at_utc": text("META_ENDED"),
        "git_commit": commit,
        "git_dirty": dirty,
        "freeze_commit": None,
        "freeze_tag": None,
        "prompt_hash": health.get("prompt_hash"),
        "num_ctx": health.get("num_ctx"),
        "seed": sole_seed("META_SERVICE_JSONL"),
        "input_csv": text("META_INPUT_CSV"),
        "service_url": text("META_SERVICE_URL"),
        "service_host_info": {
            "target_url": text("META_SERVICE_URL"),
            "ollama_base_url": health.get("ollama_base_url"),
            "ollama_url_from_load_generator": text("META_OLLAMA_URL"),
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
        # Read from the Ollama container's own environment (printenv inside it),
        # not from this load generator's shell. Recorded only, never set.
        "ollama_num_parallel": ollama_setting("OLLAMA_NUM_PARALLEL"),
        "ollama_max_loaded_models": ollama_setting("OLLAMA_MAX_LOADED_MODELS"),
        # The first warm-up id, under the key Assignment 1's tooling reads.
        "warmup_request_id": warmup_ids[0] if warmup_ids else None,
        "notes": env.get("META_NOTES", ""),
        # --- Assignment 2 ----------------------------------------------------
        "assignment": "A2",
        "config": text("META_CONFIG"),
        "service_mode": health.get("service_mode"),
        "cascade_setting": health.get("cascade_setting"),
        "cascade_small_model_tag": health.get("cascade_small_model_tag"),
        "cascade_small_model_digest": health.get("cascade_small_model_digest"),
        "cascade_large_model_tag": health.get("cascade_large_model_tag"),
        "cascade_rule": health.get("cascade_rule"),
        "gate_commit": gate.get("gate_commit"),
        "gate_tag": gate.get("gate_tag"),
        "s_seconds": number("META_S_SECONDS"),
        "response_timeout_ms": integer("META_TIMEOUT_MS"),
        "pause_s": integer("META_PAUSE_S"),
        "arrival_file": text("META_ARRIVAL_FILE"),
        "ticket_list": text("META_TICKET_LIST"),
        "workload_size": integer("META_WORKLOAD_SIZE"),
        "warmup_request_ids": warmup_ids,
        "warmup_rows": row_numbers("META_WARMUP_ROWS"),
        "large_model_direct_warmup": bool(flag("META_LARGE_DIRECT")),
        "stats_total_before": stats_total("META_STATS_BEFORE"),
        "stats_total_after": stats_total("META_STATS_AFTER"),
        "expected_models": listing("META_EXPECTED_MODELS"),
        "resident_models_before": before.get("resident") if isinstance(before, dict) else None,
        "resident_models_after": after.get("resident") if isinstance(after, dict) else None,
        "all_expected_resident_before": (
            bool(before.get("all_expected_resident")) if isinstance(before, dict) else None
        ),
        "all_expected_resident_after": (
            bool(after.get("all_expected_resident")) if isinstance(after, dict) else None
        ),
        "env_check_ok": flag("META_ENV_CHECK_OK"),
        "measured": bool(flag("META_MEASURED")),
        "jtl_samples": integer("META_JTL_SAMPLES"),
        "jtl_distinct_source_rows": integer("META_JTL_DISTINCT"),
        "ollama_keep_alive": ollama_setting("OLLAMA_KEEP_ALIVE"),
    }
    out_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return 0


COMMANDS = {
    "json-get": cmd_json_get,
    "rate-label": cmd_rate_label,
    "expected": cmd_expected,
    "candidate-tags": cmd_candidate_tags,
    "workload-check": cmd_workload_check,
    "warmup-bodies": cmd_warmup_bodies,
    "check-health": cmd_check_health,
    "collect-warmup": cmd_collect_warmup,
    "any-escalated": cmd_any_escalated,
    "large-warmup-body": cmd_large_warmup_body,
    "strip-context": cmd_strip_context,
    "residency": cmd_residency,
    "jtl-summary": cmd_jtl_summary,
    "ollama-env": cmd_ollama_env,
    "slice": cmd_slice,
    "metadata": cmd_metadata,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        err(f"usage: a2py <{'|'.join(COMMANDS)}> [args...]")
        raise SystemExit(2)
    raise SystemExit(COMMANDS[sys.argv[1]](sys.argv[2:]))
PY_A2
}

# --- the A2 workload must use only pinned candidate models -----------------
# Guardrail 1: no new models. The tags come from models/models.yaml's
# `candidates:` list (not `substitutes:`).
MODELS_YAML="${REPO_ROOT}/${MODELS_YAML_REL}"
[[ -f "$MODELS_YAML" ]] || die_usage "missing $MODELS_YAML (the pinned candidate list)"
CANDIDATE_TAGS="$(a2py candidate-tags "$MODELS_YAML")" || die_usage "no candidate tags found in $MODELS_YAML"
for tag in "${EXPECTED_MODELS[@]}"; do
    if ! printf '%s\n' "$CANDIDATE_TAGS" | grep -Fxq -- "$tag"; then
        if (( DEV )); then
            warn "'$tag' is not one of the pinned candidates in ${MODELS_YAML_REL} ($(printf '%s' "$CANDIDATE_TAGS" | tr '\n' ' ')). Allowed in --dev only."
        else
            die_usage "'$tag' is not one of the pinned candidates in ${MODELS_YAML_REL}: $(printf '%s' "$CANDIDATE_TAGS" | tr '\n' ' '). Assignment 2 may not introduce a new model."
        fi
    fi
done

# --- JMeter, docker/ssh ----------------------------------------------------
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
    command -v docker >/dev/null 2>&1 || die_usage "docker not found. Each run restarts the Ollama container and recreates triage; run this on the service host, set SERVICE_SSH=user@service-host, or set DOCKER_HOST (e.g. ssh://user@service-host)."
fi

# --- paths ----------------------------------------------------------------
abs_path() {
    case "$1" in
        /*) printf '%s' "$1" ;;
        *)  printf '%s/%s' "$REPO_ROOT" "$1" ;;
    esac
}
rel_path() {
    case "$1" in
        "${REPO_ROOT}/"*) printf '%s' "${1#"${REPO_ROOT}/"}" ;;
        *) printf '%s' "$1" ;;
    esac
}

PLAN_FILE="${REPO_ROOT}/${PLAN_REL}"
[[ -f "$PLAN_FILE" ]] || die_usage "missing plan file $PLAN_FILE"
RESET_SCRIPT="${REPO_ROOT}/scripts/reset.sh"
[[ -x "$RESET_SCRIPT" ]] || die_usage "missing or non-executable $RESET_SCRIPT (each run must start from an empty database)"
[[ -f "$COMPOSE_FILE" ]] || die_usage "missing compose file $COMPOSE_FILE (set COMPOSE_FILE if it lives elsewhere)"
GATE_SCRIPT="${REPO_ROOT}/scripts/a2_gate.py"
ENV_SNAPSHOT_SCRIPT="${REPO_ROOT}/scripts/a2_env_snapshot.py"
ARRIVAL_FILE="$(abs_path "$ARRIVAL_FILE_ARG")"
ENV_BASELINE="$(abs_path "$ENV_BASELINE_ARG")"

if (( DEV )); then
    INPUT_CSV="${REPO_ROOT}/${DEV_CSV_REL}"
    INPUT_CSV_REL="$DEV_CSV_REL"
    TICKET_LIST=""
    TICKET_LIST_META=""
    MODE="dev"
else
    INPUT_CSV="${REPO_ROOT}/${A2_CSV_REL}"
    INPUT_CSV_REL="$A2_CSV_REL"
    TICKET_LIST="${REPO_ROOT}/${TICKET_LIST_REL}"
    TICKET_LIST_META="$TICKET_LIST_REL"
    MODE="real"
    [[ -f "$GATE_SCRIPT" ]] || die_usage "missing $GATE_SCRIPT (no real A2 run without the A2 gate)"
    [[ -f "$TICKET_LIST" ]] || die_usage "missing the committed ticket list $TICKET_LIST"
    # Checked here, before anything is touched, so that a missing baseline costs
    # nothing. Dev mode skips the environment check with a warning instead.
    [[ -f "$ENV_BASELINE" ]] || die_usage "no environment baseline at ${ENV_BASELINE}. Record it ONCE, before the first Assignment 2 run of any kind, with: python scripts/a2_env_snapshot.py record ... (see its --help), commit it, then run this again. Nothing was measured."
    [[ -f "$ENV_SNAPSHOT_SCRIPT" ]] || die_usage "missing ${ENV_SNAPSHOT_SCRIPT}; the per-configuration environment check (brief, Set-up) cannot run. Nothing was measured."
fi
[[ -f "$INPUT_CSV" ]] || die_usage "missing input CSV $INPUT_CSV"

# The warm-up always uses the first three hand-written dev tickets, even in a
# real run: they are not measured, they are never team rows, and so they can
# overlap neither the workload nor the S tickets.
WARMUP_CSV="${REPO_ROOT}/${DEV_CSV_REL}"
[[ -f "$WARMUP_CSV" ]] || die_usage "missing $WARMUP_CSV (used for the three warm-up tickets)"

# --- rate, run length, timeout, pause: from S ------------------------------
S_SECONDS=""
S_ROWS=""
if [[ -f "$ARRIVAL_FILE" ]]; then
    a2py json-get "$ARRIVAL_FILE" s_seconds >/dev/null \
        || die_usage "the arrival file $ARRIVAL_FILE is not readable JSON"
    S_SECONDS="$(a2py json-get "$ARRIVAL_FILE" s_seconds)"
    S_ROWS="$(a2py json-get "$ARRIVAL_FILE" s_rows)"
    (( RATE_GIVEN ))     || RATE="$(a2py json-get "$ARRIVAL_FILE" rate_per_min)"
    (( DURATION_GIVEN )) || DURATION="$(a2py json-get "$ARRIVAL_FILE" duration_s)"
    (( TIMEOUT_GIVEN ))  || TIMEOUT_MS="$(a2py json-get "$ARRIVAL_FILE" response_timeout_ms)"
    (( PAUSE_GIVEN ))    || PAUSE_S="$(a2py json-get "$ARRIVAL_FILE" pause_s)"
    ARRIVAL_META="$(rel_path "$ARRIVAL_FILE")"
else
    ARRIVAL_META=""
    if (( ! DEV )) && ! (( RATE_GIVEN && DURATION_GIVEN && TIMEOUT_GIVEN && PAUSE_GIVEN )); then
        die_usage "no arrival file at $ARRIVAL_FILE. Measure S first (python scripts/measure_s_a2.py), or pass all four of --rate, --duration, --timeout-ms and --pause-s explicitly."
    fi
    if (( DEV )); then
        # The plan's own defaults: the brief's worked example for S = 6.
        [[ -n "$RATE" ]]       || RATE=5
        [[ -n "$DURATION" ]]   || DURATION=300
        [[ -n "$TIMEOUT_MS" ]] || TIMEOUT_MS=300000
        [[ -n "$PAUSE_S" ]]    || PAUSE_S=360
        warn "no arrival file at $ARRIVAL_FILE; dev mode uses rate ${RATE}/min, duration ${DURATION}s, timeout ${TIMEOUT_MS}ms, pause ${PAUSE_S}s"
    fi
fi

[[ "$RATE" =~ ^[0-9]+(\.[0-9]{1,2})?$ ]] || die_usage "rate per minute must be a positive number with at most two decimals (got '$RATE')"
[[ "$RATE" =~ [1-9] ]]                    || die_usage "rate per minute must be greater than zero (got '$RATE')"
[[ "$DURATION" =~ ^[0-9]+$ && "$DURATION" -ge 1 ]]     || die_usage "duration must be a positive integer number of seconds (got '$DURATION')"
[[ "$TIMEOUT_MS" =~ ^[0-9]+$ && "$TIMEOUT_MS" -ge 1 ]] || die_usage "response timeout must be a positive integer number of milliseconds (got '$TIMEOUT_MS')"
[[ "$PAUSE_S" =~ ^[0-9]+$ && "$PAUSE_S" -ge 1 ]]       || die_usage "pause must be a positive integer number of seconds (got '$PAUSE_S')"
if [[ -n "$S_SECONDS" ]]; then
    [[ "$S_SECONDS" =~ ^[0-9]+(\.[0-9]+)?$ ]] || die_usage "s_seconds in $ARRIVAL_FILE is not a number (got '$S_SECONDS')"
fi

# The brief's three timing rules (Step 4). A real run refuses to break them; a
# rehearsal may shorten everything, with a warning.
RULE_PROBLEMS=()
(( TIMEOUT_MS >= MIN_TIMEOUT_MS )) \
    || RULE_PROBLEMS+=("response timeout ${TIMEOUT_MS} ms is below the brief's 5-minute minimum (${MIN_TIMEOUT_MS} ms)")
(( PAUSE_S * 1000 >= TIMEOUT_MS + MIN_PAUSE_MARGIN_S * 1000 )) \
    || RULE_PROBLEMS+=("pause ${PAUSE_S} s does not outlast the ${TIMEOUT_MS} ms response timeout by at least ${MIN_PAUSE_MARGIN_S} s, so a slow request could be killed when the schedule ends")
(( DURATION >= MIN_DURATION_S )) \
    || RULE_PROBLEMS+=("run length ${DURATION} s is below the brief's 5-minute minimum")
if [[ -n "$S_SECONDS" ]]; then
    # 1 s of tolerance for rounding in the arrival file.
    S_MS="$("$PYTHON_BIN" -c 'import sys; print(int(round(float(sys.argv[1]) * 1000)))' "$S_SECONDS")"
    (( TIMEOUT_MS + 1000 >= 10 * S_MS )) \
        || RULE_PROBLEMS+=("response timeout ${TIMEOUT_MS} ms is below 10 x S (S = ${S_SECONDS} s)")
    (( (DURATION + 1) * 1000 >= 60 * S_MS )) \
        || RULE_PROBLEMS+=("run length ${DURATION} s is shorter than S minutes (S = ${S_SECONDS} s)")
fi
if (( ${#RULE_PROBLEMS[@]} )); then
    for problem in "${RULE_PROBLEMS[@]}"; do
        if (( DEV )); then warn "$problem (allowed in --dev only)"; else printf '%s: %s\n' "$SCRIPT_NAME" "$problem" >&2; fi
    done
    (( DEV )) || die_usage "refusing: the timing settings break the brief's Step 4 rules (see above). Fix docs/a2/arrival_rate.json or the overrides."
fi

OVERRIDES=""
if [[ -f "$ARRIVAL_FILE" ]]; then
    (( RATE_GIVEN ))     && OVERRIDES="${OVERRIDES}rate_per_min=${RATE} "
    (( DURATION_GIVEN )) && OVERRIDES="${OVERRIDES}duration_s=${DURATION} "
    (( TIMEOUT_GIVEN ))  && OVERRIDES="${OVERRIDES}response_timeout_ms=${TIMEOUT_MS} "
    (( PAUSE_GIVEN ))    && OVERRIDES="${OVERRIDES}pause_s=${PAUSE_S} "
    OVERRIDES="${OVERRIDES% }"
    if [[ -n "$OVERRIDES" ]] && (( ! DEV )); then
        warn "overriding ${ARRIVAL_META}: ${OVERRIDES}. The brief requires the SAME rate and run length for every configuration; record why in docs/a2/run-log.md."
    fi
fi

RATE_LABEL="$(a2py rate-label "$RATE")"
read -r EXPECTED_SAMPLES EXPECTED_UPPER <<EOF_EXPECTED
$(a2py expected "$RATE" "$DURATION")
EOF_EXPECTED

# --- the fixed workload ----------------------------------------------------
WORKLOAD_SIZE="$(a2py workload-check "$MODE" "$INPUT_CSV" "$TICKET_LIST" "$WARMUP_CSV" "$WARMUP_COUNT" "$S_ROWS")" \
    || die_usage "the speed-test workload failed its checks (see above)"
if "$PYTHON_BIN" -c 'import sys; sys.exit(0 if float(sys.argv[1]) > float(sys.argv[2]) else 1)' "$EXPECTED_UPPER" "$WORKLOAD_SIZE"; then
    warn "at ${RATE}/min for ${DURATION}s a run expects ~${EXPECTED_SAMPLES} arrivals, with a safe upper bound of ${EXPECTED_UPPER} -- more than the ${WORKLOAD_SIZE} tickets in ${INPUT_CSV_REL}. A run that exhausts the list is flagged (docs/a2/arrival-rate.md section 2: regenerate the list larger before the first real run)."
fi

# --- output ----------------------------------------------------------------
if [[ -n "$OUT_ROOT_ARG" ]]; then
    OUT_ROOT="$(abs_path "$OUT_ROOT_ARG")"
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

SERVICE_URL="http://${HOST}:${PORT}"
OLLAMA_URL="http://${HOST}:${OLLAMA_PORT_ARG}"
EXPECTED_MODELS_CSV="$(IFS=,; printf '%s' "${EXPECTED_MODELS[*]}")"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# remote <command words...> -- run one command inside the service host's checkout.
# Each word is quoted locally, so tags and paths survive the remote shell
# unchanged. -n: never let ssh read this script's stdin.
remote() {
    ssh -n -o BatchMode=yes -o ConnectTimeout=15 "$SERVICE_SSH" \
        "cd $(printf '%q' "$SERVICE_REPO") && $(printf '%q ' "$@")"
}

compose() {
    if [[ -n "$SERVICE_SSH" ]]; then
        # The compose file is the service host's own copy, so ./logs/service and
        # the build context resolve on that machine, not on this one. The
        # configuration's four variables are passed through, exactly as
        # run_load_test.sh passes MODEL_TAG; locally they are exported.
        local -a remote_cmd=(env
            "MODEL_TAG=${MODEL_TAG:-}"
            "SERVICE_MODE=${SERVICE_MODE:-}"
            "CASCADE_SETTING=${CASCADE_SETTING:-}"
            "CASCADE_SMALL_MODEL_TAG=${CASCADE_SMALL_MODEL_TAG:-}"
            docker compose -f docker-compose.yml)
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

# reset_service -- empty the database and bring triage back up in this
# configuration (reset.sh starts triage itself, from the exported environment).
reset_service() {
    if [[ -n "$SERVICE_SSH" ]]; then
        remote env \
            "MODEL_TAG=${MODEL_TAG:-}" \
            "SERVICE_MODE=${SERVICE_MODE:-}" \
            "CASCADE_SETTING=${CASCADE_SETTING:-}" \
            "CASCADE_SMALL_MODEL_TAG=${CASCADE_SMALL_MODEL_TAG:-}" \
            scripts/reset.sh --yes
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
    local _
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        sync_service_logs || true
        if grep -qs -- "$1" "${SERVICE_LOG_DIR%/}"/*.jsonl; then
            return 0
        fi
        sleep 2
    done
    return 1
}

now_iso_ms() {
    # Millisecond ISO-8601 in UTC, matching the service's own 'ts' format (in
    # Python because date(1)'s %3N is GNU-only and the load generator may be a Mac).
    "$PYTHON_BIN" -c 'import datetime as d; n = d.datetime.now(d.timezone.utc); print(n.strftime("%Y-%m-%dT%H:%M:%S.") + f"{n.microsecond // 1000:03d}Z")'
}

new_uuid() { "$PYTHON_BIN" -c 'import uuid; print(uuid.uuid4())'; }

# http_get <url> <out file> [X-Request-ID] -- HTTP status on stdout, body to the file.
http_get() {
    local url="$1" out="$2" rid="${3:-}" code
    if [[ -n "$rid" ]]; then
        code="$(curl -sS -o "$out" -w '%{http_code}' --max-time 15 -H "X-Request-ID: ${rid}" "$url" 2>/dev/null || true)"
    else
        code="$(curl -sS -o "$out" -w '%{http_code}' --max-time 15 "$url" 2>/dev/null || true)"
    fi
    printf '%s' "${code:-000}"
}

# wait_for_ollama -- until GET <ollama>/api/version answers 200.
wait_for_ollama() {
    local deadline=$(( $(date +%s) + HEALTH_TIMEOUT_S )) code
    while [[ $(date +%s) -lt $deadline ]]; do
        code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "${OLLAMA_URL}/api/version" 2>/dev/null || true)"
        [[ "$code" == "200" ]] && return 0
        sleep 2
    done
    return 1
}

# wait_for_service_up <scratch file> -- until /health answers HTTP 200 at all.
wait_for_service_up() {
    local deadline=$(( $(date +%s) + HEALTH_TIMEOUT_S ))
    while [[ $(date +%s) -lt $deadline ]]; do
        [[ "$(http_get "${SERVICE_URL}/health" "$1")" == "200" ]] && return 0
        sleep 2
    done
    return 1
}

# wait_for_health <health json file> -- until /health confirms this configuration.
wait_for_health() {
    local health_file="$1"
    local deadline=$(( $(date +%s) + HEALTH_TIMEOUT_S )) code
    while [[ $(date +%s) -lt $deadline ]]; do
        code="$(http_get "${SERVICE_URL}/health" "$health_file")"
        if [[ "$code" == "200" ]] && a2py check-health "$health_file" \
                "$WANT_MODEL" "$WANT_MODE" "$WANT_SETTING" "$WANT_SMALL" quiet; then
            return 0
        fi
        sleep 2
    done
    printf '%s: /health did not confirm config %s (model_tag %s, service_mode %s) within %ss.\n' \
        "$SCRIPT_NAME" "$CONFIG" "$WANT_MODEL" "$WANT_MODE" "$HEALTH_TIMEOUT_S" >&2
    code="$(http_get "${SERVICE_URL}/health" "$health_file")"
    printf '  last HTTP status: %s\n' "$code" >&2
    if [[ -s "$health_file" ]]; then
        printf '  last body: %s\n' "$(head -c 800 "$health_file")" >&2
    fi
    a2py check-health "$health_file" "$WANT_MODEL" "$WANT_MODE" "$WANT_SETTING" "$WANT_SMALL" verbose || true
    return 1
}

# capture_residency <before|after> -- `ollama ps` in the container (text, the
# brief's evidence) and GET /api/ps (JSON, what is checked). Exit 0 only when
# every expected model is listed.
capture_residency() {
    local when="$1"
    if ! compose exec -T "$OLLAMA_SERVICE" ollama ps > "${RUN_DIR}/ollama_ps_${when}.txt" 2>&1; then
        warn "${RUN_ID}: 'ollama ps' in the ${OLLAMA_SERVICE} container failed ($when); see ollama_ps_${when}.txt. The /api/ps reply is still checked."
        RUN_NOTE_EXTRA="${RUN_NOTE_EXTRA}ollama ps ($when) failed in the container; "
    fi
    local code
    code="$(http_get "${OLLAMA_URL}/api/ps" "${RUN_DIR}/ollama_ps_${when}.json")"
    if [[ "$code" != "200" ]]; then
        warn "${RUN_ID}: GET ${OLLAMA_URL}/api/ps returned HTTP ${code} ($when)"
    fi
    local listed
    if listed="$(a2py residency "${RUN_DIR}/ollama_ps_${when}.json" \
            "${WORK_DIR}/residency_${when}_run${RUN_INDEX}.json" "${EXPECTED_MODELS[@]}")"; then
        log "      resident ($when): ${listed}"
        return 0
    fi
    log "      resident ($when): ${listed}; expected: ${EXPECTED_MODELS_CSV}"
    return 1
}

# write_run_metadata -- metadata.json for the current run, from the globals.
write_run_metadata() {
    META_RUN_ID="$RUN_ID" \
    META_MODE="$MODE" \
    META_PLAN="$PLAN_NAME" \
    META_PLAN_FILE="$PLAN_REL" \
    META_MODEL_TAG="$WANT_MODEL" \
    META_RATE="$RATE" \
    META_DURATION="$DURATION" \
    META_RUN_INDEX="$RUN_INDEX" \
    META_RUNS_TOTAL="$RUNS" \
    META_STARTED="$STARTED_AT" \
    META_ENDED="$ENDED_AT" \
    META_INPUT_CSV="$INPUT_CSV_REL" \
    META_SERVICE_URL="$SERVICE_URL" \
    META_OLLAMA_URL="$OLLAMA_URL" \
    META_JMETER_VERSION="$JMETER_VERSION" \
    META_HEALTH_JSON="${RUN_DIR}/health.json" \
    META_GATE_JSON="${RUN_DIR}/gate.json" \
    META_SERVICE_JSONL="${RUN_DIR}/service.jsonl" \
    META_REPO="$REPO_ROOT" \
    META_CONFIG="$CONFIG" \
    META_S_SECONDS="$S_SECONDS" \
    META_TIMEOUT_MS="$TIMEOUT_MS" \
    META_PAUSE_S="$PAUSE_S" \
    META_ARRIVAL_FILE="$ARRIVAL_META" \
    META_TICKET_LIST="$TICKET_LIST_META" \
    META_WORKLOAD_SIZE="$WORKLOAD_SIZE" \
    META_WARMUP_IDS="$(IFS=,; printf '%s' "${WARMUP_IDS[*]+${WARMUP_IDS[*]}}")" \
    META_WARMUP_ROWS="$WARMUP_ROWS_CSV" \
    META_LARGE_DIRECT="$LARGE_DIRECT" \
    META_STATS_BEFORE="${RUN_DIR}/stats_before.json" \
    META_STATS_AFTER="${RUN_DIR}/stats_after.json" \
    META_EXPECTED_MODELS="$EXPECTED_MODELS_CSV" \
    META_RESIDENCY_BEFORE="${WORK_DIR}/residency_before_run${RUN_INDEX}.json" \
    META_RESIDENCY_AFTER="${WORK_DIR}/residency_after_run${RUN_INDEX}.json" \
    META_ENV_CHECK_OK="$ENV_CHECK_OK" \
    META_OLLAMA_ENV_FILE="$OLLAMA_ENV_FILE" \
    META_MEASURED="$MEASURED" \
    META_JTL_SAMPLES="$JTL_SAMPLES" \
    META_JTL_DISTINCT="$JTL_DISTINCT" \
    META_NOTES="${RUN_NOTES:+${RUN_NOTES}; }${RUN_NOTE_EXTRA}${STANDING_NOTE}" \
        a2py metadata "${RUN_DIR}/metadata.json"
    log "      ${RUN_DIR}/metadata.json"
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
            warn "the service is being addressed at '$HOST', which means the load generator is on the same machine as the system under test. The brief does not accept latency measured that way (\"The load generator must run on a separate machine from the service\"): a co-hosted generator steals CPU from the service. Pass --host <service machine>."
        fi
        ;;
esac

JMETER_VERSION="$("$JMETER_BIN" --version 2>&1 | grep -Eo '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -n 1 || true)"
[[ -n "$JMETER_VERSION" ]] || JMETER_VERSION="unknown"

log "Config        : $CONFIG"
if [[ "$WANT_MODE" == "cascade" ]]; then
    log "Cascade       : Setting ${WANT_SETTING}; small ${SMALL_MODEL}, large ${LARGE_MODEL} (MODEL_TAG)"
else
    log "Model         : $WANT_MODEL (single model)"
fi
log "Expected      : ${EXPECTED_MODELS_CSV} resident before every run"
log "Plan          : $PLAN_REL"
log "Arrival rate  : ${RATE}/min (label ${RATE_LABEL}); S = ${S_SECONDS:-unknown} s"
log "Duration      : ${DURATION}s of arrivals, then a ${PAUSE_S}s pause; response timeout ${TIMEOUT_MS}ms"
log "Expected      : ~${EXPECTED_SAMPLES} arrivals per run (safe upper bound ${EXPECTED_UPPER}; ${WORKLOAD_SIZE} tickets in the list)"
log "Arrival file  : ${ARRIVAL_META:-none}${OVERRIDES:+ (overridden: ${OVERRIDES})}"
log "Runs          : $RUNS"
log "Service       : $SERVICE_URL"
log "Ollama        : $OLLAMA_URL (compose service ${OLLAMA_SERVICE})"
log "Input CSV     : $INPUT_CSV_REL"
log "Ticket list   : ${TICKET_LIST_META:-none (dev)}"
log "Warm-up       : first ${WARMUP_COUNT} rows of ${DEV_CSV_REL}"
log "Env baseline  : $(rel_path "$ENV_BASELINE")"
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
    log "Each run RESTARTS the Ollama container, then calls scripts/reset.sh --yes, which"
    log "DESTROYS every ticket stored in the service's database, then recreates the"
    log "triage container as config ${CONFIG} (MODEL_TAG=${WANT_MODEL}, SERVICE_MODE=${WANT_MODE})."
    if [[ ! -t 0 ]]; then
        die_usage "not an interactive terminal and --yes was not given; refusing to restart and reset the service without confirmation"
    fi
    printf 'Proceed with %d run(s)? [y/N] ' "$RUNS"
    read -r reply
    case "$reply" in
        y|Y|yes|YES) : ;;
        *) log "Aborted; nothing was changed."; exit 0 ;;
    esac
fi

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/run_load_test_a2.XXXXXX")"
cleanup() { rm -rf "$WORK_DIR"; }
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Step A: the A2 gate (once per invocation; its verdict is copied per run)
# ---------------------------------------------------------------------------
step "Step A: A2 gate"
GATE_JSON="${WORK_DIR}/gate.json"
if (( DEV )); then
    cat > "$GATE_JSON" <<'DEV_GATE_JSON'
{
  "ok": false,
  "mode": "dev",
  "enforced": false,
  "reasons": [
    "dev mode: the A2 gate (scripts/a2_gate.py) was bypassed, so this run directory is a rehearsal and not evidence. It must never be cited."
  ]
}
DEV_GATE_JSON
    log "  bypassed (--dev). gate_commit will be recorded as null."
else
    if ! "$PYTHON_BIN" "$GATE_SCRIPT" --json --repo "$REPO_ROOT" > "$GATE_JSON"; then
        # a2_gate.py has already explained itself on stderr, in detail.
        exit 3
    fi
    GATE_COMMIT="$(a2py json-get "$GATE_JSON" gate_commit)"
    GATE_TAG="$(a2py json-get "$GATE_JSON" gate_tag)"
    log "  PASS: gated at ${GATE_COMMIT} (tag '${GATE_TAG}')"
fi
if [[ -n "$(git -C "$REPO_ROOT" status --porcelain 2>/dev/null || true)" ]]; then
    warn "the working tree has uncommitted changes. Results are traceable only to a commit; commit before measuring."
fi

# The configuration's environment, exported once: compose and reset.sh inherit it
# locally, and compose()/reset_service() pass it through ssh in remote mode.
export MODEL_TAG="$WANT_MODEL"
export SERVICE_MODE="$WANT_MODE"
export CASCADE_SETTING="$WANT_SETTING"
export CASCADE_SMALL_MODEL_TAG="$WANT_SMALL"

# ---------------------------------------------------------------------------
# Step B: environment check (once per configuration, before run 1)
# ---------------------------------------------------------------------------
# Brief, Set-up: "Before the first run, record your software versions, model
# digests and Ollama settings. Check they are unchanged before each
# configuration." The record is docs/a2/env_baseline.json; the comparison is
# scripts/a2_env_snapshot.py's. This script only gathers its inputs.
step "Step B: environment check against $(rel_path "$ENV_BASELINE")"
ENV_CHECK_JSON="${WORK_DIR}/env_check.json"
OLLAMA_ENV_FILE="${WORK_DIR}/ollama_env_full.txt"
OLLAMA_ENV_FILTERED="${WORK_DIR}/ollama_env.txt"
ENV_CHECK_OK=""
: > "$OLLAMA_ENV_FILE"

# Up, not recreated: `up -d` leaves a running container with an unchanged
# definition alone. If the definition HAD changed (an Ollama setting exported
# differently in this shell), compose would recreate it with the new settings --
# which is exactly what the check below then reports as a change.
compose up -d "$OLLAMA_SERVICE"
wait_for_ollama || die_fail "Ollama did not answer ${OLLAMA_URL}/api/version within ${HEALTH_TIMEOUT_S}s. Check: compose logs ${OLLAMA_SERVICE}, and --ollama-port."
compose up -d --no-deps "$TRIAGE_SERVICE"
wait_for_service_up "${WORK_DIR}/health_envcheck.json" \
    || warn "the service at ${SERVICE_URL} did not answer /health within ${HEALTH_TIMEOUT_S}s; the environment check may not be able to read it"

if compose exec -T "$OLLAMA_SERVICE" printenv > "$OLLAMA_ENV_FILE" 2> "${WORK_DIR}/printenv.err"; then
    a2py ollama-env "$OLLAMA_ENV_FILE" "$OLLAMA_ENV_FILTERED"
    log "  Ollama container environment captured: $(tr '\n' ' ' < "$OLLAMA_ENV_FILTERED")"
else
    : > "$OLLAMA_ENV_FILE"
    if (( DEV )); then
        warn "could not run printenv in the ${OLLAMA_SERVICE} container: $(head -c 300 "${WORK_DIR}/printenv.err")"
    else
        die_fail "could not run printenv in the ${OLLAMA_SERVICE} container, so the Ollama settings cannot be checked: $(head -c 300 "${WORK_DIR}/printenv.err"). Nothing was measured."
    fi
fi

if [[ ! -f "$ENV_BASELINE" ]]; then
    if (( DEV )); then
        warn "no environment baseline at ${ENV_BASELINE}; check skipped (--dev)."
    else
        die_usage "no environment baseline at ${ENV_BASELINE}. Record it ONCE, before the first Assignment 2 run of any kind, with: python scripts/a2_env_snapshot.py record ... (see its --help), commit it, then run this again. Nothing was measured."
    fi
elif [[ ! -f "$ENV_SNAPSHOT_SCRIPT" ]]; then
    if (( DEV )); then
        warn "missing ${ENV_SNAPSHOT_SCRIPT}; environment check skipped (--dev)."
    else
        die_usage "missing ${ENV_SNAPSHOT_SCRIPT}; the per-configuration environment check cannot run. Nothing was measured."
    fi
else
    set +e
    "$PYTHON_BIN" "$ENV_SNAPSHOT_SCRIPT" check \
        --baseline "$ENV_BASELINE" \
        --ollama-url "$OLLAMA_URL" \
        --service-url "$SERVICE_URL" \
        --ollama-env-file "$OLLAMA_ENV_FILE" \
        --jmeter-version "$JMETER_VERSION" \
        --json > "$ENV_CHECK_JSON"
    ENV_STATUS=$?
    set -e
    case "$ENV_STATUS" in
        0)
            ENV_CHECK_OK="true"
            log "  unchanged from the baseline"
            ;;
        1)
            ENV_CHECK_OK="false"
            printf '%s: the environment differs from %s:\n' "$SCRIPT_NAME" "$(rel_path "$ENV_BASELINE")" >&2
            sed 's/^/  /' "$ENV_CHECK_JSON" >&2 || true
            if (( DEV )); then
                warn "environment changed (allowed in --dev only; see above)"
            else
                die_fail "software versions, model digests or Ollama settings changed since the baseline (diff above). Configurations measured under different settings cannot be compared (brief, Set-up). Nothing was measured for ${CONFIG}."
            fi
            ;;
        *)
            ENV_CHECK_OK=""
            if (( DEV )); then
                warn "a2_env_snapshot.py could not check the environment (exit ${ENV_STATUS}); continuing (--dev)"
            else
                sed 's/^/  /' "$ENV_CHECK_JSON" >&2 || true
                die_fail "a2_env_snapshot.py could not check the environment (exit ${ENV_STATUS}; see above). An unchecked environment is not evidence. Nothing was measured for ${CONFIG}."
            fi
            ;;
    esac
fi

# ---------------------------------------------------------------------------
# Step C: once per run
# ---------------------------------------------------------------------------
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FAILED_RUNS=()
RUN_DIRS=()
# Every request_id already filed in one of this invocation's run directories, so
# that the next run's slice (whose margin can reach back into this run) does not
# copy the same line into a second run directory.
CLAIMED_IDS="${WORK_DIR}/claimed_request_ids.txt"
: > "$CLAIMED_IDS"

# The warm-up bodies are the same for every run: the same three tickets every
# time (brief, "Each run").
WARMUP_ROWS_TEXT="$(a2py warmup-bodies "$WARMUP_CSV" "$WORK_DIR" "$WARMUP_COUNT")" \
    || die_fail "could not build the warm-up request bodies from $WARMUP_CSV"
WARMUP_ROW_ARR=()
while IFS= read -r row; do
    [[ -n "$row" ]] && WARMUP_ROW_ARR+=("$row")
done <<EOF_WARMUP_ROWS
$WARMUP_ROWS_TEXT
EOF_WARMUP_ROWS
WARMUP_ROWS_CSV="$(IFS=,; printf '%s' "${WARMUP_ROW_ARR[*]}")"

# Notes common to every run of this invocation.
STANDING_NOTE="rate label=${RATE_LABEL}; pause_s=${PAUSE_S}; response_timeout_ms=${TIMEOUT_MS}; ${OVERRIDES:+arrival-file overrides: ${OVERRIDES}; }warm-up = ${WARMUP_COUNT} fixed dev tickets (rows ${WARMUP_ROWS_CSV}), excluded from service.jsonl; own GET /stats calls in stats_calls.jsonl; slice margin ${SLICE_MARGIN_S}s; resident_models_after is read after the ${PAUSE_S}s pause, so a model Ollama unloaded after OLLAMA_KEEP_ALIVE of idleness in the pause is not a mid-run reload (check load_duration in service.jsonl for that)"
if (( DEV )); then
    STANDING_NOTE="${STANDING_NOTE}; dev: the warm-up rows are also the first rows of the dev input, so the first measured samples repeat warm-up prompts"
fi

for (( RUN_INDEX = 1; RUN_INDEX <= RUNS; RUN_INDEX++ )); do
    RUN_ID="${STAMP}_${CONFIG_SAFE}_${PLAN_NAME}_${RATE_LABEL}_run${RUN_INDEX}"
    RUN_DIR="${OUT_ROOT}/${RUN_ID}"
    step "Run ${RUN_INDEX} of ${RUNS}: ${RUN_ID}"
    mkdir -p "$RUN_DIR"
    RUN_DIRS+=("$RUN_DIR")
    cp "$GATE_JSON" "${RUN_DIR}/gate.json"
    [[ -f "$ENV_CHECK_JSON" ]] && cp "$ENV_CHECK_JSON" "${RUN_DIR}/env_check.json"
    [[ -f "$OLLAMA_ENV_FILTERED" ]] && cp "$OLLAMA_ENV_FILTERED" "${RUN_DIR}/ollama_env.txt"
    RUN_NOTE_EXTRA=""
    MEASURED=0
    LARGE_DIRECT=0
    STARTED_AT=""
    ENDED_AT=""
    JTL_SAMPLES=""
    JTL_DISTINCT=""
    WARMUP_IDS=()

    # --- 1: restart Ollama --------------------------------------------------
    # Brief, "Each run": this clears Ollama's prompt cache, and no model is
    # loaded afterwards. `restart`, not `up --force-recreate`: the container's
    # definition (and so every Ollama setting) is untouched.
    log "  [1/11] restart the Ollama container (clears its prompt cache; no model loaded)"
    compose restart "$OLLAMA_SERVICE"
    wait_for_ollama || die_fail "Ollama did not answer ${OLLAMA_URL}/api/version within ${HEALTH_TIMEOUT_S}s of the restart. Nothing was measured. Check: compose logs ${OLLAMA_SERVICE}"
    log "      Ollama is up (${OLLAMA_URL}/api/version)"

    # --- 2: reset the database and recreate triage in this configuration ----
    log "  [2/11] reset the database; recreate triage as ${CONFIG}"
    reset_service
    compose up -d --force-recreate --no-deps "$TRIAGE_SERVICE"

    # --- 3: /health must confirm the configuration --------------------------
    log "  [3/11] wait for /health to confirm the configuration"
    if ! wait_for_health "${RUN_DIR}/health.json"; then
        die_fail "the service never confirmed config '${CONFIG}' with Ollama reachable. Nothing was measured. Check: compose logs ${TRIAGE_SERVICE}"
    fi
    log "      /health: model_tag ${WANT_MODEL}, service_mode ${WANT_MODE}${WANT_SETTING:+, Setting ${WANT_SETTING}, small ${WANT_SMALL}}, Ollama reachable"

    # --- 4: three fixed warm-up tickets ---------------------------------------
    log "  [4/11] warm-up: ${WARMUP_COUNT} fixed tickets, one at a time (excluded from analysis)"
    for (( w = 1; w <= WARMUP_COUNT; w++ )); do
        WARMUP_ROW="${WARMUP_ROW_ARR[$(( w - 1 ))]}"
        WARMUP_ID="warmup-$(new_uuid)"
        WARMUP_RESPONSE="${WORK_DIR}/warmup_response_run${RUN_INDEX}_${w}.json"
        WARMUP_CODE="$(curl -sS -o "$WARMUP_RESPONSE" -w '%{http_code}' \
            --max-time "$WARMUP_TIMEOUT_S" \
            -X POST "${SERVICE_URL}/tickets" \
            -H 'Content-Type: application/json' \
            -H "X-Request-ID: ${WARMUP_ID}" \
            -H "X-Source-Row: ${WARMUP_ROW}" \
            -H 'X-Warmup: 1' \
            --data-binary "@${WORK_DIR}/warmup_body_${w}.json" 2>/dev/null || true)"
        WARMUP_CODE="${WARMUP_CODE:-000}"
        if [[ "$WARMUP_CODE" != "200" ]]; then
            die_fail "warm-up ${w} of ${WARMUP_COUNT} (dev row ${WARMUP_ROW}) returned HTTP ${WARMUP_CODE}. Measuring now would charge the first samples with the model-load cost. Response: $(head -c 400 "$WARMUP_RESPONSE" 2>/dev/null || true)"
        fi
        WARMUP_IDS+=("$WARMUP_ID")
        log "      warm-up ${w}/${WARMUP_COUNT}: request_id ${WARMUP_ID} (dev row ${WARMUP_ROW}), HTTP 200"
    done
    for WARMUP_ID in "${WARMUP_IDS[@]}"; do
        wait_for_log_line "$WARMUP_ID" || warn "the warm-up log line for ${WARMUP_ID} has not reached the mirror in $SERVICE_LOG_DIR yet"
    done
    if ! a2py collect-warmup "$SERVICE_LOG_DIR" "${RUN_DIR}/warmup.jsonl" "${WARMUP_IDS[@]}"; then
        die_fail "the warm-up requests did not all produce usable log lines; the service log is not readable at $SERVICE_LOG_DIR"
    fi

    # Brief: "For the cascade, warm up both models. Make sure the warm-up tickets
    # reach the large model too (... or send one directly to the large model)."
    if [[ "$WANT_MODE" == "cascade" ]]; then
        if a2py any-escalated "${RUN_DIR}/warmup.jsonl"; then
            log "      a warm-up ticket escalated, so the large model ${LARGE_MODEL} has been loaded by the service"
        else
            log "      no warm-up ticket escalated: loading the large model ${LARGE_MODEL} with one direct /api/generate call"
            SEED="$(a2py json-get "${RUN_DIR}/health.json" seed)"
            NUM_CTX="$(a2py json-get "${RUN_DIR}/health.json" num_ctx)"
            [[ "$SEED" =~ ^-?[0-9]+$ && "$NUM_CTX" =~ ^[0-9]+$ ]] \
                || die_fail "/health did not report a usable seed ('$SEED') and num_ctx ('$NUM_CTX') for the direct large-model warm-up"
            LARGE_BODY="${WORK_DIR}/large_warmup_body.json"
            LARGE_ROW="$(a2py large-warmup-body "$REPO_ROOT" "$WARMUP_CSV" "$LARGE_MODEL" "$SEED" "$NUM_CTX" "$LARGE_BODY")" \
                || die_fail "could not build the large-model warm-up prompt with service.prompt.build_prompt()"
            LARGE_RAW="${WORK_DIR}/large_warmup_response_run${RUN_INDEX}.json"
            LARGE_CODE="$(curl -sS -o "$LARGE_RAW" -w '%{http_code}' \
                --max-time "$WARMUP_TIMEOUT_S" \
                -X POST "${OLLAMA_URL}/api/generate" \
                -H 'Content-Type: application/json' \
                --data-binary "@${LARGE_BODY}" 2>/dev/null || true)"
            LARGE_CODE="${LARGE_CODE:-000}"
            a2py strip-context "$LARGE_RAW" "${RUN_DIR}/large_model_warmup.json" || true
            if [[ "$LARGE_CODE" != "200" ]]; then
                die_fail "the direct large-model warm-up (${LARGE_MODEL}, dev row ${LARGE_ROW}) returned HTTP ${LARGE_CODE}. Response: $(head -c 400 "$LARGE_RAW" 2>/dev/null || true)"
            fi
            LARGE_DIRECT=1
            RUN_NOTE_EXTRA="${RUN_NOTE_EXTRA}large model loaded by a direct Ollama call (dev row ${LARGE_ROW}; reply in large_model_warmup.json); "
            log "      ${LARGE_MODEL}: HTTP 200 (dev row ${LARGE_ROW}; reply kept in large_model_warmup.json)"
        fi
    fi
    # A short settle so the model-load work is finished and the window below
    # contains only measured traffic.
    sleep "$SETTLE_S"

    # --- 5: residency before the run -------------------------------------------
    # Brief: "run `ollama ps` in the container and confirm both models are
    # listed. Do not start the run until they are."
    log "  [5/11] residency: ollama ps must list ${EXPECTED_MODELS_CSV}"
    if ! capture_residency before; then
        if (( DEV )); then
            warn "${RUN_ID}: not every expected model is resident (allowed in --dev only)"
            RUN_NOTE_EXTRA="${RUN_NOTE_EXTRA}expected model(s) not all resident before the run (dev); "
        else
            warn "${RUN_ID}: not every expected model (${EXPECTED_MODELS_CSV}) is resident, so this run is NOT measured (brief: \"Do not start the run until they are\"). See ollama_ps_before.txt/.json."
            RUN_NOTE_EXTRA="${RUN_NOTE_EXTRA}NOT MEASURED: expected model(s) not all resident before the run; "
            FAILED_RUNS+=("$RUN_ID")
            printf '%s\n' "${WARMUP_IDS[@]}" >> "$CLAIMED_IDS"
            write_run_metadata
            continue
        fi
    fi

    # --- 6: GET /stats, before ---------------------------------------------------
    log "  [6/11] GET /stats (before)"
    STATS_BEFORE_ID="stats-before-$(new_uuid)"
    STATS_CODE="$(http_get "${SERVICE_URL}/stats" "${RUN_DIR}/stats_before.json" "$STATS_BEFORE_ID")"
    if [[ "$STATS_CODE" == "200" ]]; then
        log "      total = $(a2py json-get "${RUN_DIR}/stats_before.json" total)"
    else
        warn "${RUN_ID}: GET /stats (before) returned HTTP ${STATS_CODE}"
        RUN_NOTE_EXTRA="${RUN_NOTE_EXTRA}GET /stats before returned HTTP ${STATS_CODE}; "
    fi

    # --- 7: JMeter ----------------------------------------------------------------
    log "  [7/11] JMeter (non-GUI, open model arrivals; ~$(( DURATION + PAUSE_S ))s including the pause)"
    JMETER_PROPS=(
        # These two sample variables become extra columns in the CSV .jtl, which
        # is what lets analysis/reconcile.py join JMeter's samples to the
        # service's own log lines by request_id.
        "-Jsample_variables=request_id,source_row"
        "-Jhost=${HOST}"
        "-Jport=${PORT}"
        "-Jrate_per_min=${RATE}"
        "-Jduration_s=${DURATION}"
        "-Jpause_s=${PAUSE_S}"
        "-Jresponse_timeout_ms=${TIMEOUT_MS}"
        "-Jinput_csv=${INPUT_CSV}"
    )
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
    MEASURED=1

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
        read -r JTL_SAMPLES JTL_DISTINCT JTL_REPEATED <<EOF_JTL
$(a2py jtl-summary "${RUN_DIR}/results.jtl")
EOF_JTL
        log "      results.jtl: ${JTL_SAMPLES} sample(s), ${JTL_DISTINCT} distinct ticket(s)"
        # Brief/playbook: no ticket may repeat within a run (Ollama's prompt
        # cache), so more samples than the list holds, or a repeated row, makes
        # the run's latency suspect.
        if (( JTL_SAMPLES > WORKLOAD_SIZE )); then
            warn "${RUN_ID}: ${JTL_SAMPLES} samples but only ${WORKLOAD_SIZE} tickets in the list: tickets repeated, so their latency may be Ollama's prompt cache"
            RUN_NOTE_EXTRA="${RUN_NOTE_EXTRA}${JTL_SAMPLES} samples > ${WORKLOAD_SIZE} workload tickets: tickets repeated (prompt cache); "
            FAILED_RUNS+=("$RUN_ID")
        elif (( JTL_SAMPLES == WORKLOAD_SIZE )); then
            warn "${RUN_ID}: all ${WORKLOAD_SIZE} tickets were used, so arrivals after the last one were stopped by the CSV Data Set Config and the offered rate was not kept to the end of the run"
            RUN_NOTE_EXTRA="${RUN_NOTE_EXTRA}workload list exhausted (${JTL_SAMPLES} of ${WORKLOAD_SIZE}); later arrivals were not sent; "
            FAILED_RUNS+=("$RUN_ID")
        fi
        if [[ "$JTL_REPEATED" != "-" ]]; then
            warn "${RUN_ID}: source row(s) ${JTL_REPEATED} were sent more than once in this run"
            RUN_NOTE_EXTRA="${RUN_NOTE_EXTRA}repeated source rows ${JTL_REPEATED}; "
            FAILED_RUNS+=("$RUN_ID")
        fi
    else
        warn "${RUN_ID}: results.jtl is empty. Nothing was measured."
        RUN_NOTE_EXTRA="${RUN_NOTE_EXTRA}empty jtl; "
        JTL_SAMPLES=0
        FAILED_RUNS+=("$RUN_ID")
    fi

    # --- 8: GET /stats, after -------------------------------------------------------
    log "  [8/11] GET /stats (after)"
    STATS_AFTER_ID="stats-after-$(new_uuid)"
    STATS_CODE="$(http_get "${SERVICE_URL}/stats" "${RUN_DIR}/stats_after.json" "$STATS_AFTER_ID")"
    if [[ "$STATS_CODE" == "200" ]]; then
        log "      total = $(a2py json-get "${RUN_DIR}/stats_after.json" total)"
    else
        warn "${RUN_ID}: GET /stats (after) returned HTTP ${STATS_CODE}"
        RUN_NOTE_EXTRA="${RUN_NOTE_EXTRA}GET /stats after returned HTTP ${STATS_CODE}; "
    fi

    # --- 9: the service's own record of the same window --------------------------
    log "  [9/11] slice the service log into the run directory"
    if [[ -n "$SERVICE_SSH" ]]; then
        sleep 2
        sync_service_logs || warn "${RUN_ID}: rsync of the service host's logs/service failed"
    fi
    if ! a2py slice "$SERVICE_LOG_DIR" "$STARTED_AT" "$ENDED_AT" "$SLICE_MARGIN_S" \
            "${RUN_DIR}/service.jsonl" "${RUN_DIR}/warmup.jsonl" "${RUN_DIR}/stats_calls.jsonl" \
            "${STATS_BEFORE_ID},${STATS_AFTER_ID}" "$CLAIMED_IDS"; then
        warn "${RUN_ID}: no service log lines fall inside the measured window. Check SERVICE_LOG_DIR and that both machines' clocks are in sync (NTP)."
        RUN_NOTE_EXTRA="${RUN_NOTE_EXTRA}service log slice empty; "
        FAILED_RUNS+=("$RUN_ID")
    fi
    # This run's warm-up lines are in its warmup.jsonl even if they fell outside
    # the window, so they belong to no later run either.
    printf '%s\n' "${WARMUP_IDS[@]}" >> "$CLAIMED_IDS"

    # --- 10: residency after the run ----------------------------------------------
    log "  [10/11] residency after the run (evidence only)"
    if ! capture_residency after; then
        # Not a failure by itself: the check runs after the trailing pause, which
        # is longer than Ollama's default 5-minute keep-alive. A mid-run reload
        # shows as a large load_duration in service.jsonl (playbook section 5).
        RUN_NOTE_EXTRA="${RUN_NOTE_EXTRA}not all expected models resident after the pause; "
    fi

    # --- 11: metadata ---------------------------------------------------------------
    log "  [11/11] write metadata.json"
    write_run_metadata
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
step "Summary"
log "Wrote ${RUNS} run directory/ies under ${OUT_ROOT}"
log ""
log "Next steps (not run automatically):"
for dir in "${RUN_DIRS[@]}"; do
    log "  python analysis/reconcile.py --run-dir $(rel_path "$dir")"
done
log "  python analysis/summarise_load_a2.py --runs $(rel_path "$OUT_ROOT")"
log "  ...and record every run in docs/a2/run-log.md (docs/playbooks/cascade-test.md section 8)."
if (( ${#FAILED_RUNS[@]} )); then
    # Deduplicate: one run can accumulate several complaints.
    printf '%s: %d run(s) have incomplete or failed evidence:\n' "$SCRIPT_NAME" \
        "$(printf '%s\n' "${FAILED_RUNS[@]}" | sort -u | wc -l | tr -d ' ')" >&2
    printf '%s\n' "${FAILED_RUNS[@]}" | sort -u | sed 's/^/  /' >&2
    printf 'Do not report a run that is listed above until you have explained it (docs/playbooks/cascade-test.md sections 6-7).\n' >&2
    if (( DEV )); then
        log ""
        log "$DEV_BANNER"
    fi
    exit 1
fi
if (( DEV )); then
    log ""
    log "$DEV_BANNER"
fi
