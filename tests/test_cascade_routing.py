"""Behaviour tests for the Assignment 2 cascade, with both model calls stubbed.

Owner: Yeo Kai Yuan (Part 1 -- technical core). TODO_A2.md §1.2, "Tests:
cascade routing logic with both model calls stubbed (no model contacted by the
test suite)".

**No model runs here and no HTTP request leaves this process.**
``service.ollama_client.generate`` is replaced by :class:`TwoModelFake`, which
answers per model tag, and the start-up/health probes are replaced too.

The escalation settings used here are *test fixtures*, written into
``service.cascade.RULE_SETTINGS`` with ``monkeypatch`` and removed after each
test. They are deliberately not the team's settings (which are Part 2's to
choose and are copied from ``cascade/escalation_rule.md`` §3), and nothing here
asserts a latency or an accuracy figure -- only routing and bookkeeping.

``tests/test_cascade.py`` (the structural label-leakage guardrails) is kept as
it was; these tests sit beside it.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient

from service import cascade
from service import main as service_main
from service import ollama_client
from service.categories import CATEGORIES, UNPARSEABLE
from service.config import ConfigError, load_settings
from service.log_schema import CASCADE_LOG_FIELDS, LOG_FIELDS, OLLAMA_TIMING_FIELDS
from service.ollama_client import OllamaResult
from service.prompt import build_prompt

#: Obviously-not-real model identities.
SMALL_TAG = "testsmall:1b"
SMALL_DIGEST = "sha256:0000small"
LARGE_TAG = "testlarge:7b"
LARGE_DIGEST = "sha256:0000large"

#: Arbitrary constants the fake reports per model. Not measurements.
SMALL_LATENCY_MS = 100.0
LARGE_LATENCY_MS = 900.0
SMALL_TIMINGS = {
    "total_duration": 90_000_000,
    "load_duration": 1_000_000,
    "prompt_eval_count": 300,
    "prompt_eval_duration": 60_000_000,
    "eval_count": 4,
    "eval_duration": 29_000_000,
}
LARGE_TIMINGS = {
    "total_duration": 850_000_000,
    "load_duration": 2_000_000,
    "prompt_eval_count": 310,
    "prompt_eval_duration": 700_000_000,
    "eval_count": 5,
    "eval_duration": 148_000_000,
}

SHORT_NARRATIVE = "My mortgage escrow was applied to the wrong account."
LONG_NARRATIVE = "My credit card was charged twice. " * 40  # 1,360 characters

#: Test-only settings. Setting A accepts two categories; Setting B is a length rule.
TEST_RULES = {
    "A": cascade.CategoryRule(accept_categories=frozenset({"Mortgage", "Credit card"})),
    "B": cascade.LengthRule(max_chars=500),
}


class TwoModelFake:
    """Replacement for :func:`service.ollama_client.generate` that answers per tag."""

    def __init__(
        self,
        *,
        small_reply: str | None = "Mortgage",
        large_reply: str | None = "Debt collection",
        small_error: str | None = None,
        large_error: str | None = None,
    ) -> None:
        self.replies = {SMALL_TAG: small_reply, LARGE_TAG: large_reply}
        self.errors = {SMALL_TAG: small_error, LARGE_TAG: large_error}
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> OllamaResult:
        self.calls.append(kwargs)
        tag = kwargs["model_tag"]
        latency = SMALL_LATENCY_MS if tag == SMALL_TAG else LARGE_LATENCY_MS
        if self.errors.get(tag):
            return OllamaResult(
                raw_text=None,
                model_latency_ms=latency,
                error=self.errors[tag],
                timings={name: None for name in OLLAMA_TIMING_FIELDS},
            )
        timings = SMALL_TIMINGS if tag == SMALL_TAG else LARGE_TIMINGS
        return OllamaResult(
            raw_text=self.replies[tag],
            model_latency_ms=latency,
            error=None,
            timings=dict(timings),
        )

    @property
    def tags_called(self) -> list[str]:
        return [call["model_tag"] for call in self.calls]


@pytest.fixture()
def test_rules(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Install the test-only rules for the duration of one test."""
    monkeypatch.setattr(cascade, "RULE_SETTINGS", dict(TEST_RULES))
    return TEST_RULES


def run_cascade(fake: TwoModelFake, narrative: str, setting: str) -> cascade.CascadeResult:
    """Run one ticket through the real cascade with ``fake`` standing in for Ollama."""
    original = ollama_client.generate
    ollama_client.generate = fake  # type: ignore[assignment]
    try:
        return _run_cascade(narrative, setting)
    finally:
        ollama_client.generate = original  # type: ignore[assignment]


def _run_cascade(narrative: str, setting: str) -> cascade.CascadeResult:
    return asyncio.run(
        cascade.classify_with_cascade(
            base_url="http://ollama.invalid:11434",
            small_model_tag=SMALL_TAG,
            small_model_digest=SMALL_DIGEST,
            large_model_tag=LARGE_TAG,
            large_model_digest=LARGE_DIGEST,
            prompt=build_prompt(narrative),
            narrative_chars=len(narrative),
            seed=42,
            num_ctx=4096,
            timeout_s=5.0,
            setting=setting,  # type: ignore[arg-type]
        )
    )


def answer(category: str, chars: int = 100) -> cascade.SmallModelAnswer:
    return cascade.SmallModelAnswer(
        predicted_category=category, raw_text=category, narrative_chars=chars, result=None
    )


# ---------------------------------------------------------------------------
# The rule shapes
# ---------------------------------------------------------------------------

def test_category_rule_accepts_only_its_listed_predicted_categories() -> None:
    rule = cascade.CategoryRule(accept_categories=frozenset({"Mortgage"}))
    assert rule.escalate(answer("Mortgage")) is False
    assert rule.escalate(answer("Debt collection")) is True
    assert rule.escalate(answer(UNPARSEABLE)) is True
    assert rule.escalates_before_small_call(10_000) is False


def test_category_rule_refuses_unknown_names_and_unparseable() -> None:
    with pytest.raises(ValueError, match="canonical category"):
        cascade.CategoryRule(accept_categories=frozenset({"mortgage"}))
    with pytest.raises(ValueError, match="UNPARSEABLE"):
        cascade.CategoryRule(accept_categories=frozenset({UNPARSEABLE}))


def test_category_rule_describes_itself_as_a_literal_condition_in_canonical_order() -> None:
    rule = cascade.CategoryRule(accept_categories=frozenset({"Mortgage", "Credit reporting"}))
    text = rule.describe()
    assert text.startswith("category: escalate = predicted_category NOT IN {")
    assert text.index('"Credit reporting"') < text.index('"Mortgage"')


def test_length_rule_escalates_long_tickets_and_unparseable_short_ones() -> None:
    rule = cascade.LengthRule(max_chars=500)
    assert rule.escalates_before_small_call(501) is True
    assert rule.escalates_before_small_call(500) is False
    assert rule.escalate(answer("Mortgage", chars=500)) is False
    assert rule.escalate(answer("Mortgage", chars=501)) is True
    assert rule.escalate(answer(UNPARSEABLE, chars=10)) is True
    assert "len(narrative) > 500" in rule.describe()


def test_an_unconfigured_setting_refuses_rather_than_guessing() -> None:
    """Until escalation_rule.md §3 is copied in, both settings are None."""
    with pytest.raises(cascade.CascadeNotConfiguredError, match="escalation_rule.md"):
        cascade.rule_for("A")
    with pytest.raises(cascade.CascadeNotConfiguredError):
        cascade.should_escalate(answer("Mortgage"), setting="B")
    with pytest.raises(cascade.CascadeNotConfiguredError, match="unknown cascade setting"):
        cascade.rule_for("C")


def test_should_escalate_uses_the_setting_it_is_given(test_rules) -> None:
    long_mortgage = answer("Mortgage", chars=900)
    assert cascade.should_escalate(long_mortgage, setting="A") is False
    assert cascade.should_escalate(long_mortgage, setting="B") is True


# ---------------------------------------------------------------------------
# classify_with_cascade
# ---------------------------------------------------------------------------

def test_an_accepted_ticket_calls_only_the_small_model(test_rules) -> None:
    fake = TwoModelFake(small_reply="Mortgage")
    result = run_cascade(fake, SHORT_NARRATIVE, "A")

    assert fake.tags_called == [SMALL_TAG]
    assert result.ok and result.escalated is False
    assert result.final_category == "Mortgage"
    assert result.final_model_tag == SMALL_TAG
    assert result.final_model_digest == SMALL_DIGEST
    assert result.small_model_category == "Mortgage"
    assert result.large_result is None
    assert result.model_latency_ms == SMALL_LATENCY_MS
    assert result.timings == SMALL_TIMINGS
    assert result.small_model_latency_ms == SMALL_LATENCY_MS
    assert result.small_load_duration == SMALL_TIMINGS["load_duration"]


def test_an_escalated_ticket_calls_small_then_large_with_the_same_prompt(test_rules) -> None:
    fake = TwoModelFake(small_reply="Debt collection", large_reply="Credit reporting")
    result = run_cascade(fake, SHORT_NARRATIVE, "A")

    assert fake.tags_called == [SMALL_TAG, LARGE_TAG]
    # The one unchanged classification prompt, for both models (brief, Scope).
    assert fake.calls[0]["prompt"] == fake.calls[1]["prompt"] == build_prompt(SHORT_NARRATIVE)
    for call in fake.calls:
        assert (call["seed"], call["num_ctx"], call["timeout_s"]) == (42, 4096, 5.0)
    assert result.ok and result.escalated is True
    assert result.final_category == "Credit reporting"
    assert result.final_model_tag == LARGE_TAG
    assert result.final_model_digest == LARGE_DIGEST
    # What the small model said is kept, independent of what was returned.
    assert result.small_model_category == "Debt collection"
    # Latency and Ollama's own fields are summed over both calls.
    assert result.model_latency_ms == SMALL_LATENCY_MS + LARGE_LATENCY_MS
    for name in OLLAMA_TIMING_FIELDS:
        assert result.timings[name] == SMALL_TIMINGS[name] + LARGE_TIMINGS[name]
    assert result.small_model_latency_ms == SMALL_LATENCY_MS


def test_an_unparseable_small_answer_is_escalated(test_rules) -> None:
    fake = TwoModelFake(small_reply="I am not sure what this is about.")
    result = run_cascade(fake, SHORT_NARRATIVE, "A")
    assert fake.tags_called == [SMALL_TAG, LARGE_TAG]
    assert result.small_model_category == UNPARSEABLE
    assert result.escalated is True


def test_the_length_rule_sends_a_long_ticket_straight_to_the_large_model(test_rules) -> None:
    fake = TwoModelFake(large_reply="Credit card")
    result = run_cascade(fake, LONG_NARRATIVE, "B")

    assert fake.tags_called == [LARGE_TAG]
    assert result.escalated is True
    assert result.small_result is None
    assert result.small_model_category is None
    assert result.small_model_latency_ms is None
    assert result.final_category == "Credit card"
    assert result.model_latency_ms == LARGE_LATENCY_MS


def test_the_length_rule_accepts_a_short_ticket_from_the_small_model(test_rules) -> None:
    fake = TwoModelFake(small_reply="Mortgage")
    result = run_cascade(fake, SHORT_NARRATIVE, "B")
    assert fake.tags_called == [SMALL_TAG]
    assert result.escalated is False


def test_a_failed_small_call_is_a_failure_not_an_escalation(test_rules) -> None:
    """No hidden fallback: a retry on the large model would distort both measures."""
    fake = TwoModelFake(small_error="ollama_timeout")
    result = run_cascade(fake, SHORT_NARRATIVE, "A")

    assert fake.tags_called == [SMALL_TAG]
    assert not result.ok
    assert result.error == "ollama_timeout"
    assert result.escalated is False
    assert result.final_category is None
    assert result.final_model_tag == SMALL_TAG
    assert result.small_model_category is None
    assert result.model_latency_ms == SMALL_LATENCY_MS
    assert all(value is None for value in result.timings.values())


def test_a_failed_large_call_after_escalation_is_reported_as_such(test_rules) -> None:
    fake = TwoModelFake(small_reply="Debt collection", large_error="ollama_http_error")
    result = run_cascade(fake, SHORT_NARRATIVE, "A")

    assert fake.tags_called == [SMALL_TAG, LARGE_TAG]
    assert not result.ok
    assert result.error == "ollama_http_error"
    assert result.escalated is True
    assert result.final_model_tag == LARGE_TAG
    assert result.small_model_category == "Debt collection"
    assert result.model_latency_ms == SMALL_LATENCY_MS + LARGE_LATENCY_MS
    # Only the small call reported timings; nothing is invented for the large one.
    assert result.timings == SMALL_TIMINGS


def test_nothing_is_cached_between_identical_tickets(test_rules) -> None:
    """Brief, Scope: caching is not permitted. Same ticket twice, two full cascades."""
    fake = TwoModelFake(small_reply="Debt collection")
    run_cascade(fake, SHORT_NARRATIVE, "A")
    run_cascade(fake, SHORT_NARRATIVE, "A")
    assert fake.tags_called == [SMALL_TAG, LARGE_TAG, SMALL_TAG, LARGE_TAG]


def test_classify_refuses_before_any_model_call_when_unconfigured() -> None:
    fake = TwoModelFake()
    with pytest.raises(cascade.CascadeNotConfiguredError):
        run_cascade(fake, SHORT_NARRATIVE, "A")
    assert fake.calls == []


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def base_env(tmp_path: Path, **overrides: str) -> dict[str, str]:
    env = {
        "OLLAMA_BASE_URL": "http://ollama.invalid:11434",
        "MODEL_TAG": LARGE_TAG,
        "MODEL_DIGEST": LARGE_DIGEST,
        "NUM_CTX": "4096",
        "OLLAMA_TIMEOUT_S": "5",
        "OLLAMA_SEED": "42",
        "DB_PATH": str(tmp_path / "volume" / "triage.db"),
        "LOG_DIR": str(tmp_path / "logs" / "service"),
    }
    env.update(overrides)
    return env


def cascade_env(tmp_path: Path, setting: str = "A", **overrides: str) -> dict[str, str]:
    env = base_env(
        tmp_path,
        SERVICE_MODE="cascade",
        CASCADE_SETTING=setting,
        CASCADE_SMALL_MODEL_TAG=SMALL_TAG,
        CASCADE_SMALL_MODEL_DIGEST=SMALL_DIGEST,
    )
    env.update(overrides)
    return env


def test_single_mode_is_the_default_and_carries_no_cascade_configuration(tmp_path: Path) -> None:
    settings = load_settings(
        env=base_env(tmp_path, CASCADE_SETTING="A", CASCADE_SMALL_MODEL_TAG=SMALL_TAG),
        use_dotenv=False,
    )
    assert settings.service_mode == "single"
    assert settings.cascade_setting is None
    assert settings.cascade_small_model_tag is None
    described = settings.describe()
    assert described["service_mode"] == "single"
    assert described["cascade_rule"] is None
    assert described["cascade_large_model_tag"] is None


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"CASCADE_SETTING": ""}, "CASCADE_SETTING"),
        ({"CASCADE_SETTING": "C"}, "CASCADE_SETTING"),
        ({"CASCADE_SMALL_MODEL_TAG": ""}, "CASCADE_SMALL_MODEL_TAG"),
        ({"CASCADE_SMALL_MODEL_TAG": LARGE_TAG}, "two different models"),
        ({"SERVICE_MODE": "fastest"}, "SERVICE_MODE"),
    ],
)
def test_bad_cascade_configuration_is_refused(tmp_path: Path, overrides, message) -> None:
    with pytest.raises(ConfigError, match=message):
        load_settings(env=cascade_env(tmp_path, **overrides), use_dotenv=False)


def test_setting_names_are_normalised_to_upper_case(tmp_path: Path) -> None:
    settings = load_settings(env=cascade_env(tmp_path, setting="b"), use_dotenv=False)
    assert settings.cascade_setting == "B"


def test_a_cascade_service_will_not_start_without_a_written_rule(tmp_path: Path) -> None:
    settings = load_settings(env=cascade_env(tmp_path), use_dotenv=False)
    with pytest.raises(ConfigError, match="escalation_rule.md"):
        service_main.create_app(settings)


# ---------------------------------------------------------------------------
# POST /tickets in cascade mode
# ---------------------------------------------------------------------------

@pytest.fixture()
def build_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator:
    stack = contextlib.ExitStack()

    async def probe(base_url: str, timeout_s: float) -> bool:
        return True

    async def digest(base_url: str, model_tag: str, timeout_s: float) -> str | None:
        return {SMALL_TAG: SMALL_DIGEST, LARGE_TAG: LARGE_DIGEST}.get(model_tag)

    def _build(fake: TwoModelFake, env: dict[str, str]):
        monkeypatch.setattr(cascade, "RULE_SETTINGS", dict(TEST_RULES))
        monkeypatch.setattr(ollama_client, "generate", fake)
        monkeypatch.setattr(ollama_client, "probe_reachable", probe)
        monkeypatch.setattr(ollama_client, "resolve_model_digest", digest)
        settings = load_settings(env=env, use_dotenv=False)
        client = stack.enter_context(TestClient(service_main.create_app(settings)))
        return client, settings

    yield _build
    stack.close()


def log_lines(settings) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for path in sorted(Path(settings.log_dir).glob("*.jsonl")):
        lines += [json.loads(raw) for raw in path.read_text(encoding="utf-8").splitlines() if raw.strip()]
    return lines


def test_the_response_shape_is_identical_whichever_model_answered(build_service, tmp_path) -> None:
    """Brief: "the caller should not be able to tell which model produced the answer"."""
    fake = TwoModelFake(small_reply="Mortgage", large_reply="Debt collection")
    client, _ = build_service(fake, cascade_env(tmp_path))
    accepted = client.post("/tickets", json={"narrative": SHORT_NARRATIVE})
    fake.replies[SMALL_TAG] = "Consumer loan"  # not in Setting A's accept-list
    escalated = client.post("/tickets", json={"narrative": SHORT_NARRATIVE})

    assert accepted.status_code == escalated.status_code == 200
    assert set(accepted.json()) == set(escalated.json()) == {"id", "category", "request_id"}
    assert set(accepted.headers) == set(escalated.headers)
    assert accepted.json()["category"] == "Mortgage"
    assert escalated.json()["category"] == "Debt collection"


def test_a_cascade_log_line_records_which_model_answered(build_service, tmp_path) -> None:
    fake = TwoModelFake(small_reply="Mortgage", large_reply="Debt collection")
    client, settings = build_service(fake, cascade_env(tmp_path))
    client.post("/tickets", json={"narrative": SHORT_NARRATIVE}, headers={"X-Request-ID": "acc-1"})
    fake.replies[SMALL_TAG] = "Bank account or service"
    client.post("/tickets", json={"narrative": SHORT_NARRATIVE}, headers={"X-Request-ID": "esc-1"})

    lines = {line["request_id"]: line for line in log_lines(settings)}
    for line in lines.values():
        assert tuple(line) == LOG_FIELDS

    acc, esc = lines["acc-1"], lines["esc-1"]
    assert acc["escalated"] is False
    assert acc["model_tag"] == SMALL_TAG and acc["model_digest"] == SMALL_DIGEST
    assert acc["predicted_category"] == acc["small_model_category"] == "Mortgage"
    assert acc["model_latency_ms"] == SMALL_LATENCY_MS
    assert acc["small_model_latency_ms"] == SMALL_LATENCY_MS

    assert esc["escalated"] is True
    assert esc["model_tag"] == LARGE_TAG and esc["model_digest"] == LARGE_DIGEST
    assert esc["predicted_category"] == "Debt collection"
    assert esc["small_model_category"] == "Bank account or service"
    assert esc["model_latency_ms"] == SMALL_LATENCY_MS + LARGE_LATENCY_MS
    assert esc["load_duration"] == SMALL_TIMINGS["load_duration"] + LARGE_TIMINGS["load_duration"]
    assert esc["small_load_duration"] == SMALL_TIMINGS["load_duration"]

    for line in (acc, esc):
        assert line["cascade_setting"] == "A"
        assert line["small_model_tag"] == SMALL_TAG


def test_the_escalation_fraction_is_derivable_from_the_log_alone(build_service, tmp_path) -> None:
    fake = TwoModelFake()
    client, settings = build_service(fake, cascade_env(tmp_path))
    replies = ["Mortgage", "Credit card", "Debt collection", UNPARSEABLE.lower(), "Mortgage"]
    for reply in replies:
        fake.replies[SMALL_TAG] = reply
        client.post("/tickets", json={"narrative": SHORT_NARRATIVE})
    lines = [line for line in log_lines(settings) if line["endpoint"] == "/tickets"]
    escalated = sum(1 for line in lines if line["escalated"])
    assert (escalated, len(lines)) == (2, 5)
    # And it agrees with the number of large-model calls actually made.
    assert fake.tags_called.count(LARGE_TAG) == escalated


def test_a_failed_small_call_returns_502_stores_nothing_and_logs_the_route(build_service, tmp_path) -> None:
    fake = TwoModelFake(small_error="ollama_timeout")
    client, settings = build_service(fake, cascade_env(tmp_path))
    response = client.post("/tickets", json={"narrative": SHORT_NARRATIVE})

    assert response.status_code == 502
    assert client.get("/stats").json()["total"] == 0
    line = [l for l in log_lines(settings) if l["endpoint"] == "/tickets"][0]
    assert line["status"] == 502 and line["error"] == "ollama_timeout"
    assert line["escalated"] is False
    assert line["model_tag"] == SMALL_TAG
    assert line["predicted_category"] is None


def test_stats_counts_the_final_category(build_service, tmp_path) -> None:
    fake = TwoModelFake(small_reply="Money transfer or service", large_reply="Credit card")
    client, _ = build_service(fake, cascade_env(tmp_path))
    client.post("/tickets", json={"narrative": SHORT_NARRATIVE})
    counts = client.get("/stats").json()["counts"]
    assert counts["Credit card"] == 1
    assert sum(counts.values()) == 1


def test_health_reports_the_mode_the_setting_and_the_literal_rule(build_service, tmp_path) -> None:
    client, _ = build_service(TwoModelFake(), cascade_env(tmp_path, setting="B"))
    health = client.get("/health").json()
    assert health["service_mode"] == "cascade"
    assert health["cascade_setting"] == "B"
    assert health["cascade_small_model_tag"] == SMALL_TAG
    assert health["cascade_small_model_digest"] == SMALL_DIGEST
    assert health["cascade_large_model_tag"] == LARGE_TAG
    assert health["model_tag"] == LARGE_TAG
    assert health["cascade_rule"] == TEST_RULES["B"].describe()


def test_the_small_model_digest_is_resolved_at_start_up_when_not_pinned(build_service, tmp_path) -> None:
    env = cascade_env(tmp_path)
    env["CASCADE_SMALL_MODEL_DIGEST"] = ""
    client, settings = build_service(TwoModelFake(), env)
    assert settings.cascade_small_model_digest == SMALL_DIGEST
    assert client.get("/health").json()["cascade_small_model_digest"] == SMALL_DIGEST


def test_single_mode_lines_carry_null_cascade_fields(build_service, tmp_path) -> None:
    """A null ``escalated`` means "no cascade involved"; only a cascade line says false."""
    fake = TwoModelFake(large_reply="Mortgage")
    client, settings = build_service(fake, base_env(tmp_path))
    client.post("/tickets", json={"narrative": SHORT_NARRATIVE})
    client.get("/stats")
    client.get("/search", params={"q": "mortgage"})
    assert fake.tags_called == [LARGE_TAG]
    for line in log_lines(settings):
        for name in CASCADE_LOG_FIELDS:
            assert line[name] is None, (line["endpoint"], name)


def test_every_category_can_be_returned_by_either_model(build_service, tmp_path) -> None:
    """Routing never narrows the output space: the large model can answer anything."""
    fake = TwoModelFake(small_reply="Debt collection")
    client, _ = build_service(fake, cascade_env(tmp_path))
    seen = set()
    for category in CATEGORIES:
        fake.replies[LARGE_TAG] = category
        seen.add(client.post("/tickets", json={"narrative": SHORT_NARRATIVE}).json()["category"])
    assert seen == set(CATEGORIES)
