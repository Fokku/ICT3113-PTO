"""Tests for the SQLite storage layer in :mod:`service.db`.

Owner: Yeo Kai Yuan (Part 1 — baseline service).

These run against a real SQLite file under pytest's ``tmp_path``, not a mock: the
behaviour under test *is* the SQL (the ``LIKE`` escaping, the clamped ``LIMIT``,
the zero-filled counts), and a mock would only assert that we called ourselves.

The naivety is not tested — a test that asserted "exactly one connection per
call" would just pin an implementation detail that Assignment 2 is meant to
change. What is tested is the behaviour Assignment 2 must preserve while it
changes it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from service.categories import CATEGORIES, UNPARSEABLE
from service.db import (
    DEFAULT_SEARCH_LIMIT,
    MAX_SEARCH_LIMIT,
    MIN_SEARCH_LIMIT,
    SEARCH_COLUMNS,
    clamp_search_limit,
    counts_by_category,
    insert_ticket,
    schema_init,
    search_tickets,
)


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """An initialised, empty database file in a directory that does not exist yet.

    The nested directory is deliberate: in Docker ``DB_PATH`` points into a fresh
    named volume, so ``connect()`` has to create the parent.
    """
    path = tmp_path / "volume" / "triage.db"
    schema_init(path)
    return path


def _add(
    path: Path,
    narrative: str,
    category: str = "Mortgage",
    *,
    request_id: str = "req-1",
    source_row: str | None = "10000",
    raw_model_output: str | None = None,
) -> int:
    """Insert one ticket with sensible defaults and return its id."""
    return insert_ticket(
        path,
        created_at="2026-10-01T09:00:00.000Z",
        request_id=request_id,
        source_row=source_row,
        narrative=narrative,
        category=category,
        raw_model_output=raw_model_output if raw_model_output is not None else category,
        model_tag="testmodel:1b",
        model_digest="sha256:aaaaaaaaaaaa",
    )


# ---------------------------------------------------------------------------
# schema_init
# ---------------------------------------------------------------------------

def test_schema_init_creates_the_file_and_its_parent(tmp_path: Path) -> None:
    path = tmp_path / "does" / "not" / "exist" / "triage.db"
    schema_init(path)
    assert path.is_file()


def test_schema_init_is_idempotent(db_path: Path) -> None:
    """Called on every start-up, so running it twice must be a no-op.

    Data written before the second call must survive it: the service restarts
    between runs and the volume is only wiped by ``scripts/reset.sh``.
    """
    ticket_id = _add(db_path, "a mortgage complaint")
    schema_init(db_path)
    schema_init(db_path)
    assert counts_by_category(db_path)["Mortgage"] == 1
    assert search_tickets(db_path, "mortgage")[0]["id"] == ticket_id


# ---------------------------------------------------------------------------
# insert_ticket
# ---------------------------------------------------------------------------

def test_insert_returns_increasing_ids(db_path: Path) -> None:
    first = _add(db_path, "first complaint")
    second = _add(db_path, "second complaint")
    assert (first, second) == (1, 2)


def test_insert_stores_every_column(db_path: Path) -> None:
    _add(
        db_path,
        "my escrow account was mishandled",
        "Mortgage",
        request_id="abc-123",
        source_row="10042",
        raw_model_output="**Mortgage**",
    )
    row = search_tickets(db_path, "escrow")[0]
    assert tuple(row) == SEARCH_COLUMNS
    assert row["request_id"] == "abc-123"
    assert row["source_row"] == "10042"
    assert row["category"] == "Mortgage"
    assert row["narrative"] == "my escrow account was mishandled"
    assert row["created_at"] == "2026-10-01T09:00:00.000Z"


def test_insert_accepts_unparseable(db_path: Path) -> None:
    """``UNPARSEABLE`` is a legal stored value; the raw reply is kept with it."""
    _add(db_path, "a confusing complaint", UNPARSEABLE, raw_model_output="I am unsure")
    assert counts_by_category(db_path)[UNPARSEABLE] == 1


def test_insert_rejects_an_unknown_category(db_path: Path) -> None:
    """An unexpected value would break the /stats total and the confusion matrix."""
    with pytest.raises(ValueError, match="refusing to store unknown category"):
        _add(db_path, "a complaint", "Mortgages")
    assert sum(counts_by_category(db_path).values()) == 0


def test_null_source_row_is_allowed(db_path: Path) -> None:
    """``X-Source-Row`` is optional: a hand-rolled curl has no CSV row."""
    _add(db_path, "a complaint with no row", source_row=None)
    assert search_tickets(db_path, "no row")[0]["source_row"] is None


# ---------------------------------------------------------------------------
# search_tickets
# ---------------------------------------------------------------------------

def test_search_matches_a_substring(db_path: Path) -> None:
    _add(db_path, "the servicer lost my escrow payment")
    _add(db_path, "a debt collector called my employer", "Debt collection")
    found = search_tickets(db_path, "escrow")
    assert [row["narrative"] for row in found] == [
        "the servicer lost my escrow payment"
    ]


@pytest.mark.parametrize("query", ["ESCROW", "escrow", "EsCrOw"])
def test_search_is_case_insensitive(db_path: Path, query: str) -> None:
    _add(db_path, "the servicer lost my ESCROW payment")
    assert len(search_tickets(db_path, query)) == 1


def test_search_returns_nothing_when_nothing_matches(db_path: Path) -> None:
    _add(db_path, "a mortgage complaint")
    assert search_tickets(db_path, "cryptocurrency") == []


def test_search_orders_by_insertion(db_path: Path) -> None:
    """Deterministic order matters: the mixed-load plan replays the same terms."""
    for index in range(5):
        _add(db_path, f"fee complaint number {index}")
    ids = [row["id"] for row in search_tickets(db_path, "fee complaint")]
    assert ids == sorted(ids)


def test_search_treats_wildcards_as_literal_text(db_path: Path) -> None:
    """Unescaped, a search for ``%`` would match every ticket in the database."""
    _add(db_path, "they charged me a 100% penalty")
    _add(db_path, "a complaint with no percent sign")
    assert len(search_tickets(db_path, "%")) == 1
    assert len(search_tickets(db_path, "100%")) == 1
    assert search_tickets(db_path, "_") == []


def test_search_with_an_empty_query_matches_everything(db_path: Path) -> None:
    """An empty ``q`` is a contains-nothing pattern, which every row satisfies.

    Recorded here as intended behaviour rather than defended: the endpoint
    requires ``q`` to be present, and an empty one is an honest "list some
    tickets".
    """
    for index in range(3):
        _add(db_path, f"complaint {index}")
    assert len(search_tickets(db_path, "")) == 3


# ---------------------------------------------------------------------------
# limit clamping
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        (None, DEFAULT_SEARCH_LIMIT),
        (1, 1),
        (50, 50),
        (500, MAX_SEARCH_LIMIT),
        (0, MIN_SEARCH_LIMIT),
        (-10, MIN_SEARCH_LIMIT),
        (501, MAX_SEARCH_LIMIT),
        (100_000, MAX_SEARCH_LIMIT),
    ],
)
def test_clamp_search_limit(requested: int | None, expected: int) -> None:
    assert clamp_search_limit(requested) == expected


def test_search_honours_the_clamped_limit(db_path: Path) -> None:
    for index in range(7):
        _add(db_path, f"a fee complaint numbered {index}")
    assert len(search_tickets(db_path, "fee", 3)) == 3
    # Clamped up to 1 rather than returning nothing.
    assert len(search_tickets(db_path, "fee", 0)) == 1
    # Clamped down to the maximum, which is larger than the data set.
    assert len(search_tickets(db_path, "fee", 100_000)) == 7


# ---------------------------------------------------------------------------
# counts_by_category
# ---------------------------------------------------------------------------

def test_counts_include_every_category_and_unparseable_when_empty(
    db_path: Path,
) -> None:
    counts = counts_by_category(db_path)
    assert list(counts) == [*CATEGORIES, UNPARSEABLE]
    assert set(counts.values()) == {0}


def test_counts_are_in_canonical_order_with_zeroes(db_path: Path) -> None:
    """Zero-count categories must still appear, so a chart's axis never moves."""
    _add(db_path, "a mortgage complaint", "Mortgage")
    _add(db_path, "another mortgage complaint", "Mortgage")
    _add(db_path, "a collector called", "Debt collection")
    _add(db_path, "gibberish reply", UNPARSEABLE, raw_model_output="???")
    counts = counts_by_category(db_path)
    assert list(counts) == [*CATEGORIES, UNPARSEABLE]
    assert counts["Mortgage"] == 2
    assert counts["Debt collection"] == 1
    assert counts[UNPARSEABLE] == 1
    assert counts["Credit reporting"] == 0
    assert sum(counts.values()) == 4
