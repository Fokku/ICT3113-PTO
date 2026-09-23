"""Tests that the JSONL request log matches the log-line contract exactly.

Owner: Yeo Kai Yuan (Part 1 — baseline service).

The request log is the assignment's primary evidence: every number on a slide has
to reconcile with a line in it, and ``analysis/common.read_service_log`` refuses
a file whose fields do not match :data:`service.log_schema.LOG_FIELDS`. So this
module tests the log twice over:

* the **builder** — :func:`service.request_log.build_log_line` must refuse an
  unknown field and a missing field, so a handler cannot drift off-schema;
* the **output** — real lines written by a real app through all four endpoints
  must have exactly the contracted keys, in order, with the contracted types.

No model runs here: the backend is mocked, as in ``tests/test_endpoints.py``.
The small harness is duplicated from that module on purpose — ``tests/conftest.py``
is shared with the other parts of the build and is not ours to extend.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from service import main as service_main
from service import ollama_client
from service.config import Settings, load_settings
from service.log_schema import (
    LOG_FIELDS,
    OLLAMA_TIMING_FIELDS,
    RAW_OUTPUT_MAX_CHARS,
)
from service.ollama_client import OllamaResult
from service.request_log import (
    LogSchemaError,
    build_log_line,
    iso_ms,
    log_path_for,
    write_log_line,
)

#: The seven fields that describe the model and must be null off ``/tickets``.
MODEL_ONLY_FIELDS: tuple[str, ...] = (
    "model_tag",
    "model_digest",
    "predicted_category",
    "raw_model_output",
    "prompt_hash",
    "num_ctx",
    "seed",
)

#: A complete, valid set of keyword arguments for :func:`build_log_line`.
#: Values are obviously synthetic; nothing here is a measurement.
VALID_FIELDS: dict[str, Any] = {
    "ts": "2026-10-01T09:00:00.000Z",
    "request_id": "req-0001",
    "source_row": "10000",
    "warmup": False,
    "endpoint": "/tickets",
    "method": "POST",
    "status": 200,
    "ticket_chars": 861,
    "model_tag": "testmodel:1b",
    "model_digest": "sha256:0000testdigest",
    "predicted_category": "Mortgage",
    "raw_model_output": "Mortgage",
    "prompt_hash": "sha256:0000000000000000",
    "num_ctx": 4096,
    "seed": 42,
    "total_latency_ms": 1.0,
    "model_latency_ms": 1.0,
    "total_duration": 1,
    "load_duration": 1,
    "prompt_eval_count": 1,
    "prompt_eval_duration": 1,
    "eval_count": 1,
    "eval_duration": 1,
    "error": None,
}


# ---------------------------------------------------------------------------
# build_log_line: the guard against schema drift
# ---------------------------------------------------------------------------

def test_the_contract_has_twenty_four_fields() -> None:
    """A field added or removed is a breaking change for every recorded run."""
    assert len(LOG_FIELDS) == 24
    assert len(set(LOG_FIELDS)) == 24
    assert set(VALID_FIELDS) == set(LOG_FIELDS)


def test_build_log_line_returns_fields_in_schema_order() -> None:
    """Key order is asserted because the file is read, diffed and grepped by hand."""
    shuffled = dict(reversed(list(VALID_FIELDS.items())))
    assert tuple(build_log_line(**shuffled)) == LOG_FIELDS


def test_build_log_line_rejects_an_unknown_field() -> None:
    with pytest.raises(LogSchemaError, match="unknown log field"):
        build_log_line(**VALID_FIELDS, model_temperature=0)


def test_build_log_line_rejects_a_misspelled_field() -> None:
    """The realistic version of the above: a typo, not an invention."""
    fields = dict(VALID_FIELDS)
    fields["predicted_catagory"] = fields.pop("predicted_category")
    with pytest.raises(LogSchemaError) as raised:
        build_log_line(**fields)
    assert "predicted_catagory" in str(raised.value)
    assert "predicted_category" in str(raised.value)  # reported as missing too


@pytest.mark.parametrize("omitted", LOG_FIELDS)
def test_build_log_line_rejects_a_missing_field(omitted: str) -> None:
    """Every field must be passed explicitly, including the null ones.

    There are no defaults on purpose: a default would let a handler quietly stop
    reporting something and nobody would notice until the run could not be
    pinned to a model.
    """
    fields = {k: v for k, v in VALID_FIELDS.items() if k != omitted}
    with pytest.raises(LogSchemaError, match="missing log field"):
        build_log_line(**fields)


def test_build_log_line_truncates_raw_output_without_appending_anything() -> None:
    """No ellipsis: the analysis compares this string against a category name."""
    long_reply = "Mortgage " + "y" * 900
    line = build_log_line(**{**VALID_FIELDS, "raw_model_output": long_reply})
    assert len(line["raw_model_output"]) == RAW_OUTPUT_MAX_CHARS
    assert line["raw_model_output"] == long_reply[:RAW_OUTPUT_MAX_CHARS]


def test_build_log_line_leaves_a_short_reply_alone() -> None:
    line = build_log_line(**{**VALID_FIELDS, "raw_model_output": "Mortgage"})
    assert line["raw_model_output"] == "Mortgage"


def test_build_log_line_rounds_latencies_to_one_decimal_place() -> None:
    line = build_log_line(
        **{**VALID_FIELDS, "total_latency_ms": 1234.5678, "model_latency_ms": 1200.04}
    )
    assert line["total_latency_ms"] == 1234.6
    assert line["model_latency_ms"] == 1200.0


def test_build_log_line_keeps_a_null_model_latency() -> None:
    """Null is not zero: ``/search`` never called the model."""
    line = build_log_line(**{**VALID_FIELDS, "model_latency_ms": None})
    assert line["model_latency_ms"] is None


def test_write_log_line_refuses_an_unbuilt_dict(tmp_path: Path) -> None:
    """The writer re-checks, because a wrong log line is worse than a crash."""
    with pytest.raises(LogSchemaError, match="LOG_FIELDS in order"):
        write_log_line(tmp_path, {"ts": "2026-10-01T09:00:00.000Z"})


# ---------------------------------------------------------------------------
# Timestamps and file naming
# ---------------------------------------------------------------------------

def test_iso_ms_formats_utc_with_milliseconds() -> None:
    moment = datetime(2026, 10, 1, 13, 53, 32, 123_456, tzinfo=timezone.utc)
    assert iso_ms(moment) == "2026-10-01T13:53:32.123Z"


def test_iso_ms_converts_to_utc() -> None:
    """A stamp must never carry a local offset: the analysis assumes UTC."""
    local = datetime(
        2026, 10, 1, 21, 0, 0, tzinfo=timezone(timedelta(hours=8))
    )  # Singapore time
    assert iso_ms(local) == "2026-10-01T13:00:00.000Z"


def test_log_file_is_named_by_the_utc_date(tmp_path: Path) -> None:
    before = datetime(2026, 10, 1, 23, 59, 59, 900_000, tzinfo=timezone.utc)
    after = before + timedelta(seconds=1)
    assert log_path_for(tmp_path, before).name == "2026-10-01.jsonl"
    # A run that crosses midnight UTC lands in two files; that is deliberate,
    # and the run scripts copy the slice they need into the run directory.
    assert log_path_for(tmp_path, after).name == "2026-10-02.jsonl"


def test_write_log_line_appends(tmp_path: Path) -> None:
    moment = datetime(2026, 10, 1, 9, 0, 0, tzinfo=timezone.utc)
    for index in range(3):
        path = write_log_line(
            tmp_path,
            build_log_line(**{**VALID_FIELDS, "request_id": f"req-{index}"}),
            moment,
        )
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["request_id"] for line in lines] == [
        "req-0",
        "req-1",
        "req-2",
    ]


def test_write_log_line_creates_the_log_directory(tmp_path: Path) -> None:
    """``LOG_DIR`` is a bind mount that may not exist on a fresh checkout."""
    target = tmp_path / "logs" / "service"
    path = write_log_line(target, build_log_line(**VALID_FIELDS))
    assert path.is_file()


# ---------------------------------------------------------------------------
# What the running service actually writes
# ---------------------------------------------------------------------------

LONG_REPLY = "Mortgage — " + "z" * 900
TIMINGS: dict[str, int] = {
    "total_duration": 120_000_000,
    "load_duration": 1_000_000,
    "prompt_eval_count": 300,
    "prompt_eval_duration": 80_000_000,
    "eval_count": 4,
    "eval_duration": 39_000_000,
}


class _FakeOllama:
    """Minimal stand-in for ``ollama_client.generate``; see tests/test_endpoints.py."""

    def __init__(self, *, reply: str | None, error: str | None = None) -> None:
        self.reply = reply
        self.error = error

    async def __call__(self, **kwargs: Any) -> OllamaResult:
        if self.error is not None:
            return OllamaResult(
                raw_text=None,
                model_latency_ms=99.9,
                error=self.error,
                timings={name: None for name in OLLAMA_TIMING_FIELDS},
            )
        return OllamaResult(
            raw_text=self.reply,
            model_latency_ms=123.4,
            error=None,
            timings=dict(TIMINGS),
        )


async def _reachable(base_url: str, timeout_s: float) -> bool:
    return True


async def _no_digest(base_url: str, model_tag: str, timeout_s: float) -> str | None:
    return None


def _settings(tmp_path: Path) -> Settings:
    return load_settings(
        env={
            "OLLAMA_BASE_URL": "http://ollama.invalid:11434",
            "MODEL_TAG": "testmodel:1b",
            "MODEL_DIGEST": "sha256:0000testdigest",
            "DB_PATH": str(tmp_path / "volume" / "triage.db"),
            "LOG_DIR": str(tmp_path / "logs" / "service"),
        },
        use_dotenv=False,
    )


@pytest.fixture()
def written_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> list[dict[str, Any]]:
    """Drive one app through every logged path and return the lines it wrote.

    Deliberately includes an over-long model reply, a model failure and both read
    endpoints, so the assertions below cover a success line, an error line and a
    line with no model involvement.
    """
    settings = _settings(tmp_path)
    fake = _FakeOllama(reply=LONG_REPLY)
    monkeypatch.setattr(ollama_client, "generate", fake)
    monkeypatch.setattr(ollama_client, "probe_reachable", _reachable)
    monkeypatch.setattr(ollama_client, "resolve_model_digest", _no_digest)

    with TestClient(service_main.create_app(settings)) as client:
        client.post(
            "/tickets",
            json={"narrative": "My mortgage escrow account was mishandled."},
            headers={"X-Request-ID": "req-ok", "X-Source-Row": "10000"},
        )
        fake.error = "ollama_timeout"
        client.post(
            "/tickets",
            json={"narrative": "A second complaint, this time the model times out."},
            headers={"X-Request-ID": "req-502", "X-Warmup": "1"},
        )
        client.get("/search", params={"q": "escrow"}, headers={"X-Request-ID": "req-s"})
        client.get("/stats", headers={"X-Request-ID": "req-t"})
        client.get("/health")  # never logged

    lines: list[dict[str, Any]] = []
    for path in sorted(Path(settings.log_dir).glob("*.jsonl")):
        for raw in path.read_text(encoding="utf-8").splitlines():
            if raw.strip():
                lines.append(json.loads(raw))
    return lines


def test_the_service_logged_one_line_per_logged_request(written_lines) -> None:
    assert [line["request_id"] for line in written_lines] == [
        "req-ok",
        "req-502",
        "req-s",
        "req-t",
    ]


def test_every_written_line_has_exactly_the_contracted_keys_in_order(
    written_lines,
) -> None:
    for line in written_lines:
        assert tuple(line) == LOG_FIELDS, line["request_id"]


def test_written_types_match_the_contract(written_lines) -> None:
    """Types, not just presence: the analysis code builds a DataFrame from these."""
    for line in written_lines:
        assert isinstance(line["ts"], str)
        assert isinstance(line["request_id"], str)
        assert line["source_row"] is None or isinstance(line["source_row"], str)
        assert isinstance(line["warmup"], bool)
        assert isinstance(line["endpoint"], str)
        assert isinstance(line["method"], str)
        assert isinstance(line["status"], int)
        assert line["ticket_chars"] is None or isinstance(line["ticket_chars"], int)
        assert isinstance(line["total_latency_ms"], float)
        assert line["model_latency_ms"] is None or isinstance(
            line["model_latency_ms"], float
        )
        assert line["error"] is None or isinstance(line["error"], str)


def test_written_timestamps_are_iso8601_utc_to_the_millisecond(written_lines) -> None:
    for line in written_lines:
        stamp = line["ts"]
        assert stamp.endswith("Z"), stamp
        # 23 characters: YYYY-MM-DDTHH:MM:SS.mmm plus the Z.
        assert len(stamp) == 24, stamp
        parsed = datetime.fromisoformat(stamp)
        assert parsed.tzinfo == timezone.utc
        assert parsed.microsecond % 1000 == 0  # millisecond precision, not micro


def test_written_timestamps_are_in_order(written_lines) -> None:
    stamps = [line["ts"] for line in written_lines]
    assert stamps == sorted(stamps)


def test_ollama_duration_fields_are_ints_or_null(written_lines) -> None:
    """Nanoseconds, copied verbatim. Never a float, never a string."""
    for line in written_lines:
        for name in OLLAMA_TIMING_FIELDS:
            value = line[name]
            assert value is None or (
                isinstance(value, int) and not isinstance(value, bool)
            ), (name, value)


def test_raw_model_output_is_capped_at_five_hundred_characters(written_lines) -> None:
    success = written_lines[0]
    assert len(LONG_REPLY) > RAW_OUTPUT_MAX_CHARS  # the input really was long
    assert len(success["raw_model_output"]) == RAW_OUTPUT_MAX_CHARS
    assert success["raw_model_output"] == LONG_REPLY[:RAW_OUTPUT_MAX_CHARS]
    for line in written_lines:
        raw = line["raw_model_output"]
        assert raw is None or len(raw) <= RAW_OUTPUT_MAX_CHARS


def test_the_successful_ticket_line_carries_the_model_fields(written_lines) -> None:
    line = written_lines[0]
    assert line["endpoint"] == "/tickets"
    assert line["status"] == 200
    assert line["predicted_category"] == "Mortgage"
    assert line["ticket_chars"] == len("My mortgage escrow account was mishandled.")
    for name, value in TIMINGS.items():
        assert line[name] == value


def test_the_failed_ticket_line_nulls_ollamas_fields_but_keeps_ours(
    written_lines,
) -> None:
    line = written_lines[1]
    assert line["status"] == 502
    assert line["error"] == "ollama_timeout"
    assert line["warmup"] is True
    assert line["predicted_category"] is None
    assert line["raw_model_output"] is None
    assert all(line[name] is None for name in OLLAMA_TIMING_FIELDS)
    assert isinstance(line["model_latency_ms"], float)
    assert isinstance(line["total_latency_ms"], float)


@pytest.mark.parametrize("index", [2, 3])
def test_non_ticket_lines_have_null_model_fields(written_lines, index: int) -> None:
    """``/search`` and ``/stats`` are logged, and no model was involved."""
    line = written_lines[index]
    assert line["endpoint"] in {"/search", "/stats"}
    assert line["ticket_chars"] is None
    assert line["model_latency_ms"] is None
    for name in MODEL_ONLY_FIELDS:
        assert line[name] is None, name
    for name in OLLAMA_TIMING_FIELDS:
        assert line[name] is None, name


def test_health_is_absent_from_the_log(written_lines) -> None:
    assert all(line["endpoint"] != "/health" for line in written_lines)


def test_written_lines_are_accepted_by_the_analysis_reader(
    written_lines, tmp_path: Path
) -> None:
    """The cross-check that matters: the analysis half can read what we write.

    ``analysis.common.read_service_log`` validates a log against ``LOG_FIELDS``
    and raises if anything is unexpected or missing, so this fails loudly if the
    two halves of the build ever disagree.
    """
    pytest.importorskip("pandas")
    from analysis.common import read_service_log

    path = tmp_path / "service.jsonl"
    path.write_text(
        "".join(json.dumps(line) + "\n" for line in written_lines), encoding="utf-8"
    )
    frame = read_service_log(path)
    assert len(frame) == len(written_lines)
    assert list(frame.columns)[: len(LOG_FIELDS)] == list(LOG_FIELDS)
