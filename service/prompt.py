"""The single, fixed classification prompt, and its hash.

Owner: Yeo Kai Yuan (Part 1 — baseline service).

There is exactly **one** prompt in this repository and it lives here. Every
measurement we report is a measurement of *this* prompt, so the prompt is
identified by :data:`PROMPT_HASH`, which is written into every service log line
and into every run's ``metadata.json``. If the template is edited, the hash
changes, the pinned hash in ``tests/test_prompt.py`` fails, and results
recorded before and after the edit must not be pooled. That failing test is the
point: it forces the edit to be a deliberate, recorded act.

Design of the prompt (deliberately plain)
-----------------------------------------
1. State the task in one sentence.
2. List the seven categories verbatim, one per line, taken from
   :data:`service.categories.CATEGORIES` so the prompt can never drift from the
   canonical spelling used by the normaliser and the confusion matrix.
3. Instruct the model to reply with the category name and nothing else.
4. Give the ticket last, after the instructions, because a small instruct model
   attends most reliably to the text nearest the end of the prompt.

What the prompt deliberately does **not** do
--------------------------------------------
No few-shot examples, no chain-of-thought suppression tricks, no category
definitions, no output schema, no "think step by step". Those are prompt-tuning
moves: they change accuracy *and* prompt length (hence CPU time per request),
so they belong in Assignment 2 where the effect can be measured against this
baseline.

# A2 candidate: few-shot examples / category definitions in the prompt to lift
# accuracy (costs prompt-eval tokens, so it must be measured, not assumed).
# A2 candidate: shortening the instruction block to cut prompt_eval_duration.
# A2 candidate: Ollama's structured-output `format` parameter so the reply is
# constrained to the seven strings and service.categories never has to parse.
"""

from __future__ import annotations

import hashlib

from service.categories import CATEGORIES

#: Placeholder the narrative is substituted into. Kept as a named constant so
#: the tests can assert the template really does carry a substitution point.
NARRATIVE_PLACEHOLDER = "{narrative}"

# The seven categories, one per line, verbatim and in canonical order. Built
# from CATEGORIES rather than typed out again: a typo here would make the model
# emit a string the normaliser cannot map, which would look like model error.
_CATEGORY_LINES = "\n".join(f"- {category}" for category in CATEGORIES)

#: The one and only classification prompt. ``{narrative}`` is the only
#: substitution point; there are no other braces in the template.
PROMPT_TEMPLATE: str = (
    "You are a support ticket triage assistant for a financial services "
    "company.\n"
    "Classify the customer complaint below into exactly one of these seven "
    "categories:\n"
    "\n"
    f"{_CATEGORY_LINES}\n"
    "\n"
    "Reply with the category name only, exactly as written above. "
    "Do not explain, do not add punctuation, and do not output anything else.\n"
    "\n"
    "Complaint:\n"
    "{narrative}\n"
    "\n"
    "Category:"
)


def prompt_hash_for(template: str) -> str:
    """Return the identifier we use for a prompt template.

    The formula is fixed by the build contract: ``"sha256:"`` followed by the
    first 16 hex characters of the SHA-256 of the UTF-8 encoded template. It is
    a function (not an inline expression) so the tests compute the hash the same
    way the service does instead of re-implementing it.

    Sixteen characters is short enough to read in a log line and far more than
    enough to distinguish the handful of prompts this project will ever have.
    """
    digest = hashlib.sha256(template.encode("utf-8")).hexdigest()
    return "sha256:" + digest[:16]


#: Identifies the prompt used for a request. Logged on every ``/tickets`` line,
#: reported by ``/health``, and stamped into every run's ``metadata.json``.
PROMPT_HASH: str = prompt_hash_for(PROMPT_TEMPLATE)


def build_prompt(narrative: str) -> str:
    """Return the full prompt for one ticket ``narrative``.

    The narrative is substituted verbatim: it is not stripped, truncated,
    lower-cased or otherwise touched. The service must send the model exactly
    what the intake sent us, because ``ticket_chars`` in the log line is
    ``len(narrative)`` and the two must describe the same text.

    Note there is no length guard. Our team's longest row is 1,999 characters,
    which fits comfortably inside the ``NUM_CTX`` of 4096 we configure; see the
    rationale in ``.env.example``. A guard that silently truncated a long
    complaint would corrupt an accuracy measurement without leaving a trace.
    """
    return PROMPT_TEMPLATE.format(narrative=narrative)
