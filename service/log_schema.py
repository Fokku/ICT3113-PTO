"""The canonical service log-line schema.

One JSON object is written per request to ``logs/service/<UTC-date>.jsonl``.
:data:`LOG_FIELDS` is the authoritative field list *in order*; the service
writes exactly these keys and nothing else, the schema test asserts it, and the
analysis scripts and their fixtures are built against it.

Adding a field is a breaking change for every run already recorded. If a field
must be added, add it at the END of :data:`LOG_FIELDS`, bump
:data:`LOG_SCHEMA_VERSION`, and say so in the README changelog, because runs
recorded before and after cannot be pooled without care.

All durations reported by Ollama (``total_duration``, ``load_duration``,
``prompt_eval_duration``, ``eval_duration``) are **nanoseconds**, copied
verbatim from the ``/api/generate`` response. Our own ``total_latency_ms`` and
``model_latency_ms`` are **milliseconds**, measured with a monotonic clock.

Schema history
--------------
* **Version 1** (Assignment 1): the first 24 fields, :data:`LOG_FIELDS_V1`.
  Every Assignment 1 run under ``results/`` and ``logs/service/`` was written
  with it, and those files are evidence, so they are never rewritten.
  ``analysis/common.read_service_log`` still reads them, filling the version 2
  fields with null.
* **Version 2** (Assignment 2): :data:`CASCADE_LOG_FIELDS` appended at the end,
  nothing reordered. They are null on every line a single-model service writes,
  and set on every ``POST /tickets`` line a cascade service writes.

What the model fields mean on a cascade line
--------------------------------------------
``model_tag`` / ``model_digest`` / ``predicted_category`` / ``raw_model_output``
describe **whichever model's answer the service returned**: the small model's
when the ticket was accepted, the large model's when it was escalated. That is
"which model produced the final classification" for the brief's purposes.

``model_latency_ms`` and the six Ollama fields are **summed over every model
call the request made** (one call when accepted, two when escalated), so that
``total_latency_ms - model_latency_ms`` is still the service's own overhead and
``model_latency_ms - total_duration/1e6`` is still time spent outside Ollama's
own work (queueing, HTTP), exactly as for a single-model line. The small call on
its own is broken out in ``small_model_latency_ms`` and ``small_load_duration``,
so the large call's share is the difference.
"""

from __future__ import annotations

LOG_SCHEMA_VERSION = 2

#: The Assignment 1 field list (schema version 1), kept so that the 24-field
#: Assignment 1 logs stay readable and checkable.
LOG_FIELDS_V1: tuple[str, ...] = (
    # --- identifiers ---------------------------------------------------
    "ts",                     # str   ISO-8601 UTC, millisecond precision, 'Z'
    "request_id",             # str   from X-Request-ID, or a generated UUID4
    "source_row",             # str|None  from X-Source-Row (the course CSV row)
    "warmup",                 # bool  true for the run script's warm-up request
    # --- request -------------------------------------------------------
    "endpoint",               # str   "/tickets" | "/search" | "/stats"
    "method",                 # str   "POST" | "GET"
    "status",                 # int   HTTP status actually returned
    "ticket_chars",           # int|None  len(narrative); null off /tickets
    # --- model ---------------------------------------------------------
    "model_tag",              # str|None  e.g. "llama3.2:1b"
    "model_digest",           # str|None  pinned digest, or resolved at startup
    "predicted_category",     # str|None  one of CATEGORIES, or "UNPARSEABLE"
    "raw_model_output",       # str|None  truncated to RAW_OUTPUT_MAX_CHARS
    "prompt_hash",            # str|None  "sha256:<16 hex>" of the prompt template
    "num_ctx",                # int|None  the num_ctx we asked Ollama for
    "seed",                   # int|None  the fixed sampling seed
    # --- timing --------------------------------------------------------
    "total_latency_ms",       # float  whole request handler, 1 dp
    "model_latency_ms",       # float|None  around the Ollama HTTP call, 1 dp
    "total_duration",         # int|None  ns, Ollama
    "load_duration",          # int|None  ns, Ollama (model load)
    "prompt_eval_count",      # int|None  tokens, Ollama
    "prompt_eval_duration",   # int|None  ns, Ollama
    "eval_count",             # int|None  tokens, Ollama
    "eval_duration",          # int|None  ns, Ollama
    # --- outcome -------------------------------------------------------
    "error",                  # str|None  short machine-readable error slug
)

#: The fields schema version 2 appends for the Assignment 2 cascade. Null on
#: every line that is not a cascade ``POST /tickets``.
CASCADE_LOG_FIELDS: tuple[str, ...] = (
    "escalated",              # bool|None  true when the large model was called
    "cascade_setting",        # str|None   "A" | "B" (the escalation rule's setting)
    "small_model_tag",        # str|None   the cascade's small model
    "small_model_category",   # str|None   what the small model said, normalised,
                              #            independent of what the service returned
    "small_model_latency_ms", # float|None the small-model call alone, 1 dp
    "small_load_duration",    # int|None   ns, Ollama load_duration of the small call
)

#: Exact key order of every line in logs/service/<date>.jsonl (version 2).
LOG_FIELDS: tuple[str, ...] = LOG_FIELDS_V1 + CASCADE_LOG_FIELDS

#: ``raw_model_output`` is sliced to this many characters before logging, so a
#: runaway model reply cannot bloat a load-test log to gigabytes.
RAW_OUTPUT_MAX_CHARS = 500

#: Fields that carry Ollama's own instrumentation, in nanoseconds/token counts.
OLLAMA_TIMING_FIELDS: tuple[str, ...] = (
    "total_duration",
    "load_duration",
    "prompt_eval_count",
    "prompt_eval_duration",
    "eval_count",
    "eval_duration",
)

#: Short, stable error slugs. The service only ever writes one of these.
ERROR_SLUGS: tuple[str, ...] = (
    "ollama_timeout",
    "ollama_connect_error",
    "ollama_http_error",
    "ollama_bad_response",
    "bad_request",
    "internal_error",
)
