#!/usr/bin/env bash
#
# run_a2_campaign.sh -- TODO_A2.md §1.5 ("After the A2 gate passes -- run everything") in order.
#
# Owner: Part 1 -- Yeo Kai Yuan (technical core).
#
# Two phases, because the brief puts a decision between them ("Do the accuracy
# test first. Then speed-test every configuration that passes both accuracy
# limits, and the cascade in all cases"):
#
#   accuracy  The cascade at Setting A, then Setting B, on the 101 test rows
#             (scripts/run_accuracy_a2.py). Single-model accuracy is NOT re-run:
#             it is reused from Assignment 1 (brief, Step 4) and scored by Part 3.
#             Part 3 then scores everything and hands back the pass/fail table.
#   speed     Three runs each (scripts/run_load_test_a2.sh): qwen2.5:7b alone first
#             (the required reference), then every other single model that passed
#             both limits (--singles, from Part 3's table), then cascade-A and
#             cascade-B whether or not they passed. Then reconcile every new run and
#             summarise (analysis/summarise_load_a2.py).
#
# Every step runs through the scripts that enforce the A2 gate themselves; this
# wrapper checks the gate first too, and stops at the first failure. Nothing is
# re-run automatically: a failed run is kept and explained (playbook section 6).
#
# Usage (from the load generator, which the brief requires to be a separate machine):
#   SERVICE_SSH=user@service-host SERVICE_REPO=ICT3113-PTO \
#     scripts/run_a2_campaign.sh accuracy --small-model <tag> --host <service-host>
#   SERVICE_SSH=user@service-host SERVICE_REPO=ICT3113-PTO \
#     scripts/run_a2_campaign.sh speed --small-model <tag> --host <service-host> \
#       --singles "granite4:3b"            # the OTHER single models that passed; may be ""
#   ... add --dry-run to print the plan without touching anything, --yes to skip the prompt.
#
# Exit codes: 0 done; 1 a step failed; 2 misuse; 3 the A2 gate is blocked.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
REFERENCE="qwen2.5:7b"

die() { printf 'run_a2_campaign.sh: %s\n' "$2" >&2; exit "$1"; }
usage() { sed -n '2,32p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

PHASE="${1:-}"
[[ "$PHASE" == "-h" || "$PHASE" == "--help" ]] && { usage; exit 0; }
[[ "$PHASE" == "accuracy" || "$PHASE" == "speed" ]] || { usage >&2; die 2 "first argument must be 'accuracy' or 'speed'"; }
shift

SMALL=""; HOST=""; PORT="8000"; SINGLES=""; SINGLES_SET=0; DRY=0; YES=0; LARGE="$REFERENCE"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --small-model) SMALL="${2:-}"; shift 2 ;;
        --large-model) LARGE="${2:-}"; shift 2 ;;
        --host)        HOST="${2:-}"; shift 2 ;;
        --port)        PORT="${2:-}"; shift 2 ;;
        --singles)     SINGLES="${2-}"; SINGLES_SET=1; shift 2 ;;
        --dry-run)     DRY=1; shift ;;
        --yes|-y)      YES=1; shift ;;
        -h|--help)     usage; exit 0 ;;
        *) die 2 "unknown argument: $1" ;;
    esac
done
[[ -n "$SMALL" ]] || die 2 "--small-model is required (the pair in cascade/escalation_rule.md section 1)"
[[ -n "$HOST" ]]  || die 2 "--host is required (the service host; the load generator must be a separate machine)"
if [[ "$PHASE" == "speed" && $SINGLES_SET -eq 0 ]]; then
    die 2 "--singles is required for the speed phase: the single models OTHER than ${REFERENCE} that passed both accuracy limits in Part 3's table (pass \"\" if none did). ${REFERENCE} is always run."
fi

PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
[[ -x "$PYTHON_BIN" ]] || PYTHON_BIN="$(command -v python3)"
SERVICE_URL="http://${HOST}:${PORT}"

run() {
    printf '+ %s\n' "$*"
    (( DRY )) && return 0
    "$@"
}

# switch_service <service mode> <setting> -- recreate triage in that configuration,
# on the service host (over ssh when SERVICE_SSH is set), then wait for /health.
switch_service() {
    local mode="$1" setting="$2"
    local -a envs=("MODEL_TAG=${LARGE}" "SERVICE_MODE=${mode}" "CASCADE_SETTING=${setting}" "CASCADE_SMALL_MODEL_TAG=${SMALL}")
    if [[ -n "${SERVICE_SSH:-}" ]]; then
        run ssh -n -o BatchMode=yes "$SERVICE_SSH" \
            "cd $(printf '%q' "${SERVICE_REPO:-ICT3113-PTO}") && env $(printf '%q ' "${envs[@]}")docker compose -f docker-compose.yml up -d --force-recreate --no-deps triage"
    else
        run env "${envs[@]}" docker compose -f "${REPO_ROOT}/docker-compose.yml" up -d --force-recreate --no-deps triage
    fi
    (( DRY )) && return 0
    local deadline=$(( $(date +%s) + 240 ))
    while [[ $(date +%s) -lt $deadline ]]; do
        if curl -fsS --max-time 10 "${SERVICE_URL}/health" 2>/dev/null | "$PYTHON_BIN" -c '
import json, sys
h = json.load(sys.stdin)
ok = (h.get("status") == "ok" and h.get("service_mode") == sys.argv[1]
      and (h.get("cascade_setting") or "") == sys.argv[2])
sys.exit(0 if ok else 1)' "$mode" "$setting"; then
            printf '  /health confirms %s %s\n' "$mode" "$setting"
            return 0
        fi
        sleep 3
    done
    die 1 "the service at ${SERVICE_URL} never confirmed SERVICE_MODE=${mode} CASCADE_SETTING=${setting}"
}

# --- the gate, before anything else ---------------------------------------
printf '== A2 gate\n'
if (( DRY )); then
    printf '+ %s scripts/a2_gate.py --json   (dry run: not checked)\n' "$PYTHON_BIN"
else
    "$PYTHON_BIN" "${REPO_ROOT}/scripts/a2_gate.py" --json > /dev/null || exit 3
    printf '  PASS\n'
fi

# --- the plan -------------------------------------------------------------
CONFIGS=()
if [[ "$PHASE" == "accuracy" ]]; then
    CONFIGS=(cascade-A cascade-B)
else
    CONFIGS=("$REFERENCE")
    for tag in $SINGLES; do
        [[ "$tag" == "$REFERENCE" ]] && continue
        grep -q "tag: \"${tag}\"" "${REPO_ROOT}/models/models.yaml" || die 2 "'$tag' is not a pinned candidate in models/models.yaml"
        CONFIGS+=("$tag")
    done
    CONFIGS+=(cascade-A cascade-B)
fi
printf '\n== Plan (%s phase): %s\n' "$PHASE" "${CONFIGS[*]}"
printf '   cascade pair: small %s, large %s; service %s\n' "$SMALL" "$LARGE" "$SERVICE_URL"
if [[ "$PHASE" == "speed" ]]; then
    printf '   three runs each, about %s minutes per run (docs/a2/arrival_rate.json)\n' \
        "$("$PYTHON_BIN" -c 'import json; d=json.load(open("'"${REPO_ROOT}"'/docs/a2/arrival_rate.json")); print(round((d["duration_s"]+d["pause_s"])/60 + 2))' 2>/dev/null || echo '?')"
fi
if (( ! DRY && ! YES )); then
    [[ -t 0 ]] || die 2 "not interactive and --yes not given"
    printf 'Proceed? [y/N] '; read -r reply
    [[ "$reply" =~ ^(y|Y|yes|YES)$ ]] || { printf 'Aborted; nothing changed.\n'; exit 0; }
fi

# --- accuracy ----------------------------------------------------------------
if [[ "$PHASE" == "accuracy" ]]; then
    for config in "${CONFIGS[@]}"; do
        printf '\n== Accuracy, test rows: %s\n' "$config"
        switch_service cascade "${config#cascade-}"
        run "$PYTHON_BIN" "${REPO_ROOT}/scripts/run_accuracy_a2.py" --config "$config" --rows test --host "$HOST" --port "$PORT" \
            || die 1 "the accuracy run for ${config} reported a failure (see above). Investigate before going on: an errored ticket counts as wrong and is never retried singly (prediction record section 4)."
    done
    printf '\nNext: Part 3 scores all configurations on the test rows:\n'
    printf '  python analysis/accuracy.py --results results/accuracy_a2 --out-dir analysis/output/accuracy_a2\n'
    printf 'then hands back the pass/fail table; run this script again with: speed --singles "<passing single models>"\n'
    exit 0
fi

# --- speed ---------------------------------------------------------------------
NEW_RUNS_MARK="$(mktemp)"
trap 'rm -f "$NEW_RUNS_MARK"' EXIT
for config in "${CONFIGS[@]}"; do
    printf '\n== Speed, 3 runs: %s\n' "$config"
    args=(--config "$config" --host "$HOST" --port "$PORT" --runs 3 --yes)
    [[ "$config" == cascade-* ]] && args+=(--small-model "$SMALL" --large-model "$LARGE")
    run "${REPO_ROOT}/scripts/run_load_test_a2.sh" "${args[@]}" \
        || die 1 "run_load_test_a2.sh reported a problem for ${config}. Read its summary, record it in docs/a2/run-log.md, and re-run only for a reason in docs/playbooks/cascade-test.md section 6."
done

printf '\n== Reconcile every new speed run\n'
fail=0
if (( ! DRY )); then
    while IFS= read -r dir; do
        "$PYTHON_BIN" "${REPO_ROOT}/analysis/reconcile.py" --run-dir "$dir" || fail=1
    done < <(find "${REPO_ROOT}/results/runs" -maxdepth 1 -type d -name '*_speed_a2_*' -newer "$NEW_RUNS_MARK" | sort)
else
    printf '+ %s analysis/reconcile.py --run-dir <each new results/runs/*_speed_a2_* dir>\n' "$PYTHON_BIN"
fi

printf '\n== Summarise\n'
run "$PYTHON_BIN" "${REPO_ROOT}/analysis/summarise_load_a2.py" --runs "${REPO_ROOT}/results/runs" \
    || fail=1
(( fail )) && die 1 "a reconcile or the summary reported a problem; see above"
printf '\nDone. Record every run in docs/a2/run-log.md; hand analysis/output/speed_a2/ to Parts 3 and 4.\n'
