"""End-to-end tests of the four endpoints, with the model backend mocked.

Owner: Yeo Kai Yuan (Part 1 — baseline service).

**No model runs here and no HTTP request leaves this process.**
``service.ollama_client.generate`` is replaced with :class:`FakeOllama`, and the
two start-up/health probes are replaced too, so the tests exercise the whole
request path — headers, prompt construction, category normalisation, storage,
the JSONL log line, the status code — without a container, a model, or a
network. That is a hard requirement of this build: no model may see any ticket
before the golden set is frozen, and nothing here may time or score a model.

These tests assert *behaviour and bookkeeping*: statuses, stored rows, log
fields. They never assert a latency or an accuracy figure. The latency values
that appear below are the fake's arbitrary constants, chosen to be obviously
synthetic, and they are asserted only to prove the number is carried from the
client into the log line unmodified.

This module builds its own app, because ``tests/conftest.py`` is shared with the
other parts of the build and is not ours to extend.
"""

from __future__ import annotations

import contextlib
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from service import main as service_main
from service import ollama_client
from service.categories import CATEGORIES, UNPARSEABLE
from service.config import Settings, load_settings
from service.log_schema import LOG_FIELDS, OLLAMA_TIMING_FIELDS
from service.ollama_client import OllamaResult
from service.prompt import PROMPT_HASH

#: Obviously-not-real model identity, so no test artefact can be mistaken for a
#: measurement of a candidate model.
TEST_MODEL_TAG = "testmodel:1b"
TEST_MODEL_DIGEST = "sha256:0000testdigest"

#: Arbitrary constants the fake reports. Not measurements of anything.
FAKE_MODEL_LATENCY_MS = 123.4
FAKE_TIMINGS: dict[str, int] = {
    "total_duration": 120_000_000,
    "load_duration": 1_000_000,
    "prompt_eval_count": 300,
    "prompt_eval_duration": 80_000_000,
    "eval_count": 4,
    "eval_duration": 39_000_000,
}

MORTGAGE_NARRATIVE = (
    "My mortgage servicer applied my escrow payment to the wrong account."
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class FakeOllama:
    """Replacement for :func:`service.ollama_client.generate`.

    Records every call so a test can assert what the service asked the model
    for (tag, seed, ``num_ctx``, prompt), and returns a fixed reply or a fixed
    error slug.
    """

    def __init__(
        self,
        *,
        reply: str | None = "Mortgage",
        error: str | None = None,
        latency_ms: float = FAKE_MODEL_LATENCY_MS,
    ) -> None:
        self.reply = reply
        self.error = error
        self.latency_ms = latency_ms
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> OllamaResult:
        self.calls.append(kwargs)
        if self.error is not None:
            # A failed call still reports the wall clock it burned, and all six
            # of Ollama's fields are null because Ollama never answered.
            return OllamaResult(
                raw_text=None,
                model_latency_ms=self.latency_ms,
                error=self.error,
                timings={name: None for name in OLLAMA_TIMING_FIELDS},
            )
        return OllamaResult(
            raw_text=self.reply,
            model_latency_ms=self.latency_ms,
            error=None,
            timings=dict(FAKE_TIMINGS),
        )

    @property
    def prompts(self) -> list[str]:
        return [call["prompt"] for call in self.calls]


def _fake_probe(reachable: bool) -> Callable[..., Any]:
    """Replacement for :func:`service.ollama_client.probe_reachable`."""

    async def _probe(base_url: str, timeout_s: float) -> bool:
        return reachable

    return _probe


def _fake_digest(digest: str | None) -> Callable[..., Any]:
    """Replacement for :func:`service.ollama_client.resolve_model_digest`."""

    async def _resolve(base_url: str, model_tag: str, timeout_s: float) -> str | None:
        return digest

    return _resolve


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

@dataclass
class Service:
    """One running app: its client, its settings, and its fake model."""

    client: TestClient
    settings: Settings
    ollama: FakeOllama

    def log_lines(self) -> list[dict[str, Any]]:
        """Every JSONL line the service has written, in order."""
        lines: list[dict[str, Any]] = []
        for path in sorted(Path(self.settings.log_dir).glob("*.jsonl")):
            for raw in path.read_text(encoding="utf-8").splitlines():
                if raw.strip():
                    lines.append(json.loads(raw))
        return lines

    def last_log_line(self) -> dict[str, Any]:
        lines = self.log_lines()
        assert lines, "the service wrote no log line at all"
        return lines[-1]

    def post_ticket(self, narrative: str = MORTGAGE_NARRATIVE, **kwargs: Any):
        return self.client.post("/tickets", json={"narrative": narrative}, **kwargs)


def make_settings(tmp_path: Path, **overrides: str) -> Settings:
    """Settings pointing at a temporary database and log directory.

    ``use_dotenv=False`` so a developer's local ``.env`` cannot change a test
    result. ``OLLAMA_BASE_URL`` points at an unroutable host as a second line of
    defence: if a test ever forgets to mock the client, it fails rather than
    reaching a real Ollama.
    """
    env = {
        "OLLAMA_BASE_URL": "http://ollama.invalid:11434",
        "MODEL_TAG": TEST_MODEL_TAG,
        "MODEL_DIGEST": TEST_MODEL_DIGEST,
        "NUM_CTX": "4096",
        "OLLAMA_TIMEOUT_S": "5",
        "OLLAMA_SEED": "42",
        "DB_PATH": str(tmp_path / "volume" / "triage.db"),
        "LOG_DIR": str(tmp_path / "logs" / "service"),
        "UVICORN_WORKERS": "1",
        "SERVICE_THREADPOOL_SIZE": "40",
    }
    env.update(overrides)
    return load_settings(env=env, use_dotenv=False)


@pytest.fixture()
def build_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Callable[..., Service]]:
    """Factory building a live app with the model backend mocked.

    The ``TestClient`` is entered as a context manager, which runs the real
    lifespan: the thread pool is sized, the schema is created, and the start-up
    configuration is logged, exactly as in the container.
    """
    stack = contextlib.ExitStack()

    def _build(
        *,
        ollama: FakeOllama | None = None,
        reachable: bool = True,
        resolved_digest: str | None = None,
        **env: str,
    ) -> Service:
        fake = ollama or FakeOllama()
        monkeypatch.setattr(ollama_client, "generate", fake)
        monkeypatch.setattr(ollama_client, "probe_reachable", _fake_probe(reachable))
        monkeypatch.setattr(
            ollama_client, "resolve_model_digest", _fake_digest(resolved_digest)
        )
        settings = make_settings(tmp_path, **env)
        client = stack.enter_context(TestClient(service_main.create_app(settings)))
        return Service(client=client, settings=settings, ollama=fake)

    yield _build
    stack.close()


# ---------------------------------------------------------------------------
# POST /tickets — happy path
# ---------------------------------------------------------------------------

def test_post_ticket_returns_id_category_and_request_id(build_service) -> None:
    service = build_service(ollama=FakeOllama(reply="Mortgage"))
    response = service.post_ticket()

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"id", "category", "request_id"}
    assert body["id"] == 1
    assert body["category"] == "Mortgage"


def test_post_ticket_stores_the_ticket_and_counts_it(build_service) -> None:
    service = build_service(ollama=FakeOllama(reply="Debt collection"))
    service.post_ticket("a collector rang my employer twice a day")

    stats = service.client.get("/stats").json()
    assert stats["total"] == 1
    assert stats["counts"]["Debt collection"] == 1


def test_post_ticket_sends_the_configured_model_options(build_service) -> None:
    """The service must ask for the model, seed and num_ctx it advertises.

    ``num_ctx`` in particular: the whole point of setting it explicitly is that
    a 1,999-character ticket is not silently truncated by Ollama's 2048 default.
    """
    service = build_service()
    service.post_ticket(MORTGAGE_NARRATIVE)

    assert len(service.ollama.calls) == 1
    call = service.ollama.calls[0]
    assert call["model_tag"] == TEST_MODEL_TAG
    assert call["seed"] == 42
    assert call["num_ctx"] == 4096
    assert call["timeout_s"] == 5.0
    # The prompt is the fixed template with the narrative embedded.
    assert MORTGAGE_NARRATIVE in call["prompt"]
    for category in CATEGORIES:
        assert f"- {category}" in call["prompt"]


def test_post_ticket_writes_one_log_line_with_the_full_schema(build_service) -> None:
    service = build_service(ollama=FakeOllama(reply="Mortgage"))
    service.post_ticket(MORTGAGE_NARRATIVE)

    lines = service.log_lines()
    assert len(lines) == 1
    line = lines[0]
    assert tuple(line) == LOG_FIELDS
    assert line["endpoint"] == "/tickets"
    assert line["method"] == "POST"
    assert line["status"] == 200
    assert line["ticket_chars"] == len(MORTGAGE_NARRATIVE)
    assert line["predicted_category"] == "Mortgage"
    assert line["raw_model_output"] == "Mortgage"
    assert line["model_tag"] == TEST_MODEL_TAG
    assert line["model_digest"] == TEST_MODEL_DIGEST
    assert line["prompt_hash"] == PROMPT_HASH
    assert line["num_ctx"] == 4096
    assert line["seed"] == 42
    assert line["error"] is None
    # Ollama's own instrumentation is copied through verbatim, in nanoseconds.
    for name, value in FAKE_TIMINGS.items():
        assert line[name] == value
    # The client's measurement of the model call reaches the log unmodified.
    assert line["model_latency_ms"] == FAKE_MODEL_LATENCY_MS
    assert isinstance(line["total_latency_ms"], float)


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------

def test_supplied_request_id_is_echoed_and_logged(build_service) -> None:
    service = build_service()
    supplied = "11111111-2222-4333-8444-555555555555"
    response = service.post_ticket(headers={"X-Request-ID": supplied})

    assert response.json()["request_id"] == supplied
    assert response.headers["X-Request-ID"] == supplied
    assert service.last_log_line()["request_id"] == supplied


def test_missing_request_id_is_generated(build_service) -> None:
    """A hand-rolled curl still gets an identifier, so every line is joinable."""
    service = build_service()
    response = service.post_ticket()

    generated = response.json()["request_id"]
    assert uuid.UUID(generated).version == 4
    assert service.last_log_line()["request_id"] == generated
    assert response.headers["X-Request-ID"] == generated


def test_source_row_is_logged_as_a_string(build_service) -> None:
    """``X-Source-Row`` is what joins an accuracy result back to the golden set."""
    service = build_service()
    service.post_ticket(headers={"X-Source-Row": "10042"})
    assert service.last_log_line()["source_row"] == "10042"


def test_absent_source_row_is_null(build_service) -> None:
    service = build_service()
    service.post_ticket()
    assert service.last_log_line()["source_row"] is None


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes"])
def test_warmup_header_marks_the_log_line(build_service, value: str) -> None:
    """The warm-up request pays the model-load cost and is excluded from analysis."""
    service = build_service()
    service.post_ticket(headers={"X-Warmup": value})
    assert service.last_log_line()["warmup"] is True


@pytest.mark.parametrize("headers", [{}, {"X-Warmup": "0"}, {"X-Warmup": "false"}])
def test_measured_requests_are_not_marked_warmup(build_service, headers) -> None:
    service = build_service()
    service.post_ticket(headers=headers)
    assert service.last_log_line()["warmup"] is False


# ---------------------------------------------------------------------------
# Unmappable replies
# ---------------------------------------------------------------------------

def test_unmappable_reply_is_stored_as_unparseable_with_the_raw_output(
    build_service,
) -> None:
    """A model that will not answer the question is recorded, not corrected.

    The request still succeeds — the service did its job — but the category is
    ``UNPARSEABLE`` and the raw reply is kept in both the database and the log so
    the failure can be shown rather than described.
    """
    reply = "I think this could be either Mortgage or Credit card, hard to say."
    service = build_service(ollama=FakeOllama(reply=reply))
    response = service.post_ticket()

    assert response.status_code == 200
    assert response.json()["category"] == UNPARSEABLE

    line = service.last_log_line()
    assert line["predicted_category"] == UNPARSEABLE
    assert line["raw_model_output"] == reply
    assert line["error"] is None  # not an error: the model answered, badly

    stats = service.client.get("/stats").json()
    assert stats["counts"][UNPARSEABLE] == 1
    assert stats["total"] == 1
    # The raw reply is searchable in storage, which is how we show what happened.
    assert service.client.get("/search", params={"q": "escrow"}).json()["count"] == 1


def test_empty_reply_is_unparseable(build_service) -> None:
    service = build_service(ollama=FakeOllama(reply=""))
    assert service.post_ticket().json()["category"] == UNPARSEABLE


# ---------------------------------------------------------------------------
# Model failure
# ---------------------------------------------------------------------------

def test_model_timeout_returns_502_and_stores_nothing(build_service) -> None:
    """A failed classification must never reach storage.

    Storing it as ``UNPARSEABLE`` would make ``/stats`` — and the accuracy
    denominator — indistinguishable from a model that answered with nonsense.
    """
    service = build_service(ollama=FakeOllama(error="ollama_timeout"))
    response = service.post_ticket()

    assert response.status_code == 502
    assert response.json()["error"] == "ollama_timeout"

    stats = service.client.get("/stats").json()
    assert stats["total"] == 0
    assert set(stats["counts"].values()) == {0}


def test_model_failure_is_logged_with_an_error_slug(build_service) -> None:
    service = build_service(ollama=FakeOllama(error="ollama_timeout"))
    service.post_ticket(MORTGAGE_NARRATIVE, headers={"X-Source-Row": "10007"})

    line = service.log_lines()[0]
    assert line["status"] == 502
    assert line["error"] == "ollama_timeout"
    assert line["predicted_category"] is None
    assert line["raw_model_output"] is None
    assert line["source_row"] == "10007"
    # The attempt is still described: which model, prompt and context length.
    assert line["model_tag"] == TEST_MODEL_TAG
    assert line["prompt_hash"] == PROMPT_HASH
    assert line["num_ctx"] == 4096
    assert line["ticket_chars"] == len(MORTGAGE_NARRATIVE)
    # Ollama never answered, so all six of its fields are null.
    for name in OLLAMA_TIMING_FIELDS:
        assert line[name] is None
    # Our own measurement of the failed call is kept: a timeout has a duration.
    assert line["model_latency_ms"] == FAKE_MODEL_LATENCY_MS


@pytest.mark.parametrize(
    "slug", ["ollama_timeout", "ollama_connect_error", "ollama_http_error",
             "ollama_bad_response"]
)
def test_every_model_error_slug_yields_502(build_service, slug: str) -> None:
    service = build_service(ollama=FakeOllama(error=slug))
    assert service.post_ticket().status_code == 502
    assert service.log_lines()[0]["error"] == slug


def test_malformed_body_is_rejected_and_logged(build_service) -> None:
    """A 422 is logged too, so every JMeter sample has a matching log line."""
    service = build_service()
    response = service.client.post("/tickets", json={"not_narrative": "x"})

    assert response.status_code == 422
    line = service.log_lines()[0]
    assert line["status"] == 422
    assert line["error"] == "bad_request"
    assert line["endpoint"] == "/tickets"
    assert line["predicted_category"] is None
    # The model was never called, so nothing about it is reported.
    assert line["model_tag"] is None
    assert not service.ollama.calls


# ---------------------------------------------------------------------------
# GET /search
# ---------------------------------------------------------------------------

def _seed_tickets(service: Service, narratives: list[str]) -> None:
    """POST several tickets so the read endpoints have something to read."""
    for index, narrative in enumerate(narratives):
        service.post_ticket(narrative, headers={"X-Source-Row": str(10000 + index)})


def test_search_is_case_insensitive(build_service) -> None:
    service = build_service()
    _seed_tickets(
        service,
        [
            "The servicer lost my ESCROW payment",
            "A collector called my employer about a card balance",
        ],
    )
    for query in ("escrow", "ESCROW", "EsCrOw"):
        body = service.client.get("/search", params={"q": query}).json()
        assert body["count"] == 1, query
        assert body["results"][0]["narrative"].endswith("payment")


def test_search_honours_and_clamps_limit(build_service) -> None:
    service = build_service()
    _seed_tickets(service, [f"a fee complaint numbered {i}" for i in range(6)])

    body = service.client.get("/search", params={"q": "fee", "limit": 2}).json()
    assert body["count"] == 2
    assert body["limit"] == 2

    # Out of range in both directions: clamped, not rejected.
    assert service.client.get(
        "/search", params={"q": "fee", "limit": 0}
    ).json()["limit"] == 1
    clamped = service.client.get("/search", params={"q": "fee", "limit": 99999}).json()
    assert clamped["limit"] == 500
    assert clamped["count"] == 6


def test_search_defaults_to_fifty(build_service) -> None:
    service = build_service()
    assert service.client.get("/search", params={"q": "x"}).json()["limit"] == 50


def test_search_requires_a_query(build_service) -> None:
    service = build_service()
    assert service.client.get("/search").status_code == 422


def test_search_is_logged_with_null_model_fields(build_service) -> None:
    service = build_service()
    service.client.get("/search", params={"q": "escrow", "limit": 10})

    line = service.last_log_line()
    assert line["endpoint"] == "/search"
    assert line["method"] == "GET"
    assert line["status"] == 200
    assert line["ticket_chars"] is None
    assert line["model_tag"] is None
    assert line["predicted_category"] is None
    assert line["model_latency_ms"] is None
    assert line["error"] is None


# ---------------------------------------------------------------------------
# GET /stats
# ---------------------------------------------------------------------------

def test_stats_counts_by_category_in_canonical_order(build_service) -> None:
    service = build_service(ollama=FakeOllama(reply="Mortgage"))
    service.post_ticket("first mortgage complaint")
    service.post_ticket("second mortgage complaint")
    service.ollama.reply = "Credit reporting"
    service.post_ticket("a bureau will not fix my file")

    body = service.client.get("/stats").json()
    assert body["total"] == 3
    assert list(body["counts"]) == [*CATEGORIES, UNPARSEABLE]
    assert body["counts"]["Mortgage"] == 2
    assert body["counts"]["Credit reporting"] == 1
    assert body["counts"]["Consumer loan"] == 0


def test_stats_on_an_empty_service_is_all_zeroes(build_service) -> None:
    """The service starts empty; ``scripts/reset.sh`` returns it to this state."""
    service = build_service()
    body = service.client.get("/stats").json()
    assert body["total"] == 0
    assert list(body["counts"]) == [*CATEGORIES, UNPARSEABLE]
    assert set(body["counts"].values()) == {0}


def test_stats_is_logged_with_null_model_fields(build_service) -> None:
    service = build_service()
    service.client.get("/stats")
    line = service.last_log_line()
    assert line["endpoint"] == "/stats"
    assert line["ticket_chars"] is None
    assert line["model_tag"] is None
    assert line["num_ctx"] is None


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

def test_health_reports_the_configuration(build_service) -> None:
    service = build_service(reachable=True)
    body = service.client.get("/health").json()

    assert body["status"] == "ok"
    assert body["ollama_reachable"] is True
    assert body["model_tag"] == TEST_MODEL_TAG
    assert body["model_digest"] == TEST_MODEL_DIGEST
    assert body["num_ctx"] == 4096
    assert body["seed"] == 42
    assert body["prompt_hash"] == PROMPT_HASH
    assert body["ollama_base_url"] == "http://ollama.invalid:11434"
    assert body["uvicorn_workers"] == 1
    assert body["threadpool_size"] == 40
    assert body["db_path"] == str(service.settings.db_path)
    assert body["categories"] == list(CATEGORIES)


def test_health_is_degraded_when_ollama_is_unreachable(build_service) -> None:
    """Still HTTP 200: the service is up, the backend is not. Check before a run."""
    service = build_service(reachable=False)
    response = service.client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["ollama_reachable"] is False


def test_health_is_not_written_to_the_request_log(build_service) -> None:
    """A container health check polls this; the lines would swamp the evidence."""
    service = build_service()
    for _ in range(3):
        service.client.get("/health")
    assert service.log_lines() == []


def test_digest_is_resolved_at_startup_when_not_pinned(build_service) -> None:
    """With ``MODEL_DIGEST`` empty, the service asks Ollama what it is serving."""
    service = build_service(resolved_digest="sha256:resolvedatstartup", MODEL_DIGEST="")
    assert service.client.get("/health").json()["model_digest"] == (
        "sha256:resolvedatstartup"
    )
    service.post_ticket()
    assert service.last_log_line()["model_digest"] == "sha256:resolvedatstartup"


def test_unresolvable_digest_is_reported_as_null(build_service) -> None:
    """Never invent a digest: a missing pin must be visible as missing."""
    service = build_service(resolved_digest=None, MODEL_DIGEST="")
    assert service.client.get("/health").json()["model_digest"] is None


def test_explicit_digest_pin_is_not_overwritten(build_service) -> None:
    """``models/models.yaml`` is the pin of record; the probe must not win."""
    service = build_service(resolved_digest="sha256:somethingelse")
    assert service.client.get("/health").json()["model_digest"] == TEST_MODEL_DIGEST


# ---------------------------------------------------------------------------
# Cross-cutting
# ---------------------------------------------------------------------------

def test_every_logged_request_appears_once_and_only_once(build_service) -> None:
    """One line per request, in order: the property reconcile.py depends on."""
    service = build_service()
    ids = [f"req-{index}" for index in range(4)]
    service.post_ticket(headers={"X-Request-ID": ids[0]})
    service.client.get("/search", params={"q": "a"}, headers={"X-Request-ID": ids[1]})
    service.client.get("/stats", headers={"X-Request-ID": ids[2]})
    service.client.get("/health", headers={"X-Request-ID": ids[3]})  # not logged

    lines = service.log_lines()
    assert [line["request_id"] for line in lines] == ids[:3]
    assert [line["endpoint"] for line in lines] == ["/tickets", "/search", "/stats"]


def test_timestamps_are_iso8601_utc_with_milliseconds(build_service) -> None:
    service = build_service()
    service.post_ticket()
    ts = service.last_log_line()["ts"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", ts), ts


def test_blank_request_id_header_falls_back_to_a_generated_one(build_service) -> None:
    """A present-but-blank header must not produce an unjoinable empty id."""
    service = build_service()
    response = service.post_ticket(headers={"X-Request-ID": "   "})
    generated = response.json()["request_id"]
    assert uuid.UUID(generated).version == 4
    assert service.last_log_line()["request_id"] == generated
