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
``ZERO_SHOT``          implemented here as the reference template.
``FEW_SHOT``           stub - owner Satya Prakash.
``ROLE_CONTEXT``       stub - owner Satya Prakash.
``CONSTRAINT_BASED``   stub - owner Satya Prakash.

The three stubs raise :class:`NotImplementedError` on purpose. They do not
silently fall back to zero-shot: a silent fallback would produce four
identical rows in the E2 accuracy table and look like a finding rather than a
missing implementation.

Owner: Satya Prakash (prompt engineering, E2) / Kishore (shared blocks + seam)
"""

from __future__ import annotations

from enum import Enum
from typing import Callable, Iterable, Sequence

from . import config
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
    return (PromptStrategy.ZERO_SHOT,)


def pending_strategies() -> tuple[PromptStrategy, ...]:
    """Strategies still to be implemented, in E2 ownership order."""
    return (
        PromptStrategy.FEW_SHOT,
        PromptStrategy.ROLE_CONTEXT,
        PromptStrategy.CONSTRAINT_BASED,
    )


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
# FEW_SHOT - not implemented
# --------------------------------------------------------------------------


def build_few_shot_prompt(
    query: str,
    allowed_intents: Sequence[str],
    *,
    examples: Iterable[tuple[str, str]] | None = None,
    n_examples: int = 4,
) -> str:
    """
    Build the few-shot prompt (E2 variant 2). NOT YET IMPLEMENTED.

    Design rationale
    ----------------
    See ``STRATEGY_RATIONALE[PromptStrategy.FEW_SHOT]``. In short: worked
    examples are expected to lift JSON validity (by demonstrating the format)
    and intent accuracy (by disambiguating confusable pairs). E2 should report
    those two effects separately, because they have different causes.

    Intended contract
    -----------------
    query:
        One raw customer message.
    allowed_intents:
        The dataset label space.
    examples:
        Iterable of ``(customer_message, expected_json_string)`` pairs. When
        None, the builder selects ``n_examples`` from the BANKING77 *train*
        split via ``data_prep.py``.
    n_examples:
        How many examples to include when ``examples`` is None.

    Returns ``str`` - the assembled prompt.

    Implementation notes for the owner
    ----------------------------------
    1. Reuse :func:`format_intent_catalogue`, :func:`format_tool_catalogue`
       and :func:`format_schema_contract`. Do not retype the schema, or an
       accuracy delta against zero-shot becomes unattributable.
    2. Examples MUST come from the train split only. Drawing them from the
       stratified evaluation sample contaminates every number in E2.
    3. Select examples deterministically under ``config.SEED`` so the prompt is
       reproducible, and log which examples were used for the prompt log
       deliverable.
    4. Include at least one example whose intent appears in
       ``intents.CONFUSABLE_PAIRS``, so E6 can test whether examples fix the
       predicted confusions.

    Raises
    ------
    NotImplementedError
        Always, until the owner implements it.
    """
    raise NotImplementedError(
        "FEW_SHOT prompt builder is not implemented yet (owner: Satya Prakash, "
        "Experiment E2). Required: assemble n_examples train-split "
        "query->JSON pairs, deterministic under config.SEED, reusing "
        "format_intent_catalogue/format_tool_catalogue/format_schema_contract."
    )


# --------------------------------------------------------------------------
# ROLE_CONTEXT - not implemented
# --------------------------------------------------------------------------


def build_role_context_prompt(
    query: str,
    allowed_intents: Sequence[str],
    *,
    role: str = "tier-1 retail banking support agent",
    channel: str = "live chat",
) -> str:
    """
    Build the role / context prompt (E2 variant 3). NOT YET IMPLEMENTED.

    Design rationale
    ----------------
    See ``STRATEGY_RATIONALE[PromptStrategy.ROLE_CONTEXT]``. This variant
    targets response quality and escalation behaviour rather than label
    accuracy, so E2 must not judge it on accuracy alone or its actual effect
    will be invisible in the results table.

    Intended contract
    -----------------
    query:
        One raw customer message.
    allowed_intents:
        The dataset label space.
    role:
        The persona assigned to the model.
    channel:
        The support channel, which sets the expected register and reply length.

    Returns ``str`` - the assembled prompt.

    Implementation notes for the owner
    ----------------------------------
    1. State the role, the operating context (first-line triage, systems are
       simulated, a human colleague is available) and the boundaries of the
       model's authority.
    2. Keep the schema and catalogue blocks byte-identical to zero-shot by
       reusing the shared formatters; only the framing prose should differ.
    3. Report this variant against evaluation criterion 4 (response safety, no
       invented account facts) and the ``requires_human`` rate, not just top-1
       accuracy.

    Raises
    ------
    NotImplementedError
        Always, until the owner implements it.
    """
    raise NotImplementedError(
        "ROLE_CONTEXT prompt builder is not implemented yet (owner: Satya "
        "Prakash, Experiment E2). Required: role and operating-context framing "
        "around the shared catalogue/schema blocks, evaluated on response "
        "safety and requires_human rate as well as accuracy."
    )


# --------------------------------------------------------------------------
# CONSTRAINT_BASED - not implemented
# --------------------------------------------------------------------------


def build_constraint_based_prompt(
    query: str,
    allowed_intents: Sequence[str],
    *,
    forbid_prose: bool = True,
    forbid_code_fences: bool = True,
) -> str:
    """
    Build the constraint-based prompt (E2 variant 4). NOT YET IMPLEMENTED.

    Design rationale
    ----------------
    See ``STRATEGY_RATIONALE[PromptStrategy.CONSTRAINT_BASED]``. This variant
    attacks the structured-output failure modes enumerated in
    ``schema.FailureKind`` by stating them as explicit prohibitions.

    Intended contract
    -----------------
    query:
        One raw customer message.
    allowed_intents:
        The dataset label space.
    forbid_prose:
        Emit the "no text outside the JSON object" rule.
    forbid_code_fences:
        Emit the "no ```json fences" rule.

    Returns ``str`` - the assembled prompt.

    Implementation notes for the owner
    ----------------------------------
    1. Write one explicit rule per member of ``schema.FailureKind``:
       NO_JSON_FOUND, MALFORMED_JSON, SCHEMA_VIOLATION, UNKNOWN_INTENT. That
       mapping is what lets E2 and E4 be compared row by row.
    2. Include the ``extra="forbid"`` consequence: inventing a field is a hard
       validation failure, so the model must emit exactly the five
       model-owned fields and no others.
    3. The headline metric for this variant is the first-attempt schema
       validity rate, i.e. validity *before* the repair-retry loop. Report
       both, since the point is reduced reliance on repair.

    Raises
    ------
    NotImplementedError
        Always, until the owner implements it.
    """
    raise NotImplementedError(
        "CONSTRAINT_BASED prompt builder is not implemented yet (owner: Satya "
        "Prakash, Experiment E2). Required: one explicit rule per "
        "schema.FailureKind member, reported on first-attempt schema validity "
        "before repair-retry."
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
    NotImplementedError
        If the strategy is a documented stub (see :func:`pending_strategies`).
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
