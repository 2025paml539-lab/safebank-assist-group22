"""
Reusable parameterized prompt templates (Requirement 11, Experiment E2).

Four prompting strategies are compared in E2. They are deliberately built from
*shared* rendered blocks - the intent catalogue, the schema contract and the
tool catalogue - so that the only thing varying between strategies is the
prompting technique itself. If each variant hand-wrote its own schema text,
an accuracy difference could be caused by wording drift rather than by the
strategy, and the comparison table would not mean anything.

Implementation status
---------------------
``ZERO_SHOT``          reference template (Kishore).
``FEW_SHOT``           implemented - owner Satya Prakash.
``ROLE_CONTEXT``       implemented - owner Satya Prakash.
``CONSTRAINT_BASED``   implemented - owner Satya Prakash.

No variant silently falls back to zero-shot: each is a genuinely distinct
template, so the four rows in the E2 accuracy table are attributable to the
strategy rather than to wording drift. The schema, intent catalogue and tool
catalogue are rendered by the shared formatters and are byte-identical across
all four variants.

Owner: Satya Prakash (prompt engineering, E2) / Kishore (shared blocks + seam)
"""

from __future__ import annotations

import random
from enum import Enum
from typing import Callable, Iterable, Sequence

from . import config
from .intents import CONFUSABLE_PAIRS
from .schema import AssistantResponse
from .tools import TOOL_REGISTRY

# --------------------------------------------------------------------------
# Strategy identity
# --------------------------------------------------------------------------


class PromptStrategy(str, Enum):
    """The four prompt variants required by Requirement 6 and Experiment E2."""

    ZERO_SHOT = "zero_shot"
    FEW_SHOT = "few_shot"
    ROLE_CONTEXT = "role_context"
    CONSTRAINT_BASED = "constraint_based"


#: Written design rationale for every strategy. The brief forbids
#: "unexplained prompts" (Section 8), so each variant carries the reason it was
#: designed that way, and the report quotes this dictionary directly.
STRATEGY_RATIONALE: dict[PromptStrategy, str] = {
    PromptStrategy.ZERO_SHOT: (
        "Instruction only, no worked examples. Establishes the floor for an "
        "instruction-tuned model: it measures how much of the task the model "
        "already understands from the label names and the schema alone. It is "
        "also the cheapest variant in prompt tokens, which matters because the "
        "77-label catalogue already dominates the context."
    ),
    PromptStrategy.FEW_SHOT: (
        "Adds k worked query -> JSON examples. Expected to help in two "
        "distinct ways that E2 should separate: it demonstrates the output "
        "format (raising JSON validity) and it disambiguates confusable intent "
        "pairs by example (raising accuracy). Examples must be drawn from the "
        "train split only, never from the evaluation sample, or the reported "
        "accuracy is contaminated."
    ),
    PromptStrategy.ROLE_CONTEXT: (
        "Assigns the model the persona of a tier-1 banking support agent and "
        "supplies the operating context (first-line triage, simulated systems, "
        "escalation available). Targets response *quality* and safety rather "
        "than label accuracy: the hypothesis is that a role-conditioned model "
        "produces customer-safe replies and uses requires_human more "
        "appropriately, which are scored criteria 4 and the escalation path."
    ),
    PromptStrategy.CONSTRAINT_BASED: (
        "States hard output constraints as explicit rules with prohibitions "
        "(exactly one JSON object, no prose, no code fences, label must be "
        "copied verbatim from the catalogue, no invented account facts). "
        "Targets the schema-validity rate and the unknown-intent failure mode "
        "directly, and is the variant expected to reduce reliance on the "
        "repair-retry loop measured in E4."
    ),
}


def implemented_strategies() -> tuple[PromptStrategy, ...]:
    """Strategies with a working builder today."""
    return (
        PromptStrategy.ZERO_SHOT,
        PromptStrategy.FEW_SHOT,
        PromptStrategy.ROLE_CONTEXT,
        PromptStrategy.CONSTRAINT_BASED,
    )


def pending_strategies() -> tuple[PromptStrategy, ...]:
    """Strategies still to be implemented, in E2 ownership order."""
    return ()


# --------------------------------------------------------------------------
# Shared rendered blocks
# --------------------------------------------------------------------------

#: Fields the model must not be asked to produce. ``disclaimer`` has a schema
#: default and is enforced by the application, not by the model: letting the
#: model write its own provenance notice would defeat the control.
_MODEL_OWNED_FIELDS: tuple[str, ...] = (
    "intent",
    "confidence",
    "response",
    "tool_call",
    "requires_human",
)


def format_intent_catalogue(allowed_intents: Sequence[str], per_line: int = 4) -> str:
    """
    Render the permitted label space as a numbered, wrapped catalogue.

    The labels are passed in rather than imported so that the authoritative
    names come from the dataset at load time (see ``intents.py``). Order is
    preserved exactly as supplied, because the dataset's own label order is
    what ``data_prep.py`` records for reproducibility.
    """
    labels = [str(label).strip() for label in allowed_intents if str(label).strip()]
    if not labels:
        raise ValueError(
            "allowed_intents is empty; the prompt would permit any label, which "
            "disables the unknown-intent guard in schema.parse_response"
        )

    lines: list[str] = []
    for start in range(0, len(labels), per_line):
        chunk = labels[start : start + per_line]
        lines.append("  " + ", ".join(chunk))
    return "\n".join(lines)


def format_schema_contract() -> str:
    """
    Render the required JSON fields from the pydantic model itself.

    Derived from ``AssistantResponse.model_fields`` rather than retyped, so the
    prompt cannot drift out of step with the validator. A prompt that asks for
    a field the schema forbids would be counted as a model failure in E4 when
    it is really a documentation bug.
    """
    fields = AssistantResponse.model_fields
    lines: list[str] = []
    for name in _MODEL_OWNED_FIELDS:
        field = fields[name]
        description = (field.description or "").strip()
        lines.append(f'  "{name}": {_type_hint_for(name)}  // {description}')
    return "\n".join(lines)


def _type_hint_for(name: str) -> str:
    """Short, model-friendly type hint for one schema field."""
    hints = {
        "intent": "string",
        "confidence": "number between 0.0 and 1.0",
        "response": "string, non-empty",
        "tool_call": '{"name": string, "args": {string: string}} or null',
        "requires_human": "boolean",
    }
    return hints[name]


def format_tool_catalogue() -> str:
    """
    Render the callable tools and their argument names from the registry.

    Built from ``TOOL_REGISTRY`` so a tool added later appears in every prompt
    without editing templates. Destructive tools are marked, because the model
    should request them rather than assume they will run: the pipeline refuses
    to auto-execute them.
    """
    lines: list[str] = []
    for spec in TOOL_REGISTRY.values():
        args = ", ".join(spec.input_model.model_fields)
        marker = " [requires human confirmation]" if spec.destructive else ""
        lines.append(f"  {spec.name.value}({args}) - {spec.description}{marker}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# ZERO_SHOT - reference implementation
# --------------------------------------------------------------------------

_ZERO_SHOT_TEMPLATE = """You are a banking customer-support triage system.

Classify the customer message into exactly one intent from the catalogue
below, then write a short, safe reply.

Permitted intents (copy one label verbatim, do not invent or reword):
{intent_catalogue}

Available tools (set tool_call only when the intent genuinely needs a system
lookup, otherwise use null):
{tool_catalogue}

Reply with ONE JSON object and nothing else:
{{
{schema_contract}
}}

Rules:
- Never state an account fact you were not given. Describe the next step instead.
- Set requires_human to true if the request needs a human agent.
- Set confidence below {threshold} when the message is genuinely ambiguous.

Customer message:
{query}

JSON:"""


def build_zero_shot_prompt(query: str, allowed_intents: Sequence[str]) -> str:
    """
    Build the zero-shot prompt (E2 variant 1, the reference template).

    Instruction-only: the model receives the task, the label catalogue, the
    tool catalogue and the output contract, but no worked examples. This is the
    baseline every other variant is measured against.

    Parameters
    ----------
    query:
        One raw customer message.
    allowed_intents:
        The dataset's label space, as loaded from BANKING77.

    Returns
    -------
    str
        A complete prompt ready for ``TextGenerator.generate``.
    """
    cleaned = _clean_query(query)
    return _ZERO_SHOT_TEMPLATE.format(
        intent_catalogue=format_intent_catalogue(allowed_intents),
        tool_catalogue=format_tool_catalogue(),
        schema_contract=format_schema_contract(),
        threshold=f"{config.ESCALATION_CONFIDENCE_THRESHOLD:.2f}",
        query=cleaned,
    )


def _clean_query(query: str) -> str:
    """
    Minimal, documented preprocessing of one customer message.

    Collapses whitespace and strips surrounding quotes. Deliberately nothing
    more: BANKING77 queries are short and informal, and aggressive cleaning
    (lowercasing, punctuation removal) would destroy cues the model uses. The
    preprocessing record in the report cites this function.
    """
    if not isinstance(query, str):
        raise TypeError(f"query must be str, got {type(query).__name__}")
    cleaned = " ".join(query.split()).strip().strip('"').strip()
    if not cleaned:
        raise ValueError("query is empty after whitespace normalisation")
    return cleaned


# --------------------------------------------------------------------------
# FEW_SHOT
# --------------------------------------------------------------------------

#: Offline worked examples used only when the caller supplies no ``examples``
#: and ``data_prep.py`` is not available (local, model-free development). Every
#: pair is hand-written to match ``AssistantResponse`` exactly, so it also
#: doubles as a format demonstration. These are illustrative stand-ins, NOT
#: BANKING77 train rows: the final E2 run MUST pass real train-split pairs via
#: the ``examples`` argument, because drawing examples from anywhere near the
#: evaluation sample would contaminate every number in the table.
#:
#: The set intentionally covers both a tool-calling intent and a confusable
#: pair member (``card_arrival`` from CONFUSABLE_PAIRS[0]) so E6 can test
#: whether examples repair the predicted confusion.
_FEWSHOT_FALLBACK_EXAMPLES: tuple[tuple[str, str], ...] = (
    (
        "My new card still hasn't turned up, it's been almost two weeks now.",
        '{"intent": "card_arrival", "confidence": 0.86, '
        '"response": "I understand the wait is frustrating. Let me check the '
        'delivery status of your card.", "tool_call": {"name": '
        '"check_card_delivery_status", "args": {"card_id": "CARD_SIM_0001"}}, '
        '"requires_human": false}',
    ),
    (
        "How many more days until my replacement card gets to me?",
        '{"intent": "card_delivery_estimate", "confidence": 0.78, '
        '"response": "Let me look up the estimated delivery window for your '
        'card.", "tool_call": {"name": "check_card_delivery_status", "args": '
        '{"card_id": "CARD_SIM_0001"}}, "requires_human": false}',
    ),
    (
        "I think someone has my card details, please stop it being used.",
        '{"intent": "compromised_card", "confidence": 0.74, '
        '"response": "Thanks for flagging this. Blocking a card is a protected '
        'action, so I will pass this to a colleague to confirm with you '
        'directly.", "tool_call": null, "requires_human": true}',
    ),
    (
        "Is there a branch near 560001 where I can deposit cash?",
        '{"intent": "atm_support", "confidence": 0.69, '
        '"response": "I can help you find a nearby branch for that. Let me '
        'search your area.", "tool_call": {"name": "find_branch", "args": '
        '{"pincode": "560001", "service": "cash_deposit"}}, '
        '"requires_human": false}',
    ),
    (
        "What's the weather like today?",
        '{"intent": "card_arrival", "confidence": 0.20, '
        '"response": "I handle banking support requests, so I am not able to '
        'help with that. I will pass you to a colleague if you have an account '
        'question.", "tool_call": null, "requires_human": true}',
    ),
)


def _select_examples(
    examples: Iterable[tuple[str, str]] | None, n_examples: int
) -> list[tuple[str, str]]:
    """
    Deterministically choose ``n_examples`` worked examples.

    When ``examples`` is supplied (the real E2 path: BANKING77 train-split
    pairs from ``data_prep.py``) it is sampled from. When it is None, the
    offline fallback bank is used so the prompt can be built and tested with no
    model and no dataset present.

    Selection is seeded from ``config.SEED`` so the same inputs always yield
    the same prompt, which the E2 prompt-log deliverable depends on. At least
    one confusable-pair member is pulled to the front when present, so the
    chosen set always exercises the disambiguation hypothesis.
    """
    if n_examples <= 0:
        raise ValueError(f"n_examples must be positive, got {n_examples}")

    pool = list(examples) if examples is not None else list(_FEWSHOT_FALLBACK_EXAMPLES)
    if not pool:
        raise ValueError(
            "no few-shot examples available; pass train-split pairs via "
            "`examples` or rely on the offline fallback bank"
        )

    confusable_labels = {p.first for p in CONFUSABLE_PAIRS} | {
        p.second for p in CONFUSABLE_PAIRS
    }

    def _intent_of(pair: tuple[str, str]) -> str:
        # Cheap, dependency-free peek at the example's intent label.
        marker = '"intent":'
        text = pair[1]
        start = text.find(marker)
        if start == -1:
            return ""
        start = text.find('"', start + len(marker))
        if start == -1:
            return ""
        end = text.find('"', start + 1)
        return text[start + 1 : end] if end != -1 else ""

    rng = random.Random(config.SEED)
    ordered = pool[:]
    rng.shuffle(ordered)

    # Guarantee a confusable-pair member leads the selection when one exists.
    ordered.sort(key=lambda pair: _intent_of(pair) not in confusable_labels)

    return ordered[: min(n_examples, len(ordered))]


_FEWSHOT_HEADER = """You are a banking customer-support triage system.

Classify each customer message into exactly one intent from the catalogue
below, then write a short, safe reply. Study the worked examples first; match
their JSON shape exactly.

Permitted intents (copy one label verbatim, do not invent or reword):
{intent_catalogue}

Available tools (set tool_call only when the intent genuinely needs a system
lookup, otherwise use null):
{tool_catalogue}

Each reply is ONE JSON object and nothing else:
{{
{schema_contract}
}}

Rules:
- Never state an account fact you were not given. Describe the next step instead.
- Set requires_human to true if the request needs a human agent.
- Set confidence below {threshold} when the message is genuinely ambiguous.
"""

_FEWSHOT_EXAMPLE = """
Customer message:
{example_query}

JSON:
{example_json}
"""

_FEWSHOT_FOOTER = """
Now classify this message.

Customer message:
{query}

JSON:"""


def build_few_shot_prompt(
    query: str,
    allowed_intents: Sequence[str],
    *,
    examples: Iterable[tuple[str, str]] | None = None,
    n_examples: int = 4,
) -> str:
    """
    Build the few-shot prompt (E2 variant 2).

    Design rationale
    ----------------
    See ``STRATEGY_RATIONALE[PromptStrategy.FEW_SHOT]``. Worked examples are
    expected to lift JSON validity (by demonstrating the format) and intent
    accuracy (by disambiguating confusable pairs). E2 reports those two effects
    separately, because they have different causes.

    Parameters
    ----------
    query:
        One raw customer message.
    allowed_intents:
        The dataset label space, as loaded from BANKING77.
    examples:
        Iterable of ``(customer_message, expected_json_string)`` pairs. For the
        real E2 run these MUST come from the BANKING77 *train* split (supplied
        by ``data_prep.py``); drawing them from the evaluation sample
        contaminates every reported number. When None, an offline fallback bank
        is used so the prompt is buildable and testable with no dataset.
    n_examples:
        How many examples to include when ``examples`` is None, or how many to
        sample when it is supplied.

    Returns
    -------
    str
        A complete prompt ready for ``TextGenerator.generate``.

    Notes
    -----
    The schema, intent catalogue and tool catalogue are rendered by the shared
    formatters, byte-identical to every other variant, so an accuracy delta
    against zero-shot is attributable to the examples alone. Selection is
    deterministic under ``config.SEED`` and always leads with a confusable-pair
    member when one is available.
    """
    cleaned = _clean_query(query)
    chosen = _select_examples(examples, n_examples)

    header = _FEWSHOT_HEADER.format(
        intent_catalogue=format_intent_catalogue(allowed_intents),
        tool_catalogue=format_tool_catalogue(),
        schema_contract=format_schema_contract(),
        threshold=f"{config.ESCALATION_CONFIDENCE_THRESHOLD:.2f}",
    )
    body = "".join(
        _FEWSHOT_EXAMPLE.format(example_query=ex_q, example_json=ex_json)
        for ex_q, ex_json in chosen
    )
    footer = _FEWSHOT_FOOTER.format(query=cleaned)
    return header + body + footer


# --------------------------------------------------------------------------
# ROLE_CONTEXT
# --------------------------------------------------------------------------

_ROLE_CONTEXT_TEMPLATE = """You are a {role}, working the {channel} channel.

Operating context:
- You are first-line triage: you understand the request, reply safely, and
  route it. You do not resolve the account yourself.
- Every system you can reach is a simulated system of record. You have no
  access to live balances, real card numbers or real customer history.
- A human colleague is always available. Hand off anything that needs real
  account authority, any irreversible action, or anything you are unsure of.
- Your authority stops at classification, a safe reply and an optional system
  lookup. You may request a tool; you may not assume it has run.

Your task: classify the customer message into exactly one intent from the
catalogue, then write a short, professional, customer-safe reply in the
register expected on {channel}.

Permitted intents (copy one label verbatim, do not invent or reword):
{intent_catalogue}

Available tools (set tool_call only when the intent genuinely needs a system
lookup, otherwise use null):
{tool_catalogue}

Reply with ONE JSON object and nothing else:
{{
{schema_contract}
}}

Rules:
- Never state an account fact you were not given. Describe the next step instead.
- Set requires_human to true whenever the request exceeds your authority or
  needs a real colleague.
- Set confidence below {threshold} when the message is genuinely ambiguous.

Customer message:
{query}

JSON:"""


def build_role_context_prompt(
    query: str,
    allowed_intents: Sequence[str],
    *,
    role: str = "tier-1 retail banking support agent",
    channel: str = "live chat",
) -> str:
    """
    Build the role / context prompt (E2 variant 3).

    Design rationale
    ----------------
    See ``STRATEGY_RATIONALE[PromptStrategy.ROLE_CONTEXT]``. This variant
    targets response *quality* and escalation behaviour rather than label
    accuracy, so E2 should judge it on evaluation criterion 4 (response safety,
    no invented account facts) and the ``requires_human`` rate, not on top-1
    accuracy alone.

    Parameters
    ----------
    query:
        One raw customer message.
    allowed_intents:
        The dataset label space, as loaded from BANKING77.
    role:
        The persona assigned to the model.
    channel:
        The support channel, which sets the expected register and reply length.

    Returns
    -------
    str
        A complete prompt ready for ``TextGenerator.generate``.

    Notes
    -----
    Only the framing prose (role, operating context, authority boundaries)
    differs from zero-shot. The intent catalogue, tool catalogue and schema
    contract are rendered by the shared formatters so they stay byte-identical
    across variants and any E2 delta is attributable to the role framing.
    """
    cleaned = _clean_query(query)
    return _ROLE_CONTEXT_TEMPLATE.format(
        role=role,
        channel=channel,
        intent_catalogue=format_intent_catalogue(allowed_intents),
        tool_catalogue=format_tool_catalogue(),
        schema_contract=format_schema_contract(),
        threshold=f"{config.ESCALATION_CONFIDENCE_THRESHOLD:.2f}",
        query=cleaned,
    )


# --------------------------------------------------------------------------
# CONSTRAINT_BASED
# --------------------------------------------------------------------------

_CONSTRAINT_HEADER = """You are a banking customer-support triage system operating under STRICT
output constraints. Your output is parsed by a machine validator that rejects
anything that does not comply exactly.

Classify the customer message into exactly one intent from the catalogue,
then write a short, safe reply.

Permitted intents (copy one label verbatim, do not invent or reword):
{intent_catalogue}

Available tools (set tool_call only when the intent genuinely needs a system
lookup, otherwise use null):
{tool_catalogue}

Required output shape - emit exactly these fields and no others:
{{
{schema_contract}
}}

HARD CONSTRAINTS (each maps to a validator failure that will reject your reply):
{constraints}

Customer message:
{query}

JSON:"""

#: One explicit rule per ``schema.FailureKind`` member. Keeping this mapping
#: exact is what lets E2 (prompt) and E4 (validation) be compared failure-kind
#: by failure-kind: a drop in NO_JSON_FOUND here should show up as the same
#: drop in E4's first-attempt failure table.
_CONSTRAINT_RULES_BY_FAILURE_KIND: tuple[tuple[str, str], ...] = (
    (
        "no_json_found",
        "Output a single JSON object. The first character must be '{{' and the "
        "last must be '}}'. No greeting, no sign-off, nothing before or after.",
    ),
    (
        "malformed_json",
        "The object must be valid JSON: double-quoted keys and string values, "
        "commas between fields, no trailing comma, no comments inside it.",
    ),
    (
        "schema_violation",
        "Emit exactly these five fields - intent, confidence, response, "
        "tool_call, requires_human - and no others. Inventing any extra field "
        "(for example account_balance) is a hard rejection. confidence must be "
        "a number from 0.0 to 1.0; response must be a non-empty string.",
    ),
    (
        "unknown_intent",
        "The intent value must be copied verbatim from the permitted-intents "
        "catalogue above. A plausible-sounding label that is not in the list "
        "is rejected.",
    ),
)


def _format_constraints(
    *, forbid_prose: bool, forbid_code_fences: bool
) -> str:
    """Render the numbered hard-constraint block.

    The four failure-kind rules are always present. The two optional rules
    (prose, code fences) reinforce ``NO_JSON_FOUND`` and are toggleable so the
    ablation in E2 can measure their individual effect.
    """
    rules = [text for _kind, text in _CONSTRAINT_RULES_BY_FAILURE_KIND]
    if forbid_prose:
        rules.append(
            "Do not write any prose, explanation or reasoning outside the JSON "
            "object."
        )
    if forbid_code_fences:
        rules.append("Do not wrap the JSON in ```json fences or any code block.")
    return "\n".join(f"{i}. {rule}" for i, rule in enumerate(rules, start=1))


def build_constraint_based_prompt(
    query: str,
    allowed_intents: Sequence[str],
    *,
    forbid_prose: bool = True,
    forbid_code_fences: bool = True,
) -> str:
    """
    Build the constraint-based prompt (E2 variant 4).

    Design rationale
    ----------------
    See ``STRATEGY_RATIONALE[PromptStrategy.CONSTRAINT_BASED]``. This variant
    attacks the structured-output failure modes enumerated in
    ``schema.FailureKind`` by stating each as an explicit prohibition. The
    headline metric is the *first-attempt* schema validity rate (validity
    before the repair-retry loop); E2 should report both so the point - reduced
    reliance on repair - is visible.

    Parameters
    ----------
    query:
        One raw customer message.
    allowed_intents:
        The dataset label space, as loaded from BANKING77.
    forbid_prose:
        Emit the "no text outside the JSON object" rule.
    forbid_code_fences:
        Emit the "no code fences" rule.

    Returns
    -------
    str
        A complete prompt ready for ``TextGenerator.generate``.

    Notes
    -----
    The constraint block carries one rule per ``schema.FailureKind`` member
    (NO_JSON_FOUND, MALFORMED_JSON, SCHEMA_VIOLATION, UNKNOWN_INTENT), so an
    improvement here can be read off against the matching failure kind in the
    E4 table. The intent catalogue, tool catalogue and schema contract come
    from the shared formatters, byte-identical to the other variants.
    """
    cleaned = _clean_query(query)
    return _CONSTRAINT_HEADER.format(
        intent_catalogue=format_intent_catalogue(allowed_intents),
        tool_catalogue=format_tool_catalogue(),
        schema_contract=format_schema_contract(),
        constraints=_format_constraints(
            forbid_prose=forbid_prose, forbid_code_fences=forbid_code_fences
        ),
        query=cleaned,
    )


# --------------------------------------------------------------------------
# Registry and dispatch
# --------------------------------------------------------------------------

#: Strategy -> builder. The pipeline selects by strategy, so implementing a
#: pending variant requires no change to any caller (Requirement 11).
PROMPT_BUILDERS: dict[PromptStrategy, Callable[..., str]] = {
    PromptStrategy.ZERO_SHOT: build_zero_shot_prompt,
    PromptStrategy.FEW_SHOT: build_few_shot_prompt,
    PromptStrategy.ROLE_CONTEXT: build_role_context_prompt,
    PromptStrategy.CONSTRAINT_BASED: build_constraint_based_prompt,
}


def build_prompt(
    strategy: PromptStrategy | str,
    query: str,
    allowed_intents: Sequence[str],
    **kwargs: object,
) -> str:
    """
    Build a prompt using the requested strategy.

    This is the single entry point used by ``pipeline.SafeBankPipeline``. The
    E2 comparison is therefore the same pipeline run four times with a
    different ``strategy``, which keeps every other variable fixed.

    Parameters
    ----------
    strategy:
        A :class:`PromptStrategy`, or its string value.
    query:
        One raw customer message.
    allowed_intents:
        The dataset label space, as loaded from BANKING77.
    **kwargs:
        Forwarded to the selected builder (for example ``n_examples`` for
        few-shot). Unknown keywords surface as a TypeError from the builder.

    Raises
    ------
    ValueError
        If ``strategy`` is not a known strategy name.
    """
    try:
        resolved = PromptStrategy(strategy)
    except ValueError:
        known = ", ".join(s.value for s in PromptStrategy)
        raise ValueError(
            f"unknown prompt strategy {strategy!r}; expected one of: {known}"
        ) from None

    return PROMPT_BUILDERS[resolved](query, allowed_intents, **kwargs)


__all__ = [
    "PROMPT_BUILDERS",
    "STRATEGY_RATIONALE",
    "PromptStrategy",
    "build_constraint_based_prompt",
    "build_few_shot_prompt",
    "build_prompt",
    "build_role_context_prompt",
    "build_zero_shot_prompt",
    "format_intent_catalogue",
    "format_schema_contract",
    "format_tool_catalogue",
    "implemented_strategies",
    "pending_strategies",
]
