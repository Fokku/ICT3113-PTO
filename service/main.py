"""The ticket triage service: FastAPI app with the four baseline endpoints.

Owner: Yeo Kai Yuan (Part 1 — baseline service).

    POST /tickets   classify one narrative with the model, store it, return it
    GET  /search    case-insensitive substring search over stored narratives
    GET  /stats     ticket counts by category
    GET  /health    configuration and backend liveness (not request-logged)

This is the Assignment 1 **baseline**, and it is deliberately the straightforward
thing:

* ``POST /tickets`` is **synchronous**. It does not return until Ollama has
  answered. There is no queue, no background task, no cache, no batching and no
  response reuse, so the latency a client sees is the model's latency plus ours.
* There is **no concurrency limit in the service**. Requests arrive as fast as
  the load generator sends them and each one opens its own connection to Ollama;
  in-flight model calls are bounded only by Ollama's ``OLLAMA_NUM_PARALLEL`` and
  its internal queue. That is why we expect the bottleneck to land in Ollama
  rather than in the web tier — and it is a prediction the stress test tests,
  not an assumption we build around.
  # A2 candidate: a bulkhead / semaphore around the model call, so the service
  # sheds or paces load instead of piling every arrival onto the backend
* One uvicorn worker (``UVICORN_WORKERS``, default 1), stated explicitly so the
  process model is part of the recorded configuration.

Blocking SQLite work is handed to the framework's worker-thread pool with
``run_in_threadpool``. That is FastAPI's default treatment of blocking I/O and
the reason ``SERVICE_THREADPOOL_SIZE`` is configured and logged: calling
``sqlite3`` straight from an ``async def`` handler would block the single event
loop for the duration of every insert and serialise requests inside *our*
process, which would move the bottleneck into the web tier as an artefact of a
coding mistake rather than a property of the design. The naivety that Assignment
2 gets to fix is the per-call connect/close in ``service/db.py``, not the loop
blocking.

Every request to ``/tickets``, ``/search`` and ``/stats`` writes exactly one
JSONL line (``service/request_log.py``). ``/health`` does not: a load test polls
it, and those lines would swamp the evidence.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, Sequence

import anyio.to_thread
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from service import db, ollama_client
from service.categories import normalise_category
from service.config import PROBE_TIMEOUT_S, Settings, load_settings
from service.log_schema import OLLAMA_TIMING_FIELDS
from service.prompt import PROMPT_HASH, build_prompt
from service.request_log import build_log_line, iso_ms, utc_now, write_log_line

LOGGER = logging.getLogger("triage")

#: Scope key holding this request's monotonic start time. A private key rather
#: than ``request.state`` so nothing in Starlette or FastAPI can overwrite it,
#: and so the endpoints and the exception handlers all read the *same* clock.
_STARTED_KEY = "triage_started"

#: Header names, spelled once. JMeter sends the first two on every sampler
#: (see the JMeter contract) and the run script sends the third on its warm-up.
HEADER_REQUEST_ID = "X-Request-ID"
HEADER_SOURCE_ROW = "X-Source-Row"
HEADER_WARMUP = "X-Warmup"

#: Accepted as "yes" in ``X-Warmup``. Anything else, including absent, is false.
_TRUTHY = frozenset({"1", "true", "yes"})


class TicketIn(BaseModel):
    """Request body of ``POST /tickets``.

    One field, no validation beyond "it is a string". The intake sends whatever
    the customer wrote; rejecting or trimming it here would make ``ticket_chars``
    in the log describe something other than what the model was asked to read.
    """

    narrative: str = Field(description="The customer complaint, verbatim.")


@dataclass(frozen=True)
class RequestContext:
    """The per-request identifiers every log line needs."""

    request_id: str
    source_row: str | None
    warmup: bool
    started: float

    @property
    def elapsed_ms(self) -> float:
        """Wall-clock milliseconds since the request entered the app, 1 dp."""
        return round((time.perf_counter() - self.started) * 1000.0, 1)


class StartTimeMiddleware:
    """Pure-ASGI middleware stamping a monotonic start time into the scope.

    Pure ASGI rather than ``BaseHTTPMiddleware`` on purpose: it must not wrap the
    response body in another stream, because that would add cost to the very
    path we are measuring. It exists so that ``total_latency_ms`` covers the
    whole request — and so the validation-error and internal-error handlers,
    which never reach an endpoint, can still report a real elapsed time instead
    of a made-up one.
    """

    def __init__(self, app: Callable[..., Any]) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") == "http":
            scope[_STARTED_KEY] = time.perf_counter()
        await self.app(scope, receive, send)


def _context(request: Request) -> RequestContext:
    """Read the three optional headers and the start time for one request.

    A missing ``X-Request-ID`` is generated here (UUID4) so that every log line
    has an identifier even for a hand-rolled ``curl``; JMeter always supplies
    one, which is what makes ``analysis/reconcile.py`` able to join its ``.jtl``
    to this log.
    """
    # Stripped before the fallback, so a header that is present but blank still
    # yields a usable identifier rather than an empty string nothing can join on.
    supplied_id = (request.headers.get(HEADER_REQUEST_ID) or "").strip()
    source_row = request.headers.get(HEADER_SOURCE_ROW)
    warmup_header = (request.headers.get(HEADER_WARMUP) or "").strip().lower()
    started = request.scope.get(_STARTED_KEY)
    return RequestContext(
        request_id=supplied_id or str(uuid.uuid4()),
        # Kept as a string: the log contract says string-or-null, and the CSV
        # row number is an identifier, not a quantity.
        source_row=source_row.strip() if source_row else None,
        warmup=warmup_header in _TRUTHY,
        started=started if isinstance(started, float) else time.perf_counter(),
    )


def _null_model_fields() -> dict[str, None]:
    """The model half of a log line, all ``None``.

    Used by ``/search`` and ``/stats`` (which are logged, and appear in the
    mixed-load test) and by the two error handlers: no model was called, so every
    model field is null rather than inherited from the configuration.
    """
    return {
        "model_tag": None,
        "model_digest": None,
        "predicted_category": None,
        "raw_model_output": None,
        "prompt_hash": None,
        "num_ctx": None,
        "seed": None,
        "model_latency_ms": None,
        **{name: None for name in OLLAMA_TIMING_FIELDS},
    }


def _configure_logging(level: str) -> None:
    """Send our own logger to stdout at ``LOG_LEVEL``.

    ``basicConfig`` is a no-op when handlers already exist, so this cooperates
    with uvicorn's logging rather than replacing it. These records are the
    container's stdout log; they are *not* the JSONL request log, which has a
    fixed schema with no room for free-form messages.
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    LOGGER.setLevel(level)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. ``settings`` defaults to the environment.

    A factory rather than a bare module-level app so the tests can run a real
    app against a temporary database and log directory without touching the
    environment or the volumes.
    """
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """Start-up: size the thread pool, create the schema, pin the model."""
        _configure_logging(settings.log_level)

        # Set explicitly so the value is visible, logged and reproducible rather
        # than being whatever the installed anyio happens to default to.
        anyio.to_thread.current_default_thread_limiter().total_tokens = (
            settings.threadpool_size
        )

        # Idempotent: the database lives in a volume that scripts/reset.sh
        # deletes between runs, so the table may or may not exist.
        db.schema_init(settings.db_path)

        if settings.model_digest is None:
            # MODEL_DIGEST was not pinned, so ask Ollama which build it serves
            # for MODEL_TAG. Failure is not fatal: the service must still start
            # (and report "degraded") when the backend is not up yet.
            digest = await ollama_client.resolve_model_digest(
                settings.ollama_base_url, settings.model_tag, PROBE_TIMEOUT_S
            )
            settings.set_resolved_digest(digest)
            if digest is None:
                LOGGER.warning(
                    "could not resolve a digest for model_tag=%s from %s; log "
                    "lines will record model_digest=null. Pin MODEL_DIGEST or "
                    "check the backend before running a benchmark.",
                    settings.model_tag,
                    settings.ollama_base_url,
                )

        # The one start-up record. Everything that could change a measurement is
        # in it, so a log file can be read back to the configuration that
        # produced it: model tag and digest, num_ctx, seed, prompt hash, worker
        # count and thread-pool size.
        LOGGER.info(
            "triage service start-up configuration: %s",
            json.dumps(settings.describe(), sort_keys=True),
        )
        yield

    app = FastAPI(
        title="ICT3113 Ticket Triage Service (Assignment 1 baseline)",
        description=(
            "Synchronous ticket classification against a local Ollama backend. "
            "Baseline: no caching, no queuing, no batching."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(StartTimeMiddleware)

    # -- logging helper ---------------------------------------------------
    def log_line(**fields: Any) -> None:
        """Build, validate and append one request log line.

        Wrapped so a failure to log cannot take the response down with it: the
        request already happened, and JMeter's ``.jtl`` will still hold the
        sample. ``analysis/reconcile.py`` reports the missing line loudly, which
        is the behaviour we want — a silent gap would be worse.
        """
        try:
            write_log_line(settings.log_dir, build_log_line(**fields))
        except Exception:  # pragma: no cover - defensive, must never 500
            LOGGER.exception("failed to write a request log line")

    # -- POST /tickets ----------------------------------------------------
    @app.post("/tickets")
    async def create_ticket(payload: TicketIn, request: Request) -> JSONResponse:
        """Classify one ticket, store it, and return the assigned category.

        Optional headers: ``X-Request-ID`` (echoed back, generated if absent),
        ``X-Source-Row`` (the course CSV row, logged so accuracy results can be
        joined to the golden set), ``X-Warmup`` (marks the log line so analysis
        can drop the model-load request).

        On a model failure the response is **502 and nothing is stored**. A
        failed classification written as ``UNPARSEABLE`` would be
        indistinguishable in ``/stats`` from a model that answered with nonsense,
        and would corrupt the accuracy denominator.
        """
        ctx = _context(request)
        narrative = payload.narrative

        result = await ollama_client.generate(
            base_url=settings.ollama_base_url,
            model_tag=settings.model_tag,
            prompt=build_prompt(narrative),
            seed=settings.ollama_seed,
            num_ctx=settings.num_ctx,
            timeout_s=settings.ollama_timeout_s,
        )

        # Fields describing the attempt: present whether it succeeded or not, so
        # a 502 line still records which model, prompt and context length failed.
        attempt: dict[str, Any] = {
            "model_tag": settings.model_tag,
            "model_digest": settings.model_digest,
            "prompt_hash": PROMPT_HASH,
            "num_ctx": settings.num_ctx,
            "seed": settings.ollama_seed,
            "model_latency_ms": result.model_latency_ms,
            **result.timings,
        }

        if not result.ok:
            status = 502
            log_line(
                ts=iso_ms(utc_now()),
                request_id=ctx.request_id,
                source_row=ctx.source_row,
                warmup=ctx.warmup,
                endpoint="/tickets",
                method="POST",
                status=status,
                ticket_chars=len(narrative),
                predicted_category=None,
                raw_model_output=None,
                total_latency_ms=ctx.elapsed_ms,
                error=result.error,
                **attempt,
            )
            return JSONResponse(
                status_code=status,
                content={
                    "detail": "model backend did not classify the ticket",
                    "error": result.error,
                    "request_id": ctx.request_id,
                },
                headers={HEADER_REQUEST_ID: ctx.request_id},
            )

        raw_output = result.raw_text or ""
        category = normalise_category(raw_output)

        # Blocking sqlite3 work off the event loop; see the module docstring.
        ticket_id = await run_in_threadpool(
            db.insert_ticket,
            settings.db_path,
            created_at=iso_ms(utc_now()),
            request_id=ctx.request_id,
            source_row=ctx.source_row,
            narrative=narrative,
            category=category,
            # Stored in full alongside the mapped category: when the category is
            # UNPARSEABLE this is the only record of what the model said, and
            # Assignment 2 needs it to judge whether a parser change is honest.
            raw_model_output=raw_output,
            model_tag=settings.model_tag,
            model_digest=settings.model_digest,
        )

        log_line(
            ts=iso_ms(utc_now()),
            request_id=ctx.request_id,
            source_row=ctx.source_row,
            warmup=ctx.warmup,
            endpoint="/tickets",
            method="POST",
            status=200,
            ticket_chars=len(narrative),
            predicted_category=category,
            raw_model_output=raw_output,
            total_latency_ms=ctx.elapsed_ms,
            error=None,
            **attempt,
        )
        return JSONResponse(
            status_code=200,
            content={
                "id": ticket_id,
                "category": category,
                "request_id": ctx.request_id,
            },
            headers={HEADER_REQUEST_ID: ctx.request_id},
        )

    # -- GET /search ------------------------------------------------------
    @app.get("/search")
    async def search(
        request: Request,
        q: str = Query(description="Substring to look for in stored narratives."),
        limit: int = Query(
            default=db.DEFAULT_SEARCH_LIMIT,
            description=(
                f"Maximum rows to return; clamped to "
                f"{db.MIN_SEARCH_LIMIT}..{db.MAX_SEARCH_LIMIT}."
            ),
        ),
    ) -> JSONResponse:
        """Return stored tickets whose narrative contains ``q``.

        ``limit`` is clamped rather than rejected, so an out-of-range value in a
        test plan still produces a sample. The effective limit is echoed in the
        response, because a client that asked for 1,000 rows and got 500 needs to
        know which happened.
        """
        ctx = _context(request)
        effective_limit = db.clamp_search_limit(limit)
        results = await run_in_threadpool(
            db.search_tickets, settings.db_path, q, effective_limit
        )
        log_line(
            ts=iso_ms(utc_now()),
            request_id=ctx.request_id,
            source_row=ctx.source_row,
            warmup=ctx.warmup,
            endpoint="/search",
            method="GET",
            status=200,
            # No ticket arrived, so there is no ticket length to report.
            ticket_chars=None,
            total_latency_ms=ctx.elapsed_ms,
            error=None,
            **_null_model_fields(),
        )
        return JSONResponse(
            status_code=200,
            content={
                "q": q,
                "limit": effective_limit,
                "count": len(results),
                "results": results,
            },
            headers={HEADER_REQUEST_ID: ctx.request_id},
        )

    # -- GET /stats -------------------------------------------------------
    @app.get("/stats")
    async def stats(request: Request) -> JSONResponse:
        """Return the ticket count per category, in canonical order.

        Every category is present with a zero when nothing has been filed under
        it, and ``UNPARSEABLE`` is one of the keys, so the shape of the response
        does not depend on what has been classified so far. ``total`` is the sum
        of the counts, which is exact because ``insert_ticket`` refuses any other
        value in the column.
        """
        ctx = _context(request)
        counts = await run_in_threadpool(db.counts_by_category, settings.db_path)
        log_line(
            ts=iso_ms(utc_now()),
            request_id=ctx.request_id,
            source_row=ctx.source_row,
            warmup=ctx.warmup,
            endpoint="/stats",
            method="GET",
            status=200,
            ticket_chars=None,
            total_latency_ms=ctx.elapsed_ms,
            error=None,
            **_null_model_fields(),
        )
        return JSONResponse(
            status_code=200,
            content={"total": sum(counts.values()), "counts": counts},
            headers={HEADER_REQUEST_ID: ctx.request_id},
        )

    # -- GET /health ------------------------------------------------------
    @app.get("/health")
    async def health() -> JSONResponse:
        """Report the resolved configuration and whether Ollama is listening.

        ``status`` is ``"ok"`` only when ``GET {OLLAMA_BASE_URL}/api/tags``
        answers within the short probe timeout; otherwise ``"degraded"``. The
        service itself still serves ``/search`` and ``/stats`` when degraded,
        which is why this returns HTTP 200 either way — the container is up, the
        backend is not. Check this before every benchmark run.

        This endpoint is deliberately **not** written to the JSONL request log:
        a container health check polls it every few seconds and a load test may
        poll it too, and those lines would swamp the run's evidence.
        """
        reachable = await ollama_client.probe_reachable(
            settings.ollama_base_url, PROBE_TIMEOUT_S
        )
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok" if reachable else "degraded",
                "ollama_reachable": reachable,
                **settings.describe(),
            },
        )

    # -- error handlers ---------------------------------------------------
    @app.exception_handler(RequestValidationError)
    async def on_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Log the 422 before returning FastAPI's usual validation response.

        Logged because ``analysis/reconcile.py`` requires a log line for every
        JMeter sample: an unlogged 422 would look like a lost request rather than
        a malformed one, and would send someone hunting a bug in the service.
        """
        ctx = _context(request)
        log_line(
            ts=iso_ms(utc_now()),
            request_id=ctx.request_id,
            source_row=ctx.source_row,
            warmup=ctx.warmup,
            endpoint=request.url.path,
            method=request.method,
            status=422,
            # The body did not parse, so there is no narrative to measure.
            ticket_chars=None,
            total_latency_ms=ctx.elapsed_ms,
            error="bad_request",
            **_null_model_fields(),
        )
        return JSONResponse(
            status_code=422,
            content={"detail": json.loads(json.dumps(exc.errors(), default=str))},
            headers={HEADER_REQUEST_ID: ctx.request_id},
        )

    @app.exception_handler(Exception)
    async def on_unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        """Log an unexpected 500 and answer with a JSON body.

        Starlette re-raises the original exception after this handler returns, so
        uvicorn still prints the traceback to the container log; the handler only
        ensures the failure also reaches the JSONL log and reconciles with the
        JMeter sample.

        There should be no path here. If a run's logs contain an
        ``internal_error`` line, that run is not evidence until the cause is
        understood, so the line records the endpoint and the elapsed time and
        invents nothing about the model.
        """
        ctx = _context(request)
        log_line(
            ts=iso_ms(utc_now()),
            request_id=ctx.request_id,
            source_row=ctx.source_row,
            warmup=ctx.warmup,
            endpoint=request.url.path,
            method=request.method,
            status=500,
            ticket_chars=None,
            total_latency_ms=ctx.elapsed_ms,
            error="internal_error",
            **_null_model_fields(),
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "internal error",
                "error": "internal_error",
                "request_id": ctx.request_id,
            },
            headers={HEADER_REQUEST_ID: ctx.request_id},
        )

    return app


#: The ASGI application uvicorn serves: ``uvicorn service.main:app --workers 1``.
#: Built at import time from the environment, but it opens no file and no socket
#: until start-up, so importing this module is always safe.
app = create_app()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the service with uvicorn, for use outside Docker.

    The container does not use this — its ``CMD`` calls ``uvicorn`` directly — but
    a teammate running the service on a laptop against an Ollama on another
    machine needs a one-liner:

        OLLAMA_BASE_URL=http://<host>:11434 DB_PATH=./triage.db \\
        LOG_DIR=./logs/service .venv/bin/python -m service.main

    Every default comes from the environment via :func:`load_settings`, so this
    entry point cannot configure the service differently from the container. The
    flags exist only to override host, port and log level for a quick local run.
    """
    parser = argparse.ArgumentParser(
        prog="python -m service.main",
        description=(
            "Run the ICT3113 ticket triage service (Assignment 1 baseline). "
            "Defaults come from the environment and .env; see .env.example."
        ),
    )
    parser.add_argument("--host", default=None, help="Override SERVICE_HOST.")
    parser.add_argument("--port", type=int, default=None, help="Override SERVICE_PORT.")
    parser.add_argument(
        "--log-level",
        default=None,
        help="Override LOG_LEVEL (uvicorn needs it lower-case).",
    )
    args = parser.parse_args(argv)

    settings = load_settings()
    # Imported here, not at module scope: importing this module must not require
    # uvicorn (the tests and the analysis code import it without a server).
    import uvicorn

    uvicorn.run(
        # An import string rather than the app object, because that is what
        # uvicorn needs in order to honour --workers.
        "service.main:app",
        host=args.host or settings.service_host,
        port=args.port or settings.service_port,
        # One worker, from the configuration. Not a flag: changing the process
        # model changes what is being measured, so it has to be a recorded
        # configuration value rather than a command-line afterthought.
        workers=settings.uvicorn_workers,
        log_level=(args.log_level or settings.log_level).lower(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
