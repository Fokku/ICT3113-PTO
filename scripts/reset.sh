#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# reset.sh — return the triage service to an empty database.
# Owner: Yeo Kai Yuan (Part 1 — baseline service)
#
# The brief says the service starts empty and tickets enter only through
# POST /tickets. Every measured run must therefore begin with an empty store: a
# GET /search over 3,000 leftover tickets from yesterday's run does a different
# amount of work from one over the 300 this run posted, and GET /stats would
# report counts that belong to no single run.
#
# What it does, in order:
#   1. stops and removes the triage container (so the volume is not in use),
#   2. deletes the named volume holding triage.db,
#   3. starts the triage container again and waits for it to report healthy.
#
# What it deliberately does NOT do:
#   * It does not touch the ollama_models volume. That volume holds several
#     gigabytes of pulled candidate models, and deleting it would force a re-pull
#     of every one of them before the next run.
#   * It does not delete anything under logs/. Those files are evidence: every
#     number we report has to reconcile with them, and the run scripts slice the
#     window they need out of them by timestamp.
#
# Usage:  scripts/reset.sh [--yes] [--project-name NAME]
# ---------------------------------------------------------------------------
set -euo pipefail

# Resolve the repository root from this script's own location, so the script works
# when invoked from any directory (and via a symlink or a relative path).
SCRIPT_PATH="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_PATH}/.." && pwd -P)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.yml"

# Must match `name:` in docker-compose.yml: Compose prefixes volume names with the
# project name, so the volume we delete is "<project>_<volume>".
DEFAULT_PROJECT_NAME="ict3113-triage"
DB_VOLUME_SUFFIX="triage_db"
SERVICE="triage"

# Seconds to wait for the restarted container to report healthy.
HEALTH_TIMEOUT_S=90

ASSUME_YES=0
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-${DEFAULT_PROJECT_NAME}}"

usage() {
    cat <<'USAGE'
Usage: scripts/reset.sh [--yes] [--project-name NAME]

Wipes the SQLite database volume so the triage service starts empty, then
restarts the service. Run this before every measured benchmark run.

Options:
  --yes                 Do not ask for confirmation. Required when running from a
                        script or a CI job, because there is no terminal to answer.
  --project-name NAME   Compose project name (default: ict3113-triage, or
                        $COMPOSE_PROJECT_NAME if it is set). The database volume
                        removed is "<NAME>_triage_db".
  -h, --help            Show this message and exit.

Never removes the Ollama model volume (that would force a multi-gigabyte
re-pull) and never removes anything under logs/ (that is evidence).

Exit codes:
  0  reset complete
  1  cancelled at the confirmation prompt, or a docker command failed
  2  confirmation needed but there is no terminal to ask (pass --yes)
USAGE
}

log()  { printf '%s\n' "$*"; }
fail() { printf 'reset.sh: %s\n' "$*" >&2; exit 1; }

# --- argument parsing ------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes)
            ASSUME_YES=1
            shift
            ;;
        --project-name)
            [[ $# -ge 2 ]] || fail "--project-name needs a value"
            PROJECT_NAME="$2"
            shift 2
            ;;
        --project-name=*)
            PROJECT_NAME="${1#*=}"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'reset.sh: unknown option %s\n\n' "$1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

[[ -f "${COMPOSE_FILE}" ]] || fail "no docker-compose.yml at ${COMPOSE_FILE}"
command -v docker >/dev/null 2>&1 || fail "docker is not on PATH"

DB_VOLUME="${PROJECT_NAME}_${DB_VOLUME_SUFFIX}"
compose() { docker compose --project-name "${PROJECT_NAME}" --file "${COMPOSE_FILE}" "$@"; }

# --- confirmation ---------------------------------------------------------
if [[ "${ASSUME_YES}" -ne 1 ]]; then
    if [[ ! -t 0 ]]; then
        printf 'reset.sh: refusing to delete %s without confirmation. Pass --yes.\n' \
            "${DB_VOLUME}" >&2
        exit 2
    fi
    log "About to DELETE the docker volume '${DB_VOLUME}' (every stored ticket)."
    log "Logs under logs/ and the Ollama model volume are NOT touched."
    read -r -p "Continue? [y/N] " reply
    case "${reply}" in
        y|Y|yes|YES) ;;
        *) log "Cancelled. Nothing was deleted."; exit 1 ;;
    esac
fi

# --- 0. make sure the bind-mounted log directory exists -------------------
# If ./logs/service is missing, the Docker daemon creates it as root when it
# mounts it, and the non-root service user then cannot append to it.
mkdir -p "${REPO_ROOT}/logs/service"

# --- 1. stop and remove the triage container ------------------------------
# The volume cannot be removed while a container is using it. --stop stops it
# first; --force skips Compose's own prompt. A missing container is not an error.
log "Stopping and removing the ${SERVICE} container..."
compose rm --stop --force "${SERVICE}"

# --- 2. remove the database volume ---------------------------------------
if docker volume inspect "${DB_VOLUME}" >/dev/null 2>&1; then
    log "Removing volume ${DB_VOLUME}..."
    docker volume rm "${DB_VOLUME}" >/dev/null
else
    log "Volume ${DB_VOLUME} does not exist; nothing to remove."
fi

# --- 3. start the service again ------------------------------------------
# Compose recreates the volume empty, and the service's start-up creates the
# schema in it. No --profile here: this restarts the service only, which is also
# correct when Ollama runs on another machine.
log "Starting ${SERVICE} again..."
compose up --detach "${SERVICE}"

# --- 4. wait for it to be healthy ----------------------------------------
container_id="$(compose ps --quiet "${SERVICE}" || true)"
if [[ -z "${container_id}" ]]; then
    fail "the ${SERVICE} container did not start; see: docker compose logs ${SERVICE}"
fi

log "Waiting up to ${HEALTH_TIMEOUT_S}s for ${SERVICE} to report healthy..."
deadline=$(( SECONDS + HEALTH_TIMEOUT_S ))
state=""
while (( SECONDS < deadline )); do
    # A container without a healthcheck reports an empty string; ours has one.
    state="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
             "${container_id}" 2>/dev/null || echo "gone")"
    [[ "${state}" == "healthy" ]] && break
    sleep 2
done

if [[ "${state}" != "healthy" ]]; then
    printf 'reset.sh: %s is "%s" after %ss.\n' "${SERVICE}" "${state}" "${HEALTH_TIMEOUT_S}" >&2
    printf 'Inspect it with: docker compose logs %s\n' "${SERVICE}" >&2
    exit 1
fi

log ""
log "Reset complete. The service is empty and healthy."
log "Check the backend before running a benchmark:"
log "  curl -s http://localhost:\${SERVICE_PORT:-8000}/health"
log "It must report \"status\": \"ok\" — \"degraded\" means Ollama is unreachable."
