"""The Assignment 2 cascade: small model first, escalation rule, optional large-model call.

Owner: Yeo Kai Yuan (Part 1 -- technical core). STUB -- not wired into
``service/main.py`` yet. This file exists so the interface is fixed before
implementation starts, not so implementation can be skipped.

What this module is for
------------------------
One call, :func:`classify_with_cascade`, that ``POST /tickets`` uses in place of
a single :func:`service.ollama_client.generate` call when the service is running
in cascade mode. It always calls the small model once, with the unchanged
prompt (``service/prompt.py`` -- the brief fixes the prompt for every model in
every configuration, cascade included). It applies the escalation rule from
``../cascade/escalation_rule.md`` to the small model's own reply, and calls the
large model, with the same unchanged prompt, only when the rule says to.

The hard rule this file exists to enforce
------------------------------------------
**The escalation rule may only ever look at what the small model itself
produced for THIS ticket** -- its predicted category, its raw reply text, a
confidence word from a second small-model call, or the ticket's own length.
It must never read ``golden/golden_set.csv`` or any golden label. At inference
time the true category is unknown; a rule that peeked at the label would not
be a rule a deployed system could run. See ``TODO_A2.md``, guardrail 6.

:func:`should_escalate` is the one place that decision is made, and it is
written to take only a :class:`SmallModelAnswer` -- there is no label
parameter to pass it, on purpose. Implement the rule from
``../cascade/escalation_rule.md`` §2 inside that function and nowhere else;
tuning against golden labels happens offline, in analysis scripts, against the
tuning-set rows of ``golden/split_a2.csv`` -- never inside this module.

Caller contract (unchanged from the single-model baseline)
------------------------------------------------------------
``POST /tickets``'s HTTP response shape does not change: ``{"id", "category",
"request_id"}``, regardless of which model answered. Everything this module
adds -- which model answered, whether escalation occurred, the small model's
own answer, which setting was active -- goes into the service log only (the
new fields appended to ``service/log_schema.py.LOG_FIELDS``: ``escalated``,
``cascade_setting``, ``small_model_tag``, ``small_model_category``), never into
the HTTP response.

Deliberate non-optimisations
-----------------------------
No caching of either model's answer, ever -- not within a run, not across the
two settings. Every ticket pays the small-model call, and the large-model call
when escalated, in full, every time. The brief forbids caching explicitly
(Scope: "not permitted"), and a cascade's whole measured quantity is the cost
of those calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from service.ollama_client import OllamaResult

CascadeSetting = Literal["A", "B"]


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
    result: OllamaResult  # the small model's full result, for latency/timing fields


@dataclass(frozen=True)
class CascadeResult:
    """The outcome of running one ticket through the cascade.

    ``final_category`` / ``final_model_tag`` / ``final_model_digest`` describe
    whichever model actually produced the answer -- these map directly onto
    the existing ``predicted_category`` / ``model_tag`` / ``model_digest`` log
    fields, which already mean "whichever model answered" for a single-model
    run. The four fields below them are new, appended to the end of
    ``LOG_FIELDS`` (see ``TODO_A2.md``'s interface table) and set on every
    cascade request, never on a single-model request.
    """

    final_category: str
    final_model_tag: str
    final_model_digest: str | None
    escalated: bool
    cascade_setting: CascadeSetting
    small_model_tag: str
    small_model_category: str
    small_result: OllamaResult
    large_result: OllamaResult | None  # None when not escalated


def should_escalate(answer: SmallModelAnswer, *, setting: CascadeSetting) -> bool:
    """The escalation rule from ``../cascade/escalation_rule.md`` section 2.

    Implement the exact accept/escalate condition written there, as a literal
    boolean expression over ``answer``'s fields -- do not add parameters.
    Adding a label or a golden-set lookup to this function's signature is the
    single most likely way this module gets the brief's requirement wrong; see
    the module docstring before changing the signature.

    TODO(cascade): implement from ``../cascade/escalation_rule.md`` §2-3 once
    that document names the exact signal and the two settings' parameter
    values.
    """
    raise NotImplementedError(
        "Implement from ../cascade/escalation_rule.md section 2-3. "
        "See the module docstring's guardrail before adding any parameter "
        "to this function."
    )


async def classify_with_cascade(
    *,
    base_url: str,
    small_model_tag: str,
    small_model_digest: str | None,
    large_model_tag: str,
    large_model_digest: str | None,
    prompt: str,
    seed: int,
    num_ctx: int,
    timeout_s: float,
    setting: CascadeSetting,
) -> CascadeResult:
    """Classify one ticket through the cascade at the given setting.

    Always calls the small model once via ``service.ollama_client.generate``.
    Calls the large model, via the same function, only when
    :func:`should_escalate` returns true for the small model's own answer.
    The prompt passed to both calls is the one unchanged template from
    ``service/prompt.py`` -- this function does not build a different prompt
    for either model.

    TODO(cascade): implement once ``should_escalate`` is implemented. Wire the
    result into ``service/main.py``'s ``POST /tickets`` handler and into the
    new ``service/log_schema.py`` fields -- neither is done by this stub.
    """
    raise NotImplementedError(
        "Implement should_escalate() first, then this function, then wire "
        "both into service/main.py. Not done by this stub on purpose -- see "
        "TODO_A2.md section 1.2."
    )
