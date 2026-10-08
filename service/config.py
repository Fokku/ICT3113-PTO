"""Service configuration, resolved once from the environment.

Owner: Yeo Kai Yuan (Part 1 — baseline service).

Every knob the service has is an environment variable listed in ``.env.example``
and in the build contract's configuration table. Nothing is hard-coded in a
handler, and nothing is read from the environment outside this module, so that
:meth:`Settings.describe` is a complete and honest record of how the service was
configured for a run. That record is logged once at start-up and served by
``/health``; ``scripts/capture_env.sh`` captures it alongside the hardware
description, and every run's ``metadata.json`` repeats the parts that affect the
measurement (model tag and digest, ``num_ctx``, seed, prompt hash).

Precedence is: real environment variables first, then values from ``.env``, then
the defaults below. ``python-dotenv`` is called with ``override=False`` to get
that order, because in Docker Compose the environment is authoritative and a
stale ``.env`` on a teammate's laptop must never win.

This module deliberately performs **no I/O other than reading ``.env``** and
opens no network connection, so ``import service.config`` is safe in a test, in
a script, and at image build time.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from dotenv import load_dotenv

from service.categories import CATEGORIES
from service.prompt import PROMPT_HASH

# ---------------------------------------------------------------------------
# Defaults — these are the values in .env.example and in the build contract.
# Keep the three in step: a default that exists only here is invisible.
# ---------------------------------------------------------------------------
DEFAULT_OLLAMA_BASE_URL = "http://ollama:11434"
DEFAULT_MODEL_TAG = "llama3.2:1b-instruct-q4_K_M"
DEFAULT_NUM_CTX = 4096
DEFAULT_OLLAMA_TIMEOUT_S = 120.0
DEFAULT_OLLAMA_SEED = 42
DEFAULT_DB_PATH = "/data/triage.db"
DEFAULT_LOG_DIR = "/logs/service"
DEFAULT_SERVICE_HOST = "0.0.0.0"
DEFAULT_SERVICE_PORT = 8000
DEFAULT_UVICORN_WORKERS = 1
DEFAULT_THREADPOOL_SIZE = 40
DEFAULT_LOG_LEVEL = "INFO"

#: Timeout for the two short "is Ollama there?" calls (`GET /api/tags`). Not a
#: configuration variable: it is a liveness probe, not part of the measured
#: path, and it must stay short so ``/health`` cannot itself become slow.
PROBE_TIMEOUT_S = 3.0


class ConfigError(ValueError):
    """Raised when an environment variable is present but unusable.

    We fail at start-up rather than coerce a nonsense value, because a service
    that quietly ran with ``num_ctx=0`` would produce results that look real.
    """


def _raw(env: Mapping[str, str], name: str) -> str | None:
    """Return a stripped environment value, treating empty strings as unset."""
    value = env.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _as_str(env: Mapping[str, str], name: str, default: str) -> str:
    return _raw(env, name) or default


def _as_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = _raw(env, name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:  # pragma: no cover - message is the useful part
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def _as_float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = _raw(env, name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:  # pragma: no cover - message is the useful part
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc


@dataclass
class Settings:
    """The resolved configuration of one running service process.

    Not frozen, because of exactly one permitted mutation:
    :meth:`set_resolved_digest`. See that method for why.
    """

    ollama_base_url: str
    model_tag: str
    model_digest: str | None
    num_ctx: int
    ollama_timeout_s: float
    ollama_seed: int
    db_path: Path
    log_dir: Path
    service_host: str
    service_port: int
    uvicorn_workers: int
    threadpool_size: int
    log_level: str

    # -- validation --------------------------------------------------------
    def __post_init__(self) -> None:
        if self.num_ctx <= 0:
            raise ConfigError(f"NUM_CTX must be positive, got {self.num_ctx}")
        if self.ollama_timeout_s <= 0:
            raise ConfigError(
                f"OLLAMA_TIMEOUT_S must be positive, got {self.ollama_timeout_s}"
            )
        if not 1 <= self.service_port <= 65535:
            raise ConfigError(f"SERVICE_PORT out of range: {self.service_port}")
        if self.uvicorn_workers < 1:
            raise ConfigError(
                f"UVICORN_WORKERS must be at least 1, got {self.uvicorn_workers}"
            )
        if self.threadpool_size < 1:
            raise ConfigError(
                f"SERVICE_THREADPOOL_SIZE must be at least 1, got "
                f"{self.threadpool_size}"
            )
        # Trailing slashes would give us "http://host:11434//api/generate", which
        # some proxies treat as a different path. Normalise once, here.
        self.ollama_base_url = self.ollama_base_url.rstrip("/")
        self.log_level = self.log_level.upper()

    # -- the one permitted mutation ---------------------------------------
    def set_resolved_digest(self, digest: str | None) -> None:
        """Record the model digest discovered from Ollama at start-up.

        ``MODEL_DIGEST`` may be left empty in the environment, in which case the
        service asks Ollama's ``/api/tags`` which digest is actually being served
        for ``MODEL_TAG`` and stores the answer here. Every log line and
        ``/health`` then report the digest that genuinely served the request,
        which is what Slide 5 has to pin. An explicit ``MODEL_DIGEST`` is never
        overwritten: the pin recorded in ``models/models.yaml`` wins, so a
        mismatch shows up as a discrepancy in the start-up log rather than being
        silently papered over.
        """
        if self.model_digest is None and digest:
            self.model_digest = digest

    # -- reporting ---------------------------------------------------------
    def describe(self) -> dict[str, Any]:
        """Return the JSON-serialisable record of this configuration.

        This one dict is the body of the start-up log line and the body of
        ``/health``, which adds only the two things that are not configuration:
        the liveness ``status`` and ``ollama_reachable``. Anything a reader of a
        result needs to know about how the service was configured must appear
        here.
        """
        return {
            "model_tag": self.model_tag,
            "model_digest": self.model_digest,
            "num_ctx": self.num_ctx,
            "seed": self.ollama_seed,
            "prompt_hash": PROMPT_HASH,
            "ollama_base_url": self.ollama_base_url,
            "ollama_timeout_s": self.ollama_timeout_s,
            "db_path": str(self.db_path),
            "log_dir": str(self.log_dir),
            "service_host": self.service_host,
            "service_port": self.service_port,
            "uvicorn_workers": self.uvicorn_workers,
            "threadpool_size": self.threadpool_size,
            "log_level": self.log_level,
            "categories": list(CATEGORIES),
        }


def load_settings(
    env: Mapping[str, str] | None = None,
    *,
    dotenv_path: Path | str | None = None,
    use_dotenv: bool = True,
) -> Settings:
    """Build a :class:`Settings` from ``env`` (default: ``os.environ``).

    ``use_dotenv`` loads ``.env`` into ``os.environ`` first (without
    overriding anything already set). Tests pass an explicit ``env`` mapping and
    ``use_dotenv=False`` so a developer's local ``.env`` cannot change a test
    result.
    """
    if use_dotenv:
        # override=False: a real environment variable always beats .env.
        load_dotenv(dotenv_path=dotenv_path, override=False)
    if env is None:
        env = os.environ

    return Settings(
        ollama_base_url=_as_str(env, "OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
        model_tag=_as_str(env, "MODEL_TAG", DEFAULT_MODEL_TAG),
        # Empty means "resolve it from /api/tags at start-up" (see the contract).
        model_digest=_raw(env, "MODEL_DIGEST"),
        num_ctx=_as_int(env, "NUM_CTX", DEFAULT_NUM_CTX),
        ollama_timeout_s=_as_float(env, "OLLAMA_TIMEOUT_S", DEFAULT_OLLAMA_TIMEOUT_S),
        ollama_seed=_as_int(env, "OLLAMA_SEED", DEFAULT_OLLAMA_SEED),
        db_path=Path(_as_str(env, "DB_PATH", DEFAULT_DB_PATH)),
        log_dir=Path(_as_str(env, "LOG_DIR", DEFAULT_LOG_DIR)),
        service_host=_as_str(env, "SERVICE_HOST", DEFAULT_SERVICE_HOST),
        service_port=_as_int(env, "SERVICE_PORT", DEFAULT_SERVICE_PORT),
        uvicorn_workers=_as_int(env, "UVICORN_WORKERS", DEFAULT_UVICORN_WORKERS),
        threadpool_size=_as_int(
            env, "SERVICE_THREADPOOL_SIZE", DEFAULT_THREADPOOL_SIZE
        ),
        log_level=_as_str(env, "LOG_LEVEL", DEFAULT_LOG_LEVEL),
    )
