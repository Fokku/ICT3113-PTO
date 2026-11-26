"""The Assignment 2 cascade: small model first, escalation rule, optional large-model call.

Owner: Yeo Kai Yuan (Part 1 -- technical core).

What this module is for
------------------------
One call, :func:`classify_with_cascade`, that ``POST /tickets`` uses in place of
a single :func:`service.ollama_client.generate` call when the service runs with
``SERVICE_MODE=cascade``. It calls the small model once, with the unchanged
prompt (``service/prompt.py`` -- the brief fixes the prompt for every model in
every configuration, cascade included). It applies the escalation rule from
``../cascade/escalation_rule.md`` to the small model's own reply, and calls the
large model, with the same unchanged prompt, only when the rule says to.

The hard rule this file exists to enforce
------------------------------------------
**The escalation rule may only ever look at what the small model itself
produced for THIS ticket** -- its predicted category, its raw reply text, or the
ticket's own length. It must never read ``golden/golden_set.csv`` or any golden
label. At inference time the true category is unknown; a rule that peeked at the
label would not be a rule a deployed system could run. See ``TODO_A2.md``,
guardrail 6.

:func:`should_escalate` is the one place that decision is made, and it is
written to take only a :class:`SmallModelAnswer` -- there is no label
parameter to pass it, on purpose. Tuning against golden labels happens offline,
against the tuning-set rows of ``golden/split_a2.csv`` -- never inside this
module.

Where the two settings live
---------------------------
:data:`RULE_SETTINGS` below is the **only** place the settings' parameter values
exist in code. It maps ``"A"`` and ``"B"`` to a rule object whose
:meth:`describe` prints the literal accept/escalate condition. Its values must be
copied verbatim from ``../cascade/escalation_rule.md`` section 3 once Part 2 has
written it; until then both are ``None`` and a cascade service refuses to start
(``CascadeNotConfiguredError``), so a cascade can never run on a rule nobody
wrote down. ``scripts/cascade_replay.py`` is the rule-fidelity check that proves
the code and the document agree (``TODO_A2.md`` §1.2).

Two rule shapes are implemented, the two of the brief's four examples that need
no model call beyond the two the cascade already makes:

* :class:`CategoryRule` -- brief, Example method 1. Accept the small model's
  answer when its *predicted* category is in an accept-list; otherwise
  escalate. ``UNPARSEABLE`` is never in the accept-list, so it always escalates.
* :class:`LengthRule` -- brief, Example method 4. Tickets longer than a cut-off
  go **straight** to the large model without a small-model call ("long tickets
  straight to the large model"); short tickets go to the small model, whose
  answer is accepted unless it is ``UNPARSEABLE``.

The brief's other two examples (agreement, self-reported confidence) need an
extra model call and a second, rule-only prompt. They are not implemented: if
the team chooses one, it needs a new rule class here, a new prompt that is
*not* the classification prompt, and its call's latency added to every reported
cascade figure.

Caller contract (unchanged from the single-model baseline)
------------------------------------------------------------
``POST /tickets``'s HTTP response shape does not change: ``{"id", "category",
"request_id"}``, regardless of which model answered. Everything this module
adds -- which model answered, whether escalation occurred, the small model's
own answer, which setting was active -- goes into the service log only (the
fields in ``service/log_schema.py.CASCADE_LOG_FIELDS``), never into the HTTP
response.

Deliberate non-optimisations
-----------------------------
No caching of either model's answer, ever -- not within a run, not across the
two settings. Every ticket pays the small-model call, and the large-model call
when escalated, in full, every time. The brief forbids caching explicitly
(Scope: "not permitted"), and a cascade's whole measured quantity is the cost
of those calls. No retry and no fallback either: a failed small-model call is a
502, exactly like a failed single-model call, and is **not** quietly escalated
-- a hidden second attempt would make the escalation fraction and the latency
describe something other than the rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal, Protocol, Union

from service import ollama_client
from service.categories import CATEGORIES, UNPARSEABLE, normalise_category
from service.log_schema import OLLAMA_TIMING_FIELDS
from service.ollama_client import OllamaResult

CascadeSetting = Literal["A", "B"]


class CascadeNotConfiguredError(ValueError):
    """Raised when a cascade setting has no rule in :data:`RULE_SETTINGS` yet."""


@dataclass(frozen=True)
class SmallModelAnswer:
    """What the small model produced for one ticket -- the ONLY thing the
    escalation rule is allowed to see.

    Deliberately excludes the ticket's golden label. If a future edit adds a
    field here that is not derived purely from the small model's own call
    (its parsed category, its raw text, or the ticket's own narrative length),
    that edit has probably reintroduced label leakage -- see the module
    docstring.
    """

    predicted_category: str  # one of service.categories.CATEGORIES, or UNPARSEABLE
    raw_text: str | None
    narrative_chars: int
    result: OllamaResult | None  # the small model's full result; None when replayed offline


# ---------------------------------------------------------------------------
# The rules
# ---------------------------------------------------------------------------

class EscalationRule(Protocol):
    """What every rule shape provides. Implemented by the dataclasses below."""

    method: ClassVar[str]

    def escalates_before_small_call(self, narrative_chars: int) -> bool:
        """True when the ticket goes straight to the large model, unasked of the small one."""

    def escalate(self, answer: SmallModelAnswer) -> bool:
        """The full accept/escalate decision for a ticket the small model answered."""

    def describe(self) -> str:
        """The literal condition, as written in ``cascade/escalation_rule.md`` §2."""


@dataclass(frozen=True)
class CategoryRule:
    """Brief, Example method 1: accept the small model on its reliable categories.

    ``escalate = predicted_category NOT IN accept_categories``. The rule reads
    the *predicted* category -- the true one is unknown when the ticket arrives.
    """

    accept_categories: frozenset[str]
    method: ClassVar[str] = "category"

    def __post_init__(self) -> None:
        unknown = sorted(set(self.accept_categories) - set(CATEGORIES))
        if unknown:
            # UNPARSEABLE lands here too: accepting it would return
            # "UNPARSEABLE" to the caller as if it were a category.
            raise ValueError(
                f"CategoryRule accept_categories must be canonical category names "
                f"from service/categories.py; not allowed: {unknown}"
            )

    def escalates_before_small_call(self, narrative_chars: int) -> bool:
        return False

    def escalate(self, answer: SmallModelAnswer) -> bool:
        return answer.predicted_category not in self.accept_categories

    def describe(self) -> str:
        ordered = [c for c in CATEGORIES if c in self.accept_categories]
        accepted = ", ".join(f'"{c}"' for c in ordered)
        return f"category: escalate = predicted_category NOT IN {{{accepted}}}"


@dataclass(frozen=True)
class LengthRule:
    """Brief, Example method 4: short tickets to the small model, long ones to the large.

    ``escalate = len(narrative) > max_chars OR predicted_category == "UNPARSEABLE"``.
    A ticket over the cut-off is sent straight to the large model and the small
    model is never called for it (brief: "long tickets straight to the large
    model"), so it pays only the large model's latency.
    """

    max_chars: int
    method: ClassVar[str] = "length"

    def __post_init__(self) -> None:
        if not isinstance(self.max_chars, int) or self.max_chars < 0:
            raise ValueError(f"LengthRule max_chars must be a non-negative int, got {self.max_chars!r}")

    def escalates_before_small_call(self, narrative_chars: int) -> bool:
        return narrative_chars > self.max_chars

    def escalate(self, answer: SmallModelAnswer) -> bool:
        return (
            self.escalates_before_small_call(answer.narrative_chars)
            or answer.predicted_category == UNPARSEABLE
        )

    def describe(self) -> str:
        return (
            f"length: escalate = len(narrative) > {self.max_chars} "
            f'OR predicted_category == "UNPARSEABLE" '
            f"(tickets over {self.max_chars} characters skip the small model)"
        )


Rule = Union[CategoryRule, LengthRule]

#: Setting A and Setting B, copied verbatim from ``cascade/escalation_rule.md``
#: §2-3 (frozen at tag ``a2-predictions-freeze``), and written nowhere else in
#: code. Small model ``granite4:3b``, large model ``qwen2.5:7b`` (§1).
#: ``scripts/cascade_replay.py --small-model granite4:3b`` proves the code gives
#: §3's tuning-set escalation counts exactly: 78/99 at A and 59/99 at B
#: (``tests/test_rule_fidelity.py``).
RULE_SETTINGS: dict[str, Rule | None] = {
    # The "reliable categories" setting: the predicted categories granite4:3b
    # got right every time on the tuning set.
    "A": CategoryRule(
        accept_categories=frozenset({"Mortgage", "Consumer loan", "Debt collection"})
    ),
    # The "lowest escalation that still passes" setting: A plus Credit card.
    "B": CategoryRule(
        accept_categories=frozenset({"Mortgage", "Consumer loan", "Debt collection", "Credit card"})
    ),
}


def rule_for(setting: str) -> Rule:
    """The configured rule for ``setting``, or :class:`CascadeNotConfiguredError`."""
    if setting not in RULE_SETTINGS:
        raise CascadeNotConfiguredError(
            f"unknown cascade setting {setting!r}; the settings are "
            f"{sorted(RULE_SETTINGS)} (\"Setting A\" / \"Setting B\")"
        )
    rule = RULE_SETTINGS[setting]
    if rule is None:
        raise CascadeNotConfiguredError(
            f"Setting {setting} has no escalation rule yet. Copy it from "
            f"cascade/escalation_rule.md section 3 into service/cascade.py "
            f"RULE_SETTINGS, then run scripts/cascade_replay.py."
        )
    return rule


def should_escalate(answer: SmallModelAnswer, *, setting: CascadeSetting) -> bool:
    """The escalation rule from ``../cascade/escalation_rule.md`` section 2.

    The full decision for a ticket at ``setting``, from the small model's own
    answer only. Do not add parameters: adding a label or a golden-set lookup to
    this signature is the single most likely way this module gets the brief's
    requirement wrong; see the module docstring.
    """
    return rule_for(setting).escalate(answer)


def escalates_before_small_call(narrative_chars: int, *, setting: CascadeSetting) -> bool:
    """True when the rule sends a ticket straight to the large model (length rule only)."""
    return rule_for(setting).escalates_before_small_call(narrative_chars)


# ---------------------------------------------------------------------------
# The cascade call
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CascadeResult:
    """The outcome of running one ticket through the cascade.

    ``final_category`` / ``final_model_tag`` / ``final_model_digest`` describe
    whichever model actually produced the answer -- these map directly onto
    the existing ``predicted_category`` / ``model_tag`` / ``model_digest`` log
    fields, which already mean "whichever model answered" for a single-model
    run. On a failure they name the model whose call failed, and
    ``final_category`` is ``None``.
    """

    final_category: str | None
    final_raw_text: str | None
    final_model_tag: str
    final_model_digest: str | None
    escalated: bool
    cascade_setting: CascadeSetting
    small_model_tag: str
    small_model_category: str | None  # None when the small model was not asked, or failed
    small_result: OllamaResult | None  # None when the rule skipped the small model
    large_result: OllamaResult | None  # None when not escalated
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.final_category is not None

    @property
    def _calls(self) -> list[OllamaResult]:
        return [r for r in (self.small_result, self.large_result) if r is not None]

    @property
    def model_latency_ms(self) -> float:
        """Wall clock spent in model calls for this ticket: one call, or both summed."""
        return round(sum(r.model_latency_ms for r in self._calls), 1)

    @property
    def timings(self) -> dict[str, int | None]:
        """Ollama's six fields, summed over the calls that reported them.

        A field no call reported stays ``None`` rather than becoming 0: a
        made-up zero would read as "Ollama said it took no time".
        """
        summed: dict[str, int | None] = {}
        for name in OLLAMA_TIMING_FIELDS:
            values = [r.timings.get(name) for r in self._calls]
            present = [v for v in values if v is not None]
            summed[name] = sum(present) if present else None
        return summed

    @property
    def small_model_latency_ms(self) -> float | None:
        return None if self.small_result is None else self.small_result.model_latency_ms

    @property
    def small_load_duration(self) -> int | None:
        if self.small_result is None:
            return None
        return self.small_result.timings.get("load_duration")


async def classify_with_cascade(
    *,
    base_url: str,
    small_model_tag: str,
    small_model_digest: str | None,
    large_model_tag: str,
    large_model_digest: str | None,
    prompt: str,
    narrative_chars: int,
    seed: int,
    num_ctx: int,
    timeout_s: float,
    setting: CascadeSetting,
) -> CascadeResult:
    """Classify one ticket through the cascade at the given setting.

    Calls the small model once via ``service.ollama_client.generate`` (looked up
    on the module at call time, so the test suite's fake replaces it), unless
    the rule sends the ticket straight to the large model. Calls the large
    model, via the same function, only when :func:`should_escalate` returns
    true for the small model's own answer. ``prompt`` is the one unchanged
    template from ``service/prompt.py``, passed to both calls as-is.
    """
    rule = rule_for(setting)  # raises before any model call if not configured

    async def large_call() -> OllamaResult:
        return await ollama_client.generate(
            base_url=base_url,
            model_tag=large_model_tag,
            prompt=prompt,
            seed=seed,
            num_ctx=num_ctx,
            timeout_s=timeout_s,
        )

    def finish_large(
        large: OllamaResult,
        small: OllamaResult | None,
        small_category: str | None,
    ) -> CascadeResult:
        return CascadeResult(
            final_category=normalise_category(large.raw_text) if large.ok else None,
            final_raw_text=large.raw_text if large.ok else None,
            final_model_tag=large_model_tag,
            final_model_digest=large_model_digest,
            escalated=True,
            cascade_setting=setting,
            small_model_tag=small_model_tag,
            small_model_category=small_category,
            small_result=small,
            large_result=large,
            error=None if large.ok else large.error,
        )

    # Length rule: a long ticket never sees the small model.
    if rule.escalates_before_small_call(narrative_chars):
        large = await large_call()
        return finish_large(large, None, None)

    small = await ollama_client.generate(
        base_url=base_url,
        model_tag=small_model_tag,
        prompt=prompt,
        seed=seed,
        num_ctx=num_ctx,
        timeout_s=timeout_s,
    )
    if not small.ok:
        # A failed small call is a failed request, not an escalation: see the
        # module docstring ("no retry and no fallback").
        return CascadeResult(
            final_category=None,
            final_raw_text=None,
            final_model_tag=small_model_tag,
            final_model_digest=small_model_digest,
            escalated=False,
            cascade_setting=setting,
            small_model_tag=small_model_tag,
            small_model_category=None,
            small_result=small,
            large_result=None,
            error=small.error,
        )

    small_category = normalise_category(small.raw_text)
    answer = SmallModelAnswer(
        predicted_category=small_category,
        raw_text=small.raw_text,
        narrative_chars=narrative_chars,
        result=small,
    )
    if not should_escalate(answer, setting=setting):
        return CascadeResult(
            final_category=small_category,
            final_raw_text=small.raw_text,
            final_model_tag=small_model_tag,
            final_model_digest=small_model_digest,
            escalated=False,
            cascade_setting=setting,
            small_model_tag=small_model_tag,
            small_model_category=small_category,
            small_result=small,
            large_result=None,
            error=None,
        )

    large = await large_call()
    return finish_large(large, small, small_category)
