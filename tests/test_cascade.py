"""Structural guardrail tests for the Assignment 2 cascade.

Owner: Yeo Kai Yuan (Part 1 -- technical core).

These tests do not test the escalation rule's *behaviour* -- it is not
implemented yet (``service/cascade.py`` is a stub), and once it is, its
correctness is an analysis question (``TODO_A2.md`` section 2.4), not a
unit-test one. What these tests check, and can check right now and forever
regardless of implementation, is the one hard structural constraint the
brief sets on *how* the decision may be made: the escalation rule must only
ever see what the small model itself produced for a ticket, never the
ticket's true golden label.

If a future edit adds a label- or golden-set-shaped parameter to
:func:`service.cascade.should_escalate` (or to the dataclasses feeding it),
these tests fail -- on purpose, caught by ``pytest`` before any benchmark run,
rather than by a marker reading the escalation rule document against the
implementation afterwards.
"""

from __future__ import annotations

import inspect

from service import cascade

#: Substrings that, if found in a parameter or field name, suggest the true
#: category could reach the escalation decision. Checked case-insensitively.
_FORBIDDEN_NAME_FRAGMENTS = (
    "label",
    "golden",
    "true_category",
    "true_label",
    "gold_category",
    "answer_key",
)


def _assert_no_forbidden_names(names: tuple[str, ...], *, where: str) -> None:
    for name in names:
        lowered = name.lower()
        for fragment in _FORBIDDEN_NAME_FRAGMENTS:
            assert fragment not in lowered, (
                f"{where} has '{name}', which looks like it could carry the true "
                f"golden label into the escalation rule. The rule may only see "
                f"what the small model itself produced -- see "
                f"service/cascade.py's module docstring."
            )


def test_should_escalate_signature_carries_no_label() -> None:
    """``should_escalate`` must never be given a way to see the true category."""
    sig = inspect.signature(cascade.should_escalate)
    _assert_no_forbidden_names(
        tuple(sig.parameters), where="should_escalate()'s parameters"
    )


def test_small_model_answer_carries_no_label() -> None:
    """``SmallModelAnswer`` -- the only input the rule may read -- stays label-free."""
    fields = tuple(cascade.SmallModelAnswer.__dataclass_fields__)
    _assert_no_forbidden_names(fields, where="SmallModelAnswer's fields")


def test_classify_with_cascade_signature_carries_no_label() -> None:
    """The top-level entry point must not accept a label parameter either."""
    sig = inspect.signature(cascade.classify_with_cascade)
    _assert_no_forbidden_names(
        tuple(sig.parameters), where="classify_with_cascade()'s parameters"
    )


def test_cascade_result_names_whichever_model_answered() -> None:
    """``CascadeResult`` must describe the final answer generically, not per-model.

    A field like ``large_model_category`` (rather than ``final_category``)
    would make it possible for the HTTP response or the log to leak which
    model answered through field *presence* rather than a value -- the brief
    requires the caller cannot tell which model produced the answer.
    """
    fields = set(cascade.CascadeResult.__dataclass_fields__)
    assert "final_category" in fields
    assert "final_model_tag" in fields
    forbidden = {"large_model_category", "small_model_final_category"}
    assert not (fields & forbidden), (
        "CascadeResult should describe the final answer generically "
        "(final_category / final_model_tag), not per-model."
    )
