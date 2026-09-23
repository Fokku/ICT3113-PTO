"""The seven ticket categories and the reply normaliser.

This module is the single source of truth for category names across the whole
repository -- the service, the analysis scripts, the labelling helpers and the
tests all import from here. Do not redefine the list anywhere else, and do not
change the ordering: :data:`CATEGORIES` order is the axis order used by the
confusion matrix, so changing it silently changes every chart we have produced.

The module deliberately has **no third-party imports** so that anything in the
repository can import it without pulling FastAPI in.

Normalisation rules (applied in order; the first rule that yields a single
category wins)
--------------------------------------------------------------------------
1. A reply that is ``None``, empty, or whitespace only maps to ``UNPARSEABLE``.
2. Cosmetic stripping: Markdown code fences and ``*``/``#``/backtick emphasis
   characters are removed, surrounding quotes are removed, a leading label such
   as ``Category:`` / ``Answer:`` / ``Classification:`` is removed, and trailing
   sentence punctuation (``. , ; : ! ?``) is removed.
3. Underscores and hyphens are treated as word separators (so ``credit_card``
   and ``credit-card`` both reduce to ``credit card``), the result is casefolded
   and its internal whitespace is collapsed to single spaces.
4. **Exact match** against the seven canonical names (casefolded).
5. **Alias match** against :data:`_ALIASES` -- an intentionally small table of
   *orthographic* variants only (plurals, run-together spellings, the obvious
   shortened forms). Case, hyphenation and snake_case are already handled by
   rule 3, so they need no entries. See the note on semantics below.
6. **Containment**: every canonical name and every alias is searched for as a
   substring of the cleaned reply. If the set of categories found has exactly
   one member, that category wins. Zero matches or two or more matches map to
   ``UNPARSEABLE``.
7. Anything else maps to ``UNPARSEABLE`` and the raw reply is kept in the log
   and in the database so we can show what the model actually said.

A deliberate non-feature: **no semantic remapping.**
--------------------------------------------------------------------------
The alias table does not map, for example, ``"student loan"`` or
``"vehicle loan"`` onto ``"Consumer loan"``, nor the CFPB's longer modern
category names onto ours. Doing so would be us deciding, in code, what a model
meant -- which quietly improves measured accuracy and hides real model error.
The baseline must show the model's honest output.

# A2 candidate: constrained decoding (Ollama ``format`` / JSON schema) or a
# grammar so the model can only emit one of the seven strings, removing the
# post-hoc parser entirely.
# A2 candidate: a richer alias/synonym table, or an embedding nearest-neighbour
# match, to recover replies that currently land in UNPARSEABLE.
"""

from __future__ import annotations

import re

#: The seven categories, in canonical order. This order is the confusion-matrix
#: axis order. Taken verbatim from the assignment brief.
CATEGORIES: tuple[str, ...] = (
    "Credit reporting",
    "Debt collection",
    "Mortgage",
    "Credit card",
    "Bank account or service",
    "Consumer loan",
    "Money transfer or service",
)

#: Stored when a model reply cannot be mapped onto exactly one category.
UNPARSEABLE: str = "UNPARSEABLE"

#: Every value the ``category`` column may legally hold.
VALID_STORED_VALUES: frozenset[str] = frozenset(CATEGORIES) | {UNPARSEABLE}

# Orthographic aliases only -- see the module docstring. Keys are already
# casefolded and whitespace-collapsed. Each entry carries the reason it exists.
_ALIASES: dict[str, str] = {
    "credit report": "Credit reporting",          # gerund dropped
    "credit reports": "Credit reporting",         # plural
    "creditreporting": "Credit reporting",        # run together
    "debt collections": "Debt collection",        # plural
    "debtcollection": "Debt collection",          # run together
    "mortgages": "Mortgage",                      # plural
    "credit cards": "Credit card",                # plural
    "creditcard": "Credit card",                  # run together
    "bank account": "Bank account or service",    # canonical name truncated
    "bank accounts": "Bank account or service",   # plural of the above
    "bank account or services": "Bank account or service",   # plural tail
    "consumer loans": "Consumer loan",            # plural
    "consumerloan": "Consumer loan",              # run together
    "money transfer": "Money transfer or service",   # canonical name truncated
    "money transfers": "Money transfer or service",  # plural of the above
    "money transfer or services": "Money transfer or service",  # plural tail
}

# A leading label the model may prepend, e.g. "Category: Mortgage".
_LEADING_LABEL = re.compile(
    r"^\s*(?:category|answer|classification|label|result|output)\s*[:\-]\s*",
    re.IGNORECASE,
)
_CODE_FENCE = re.compile(r"```[a-zA-Z]*")
_EMPHASIS = re.compile(r"[*#`]")
# Underscores and hyphens are word separators, not punctuation to delete:
# "credit_card" and "credit-card" must both reduce to "credit card".
_SEPARATORS = re.compile(r"[_\-]+")
_WHITESPACE = re.compile(r"\s+")

#: Lookup used by rules 4-6: casefolded surface form -> canonical category.
_SURFACE_FORMS: dict[str, str] = {
    **{name.casefold(): name for name in CATEGORIES},
    **_ALIASES,
}


def clean_reply(raw: str) -> str:
    """Apply rules 2 and 3 and return the cleaned, casefolded reply.

    Exposed separately so the tests (and anyone debugging an ``UNPARSEABLE``)
    can see exactly what the parser was matching against.
    """
    text = _CODE_FENCE.sub(" ", raw)
    text = _EMPHASIS.sub("", text)
    text = text.strip()
    # Repeatedly strip a leading label: "Answer: Category: Mortgage".
    while True:
        stripped = _LEADING_LABEL.sub("", text)
        if stripped == text:
            break
        text = stripped
    text = text.strip().strip("\"'“”‘’")
    text = text.strip(" .,;:!?\n\t")
    text = _SEPARATORS.sub(" ", text)
    text = _WHITESPACE.sub(" ", text).strip()
    return text.casefold()


def normalise_category(raw: str | None) -> str:
    """Map a raw model reply onto one of :data:`CATEGORIES` or ``UNPARSEABLE``.

    See the module docstring for the numbered rules. This function never raises.
    """
    if raw is None:
        return UNPARSEABLE

    cleaned = clean_reply(raw)
    if not cleaned:
        return UNPARSEABLE

    # Rules 4 and 5: exact match on a canonical name or on an alias.
    exact = _SURFACE_FORMS.get(cleaned)
    if exact is not None:
        return exact

    # Rule 6: containment, but only when it is unambiguous.
    found: set[str] = {
        category
        for surface, category in _SURFACE_FORMS.items()
        if surface in cleaned
    }
    if len(found) == 1:
        return next(iter(found))

    # Rule 7.
    return UNPARSEABLE


def is_valid_category(value: str) -> bool:
    """True if ``value`` is one of the seven categories (not ``UNPARSEABLE``)."""
    return value in CATEGORIES
