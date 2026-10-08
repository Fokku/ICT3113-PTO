#!/usr/bin/env bash
#
# run_analysis.sh -- every analysis step, over every run, into analysis/output/.
#
# Owner: Part 1 -- Yeo Kai Yuan (technical core).
#
# Runs the five analysis scripts in the order README section 7 prescribes, over
# every run directory that exists, and writes each one's output where the deck
# builder (slides/collect_deck_data.py) reads it:
#
#   reconcile        one call per run dir      -> analysis/output/reconcile/<run>__*.{csv,md}
#   summarise_load   all load/mixed runs       -> analysis/output/load/
#   accuracy         all accuracy runs         -> analysis/output/accuracy/
#   stress_summary   one call per stress run   -> analysis/output/stress/<run>/
#   bottleneck_hints one call per load/mixed/stress run -> analysis/output/bottleneck/<run>/
#
# It computes nothing itself. Every threshold is the requirement it tests
# (workload/requirements.md): p95 10 000 ms (R1), error rate 5% (R2). A non-zero
# exit from reconcile is reported in analysis/output/reconcile/SUMMARY.md and in
# this script's exit status: "a non-zero exit here must be fixed, not reported
# around" (TODO.md 1.8).
#
# Usage:
#   scripts/run_analysis.sh [--results results] [--out analysis/output]
#   scripts/run_analysis.sh --results results/dev --out /tmp/dev-analysis   # rehearsal
#
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
cd "$REPO_ROOT"

RESULTS="results"
OUT="analysis/output"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --results) RESULTS="$2"; shift 2 ;;
        --out)     OUT="$2"; shift 2 ;;
        -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
        *) echo "run_analysis.sh: unknown argument $1" >&2; exit 2 ;;
    esac
done

PY="${REPO_ROOT}/.venv/bin/python"
[[ -x "$PY" ]] || PY="$(command -v python3)"
P95_LIMIT_MS=10000
ERROR_RATE_LIMIT=0.05
STATUS=0

mkdir -p "$OUT"
shopt -s nullglob
RUN_DIRS=("$RESULTS"/runs/*_run[0-9]*)

# --- 1. reconcile every run -------------------------------------------------
mkdir -p "$OUT/reconcile"
{
    echo "# Reconciliation summary"
    echo
    echo "One row per run directory: \`analysis/reconcile.py\` joins the JMeter \`.jtl\` to the"
    echo "service log on \`request_id\`. Exit 0 means every sample matched and the two clocks agree."
    echo
    echo "| Run | Exit | Report |"
    echo "|---|---|---|"
} > "$OUT/reconcile/SUMMARY.md"
for run in "${RUN_DIRS[@]}"; do
    name="$(basename "$run")"
    set +e
    "$PY" analysis/reconcile.py --run-dir "$run" --out-dir "$OUT/reconcile" > "$OUT/reconcile/${name}__stdout.txt" 2>&1
    code=$?
    set -e
    echo "| \`$name\` | $code | \`${name}__report.md\` |" >> "$OUT/reconcile/SUMMARY.md"
    if (( code != 0 )); then
        echo "reconcile FAILED for $name (exit $code) -- see $OUT/reconcile/${name}__stdout.txt" >&2
        STATUS=1
    fi
done

# --- 2. load and mixed runs ---------------------------------------------------
if compgen -G "$RESULTS/runs/*_load_post_tickets_*" > /dev/null || compgen -G "$RESULTS/runs/*_mixed_load_*" > /dev/null; then
    "$PY" analysis/summarise_load.py --runs "$RESULTS/runs" --out-dir "$OUT/load" \
        || { echo "summarise_load FAILED" >&2; STATUS=1; }
fi

# --- 3. accuracy -----------------------------------------------------------
if compgen -G "$RESULTS/accuracy/*/responses.csv" > /dev/null; then
    "$PY" analysis/accuracy.py --results "$RESULTS/accuracy" --golden golden/golden_set.csv --out-dir "$OUT/accuracy" \
        || { echo "accuracy FAILED its sanity checks -- read $OUT/accuracy/accuracy_report.md" >&2; STATUS=1; }
fi

# --- 4. stress runs: the step boundaries come from the run's own metadata ----
for run in "$RESULTS"/runs/*_stress_ramp_ramp_run*; do
    name="$(basename "$run")"
    read -r start step steps step_s < <("$PY" - "$run/metadata.json" <<'PYEOF'
import json, re, sys
notes = json.load(open(sys.argv[1], encoding="utf-8")).get("notes", "")
def grab(key, default):
    m = re.search(rf"{key}=(\d+)", notes)
    return m.group(1) if m else default
print(grab("ramp_start_per_min", "1"), grab("ramp_step_per_min", "4"),
      grab("ramp_steps", "6"), grab("ramp_step_duration_s", "120"))
PYEOF
)
    rates="$("$PY" -c "print(','.join(str($start + k * $step) for k in range($steps)))")"
    mkdir -p "$OUT/stress/$name"
    "$PY" analysis/stress_summary.py --run-dir "$run" --step-seconds "$step_s" \
        --offered-rates "$rates" --p95-limit-ms "$P95_LIMIT_MS" \
        --error-rate-limit "$ERROR_RATE_LIMIT" --label "POST /tickets" --out-dir "$OUT/stress/$name" \
        || { echo "stress_summary FAILED for $name" >&2; STATUS=1; }
done

# --- 5. where the time went, per run ----------------------------------------
for run in "${RUN_DIRS[@]}"; do
    name="$(basename "$run")"
    mkdir -p "$OUT/bottleneck/$name"
    "$PY" analysis/bottleneck_hints.py --run-dir "$run" --out-dir "$OUT/bottleneck/$name" > /dev/null \
        || { echo "bottleneck_hints FAILED for $name" >&2; STATUS=1; }
done

echo "analysis written under $OUT ($([[ $STATUS -eq 0 ]] && echo every step passed || echo 'FAILURES: read the messages above'))"
exit "$STATUS"
