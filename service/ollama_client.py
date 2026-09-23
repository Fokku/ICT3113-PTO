"""The HTTP client for the Ollama model backend.

Owner: Yeo Kai Yuan (Part 1 — baseline service).

Three calls live here and nothing else:

* :func:`generate` — one synchronous classification, ``POST /api/generate``.
  This is the call the whole assignment measures.
* :func:`probe_reachable` — a short-timeout ``GET /api/tags`` used by
  ``/health``. Liveness only.
* :func:`resolve_model_digest` — reads ``GET /api/tags`` at start-up to find the
  digest Ollama is actually serving for our tag, so results can be pinned to a
  model build (Slide 5) even when ``MODEL_DIGEST`` was left empty.

Request shape is fixed by the build contract::

    {"model": MODEL_TAG, "prompt": ..., "stream": false,
     "options": {"temperature": 0, "seed": OLLAMA_SEED, "num_ctx": NUM_CTX}}

``temperature`` is 0 and ``seed`` is fixed so that re-running the accuracy test
on the same model and prompt gives the same answers; a run we cannot reproduce is
not evidence. ``num_ctx`` is set explicitly — see the rationale in
``.env.example``. ``stream`` is false because the baseline is synchronous: we
want one request, one reply, and Ollama's own timing block, which only arrives
with the final object.

Failures never raise into the handler. They come back as an
:class:`OllamaResult` with :attr:`OllamaResult.error` set to a slug from
:data:`service.log_schema.ERROR_SLUGS`, because the handler must log a line for
every request before it answers — an unlogged 502 would leave a JMeter sample
that ``analysis/reconcile.py`` cannot match to anything.

Deliberate non-optimisations
----------------------------
No retries, no client reuse, no streaming, no connection warm-keeping. Each is
marked at the line it applies to.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from service.log_schema import OLLAMA_TIMING_FIELDS

#: Path of the generation endpoint on the Ollama server.
GENERATE_PATH = "/api/generate"
#: Path listing the models the server currently has pulled.
TAGS_PATH = "/api/tags"


@dataclass(frozen=True)
class OllamaResult:
    """The outcome of one model call: reply text, Ollama's timings, or an error.

    ``model_latency_ms`` is our own wall-clock measurement around the HTTP call,
    in milliseconds to one decimal place, and it is set even when the call
    failed — a timeout that took the full ``OLLAMA_TIMEOUT_S`` is a measurement
    we want in the log.

    The six Ollama fields are copied through **verbatim, in nanoseconds**. We do
    not convert them: the nanosecond values are what Ollama reported and what a
    marker can check against Ollama's own documentation.
    """

    raw_text: str | None
    model_latency_ms: float
    error: str | None = None
    timings: dict[str, int | None] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """True when the model answered and there is a reply to classify."""
        return self.error is None and self.raw_text is not None


def _empty_timings() -> dict[str, int | None]:
    """All six Ollama timing/count fields present and ``None``.

    Every log line carries all six keys whether Ollama replied or not, so the
    schema is identical for a success and a failure.
    """
    return {name: None for name in OLLAMA_TIMING_FIELDS}


def _as_int_or_none(value: Any) -> int | None:
    """Coerce one of Ollama's timing values to ``int``, or ``None``.

    The log contract says these fields are integers or null. Ollama sends
    integers; a future version sending a float or a string must not put a
    non-integer into the log and break the analysis dtypes.
    """
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _elapsed_ms(started: float) -> float:
    """Milliseconds since ``started`` (a ``time.perf_counter`` reading), 1 dp."""
    return round((time.perf_counter() - started) * 1000.0, 1)


async def generate(
    *,
    base_url: str,
    model_tag: str,
    prompt: str,
    seed: int,
    num_ctx: int,
    timeout_s: float,
) -> OllamaResult:
    """Classify one prompt. Never raises; returns an error slug instead.

    The A2 candidates below are the whole point of the baseline: this function is
    where the time goes, and every line of it is the obvious thing rather than
    the fast thing.
    """
    payload: dict[str, Any] = {
        "model": model_tag,
        "prompt": prompt,
        # Synchronous baseline: one request, one complete reply.
        # A2 candidate: stream=true and stop as soon as the category is decodable
        "stream": False,
        "options": {
            # Greedy decoding plus a fixed seed makes a run reproducible.
            "temperature": 0,
            "seed": seed,
            # Set explicitly: Ollama's own default of 2048 would silently
            # truncate our longest tickets plus this prompt.
            "num_ctx": num_ctx,
        },
    }

    started = time.perf_counter()
    try:
        # A2 candidate: reuse one module-level AsyncClient (HTTP connection
        # pooling / keep-alive) instead of building one per request
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            # A2 candidate: retry/hedge a slow call (deliberately absent — a
            # retry would hide the very latency we are here to measure)
            response = await client.post(base_url + GENERATE_PATH, json=payload)
    except httpx.TimeoutException:
        return OllamaResult(
            raw_text=None,
            model_latency_ms=_elapsed_ms(started),
            error="ollama_timeout",
            timings=_empty_timings(),
        )
    except httpx.RequestError:
        # Connection refused, DNS failure, connection reset: the backend is not
        # there, which is a different fault from "there but too slow".
        return OllamaResult(
            raw_text=None,
            model_latency_ms=_elapsed_ms(started),
            error="ollama_connect_error",
            timings=_empty_timings(),
        )
    latency_ms = _elapsed_ms(started)

    if response.status_code != httpx.codes.OK:
        # Ollama answers 404 for a model that has not been pulled and 500 when
        # it runs out of memory loading one. Both must be visible in the log.
        return OllamaResult(
            raw_text=None,
            model_latency_ms=latency_ms,
            error="ollama_http_error",
            timings=_empty_timings(),
        )

    try:
        body = response.json()
    except ValueError:
        return OllamaResult(
            raw_text=None,
            model_latency_ms=latency_ms,
            error="ollama_bad_response",
            timings=_empty_timings(),
        )
    if not isinstance(body, dict) or not isinstance(body.get("response"), str):
        # A 200 without a "response" string is not something we can classify.
        return OllamaResult(
            raw_text=None,
            model_latency_ms=latency_ms,
            error="ollama_bad_response",
            timings=_empty_timings(),
        )

    timings = {
        name: _as_int_or_none(body.get(name)) for name in OLLAMA_TIMING_FIELDS
    }
    return OllamaResult(
        raw_text=body["response"],
        model_latency_ms=latency_ms,
        error=None,
        timings=timings,
    )


async def probe_reachable(base_url: str, timeout_s: float) -> bool:
    """True if Ollama answers ``GET /api/tags`` within ``timeout_s``.

    Liveness only: this does **not** load a model and does **not** tell us
    whether ``MODEL_TAG`` is pulled. ``/health`` reports it as
    ``ollama_reachable`` and degrades the service status when it is false, so
    that a load test cannot be started against a backend that is not listening.

    The timeout is short and separate from ``OLLAMA_TIMEOUT_S`` on purpose: a
    health check that could block for two minutes is worse than no health check.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.get(base_url + TAGS_PATH)
    except httpx.HTTPError:
        return False
    return response.status_code == httpx.codes.OK


async def resolve_model_digest(
    base_url: str, model_tag: str, timeout_s: float
) -> str | None:
    """Return the digest Ollama reports for ``model_tag``, or ``None``.

    ``GET /api/tags`` lists ``{"models": [{"name": "llama3.2:1b",
    "digest": "...", ...}, ...]}``. We match on ``name`` (and on ``model``,
    which newer Ollama versions also send) and return the digest with a
    ``sha256:`` prefix so the value looks the same whether it came from here or
    from an explicit ``MODEL_DIGEST`` pin in ``models/models.yaml``.

    Returns ``None`` — never raises and never guesses — when Ollama is
    unreachable or does not have the tag. A missing digest must show up as a
    missing digest in the log; inventing one would be fabricating evidence.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.get(base_url + TAGS_PATH)
    except httpx.HTTPError:
        return None
    if response.status_code != httpx.codes.OK:
        return None
    try:
        body = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None

    for entry in body.get("models") or []:
        if not isinstance(entry, dict):
            continue
        names = {entry.get("name"), entry.get("model")}
        if model_tag not in names:
            continue
        digest = entry.get("digest")
        if not isinstance(digest, str) or not digest:
            return None
        return digest if digest.startswith("sha256:") else f"sha256:{digest}"
    return None
