"""Tests for the reply normaliser in :mod:`service.categories`.

Owner: Yeo Kai Yuan (Part 1 — baseline service).

The normaliser sits between the model's free text and every accuracy number we
report, so it is the one piece of the service where a quiet bug would change a
result rather than break a request. These tests therefore pin the *documented*
behaviour of each numbered rule in the module docstring, including the cases the
parser must refuse to guess at.

The cleaned strings asserted here are what ``clean_reply`` really produces; they
are checked so that a debugging session on an ``UNPARSEABLE`` can start from a
known-good baseline of what the parser was matching against.
"""

from __future__ import annotations

import pytest

from service.categories import (
    CATEGORIES,
    UNPARSEABLE,
    VALID_STORED_VALUES,
    clean_reply,
    is_valid_category,
    normalise_category,
)

# Imported deliberately, although private: the test below asserts that every
# alias the module ships is exercised by this file, so adding an alias without
# adding a case fails the suite instead of going untested.
from service.categories import _ALIASES  # noqa: PLC2701

#: The documented alias table, spelled out here rather than derived from the
#: module, so the test is an independent statement of intent.
ALIAS_CASES: tuple[tuple[str, str], ...] = (
    ("credit report", "Credit reporting"),
    ("credit reports", "Credit reporting"),
    ("creditreporting", "Credit reporting"),
    ("debt collections", "Debt collection"),
    ("debtcollection", "Debt collection"),
    ("mortgages", "Mortgage"),
    ("credit cards", "Credit card"),
    ("creditcard", "Credit card"),
    ("bank account", "Bank account or service"),
    ("bank accounts", "Bank account or service"),
    ("bank account or services", "Bank account or service"),
    ("consumer loans", "Consumer loan"),
    ("consumerloan", "Consumer loan"),
    ("money transfer", "Money transfer or service"),
    ("money transfers", "Money transfer or service"),
    ("money transfer or services", "Money transfer or service"),
)


# ---------------------------------------------------------------------------
# The canonical names themselves
# ---------------------------------------------------------------------------

def test_there_are_exactly_seven_categories_in_brief_order() -> None:
    """The list and its order are load-bearing: it is the confusion-matrix axis."""
    assert CATEGORIES == (
        "Credit reporting",
        "Debt collection",
        "Mortgage",
        "Credit card",
        "Bank account or service",
        "Consumer loan",
        "Money transfer or service",
    )


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_canonical_name_round_trips(category: str) -> None:
    """A model that answers perfectly must never be recorded as unparseable."""
    assert normalise_category(category) == category


@pytest.mark.parametrize("category", CATEGORIES)
def test_no_canonical_name_maps_to_unparseable(category: str) -> None:
    """Restated as the negative, because this is the failure that would hurt most.

    Checked in several shapes a well-behaved model might legitimately use.
    """
    for variant in (
        category,
        category.lower(),
        category.upper(),
        f"  {category}  ",
        f"{category}.",
        f'"{category}"',
        f"**{category}**",
        f"Category: {category}",
    ):
        assert normalise_category(variant) == category, variant


def test_valid_stored_values_is_the_seven_plus_unparseable() -> None:
    """The database column accepts exactly these eight strings."""
    assert VALID_STORED_VALUES == frozenset(CATEGORIES) | {UNPARSEABLE}
    assert all(is_valid_category(c) for c in CATEGORIES)
    assert not is_valid_category(UNPARSEABLE)
    assert not is_valid_category("Mortgages")


# ---------------------------------------------------------------------------
# Rule 2 and 3: cosmetic cleaning
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("raw", "expected_clean"),
    [
        ("Mortgage", "mortgage"),
        ("MORTGAGE", "mortgage"),
        ("  Mortgage \n", "mortgage"),
        ("**Mortgage**", "mortgage"),
        ("`Mortgage`", "mortgage"),
        ("### Mortgage", "mortgage"),
        ('"Mortgage"', "mortgage"),
        ("'Mortgage'", "mortgage"),
        ("“Mortgage”", "mortgage"),          # curly double quotes
        ("‘Mortgage’", "mortgage"),          # curly single quotes
        ("Mortgage.", "mortgage"),
        ("Mortgage!", "mortgage"),
        ("Category: Mortgage", "mortgage"),
        ("answer: mortgage", "mortgage"),
        ("Answer: Category: Mortgage", "mortgage"),    # repeated label prefix
        ("Classification - Credit card", "credit card"),
        ("```\nMortgage\n```", "mortgage"),
        ("```text\nMortgage\n```", "mortgage"),
        ("credit_card", "credit card"),                # underscore separator
        ("credit-card", "credit card"),                # hyphen separator
        ("Credit    reporting", "credit reporting"),   # whitespace collapsed
    ],
)
def test_clean_reply_strips_cosmetics(raw: str, expected_clean: str) -> None:
    assert clean_reply(raw) == expected_clean


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("**Mortgage**", "Mortgage"),
        ('"Credit card"', "Credit card"),
        ("```\nConsumer loan\n```", "Consumer loan"),
        ("Category: Bank account or service.", "Bank account or service"),
        ("Label: bank_account", "Bank account or service"),
        ("CREDIT-REPORTING", "Credit reporting"),
        ("money_transfer_or_service", "Money transfer or service"),
        ("‘Debt collection’", "Debt collection"),
    ],
)
def test_cosmetic_variants_normalise(raw: str, expected: str) -> None:
    """Punctuation, markdown, quotes and separators must not cost us accuracy."""
    assert normalise_category(raw) == expected


# ---------------------------------------------------------------------------
# Rule 5: the alias table
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(("alias", "expected"), ALIAS_CASES)
def test_each_alias_maps_to_its_category(alias: str, expected: str) -> None:
    assert normalise_category(alias) == expected
    # Case and separator handling happens before the alias lookup, so the same
    # alias must also work shouted and hyphenated.
    assert normalise_category(alias.upper()) == expected
    assert normalise_category(alias.replace(" ", "_")) == expected


def test_every_shipped_alias_is_covered_by_this_file() -> None:
    """A new alias must arrive with a test; this is the tripwire that enforces it."""
    assert set(_ALIASES) == {alias for alias, _ in ALIAS_CASES}


# ---------------------------------------------------------------------------
# Rule 6: containment, only when unambiguous
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("The category is Mortgage.", "Mortgage"),
        ("This ticket is about a credit card dispute", "Credit card"),
        ("1. Mortgage", "Mortgage"),
        ("Mortgage\n\nExplanation: the ticket mentions escrow.", "Mortgage"),
        # "bank account" is an alias of "Bank account or service", so both
        # surface forms point at the same category and the match is unambiguous.
        ("Bank account or service", "Bank account or service"),
        ("money transfer or service", "Money transfer or service"),
    ],
)
def test_single_containment_match_wins(raw: str, expected: str) -> None:
    assert normalise_category(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "It is either Credit card or Mortgage",
        "Credit reporting or Debt collection",
        "Mortgage / Consumer loan",
        "I'd say this is about a mortgage, but it could involve debt collection.",
        "Debt collection (previously Credit reporting)",
    ],
)
def test_two_categories_is_unparseable(raw: str) -> None:
    """The parser must not pick a winner when the model named two categories.

    Choosing one — the first, the longest, the most likely — would be us
    deciding what the model meant, which flatters the accuracy figure. An
    ambiguous reply is a model failure and is recorded as one.
    """
    assert normalise_category(raw) == UNPARSEABLE


# ---------------------------------------------------------------------------
# Rules 1 and 7: nothing usable
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "   ",
        "\n\t ",
        "```\n```",
        "banana",
        "I cannot classify this ticket.",
        "Category: unknown",
        "Insurance",              # a real CFPB category, but not one of our seven
        "Student loan",           # deliberately NOT remapped onto Consumer loan
        "Vehicle loan or lease",  # ditto
        "7",
        "Category 3",
    ],
)
def test_unusable_replies_are_unparseable(raw: str | None) -> None:
    assert normalise_category(raw) == UNPARSEABLE


def test_semantically_close_names_are_not_remapped() -> None:
    """No semantic remapping: see the note in the module docstring.

    Mapping the CFPB's modern category names or a product name onto one of our
    seven would improve the measured accuracy of every model without improving
    any model, and would hide a real class of model error.
    """
    for raw in ("Checking or savings account", "Payday loan", "Credit repair"):
        assert normalise_category(raw) == UNPARSEABLE


def test_normalise_never_raises_on_odd_input() -> None:
    """The handler calls this on whatever the model returned; it must not throw."""
    for raw in ("\x00", "中文", "%s", "{}", "-" * 1000, "\\"):
        assert normalise_category(raw) in VALID_STORED_VALUES
