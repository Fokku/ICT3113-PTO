"""The JSONL request log: one JSON object per request, one file per UTC date.

Owner: Yeo Kai Yuan (Part 1 — baseline service).

This log is the assignment's primary evidence. Every number that reaches a slide
has to reconcile with a line written here, so the module has one job and takes it
seriously: **the schema cannot drift.** The only way to produce a line is
:func:`build_log_line`, which takes keyword arguments, refuses an unknown field,
refuses a missing field, and returns the fields in
:data:`service.log_schema.LOG_FIELDS` order. A handler that forgets a field gets
an exception at development time instead of a log file that
``analysis/common.read_service_log`` rejects after a 15-minute load test.

File naming: ``<LOG_DIR>/<UTC date>.jsonl``, with the date taken at **write**
time. A run that crosses midnight UTC therefore lands in two files; that is
deliberate and the run scripts copy the slice they need into the run directory.

Deliberately naive
------------------
One ``open(..., "a")`` + ``write`` + ``flush`` + ``close`` per request, with no
buffering, no background writer and no queue.

# A2 candidate: buffered / async logging instead of an open-write-close per
# request (and the matching measurement of how much it actually costs)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from service.log_schema import LOG_FIELDS, RAW_OUTPUT_MAX_CHARS

#: Fields rounded to one decimal place by :func:`build_log_line`.
_LATENCY_FIELDS = ("total_latency_ms", "model_latency_ms")


class LogSchemaError(ValueError):
    """Raised when a caller tries to build a line that is off-schema.

    Deliberately loud. A silently wrong log line is worse than a crash, because
    the crash is found in a test and the wrong line is found in a viva.
    """


def utc_now() -> datetime:
    """Current UTC time. A seam the tests replace with a fixed moment."""
    return datetime.now(timezone.utc)


def iso_ms(moment: datetime) -> str:
    """Format ``moment`` as the log contract requires: UTC, milliseconds, ``Z``.

    ``datetime.isoformat`` gives microseconds (six digits) and ``+00:00``, so we
    format by hand. Millisecond precision is the contract because JMeter's
    ``timeStamp`` column is milliseconds, and ``analysis/reconcile.py`` compares
    the two timelines.

    Truncates rather than rounds the sub-millisecond part, so the stamp is never
    a millisecond ahead of the event it describes.
    """
    moment = moment.astimezone(timezone.utc)
    return f"{moment:%Y-%m-%dT%H:%M:%S}.{moment.microsecond // 1000:03d}Z"


def build_log_line(**fields: Any) -> dict[str, Any]:
    """Validate and normalise one log line; return it in ``LOG_FIELDS`` order.

    Every field in :data:`service.log_schema.LOG_FIELDS` must be passed
    explicitly, including the ones that are ``None`` for this endpoint. There are
    no defaults on purpose: a default would let a handler quietly stop reporting
    something (say ``model_digest``) and nobody would notice until the results
    could not be pinned to a model build.

    Two normalisations are applied here rather than in the handlers, so they hold
    for every writer:

    * ``raw_model_output`` is sliced to
      :data:`service.log_schema.RAW_OUTPUT_MAX_CHARS` characters. Nothing is
      appended — no ellipsis — because the analysis code compares this string
      against the model's category and a marker suffix would break that.
    * ``total_latency_ms`` and ``model_latency_ms`` are rounded to one decimal
      place, the precision the contract states.

    Raises :class:`LogSchemaError` for an unknown or a missing field.
    """
    # Both problems are reported together, because the commonest cause is a
    # single typo — which shows up as one unknown field *and* one missing field,
    # and is far quicker to diagnose when both halves are named at once.
    problems: list[str] = []
    unknown = sorted(set(fields) - set(LOG_FIELDS))
    if unknown:
        problems.append(
            f"unknown log field(s) {unknown}; the schema is fixed by "
            f"service/log_schema.py LOG_FIELDS"
        )
    missing = [name for name in LOG_FIELDS if name not in fields]
    if missing:
        problems.append(
            f"missing log field(s) {missing}; every field must be passed "
            f"explicitly, using None where it does not apply"
        )
    if problems:
        raise LogSchemaError(" / ".join(problems))

    line = dict(fields)

    raw = line["raw_model_output"]
    if isinstance(raw, str) and len(raw) > RAW_OUTPUT_MAX_CHARS:
        line["raw_model_output"] = raw[:RAW_OUTPUT_MAX_CHARS]

    for name in _LATENCY_FIELDS:
        value = line[name]
        if value is not None:
            line[name] = round(float(value), 1)

    # Rebuild in schema order: json.dumps preserves insertion order, so the
    # file is readable and diffable, and the field-order test is meaningful.
    return {name: line[name] for name in LOG_FIELDS}


def log_path_for(log_dir: Path | str, moment: datetime | None = None) -> Path:
    """Return the log file for ``moment`` (default: now): ``<dir>/<date>.jsonl``."""
    when = (moment or utc_now()).astimezone(timezone.utc)
    return Path(log_dir) / f"{when:%Y-%m-%d}.jsonl"


def write_log_line(
    log_dir: Path | str,
    line: dict[str, Any],
    moment: datetime | None = None,
) -> Path:
    """Append one already-built ``line`` as JSON and return the file written.

    ``line`` must have come from :func:`build_log_line`; this function re-checks
    the key set anyway, because the check is cheap compared with discovering
    after a benchmark that one handler wrote a different shape.

    ``ensure_ascii=False`` keeps the narrative-derived text readable; the file is
    UTF-8. The explicit ``flush`` is what makes a line survive a container kill
    mid-run, which is exactly the scenario a stress test creates.
    """
    if tuple(line) != LOG_FIELDS:
        raise LogSchemaError(
            "log line keys are not LOG_FIELDS in order; build it with "
            "build_log_line()"
        )
    path = log_path_for(log_dir, moment)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(line, ensure_ascii=False)
    # A2 candidate: buffered / async logging instead of an open-write-close per
    # request
    with path.open("a", encoding="utf-8") as handle:
        handle.write(payload + "\n")
        handle.flush()
    return path
