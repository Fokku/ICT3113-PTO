#!/usr/bin/env bash
#
# run_campaign.sh -- the whole post-freeze benchmark campaign, in one command.
#
# Owner: Part 1 -- Yeo Kai Yuan (technical core).
#
# It adds no measurement logic of its own. It calls the two sanctioned drivers,
# scripts/run_accuracy.py and scripts/run_load_test.sh, with exactly the
# parameters fixed in workload/workload_model.md ("Derived arrival rates for
# testing"), phase by phase across the candidate models:
#
#   1. accuracy for each model: switch the triage service to it, confirm /health
#               reports the digest pinned in models/models.yaml, then post every
#               golden-set ticket once (scripts/run_accuracy.py)
#   2. load     for each model, load_post_tickets at each rate in RATES,
#               DURATION_S each, RUNS runs
#   3. mixed    for each model, mixed_load at MIXED_RATE tickets/min +
#               SEARCH_RATE searches/min
#   4. stress   stress_ramp, once, for each model listed in STRESS_MODELS
#
# Resumable: a configuration that already has complete evidence for the current
# freeze commit is skipped, so the command can simply be re-run after an
# interruption. A configuration that stopped part-way (fewer than three complete
# run directories) is moved to results/excluded/ with the reason recorded, and
# run again in full -- three runs per configuration, never a top-up.
#
# Every command, its exit status and its wall-clock time go to
# results/campaign/campaign_<UTC stamp>.log, which is committed with the results.
# A failed configuration is logged and the campaign moves on; nothing is retried
# silently.
#
# Usage (from the load generator, after the freeze gate passes):
#   SERVICE_SSH=user@service-host TARGET_HOST=service-host \
#       scripts/run_campaign.sh [--models "llama3.2:1b qwen2.5:7b"] [--only accuracy|load|mixed|stress]
#   Rehearsal on synthetic tickets (no freeze needed, writes only under results/dev):
#   TARGET_HOST=... DURATION_S=60 RUNS=1 scripts/run_campaign.sh --dev
#
# Environment:
#   SERVICE_SSH     user@host of the service host (remote mode of both drivers);
#                   unset means the service runs under this machine's docker
#   SERVICE_REPO    checkout on the service host (default ICT3113-PTO)
#   TARGET_HOST     host name or address JMeter and the accuracy driver send to
#                   (deliberately not SERVICE_HOST: docker-compose.yml uses that
#                   name for the address uvicorn binds to inside the container)
#   TARGET_PORT     default 8000
#   JMETER_HOME     JMeter 5.6.x installation (or jmeter on PATH)
#   RATES           default "1 4 12"        (requests per minute)
#   DURATION_S      default 600
#   RUNS            default 3
#   MIXED_RATE      default 1;  SEARCH_RATE default 1
#   STRESS_MODELS   default "" (set to the tag(s) that get the stress ramp)
#   RAMP_START_PER_MIN, RAMP_STEP_PER_MIN, RAMP_STEPS, RAMP_STEP_DURATION_S
#                   defaults 1, 4, 6, 120 (workload_model.md); the stress run's
#                   --duration is RAMP_STEPS x RAMP_STEP_DURATION_S + 120 s drain
#
# Exit codes: 0 every configuration complete; 1 at least one failed;
#             2 misuse; 3 the freeze gate is closed.
#
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
cd "$REPO_ROOT"

SERVICE_SSH="${SERVICE_SSH:-}"
SERVICE_REPO="${SERVICE_REPO:-ICT3113-PTO}"
TARGET_HOST="${TARGET_HOST:-}"
TARGET_PORT="${TARGET_PORT:-8000}"
RATES="${RATES:-1 4 12}"
DURATION_S="${DURATION_S:-600}"
RUNS="${RUNS:-3}"
MIXED_RATE="${MIXED_RATE:-1}"
SEARCH_RATE="${SEARCH_RATE:-1}"
STRESS_MODELS="${STRESS_MODELS:-}"
RAMP_START_PER_MIN="${RAMP_START_PER_MIN:-1}"
RAMP_STEP_PER_MIN="${RAMP_STEP_PER_MIN:-4}"
RAMP_STEPS="${RAMP_STEPS:-6}"
RAMP_STEP_DURATION_S="${RAMP_STEP_DURATION_S:-120}"
HEALTH_TIMEOUT_S="${HEALTH_TIMEOUT_S:-300}"
export SERVICE_SSH SERVICE_REPO

MODELS_ARG=""
ONLY=""
DEV=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --models) MODELS_ARG="$2"; shift 2 ;;
        --only)   ONLY="$2"; shift 2 ;;
        --dev)    DEV=1; shift ;;
        -h|--help) sed -n '2,56p' "$0"; exit 0 ;;
        *) printf 'run_campaign.sh: unknown argument %s\n' "$1" >&2; exit 2 ;;
    esac
done
case "$ONLY" in ""|accuracy|load|mixed|stress) : ;; *) echo "--only must be accuracy|load|mixed|stress" >&2; exit 2 ;; esac
[[ -n "$TARGET_HOST" ]] || { echo "run_campaign.sh: set TARGET_HOST (the address JMeter sends to)" >&2; exit 2; }

PY="${REPO_ROOT}/.venv/bin/python"
[[ -x "$PY" ]] || PY="$(command -v python3)"

# The candidate tags, in models.yaml order, unless --models narrows them.
if [[ -n "$MODELS_ARG" ]]; then
    read -r -a MODELS <<< "$MODELS_ARG"
else
    read -r -a MODELS <<< "$("$PY" - <<'PY'
import yaml
with open("models/models.yaml", encoding="utf-8") as handle:
    data = yaml.safe_load(handle)
print(" ".join(entry["tag"] for entry in data["candidates"]))
PY
)"
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
if (( DEV )); then
    RESULTS_ROOT="results/dev"          # gitignored: a rehearsal is never evidence
    MODE="dev"
    DEV_FLAG=(--dev)
else
    RESULTS_ROOT="results"
    MODE="real"
    DEV_FLAG=()
fi
mkdir -p "${RESULTS_ROOT}/campaign"
CAMPAIGN_LOG="${RESULTS_ROOT}/campaign/campaign_${STAMP}.log"
FAILED=()

note() { printf '%s  %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$CAMPAIGN_LOG"; }

# Keep the load generator awake for the whole campaign (macOS); harmless elsewhere.
if command -v caffeinate >/dev/null 2>&1; then
    caffeinate -dims -w $$ &
fi

# --- the freeze gate, once, so that a closed gate stops everything at once ----
if (( DEV )); then
    FREEZE_COMMIT=""
else
    if ! "$PY" scripts/freeze_gate.py --json > /dev/null; then
        "$PY" scripts/freeze_gate.py >&2 || true
        exit 3
    fi
    FREEZE_COMMIT="$("$PY" scripts/freeze_gate.py --json | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["freeze_commit"])')"
fi

# svc <command...> -- run a command in the service host's checkout over ssh, or in
# this checkout when the service runs under this machine's docker.
svc() {
    if [[ -n "$SERVICE_SSH" ]]; then
        ssh -o BatchMode=yes -o ConnectTimeout=15 "$SERVICE_SSH" \
            "cd $(printf '%q' "$SERVICE_REPO") && $(printf '%q ' "$@")"
    else
        ( cd "$REPO_ROOT" && "$@" )
    fi
}

pinned_digest() {
    "$PY" - "$1" <<'PY'
import sys, yaml
with open("models/models.yaml", encoding="utf-8") as handle:
    data = yaml.safe_load(handle)
for entry in data["candidates"]:
    if entry["tag"] == sys.argv[1]:
        print((entry.get("pinned") or {}).get("digest") or "")
        break
PY
}

safe_tag() { printf '%s' "$1" | sed -e 's/[^A-Za-z0-9._-]\{1,\}/-/g' -e 's/^-*//' -e 's/-*$//'; }

# complete_runs <model> <plan> <rate label> -- run dirs with full evidence for
# this freeze commit, one per line.
complete_runs() {
    "$PY" - "$(safe_tag "$1")" "$2" "$3" "$FREEZE_COMMIT" "$MODE" "$RESULTS_ROOT" <<'PY'
import json, sys
from pathlib import Path
model, plan, rate, freeze, mode, root = sys.argv[1:7]
for run in sorted(Path(root, "runs").glob(f"*_{model}_{plan}_{rate}_run*")):
    meta = run / "metadata.json"
    jtl, log = run / "results.jtl", run / "service.jsonl"
    if not (meta.is_file() and jtl.is_file() and log.is_file()):
        print(f"INCOMPLETE {run}")
        continue
    data = json.loads(meta.read_text(encoding="utf-8"))
    if data.get("mode") != mode or (mode == "real" and data.get("freeze_commit") != freeze):
        continue
    lines = sum(1 for _ in jtl.open(encoding="utf-8")) - 1
    ok = lines > 0 and log.stat().st_size > 0 and "jmeter exit status" not in data.get("notes", "")
    print(("COMPLETE " if ok else "INCOMPLETE ") + str(run))
PY
}

# exclude_dirs <reason> <dir>... -- move incomplete evidence aside, never delete it.
exclude_dirs() {
    local reason="$1"; shift
    local dir dest
    for dir in "$@"; do
        dest="${RESULTS_ROOT}/excluded/$(basename "$(dirname "$dir")")"
        mkdir -p "$dest"
        mv "$dir" "$dest/"
        printf -- '- `%s/%s` -- %s (moved by run_campaign.sh, %s)\n' \
            "$dest" "$(basename "$dir")" "$reason" "$STAMP" >> "${RESULTS_ROOT}/excluded/EXCLUDED.md"
        note "excluded $dir: $reason"
    done
}

# run_step <name> <command...> -- run, log, time; never abort the campaign.
run_step() {
    local name="$1"; shift
    local started=$SECONDS status
    note "START $name :: $*"
    set +e
    "$@" >> "$CAMPAIGN_LOG" 2>&1
    status=$?
    set -e
    if (( status == 0 )); then
        note "DONE  $name ($(( SECONDS - started ))s)"
    else
        note "FAIL  $name (exit $status after $(( SECONDS - started ))s)"
        FAILED+=("$name")
    fi
    return 0
}

switch_model() {
    local model="$1" digest health_json deadline
    digest="$(pinned_digest "$model")"
    note "switch service to $model (pinned digest ${digest:-NONE})"
    if [[ -z "$digest" ]] && (( ! DEV )); then
        note "FAIL  switch $model: no pinned digest in models/models.yaml"
        return 1
    fi
    svc env "MODEL_TAG=${model}" docker compose -f docker-compose.yml up -d ollama >> "$CAMPAIGN_LOG" 2>&1
    svc env "MODEL_TAG=${model}" docker compose -f docker-compose.yml up -d --force-recreate --no-deps triage >> "$CAMPAIGN_LOG" 2>&1
    deadline=$(( SECONDS + HEALTH_TIMEOUT_S ))
    while (( SECONDS < deadline )); do
        health_json="$(curl -s --max-time 10 "http://${TARGET_HOST}:${TARGET_PORT}/health" || true)"
        if "$PY" - "$model" "$digest" "$health_json" <<'PY'
import json, sys
model, digest, raw = sys.argv[1:4]
try:
    health = json.loads(raw)
except json.JSONDecodeError:
    raise SystemExit(1)
ok = (health.get("model_tag") == model and health.get("ollama_reachable")
      and health.get("status") == "ok")
if ok and digest and health.get("model_digest") not in (digest, f"sha256:{digest}", digest.removeprefix("sha256:")):
    print(f"DIGEST MISMATCH: /health {health.get('model_digest')} vs pinned {digest}", file=sys.stderr)
    raise SystemExit(2)
raise SystemExit(0 if ok else 1)
PY
        then
            note "service is serving $model with the pinned digest"
            return 0
        elif (( $? == 2 )); then
            note "FAIL  switch $model: digest reported by /health differs from the pin"
            return 1
        fi
        sleep 3
    done
    note "FAIL  switch $model: /health never reported it within ${HEALTH_TIMEOUT_S}s"
    return 1
}

load_config() {
    local model="$1" plan="$2" label="$3"; shift 3
    local -a lines complete=() incomplete=()
    mapfile -t lines < <(complete_runs "$model" "$plan" "$label")
    local line
    for line in "${lines[@]}"; do
        case "$line" in
            COMPLETE*)   complete+=("${line#COMPLETE }") ;;
            INCOMPLETE*) incomplete+=("${line#INCOMPLETE }") ;;
        esac
    done
    if (( ${#complete[@]} >= RUNS && ${#incomplete[@]} == 0 )); then
        note "skip  $model $plan $label: ${#complete[@]} complete run(s) already"
        return 0
    fi
    if (( ${#complete[@]} + ${#incomplete[@]} > 0 )); then
        exclude_dirs "partial configuration (${#complete[@]} complete, ${#incomplete[@]} incomplete of ${RUNS}); re-run in full" \
            "${complete[@]}" "${incomplete[@]}"
    fi
    run_step "$model $plan $label" "$@"
}

note "campaign $STAMP ($MODE): models=(${MODELS[*]}) rates=($RATES) duration=${DURATION_S}s runs=$RUNS freeze=${FREEZE_COMMIT:-none}"
note "service http://${TARGET_HOST}:${TARGET_PORT} via ${SERVICE_SSH:-local docker}; stress models=(${STRESS_MODELS:-none})"

COMMON=(--host "$TARGET_HOST" --port "$TARGET_PORT" --duration "$DURATION_S" --runs "$RUNS" --yes ${DEV_FLAG[@]+"${DEV_FLAG[@]}"})
[[ -n "${JMETER_HOME:-}" ]] && COMMON+=(--jmeter-home "$JMETER_HOME")

# Phase by phase rather than model by model: if the campaign is cut short, every
# model already has its accuracy and steady-state load results, which is what
# requirements R1-R4 are judged on. Each load run switches the model itself
# (reset + recreate with MODEL_TAG), and its warm-up pays any model-load cost.

accuracy_done() {
    compgen -G "${RESULTS_ROOT}/accuracy/$(safe_tag "$1")_*/metadata.json" > /dev/null || return 1
    "$PY" - "$(safe_tag "$1")" "$FREEZE_COMMIT" "$MODE" "$RESULTS_ROOT" <<'PY'
import json, sys
from pathlib import Path
safe, freeze, mode, root = sys.argv[1:5]
for meta in Path(root, "accuracy").glob(f"{safe}_*/metadata.json"):
    data = json.loads(meta.read_text(encoding="utf-8"))
    if (data.get("mode") == mode and (mode == "dev" or data.get("freeze_commit") == freeze)
            and "posted=" in data.get("notes", "")):
        raise SystemExit(0)
raise SystemExit(1)
PY
}

if [[ -z "$ONLY" || "$ONLY" == "accuracy" ]]; then
    for model in "${MODELS[@]}"; do
        if accuracy_done "$model"; then
            note "skip  $model accuracy: a complete run exists for this freeze"
        elif switch_model "$model"; then
            run_step "$model accuracy" "$PY" scripts/run_accuracy.py --model "$model" \
                --host "$TARGET_HOST" --port "$TARGET_PORT" ${DEV_FLAG[@]+"${DEV_FLAG[@]}"}
        else
            FAILED+=("$model switch")
        fi
    done
fi

if [[ -z "$ONLY" || "$ONLY" == "load" ]]; then
    for model in "${MODELS[@]}"; do
        for rate in $RATES; do
            load_config "$model" load_post_tickets "${rate}pm" \
                scripts/run_load_test.sh --plan load_post_tickets --model "$model" --rate "$rate" "${COMMON[@]}"
        done
    done
fi

if [[ -z "$ONLY" || "$ONLY" == "mixed" ]]; then
    for model in "${MODELS[@]}"; do
        load_config "$model" mixed_load "${MIXED_RATE}pm" \
            scripts/run_load_test.sh --plan mixed_load --model "$model" --rate "$MIXED_RATE" \
            --search-rate "$SEARCH_RATE" "${COMMON[@]}"
    done
fi

if [[ -z "$ONLY" || "$ONLY" == "stress" ]]; then
    # Six literal steps (the .jmx cannot loop a schedule) plus the drain.
    STRESS_DURATION=$(( 6 * RAMP_STEP_DURATION_S + ${DRAIN_S:-150} ))
    for model in $STRESS_MODELS; do
        RUNS_SAVED="$RUNS"; RUNS=1
        load_config "$model" stress_ramp ramp \
            env RAMP_STEP_PER_MIN="$RAMP_STEP_PER_MIN" RAMP_STEPS="$RAMP_STEPS" \
                RAMP_STEP_DURATION_S="$RAMP_STEP_DURATION_S" RAMP_START_PER_MIN="$RAMP_START_PER_MIN" \
            scripts/run_load_test.sh --plan stress_ramp --model "$model" --rate "$RAMP_START_PER_MIN" \
                --host "$TARGET_HOST" --port "$TARGET_PORT" --duration "$STRESS_DURATION" --runs 1 --yes \
                ${JMETER_HOME:+--jmeter-home "$JMETER_HOME"} ${DEV_FLAG[@]+"${DEV_FLAG[@]}"}
        RUNS="$RUNS_SAVED"
    done
fi

# One last mirror of the service host's log, so logs/service holds every line.
if [[ -n "$SERVICE_SSH" ]]; then
    rsync -a -e "ssh -o BatchMode=yes -o ConnectTimeout=15" \
        "${SERVICE_SSH}:${SERVICE_REPO%/}/logs/service/" "logs/service/" >> "$CAMPAIGN_LOG" 2>&1 || true
fi

if (( ${#FAILED[@]} )); then
    note "CAMPAIGN FINISHED WITH FAILURES: ${FAILED[*]}"
    exit 1
fi
note "CAMPAIGN COMPLETE"
