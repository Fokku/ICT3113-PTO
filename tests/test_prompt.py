"""Tests for the fixed classification prompt in :mod:`service.prompt`.

Owner: Yeo Kai Yuan (Part 1 — baseline service).

Two things matter about the prompt. First, it must name the seven categories
exactly as the normaliser spells them, or the model will be marked wrong for
answering the question we actually asked. Second, it must be *identified*: every
log line and every ``metadata.json`` carries ``PROMPT_HASH``, and results
gathered under two different prompts must never be pooled.

:data:`PINNED_PROMPT_HASH` below is therefore a tripwire, not a duplicate
constant. If it fails, the prompt has changed: that is allowed, but it must be
deliberate. Update the pin, note the change in the README changelog, and treat
every result recorded under the old hash as belonging to a different experiment.
"""

from __future__ import annotations

import re

import pytest

from service.categories import CATEGORIES
from service.prompt import (
    NARRATIVE_PLACEHOLDER,
    PROMPT_HASH,
    PROMPT_TEMPLATE,
    build_prompt,
    prompt_hash_for,
)

#: The hash of the prompt this baseline was measured with.
PINNED_PROMPT_HASH = "sha256:681131c48bdc15a1"

#: A narrative in the shape the intake really sends: a paragraph of prose.
SAMPLE_NARRATIVE = (
    "My mortgage servicer applied my payment to the wrong account and then "
    "reported the payment as late to the credit bureaus."
)


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("category", CATEGORIES)
def test_template_names_every_category_verbatim(category: str) -> None:
    """Each of the seven appears character-for-character, on its own bullet."""
    assert f"- {category}\n" in PROMPT_TEMPLATE


def test_categories_appear_in_canonical_order() -> None:
    """Order is not cosmetic: a small model is sensitive to option order, and we
    want the prompt's order to match the order every chart uses."""
    positions = [PROMPT_TEMPLATE.index(f"- {c}") for c in CATEGORIES]
    assert positions == sorted(positions)


def test_template_asks_for_the_category_name_only() -> None:
    """The instruction the whole post-hoc parser depends on must be present."""
    lowered = PROMPT_TEMPLATE.lower()
    assert "category name only" in lowered
    assert "do not explain" in lowered


def test_template_has_no_few_shot_examples() -> None:
    """Few-shot prompting is an Assignment 2 experiment, not part of the baseline.

    A crude but effective check: an example block would have to quote a complaint
    and its answer, which means the word "example" or a second "Complaint:".
    """
    assert "example" not in PROMPT_TEMPLATE.lower()
    assert PROMPT_TEMPLATE.count("Complaint:") == 1


def test_template_has_exactly_one_substitution_point() -> None:
    """``str.format`` is used, so a stray brace would raise at request time."""
    assert PROMPT_TEMPLATE.count(NARRATIVE_PLACEHOLDER) == 1
    assert re.findall(r"\{[^}]*\}", PROMPT_TEMPLATE) == [NARRATIVE_PLACEHOLDER]


# ---------------------------------------------------------------------------
# The hash
# ---------------------------------------------------------------------------

def test_prompt_hash_has_the_contracted_shape() -> None:
    assert re.fullmatch(r"sha256:[0-9a-f]{16}", PROMPT_HASH)


def test_prompt_hash_is_derived_from_the_template() -> None:
    assert PROMPT_HASH == prompt_hash_for(PROMPT_TEMPLATE)


def test_prompt_hash_is_stable() -> None:
    """The pin. See the module docstring before changing this value."""
    assert PROMPT_HASH == PINNED_PROMPT_HASH, (
        "The prompt template has changed, so every result recorded under "
        f"{PINNED_PROMPT_HASH} was produced by a different prompt. If the change "
        "is intended, update PINNED_PROMPT_HASH, record it in the README "
        "changelog, and do not pool old and new runs."
    )


def test_prompt_hash_changes_when_the_template_changes() -> None:
    """A one-character edit must produce a different identifier."""
    edited = PROMPT_TEMPLATE + " "
    assert prompt_hash_for(edited) != PROMPT_HASH
    assert prompt_hash_for(PROMPT_TEMPLATE.replace("seven", "7")) != PROMPT_HASH


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------

def test_build_prompt_embeds_the_narrative_verbatim() -> None:
    built = build_prompt(SAMPLE_NARRATIVE)
    assert SAMPLE_NARRATIVE in built
    assert NARRATIVE_PLACEHOLDER not in built


def test_build_prompt_keeps_the_instructions() -> None:
    """The narrative is inserted into the template, not substituted for it."""
    built = build_prompt(SAMPLE_NARRATIVE)
    for category in CATEGORIES:
        assert f"- {category}" in built
    assert built.rstrip().endswith("Category:")


@pytest.mark.parametrize(
    "narrative",
    [
        "",                                  # empty body; the intake's problem
        "   leading and trailing   ",        # whitespace must survive unchanged
        "braces {like} these",               # must not be treated as a format spec
        "percent %s signs",
        "non-ascii: café",
        "XXXX XXXX redaction markers",       # the CFPB data is full of these
    ],
)
def test_build_prompt_does_not_mangle_the_narrative(narrative: str) -> None:
    """Whatever the customer wrote reaches the model unchanged.

    ``ticket_chars`` in the log line is ``len(narrative)``, so if this function
    trimmed or escaped anything the log would describe different text from the
    one the model was shown.
    """
    assert narrative in build_prompt(narrative)


def test_build_prompt_is_deterministic() -> None:
    """Same input, same prompt: a precondition for reproducible accuracy runs."""
    assert build_prompt(SAMPLE_NARRATIVE) == build_prompt(SAMPLE_NARRATIVE)
