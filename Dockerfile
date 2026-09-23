# ---------------------------------------------------------------------------
# ICT3113 Assignment 1 — ticket triage service (Team 10)
# Owner: Yeo Kai Yuan (Part 1 — baseline service)
#
# Base image: python:3.11-slim (Debian), NOT alpine.
# Alpine is musl-based, and the wheels for pydantic-core (a Rust extension) and
# uvicorn's optional C speed-ups are built for glibc. On alpine pip either falls
# back to compiling them — which needs a toolchain in the image and minutes of
# build time — or to slower pure-Python fallbacks. Neither is a sensible trade
# for a service whose performance we are about to measure: we want the ordinary,
# well-trodden runtime, not a variant nobody else benchmarks.
#
# The image contains the service and its five runtime dependencies. It does NOT
# contain the tests, the analysis scripts, pandas, matplotlib, JMeter, the course
# CSV or our team rows (see .dockerignore): the container must never be able to
# read the dataset directly, because tickets reach the service only through
# POST /tickets.
# ---------------------------------------------------------------------------
FROM python:3.11-slim

# Host UID/GID of the account that owns ./logs/service on the Docker host. The
# bind-mounted log directory is owned by the host user, so the container user has
# to match it to be able to append. 1000 is the first ordinary user on a typical
# Linux install; if `id -u` says something else, rebuild with
#   docker compose build --build-arg APP_UID=$(id -u) --build-arg APP_GID=$(id -g)
ARG APP_UID=1000
ARG APP_GID=1000

# PYTHONDONTWRITEBYTECODE: no .pyc clutter in a read-only-ish image.
# PYTHONUNBUFFERED: stdout is unbuffered, so the start-up configuration line and
# any warning appear in `docker logs` immediately rather than after a buffer
# fills. During a load test that difference is the difference between seeing a
# problem and not.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Runtime dependencies only, from requirements.txt. requirements-dev.txt (pytest,
# pandas, matplotlib, PyYAML) is host-side tooling and is deliberately absent:
# nothing in the image should be able to run an analysis script.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Non-root user. Nothing in this service needs root, and a load test that can be
# made to write files should not be able to write them as root.
RUN groupadd --gid "${APP_GID}" triage \
 && useradd --uid "${APP_UID}" --gid "${APP_GID}" --no-create-home --shell /usr/sbin/nologin triage \
 # Both mount points are created in the image and owned by the service user, so
 # a *named* volume mounted over /data inherits that ownership. The /logs/service
 # bind mount takes its ownership from the host directory instead — hence APP_UID.
 && mkdir -p /data /logs/service \
 && chown -R triage:triage /data /logs/service /app

# The application package. Copied after pip install so a code change does not
# invalidate the dependency layer.
COPY --chown=triage:triage service/ ./service/

USER triage

# Documentation only; the published port is set in docker-compose.yml.
EXPOSE 8000

# Liveness of the web tier. /health answers 200 even when Ollama is unreachable
# (it reports "degraded"), which is what we want: the triage container is up, and
# the backend being down is a separate fact reported in the body. The timeout is
# generous because /health probes Ollama with a short timeout of its own.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('SERVICE_PORT', '8000') + '/health', timeout=8).read()"]

# ONE uvicorn worker, stated explicitly rather than left to a default, because
# the process model is part of the baseline we report (Slide 2) and part of every
# run's metadata.json. One worker also means one writer to the SQLite file and
# one appender to the JSONL log, so the evidence cannot interleave.
#   A2 candidate: more uvicorn workers (and the SQLite/log-contention work that
#   would then be needed) — an Assignment 2 experiment, not a baseline default.
# `exec` so uvicorn is PID 1 and receives docker stop's SIGTERM directly.
# LOG_LEVEL is lower-cased because uvicorn only accepts lower-case level names.
CMD ["sh", "-c", "exec uvicorn service.main:app --host \"${SERVICE_HOST:-0.0.0.0}\" --port \"${SERVICE_PORT:-8000}\" --workers \"${UVICORN_WORKERS:-1}\" --log-level \"$(echo \"${LOG_LEVEL:-INFO}\" | tr '[:upper:]' '[:lower:]')\""]
