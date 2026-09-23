"""SQLite storage for classified tickets. Stdlib ``sqlite3`` only.

Owner: Yeo Kai Yuan (Part 1 — baseline service).

The service starts empty and tickets arrive one at a time through
``POST /tickets``; there is no bulk import and no migration story. So the
storage layer is three statements and a schema.

Deliberately naive, and why
---------------------------
Every function in this module opens its **own** connection, does one piece of
work, commits if it wrote, and closes. That is one ``sqlite3.connect`` per HTTP
request. It is the first thing a profiler will point at, and it is exactly what
Assignment 2 is for; the baseline exists to be measured, not to be fast. The
journal mode is left at SQLite's default (rollback journal, i.e. not WAL), there
are no indexes beyond the implicit primary key, and ``/search`` is a full-table
``LIKE`` scan.

Every one of those choices carries an ``A2 candidate:`` comment at the line it
applies to, so the optimisation work has a checklist rather than a hunt.

Concurrency note: with ``UVICORN_WORKERS=1`` there is one process, and the
handlers hand these blocking calls to the framework's worker-thread pool, so a
handful of connections can be open at once. SQLite serialises writers with a
short busy-wait; :data:`BUSY_TIMEOUT_S` bounds it so a writer fails loudly with
"database is locked" rather than hanging for the whole request timeout.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from service.categories import CATEGORIES, UNPARSEABLE, VALID_STORED_VALUES

#: ``limit`` on ``GET /search`` is clamped into this range. A client asking for
#: 100,000 rows would otherwise turn one request into a multi-megabyte response
#: and make the load test measure JSON serialisation instead of triage.
MIN_SEARCH_LIMIT = 1
MAX_SEARCH_LIMIT = 500
DEFAULT_SEARCH_LIMIT = 50

#: Seconds SQLite waits for a lock before raising ``database is locked``.
BUSY_TIMEOUT_S = 5.0

#: Columns ``GET /search`` returns, in this order. ``narrative`` is returned in
#: full: an agent searching for a ticket needs to read it, and truncating here
#: would make the response size unrepresentative of the real thing.
SEARCH_COLUMNS: tuple[str, ...] = (
    "id",
    "created_at",
    "request_id",
    "source_row",
    "category",
    "narrative",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at        TEXT    NOT NULL,   -- ISO-8601 UTC, millisecond precision
    request_id        TEXT    NOT NULL,   -- joins a row to its service log line
    source_row        TEXT,               -- course CSV row, from X-Source-Row
    narrative         TEXT    NOT NULL,   -- exactly what the intake posted
    category          TEXT    NOT NULL,   -- a canonical category, or UNPARSEABLE
    raw_model_output  TEXT,               -- what the model actually said
    model_tag         TEXT,               -- which model produced the category
    model_digest      TEXT                -- and which build of it
);
"""
# A2 candidate: an index on `category` for GET /stats, and an FTS5 virtual table
# mirroring `narrative` for GET /search. Both are omitted on purpose: the
# baseline must show what an unindexed store costs.


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Open a **new** connection to ``db_path``.

    Called once per operation, never cached.

    # A2 candidate: persistent connection, WAL journal mode, prepared statements
    """
    path = Path(db_path)
    # The directory is created here rather than at start-up only, because the
    # DB_PATH default lives in a Docker volume that may be mounted empty.
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=BUSY_TIMEOUT_S)
    # Row objects let the handlers build dicts by column name, so adding a
    # column cannot silently shift a value into the wrong JSON key.
    connection.row_factory = sqlite3.Row
    return connection


def schema_init(db_path: Path | str) -> None:
    """Create the ``tickets`` table if it does not exist.

    Idempotent: safe to call on every start-up, which is exactly what the
    service does, because the database lives in a volume that may be brand new
    (``scripts/reset.sh`` deletes it between runs so ``/stats`` starts at zero).
    """
    connection = connect(db_path)
    try:
        # `with connection` commits (or rolls back) the DDL; it does NOT close,
        # so every function here closes in its own `finally`. A leaked handle
        # per request would hold the rollback journal open.
        with connection:
            connection.executescript(_SCHEMA)
    finally:
        connection.close()


def insert_ticket(
    db_path: Path | str,
    *,
    created_at: str,
    request_id: str,
    source_row: str | None,
    narrative: str,
    category: str,
    raw_model_output: str | None,
    model_tag: str | None = None,
    model_digest: str | None = None,
) -> int:
    """Store one classified ticket and return its new ``id``.

    ``category`` must be one of the seven canonical names or ``UNPARSEABLE``;
    anything else is a programming error and raises, because an unexpected value
    in this column would silently break ``GET /stats`` (whose total is the sum of
    the per-category counts) and the confusion matrix.

    A ticket is only ever stored *after* a successful model call. On a model
    failure the service returns 502 and stores nothing — see ``service/main.py``.
    """
    if category not in VALID_STORED_VALUES:
        raise ValueError(
            f"refusing to store unknown category {category!r}; expected one of "
            f"{sorted(VALID_STORED_VALUES)}"
        )
    connection = connect(db_path)
    try:
        with connection:  # commits on success, rolls back on an exception
            cursor = connection.execute(
                """
                INSERT INTO tickets (created_at, request_id, source_row,
                                     narrative, category, raw_model_output,
                                     model_tag, model_digest)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    request_id,
                    source_row,
                    narrative,
                    category,
                    raw_model_output,
                    model_tag,
                    model_digest,
                ),
            )
            ticket_id = cursor.lastrowid
    finally:
        connection.close()
    if ticket_id is None:  # pragma: no cover - sqlite always sets lastrowid here
        raise RuntimeError("INSERT did not yield a row id")
    return int(ticket_id)


def clamp_search_limit(limit: int | None) -> int:
    """Clamp a requested ``limit`` into ``1..500``; ``None`` gives the default.

    Clamping rather than rejecting: a load test that asked for 1,000 rows should
    still produce a sample, and the response size stays bounded either way.
    """
    if limit is None:
        return DEFAULT_SEARCH_LIMIT
    return max(MIN_SEARCH_LIMIT, min(MAX_SEARCH_LIMIT, int(limit)))


def _like_pattern(query: str) -> str:
    """Wrap ``query`` as a contains-pattern, escaping SQL ``LIKE`` wildcards.

    Without this, a search for ``100%`` would match every ticket, and a search
    for ``_`` would match any single character. ``\\`` is declared as the escape
    character in the statement below.
    """
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def search_tickets(
    db_path: Path | str,
    q: str,
    limit: int | None = DEFAULT_SEARCH_LIMIT,
) -> list[dict[str, Any]]:
    """Return stored tickets whose narrative contains ``q``, case-insensitively.

    Ordered by ``id`` ascending — insertion order, oldest first. There is no
    pagination and no relevance ranking; ``limit`` simply cuts the list off.
    Deterministic ordering matters more than usefulness here, because the JMeter
    mixed-load plan replays the same search terms and we need comparable work
    per sample.

    Both sides are lower-cased explicitly rather than relying on ``LIKE`` being
    case-insensitive by default, so the behaviour cannot be changed out from
    under us by ``PRAGMA case_sensitive_like``. Like SQLite's own ``LIKE``, this
    folds ASCII only; the CFPB narratives are ASCII with redaction markers.

    # A2 candidate: SQLite FTS5 virtual table / index instead of a full-table
    # LIKE scan (the scan re-reads every narrative on every search).
    """
    effective_limit = clamp_search_limit(limit)
    columns = ", ".join(SEARCH_COLUMNS)
    connection = connect(db_path)
    try:
        rows = connection.execute(
            f"""
            SELECT {columns}
              FROM tickets
             WHERE lower(narrative) LIKE lower(?) ESCAPE '\\'
             ORDER BY id
             LIMIT ?
            """,
            (_like_pattern(q), effective_limit),
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def counts_by_category(db_path: Path | str) -> dict[str, int]:
    """Return a ticket count for every category, in canonical order.

    All eight keys are always present — the seven categories in
    :data:`service.categories.CATEGORIES` order, then ``UNPARSEABLE`` — with
    zeros for categories nothing has been filed under yet. A caller can
    therefore sum the values to get the total row count, and a chart built from
    this dict always has the same axis.
    """
    counts = {category: 0 for category in (*CATEGORIES, UNPARSEABLE)}
    connection = connect(db_path)
    try:
        rows = connection.execute(
            "SELECT category, COUNT(*) AS n FROM tickets GROUP BY category"
        ).fetchall()
    finally:
        connection.close()
    for row in rows:
        # insert_ticket() validates the column, so an unknown key here would
        # mean the file was written by something other than this service.
        if row["category"] in counts:
            counts[row["category"]] += int(row["n"])
        else:  # pragma: no cover - defensive
            raise ValueError(
                f"database contains unknown category {row['category']!r}; "
                f"was it written by this service?"
            )
    return counts
