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
"""

from __future__ import annotations

LOG_SCHEMA_VERSION = 1

#: Exact key order of every line in logs/service/<date>.jsonl.
LOG_FIELDS: tuple[str, ...] = (
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
