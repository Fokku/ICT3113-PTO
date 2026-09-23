#!/usr/bin/env bash
#
# capture_env.sh -- record what this machine is, for Slide 7 (Test Environment).
#
# Owner: Part 1 -- Yeo Kai Yuan (technical core). Evidence consumer: Part 5.
#
# The brief requires us to describe the hardware and software of each machine
# (service, Ollama, load generator), to confirm that the load generator ran on a
# separate machine, and to say how our results scale to the client's deployment.
# That description has to be a captured fact rather than someone's recollection
# three weeks later, so this script is run ONCE PER MACHINE and its output is
# committed to docs/environment/<hostname>.txt.
#
# Usage:
#   scripts/capture_env.sh [--out-dir docs/environment] [--role service|ollama|loadgen|all]
#
# Design notes:
#   * Linux and macOS are both supported, because the team's machines differ.
#   * Every probe degrades gracefully: a missing tool is recorded as
#     "not installed" rather than aborting the capture. A half-written evidence
#     file is worse than a complete one with gaps in it.
#   * Ollama's version is read from the HTTP API when the CLI binary is absent,
#     which is the normal case on a machine that only runs the container.
#   * NOTHING here runs a model, times anything, or loads a model. It reads
#     versions and hardware facts only.
#
set -euo pipefail

# Resolve the repository root from this script's own location so the script works
# from any working directory (including a cron job or another machine's shell).
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"

DEFAULT_OUT_DIR="${REPO_ROOT}/docs/environment"
OUT_DIR="${DEFAULT_OUT_DIR}"
ROLE="all"

# Where to ask about Ollama when the CLI is not installed on this machine.
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"

usage() {
    cat <<'USAGE'
capture_env.sh -- record this machine's hardware and software for Slide 7.

Usage:
  scripts/capture_env.sh [--out-dir DIR] [--role ROLE]

Options:
  --out-dir DIR   Directory to write <hostname>.txt into.
                  Default: docs/environment (inside the repository).
  --role ROLE     What this machine does in the test setup. One of:
                    service   runs the triage web service container
                    ollama    runs the Ollama model backend
                    loadgen   runs JMeter / the accuracy driver
                    all       runs everything (see the warning below)
                  Default: all.
  -h, --help      Print this help and exit.

Run it once on every machine involved in a test, then commit the results:
  scripts/capture_env.sh --role service   # on the service host
  scripts/capture_env.sh --role ollama    # on the Ollama host
  scripts/capture_env.sh --role loadgen   # on the load generator

The brief requires the load generator to run on a machine separate from the
system under test, so a capture with --role all is a warning sign and is
flagged as such in the output.

Environment variables:
  OLLAMA_BASE_URL   Where to ask for Ollama's version when the CLI is absent
                    (default http://localhost:11434).
  JMETER_HOME       Consulted if 'jmeter' is not on PATH.
USAGE
}

die() { printf 'capture_env.sh: %s\n' "$*" >&2; exit 2; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --out-dir)
            [[ $# -ge 2 ]] || die "--out-dir needs a value"
            OUT_DIR="$2"; shift 2 ;;
        --out-dir=*) OUT_DIR="${1#*=}"; shift ;;
        --role)
            [[ $# -ge 2 ]] || die "--role needs a value"
            ROLE="$2"; shift 2 ;;
        --role=*) ROLE="${1#*=}"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "unknown argument: $1" ;;
    esac
done

case "$ROLE" in
    service|ollama|loadgen|all) : ;;
    *) die "--role must be one of service, ollama, loadgen, all (got '$ROLE')" ;;
esac

# ---------------------------------------------------------------------------
# Small probe helpers. Each one prints a value or the literal "not installed",
# and none of them may abort the script.
# ---------------------------------------------------------------------------

have() { command -v "$1" >/dev/null 2>&1; }

# field <label> <value...>
field() { printf '%-24s: %s\n' "$1" "${2-}"; }

# first_line: collapse a command's output to its first non-empty line.
first_line() { awk 'NF {print; exit}'; }

# probe <label> <command...> -- run the command, print its first line, or note
# that the tool is missing. Never fails.
probe() {
    local label="$1"; shift
    if ! have "$1"; then
        field "$label" "not installed"
        return 0
    fi
    local out=""
    out="$("$@" 2>/dev/null | first_line || true)"
    field "$label" "${out:-present, version not reported}"
}

# sysctl_value <key> -- macOS hardware facts.
sysctl_value() {
    local out=""
    out="$(sysctl -n "$1" 2>/dev/null || true)"
    printf '%s' "${out:-unknown}"
}

# lscpu_value <label> -- one field from lscpu, by exact label.
lscpu_value() {
    local out=""
    out="$(lscpu 2>/dev/null | awk -F': *' -v want="$1" '$1 == want {print $2; exit}' || true)"
    printf '%s' "${out:-unknown}"
}

human_kib() {       # human_kib <kibibytes>
    awk -v kib="${1:-0}" 'BEGIN { if (kib+0 == 0) { print "unknown"; exit }
        printf "%.1f GiB (%d kB)", kib/1048576, kib }'
}

human_bytes() {     # human_bytes <bytes>
    awk -v b="${1:-0}" 'BEGIN { if (b+0 == 0) { print "unknown"; exit }
        printf "%.1f GiB (%d bytes)", b/1073741824, b }'
}

HOST_NAME="$(hostname 2>/dev/null || uname -n 2>/dev/null || echo unknown-host)"
# Keep the filename safe on every platform: only letters, digits, dot, dash, _.
SAFE_HOST="$(printf '%s' "$HOST_NAME" | tr -c 'A-Za-z0-9._-' '-' | sed 's/-\{2,\}/-/g; s/^-//; s/-$//')"
[[ -n "$SAFE_HOST" ]] || SAFE_HOST="unknown-host"

CAPTURED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
KERNEL_NAME="$(uname -s 2>/dev/null || echo unknown)"

mkdir -p "$OUT_DIR"
OUT_FILE="${OUT_DIR%/}/${SAFE_HOST}.txt"

# Build into a temporary file and move it into place, so an interrupted capture
# never leaves a truncated evidence file behind.
TMP_FILE="$(mktemp "${TMPDIR:-/tmp}/capture_env.XXXXXX")"
cleanup() { rm -f "$TMP_FILE"; }
trap cleanup EXIT

{
    echo "============================================================================"
    echo "ICT3113 Assignment 1 (Team 10) -- test environment capture"
    echo "============================================================================"
    field "Host" "$HOST_NAME"
    field "Declared role" "$ROLE"
    field "Captured at (UTC)" "$CAPTURED_AT"
    field "Captured by" "scripts/capture_env.sh"
    echo
    echo "This file is generated evidence for Slide 7 (Test Environment) and for the"
    echo "service_host_info / load_generator_host_info fields of every run's"
    echo "metadata.json. It is regenerated in place, so do NOT hand-edit it: record"
    echo "the narrative (network between the machines, anything that could make the"
    echo "measurements unrepresentative, how results scale to the client) in the Part 5"
    echo "test-environment playbook and cite this file from there."
    echo
    if [[ "$ROLE" == "all" ]]; then
        echo "WARNING: role 'all' declares that this one machine runs the service, the"
        echo "model backend and the load generator together. The brief does not accept"
        echo "latency measured with a co-hosted load generator, because the generator"
        echo "steals CPU from the service. If that is not what this machine does,"
        echo "re-run with the correct --role."
        echo
    fi
} > "$TMP_FILE"

# --- 1. Operating system ---------------------------------------------------
{
    echo "-- 1. Operating system -----------------------------------------------------"
    field "uname -s" "$(uname -s 2>/dev/null || echo unknown)"
    field "uname -r (kernel)" "$(uname -r 2>/dev/null || echo unknown)"
    field "uname -m (arch)" "$(uname -m 2>/dev/null || echo unknown)"
    case "$KERNEL_NAME" in
        Linux)
            if [[ -r /etc/os-release ]]; then
                # shellcheck disable=SC1091
                distro="$(. /etc/os-release 2>/dev/null && printf '%s' "${PRETTY_NAME:-${NAME:-unknown}}")"
                field "Distribution" "${distro:-unknown}"
            else
                field "Distribution" "unknown (/etc/os-release not readable)"
            fi
            field "libc" "$(getconf GNU_LIBC_VERSION 2>/dev/null || echo unknown)"
            if [[ -r /proc/1/cgroup ]] && grep -qE 'docker|containerd|kubepods' /proc/1/cgroup 2>/dev/null; then
                field "Container" "this capture is running INSIDE a container"
            fi
            ;;
        Darwin)
            field "macOS version" "$(sw_vers -productVersion 2>/dev/null || echo unknown)"
            field "macOS build" "$(sw_vers -buildVersion 2>/dev/null || echo unknown)"
            field "Hardware model" "$(sysctl_value hw.model)"
            ;;
        *)
            field "Note" "unrecognised kernel; only uname facts were captured"
            ;;
    esac
    echo
} >> "$TMP_FILE"

# --- 2. CPU ----------------------------------------------------------------
# CPU detail matters more than usual here: all inference is CPU-only by client
# constraint, so the model's core count and vector extensions are the single
# biggest determinant of what we measure.
{
    echo "-- 2. CPU ------------------------------------------------------------------"
    case "$KERNEL_NAME" in
        Linux)
            if have lscpu; then
                field "Model name" "$(lscpu_value 'Model name')"
                field "Vendor" "$(lscpu_value 'Vendor ID')"
                field "Architecture" "$(lscpu_value 'Architecture')"
                field "Sockets" "$(lscpu_value 'Socket(s)')"
                field "Cores per socket" "$(lscpu_value 'Core(s) per socket')"
                field "Threads per core" "$(lscpu_value 'Thread(s) per core')"
                field "Logical CPUs" "$(lscpu_value 'CPU(s)')"
                field "CPU max MHz" "$(lscpu_value 'CPU max MHz')"
                field "L3 cache" "$(lscpu_value 'L3 cache')"
                field "Virtualisation" "$(lscpu_value 'Hypervisor vendor')"
                # Vector extensions available to the inference runtime.
                flags="$(lscpu 2>/dev/null | awk -F': *' '$1 == "Flags" {print $2; exit}' || true)"
                present=""
                for ext in avx avx2 avx512f avx_vnni f16c fma; do
                    case " $flags " in *" $ext "*) present="${present}${ext} " ;; esac
                done
                field "Vector extensions" "${present:-none detected}"
            else
                field "lscpu" "not installed"
            fi
            field "nproc (online CPUs)" "$(nproc 2>/dev/null || echo unknown)"
            if [[ -r /proc/cpuinfo ]]; then
                field "/proc/cpuinfo model" \
                    "$(awk -F': ' '/^model name/ {print $2; exit}' /proc/cpuinfo 2>/dev/null || echo unknown)"
            fi
            ;;
        Darwin)
            field "Model name" "$(sysctl_value machdep.cpu.brand_string)"
            field "Physical cores" "$(sysctl_value hw.physicalcpu)"
            field "Logical cores" "$(sysctl_value hw.logicalcpu)"
            field "CPU family" "$(sysctl_value machdep.cpu.family)"
            field "Byte order/arch" "$(sysctl_value hw.byteorder) / $(uname -m 2>/dev/null || echo unknown)"
            field "Vector extensions" "$(sysctl_value machdep.cpu.features) $(sysctl_value machdep.cpu.leaf7_features)"
            ;;
        *)
            field "CPU" "unknown (unsupported platform)"
            ;;
    esac
    echo
} >> "$TMP_FILE"

# --- 3. Memory and storage -------------------------------------------------
{
    echo "-- 3. Memory and storage ---------------------------------------------------"
    case "$KERNEL_NAME" in
        Linux)
            mem_kib="$(awk '/^MemTotal:/ {print $2; exit}' /proc/meminfo 2>/dev/null || true)"
            field "Total RAM" "$(human_kib "${mem_kib:-0}")"
            swap_kib="$(awk '/^SwapTotal:/ {print $2; exit}' /proc/meminfo 2>/dev/null || true)"
            field "Total swap" "$(human_kib "${swap_kib:-0}")"
            ;;
        Darwin)
            field "Total RAM" "$(human_bytes "$(sysctl_value hw.memsize)")"
            ;;
    esac
    # Disk free where the repository lives: JMeter .jtl files and service logs
    # are kept for every reported run, so this is worth recording.
    if have df; then
        field "Repo filesystem" "$(df -h "$REPO_ROOT" 2>/dev/null | awk 'NR==2 {print $2" total, "$4" free on "$1" ("$6")"}' || echo unknown)"
    fi
    echo
} >> "$TMP_FILE"

# --- 4. Software versions --------------------------------------------------
{
    echo "-- 4. Software versions ----------------------------------------------------"
    probe "python3" python3 --version
    if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
        field "repo .venv python" "$("${REPO_ROOT}/.venv/bin/python" --version 2>&1 | first_line || true)"
    else
        field "repo .venv python" "not present on this machine"
    fi
    probe "docker" docker --version
    if have docker; then
        server="$(docker version --format '{{.Server.Version}}' 2>/dev/null || true)"
        field "docker server" "${server:-daemon not reachable from this shell}"
        compose="$(docker compose version 2>/dev/null | first_line || true)"
        if [[ -z "$compose" ]]; then
            # The legacy standalone binary is a different product; record which.
            compose="$(docker-compose --version 2>/dev/null | first_line || true)"
            [[ -n "$compose" ]] && compose="$compose (legacy standalone docker-compose)"
        fi
        field "docker compose" "${compose:-not installed}"
    else
        field "docker server" "not installed"
        field "docker compose" "not installed"
    fi
    probe "curl" curl --version
    probe "git" git --version
    echo
} >> "$TMP_FILE"

# --- 5. Model backend (Ollama) --------------------------------------------
{
    echo "-- 5. Model backend (Ollama) -----------------------------------------------"
    if have ollama; then
        field "ollama CLI" "$(ollama --version 2>&1 | first_line || true)"
    else
        field "ollama CLI" "not installed (normal on a machine that only runs the container)"
    fi
    field "OLLAMA_BASE_URL" "$OLLAMA_BASE_URL"
    api_version=""
    if have curl; then
        # --max-time keeps a capture on a machine with no Ollama fast; a missing
        # backend is a fact to record, not a reason to hang.
        api_version="$(curl -fsS --max-time 3 "${OLLAMA_BASE_URL}/api/version" 2>/dev/null || true)"
    fi
    if [[ -n "$api_version" ]]; then
        field "ollama /api/version" "$api_version"
    else
        field "ollama /api/version" "not reachable at ${OLLAMA_BASE_URL}"
    fi
    for var in OLLAMA_NUM_PARALLEL OLLAMA_MAX_LOADED_MODELS OLLAMA_NUM_THREADS OLLAMA_KEEP_ALIVE; do
        value="${!var-}"
        field "$var" "${value:-unset (Ollama default)}"
    done
    echo "Note: the candidate model tags and digests are pinned in models/models.yaml"
    echo "and are recorded again in every run's metadata.json; they are not captured"
    echo "here, because this file describes the machine and not the experiment."
    echo
} >> "$TMP_FILE"

# --- 6. Load generator (JMeter) -------------------------------------------
{
    echo "-- 6. Load generator (JMeter) ----------------------------------------------"
    jmeter_bin=""
    if have jmeter; then
        jmeter_bin="$(command -v jmeter)"
    elif [[ -n "${JMETER_HOME:-}" && -x "${JMETER_HOME}/bin/jmeter" ]]; then
        jmeter_bin="${JMETER_HOME}/bin/jmeter"
    fi
    if [[ -n "$jmeter_bin" ]]; then
        field "jmeter binary" "$jmeter_bin"
        # JMeter prints a banner around the version; pull out the first version-
        # shaped token rather than trying to parse the ASCII art.
        jver="$("$jmeter_bin" --version 2>&1 | grep -Eo '[0-9]+\.[0-9]+(\.[0-9]+)?' | first_line || true)"
        field "jmeter version" "${jver:-present, version not parsed}"
        field "java (used by JMeter)" "$( (java -version 2>&1 | first_line) || echo 'not installed' )"
    else
        field "jmeter binary" "not installed"
        field "jmeter version" "not installed"
        field "java" "$( (java -version 2>&1 | first_line) || echo 'not installed' )"
    fi
    field "JMETER_HOME" "${JMETER_HOME:-unset}"
    echo
} >> "$TMP_FILE"

# --- 7. Network addresses -------------------------------------------------
{
    echo "-- 7. Network ---------------------------------------------------------------"
    case "$KERNEL_NAME" in
        Linux)
            if have ip; then
                ip -4 -o addr show scope global 2>/dev/null \
                    | awk '{printf "%-24s: %s on %s\n", "IPv4 address", $4, $2}' || true
            elif have ifconfig; then
                ifconfig 2>/dev/null | awk '/inet /{printf "%-24s: %s\n", "IPv4 address", $2}' || true
            else
                field "IPv4 address" "no ip/ifconfig available"
            fi
            ;;
        Darwin)
            if have ifconfig; then
                ifconfig 2>/dev/null | awk '/inet /&&$2!="127.0.0.1"{printf "%-24s: %s\n", "IPv4 address", $2}' || true
            fi
            ;;
    esac
    echo
    echo "TODO(Part 5 -- Teammate D): describe the network between the machines"
    echo "  (link speed, switch or Wi-Fi, same subnet or not, anything shared with"
    echo "  other traffic) and anything that could make these measurements"
    echo "  unrepresentative of the client's deployment. Put it in the Part 5"
    echo "  test-environment section and cite this file. Do not write it here: this"
    echo "  file is regenerated."
    echo
} >> "$TMP_FILE"

# --- 8. Repository state ---------------------------------------------------
{
    echo "-- 8. Repository state -----------------------------------------------------"
    field "Repository path" "$REPO_ROOT"
    if have git && git -C "$REPO_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
        field "Commit" "$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
        field "Branch" "$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
        if [[ -n "$(git -C "$REPO_ROOT" status --porcelain 2>/dev/null || true)" ]]; then
            field "Working tree" "DIRTY (uncommitted changes at capture time)"
        else
            field "Working tree" "clean"
        fi
        field "golden-freeze tag" \
            "$(git -C "$REPO_ROOT" rev-parse -q --verify 'refs/tags/golden-freeze^{commit}' 2>/dev/null || echo 'not created yet')"
    else
        field "git" "not a repository (or git not installed)"
    fi
    echo
    echo "-- end of capture ----------------------------------------------------------"
} >> "$TMP_FILE"

mv "$TMP_FILE" "$OUT_FILE"
trap - EXIT

printf 'Wrote %s\n' "$OUT_FILE"
printf 'Role declared: %s. Re-run on every machine involved in a test.\n' "$ROLE"
