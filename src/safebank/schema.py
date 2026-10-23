"""
Structured-output contract and validation (Requirement 9, Experiment E4).

This module is the single definition of what a well-formed assistant response
looks like. Everything downstream - the tool router, the evaluation harness,
the notebook - depends on this contract rather than on raw model text.

It deliberately has no dependency on transformers or torch, so it is fully
testable offline.

Owner: Kishore (structured output + tool calling)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import config

# --------------------------------------------------------------------------
# Tool identity
# --------------------------------------------------------------------------


class ToolName(str, Enum):
    """The tools the assistant is permitted to request.

    Using an enum rather than a free string means a hallucinated tool name is
    caught by schema validation instead of reaching the router.
    """

    CHECK_CARD_DELIVERY_STATUS = "check_card_delivery_status"
    BLOCK_CARD = "block_card"
    FIND_BRANCH = "find_branch"


# --------------------------------------------------------------------------
# Response models
# --------------------------------------------------------------------------


class ToolCall(BaseModel):
    """A request from the model to invoke one tool."""

    model_config = ConfigDict(extra="forbid")

    name: ToolName = Field(description="Which tool to invoke.")
    args: dict[str, str] = Field(
        default_factory=dict,
        description="Flat string arguments; validated again by the tool itself.",
    )


class AssistantResponse(BaseModel):
    """
    The machine-readable contract for one assistant turn.

    ``extra="forbid"`` is intentional: if the model invents a field, we want a
    validation failure we can count in E4, not a silently ignored key.
    """

    model_config = ConfigDict(extra="forbid")

    intent: str = Field(
        description="Predicted BANKING77 intent name, exactly as in the dataset."
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Model's self-reported confidence in the intent."
    )
    response: str = Field(
        min_length=1, description="Customer-facing reply, safe to show as-is."
    )
    tool_call: ToolCall | None = Field(
        default=None, description="Tool to invoke, or null if none is needed."
    )
    requires_human: bool = Field(
        default=False, description="True when the request must be escalated."
    )
    disclaimer: str = Field(
        default=config.SAFETY_DISCLAIMER,
        description="Mandatory provenance notice attached to every response.",
    )


def response_json_schema() -> dict:
    """JSON Schema for :class:`AssistantResponse`, for the report appendix."""
    return AssistantResponse.model_json_schema()


# --------------------------------------------------------------------------
# Extracting JSON from model text
# --------------------------------------------------------------------------


def extract_json_block(text: str) -> str | None:
    """
    Pull the first balanced JSON object out of raw model output.

    Causal LMs rarely emit bare JSON. They wrap it in prose, in ```json fences,
    or emit trailing commentary. This scans for the first ``{`` and returns the
    substring up to its matching ``}``, respecting string literals and escapes
    so a brace inside a response string does not end the scan early.

    Returns None when no balanced object is present.
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return None


# --------------------------------------------------------------------------
# Validation outcome
# --------------------------------------------------------------------------


class FailureKind(str, Enum):
    """Why a raw completion failed to become a valid response.

    These categories are counted directly in the E4 and E6 tables.
    """

    NO_JSON_FOUND = "no_json_found"
    MALFORMED_JSON = "malformed_json"
    SCHEMA_VIOLATION = "schema_violation"
    UNKNOWN_INTENT = "unknown_intent"


@dataclass
class ValidationOutcome:
    """Result of trying to turn one raw completion into an AssistantResponse."""

    ok: bool
    response: AssistantResponse | None = None
    failure: FailureKind | None = None
    errors: list[str] = field(default_factory=list)
    extracted_json: str | None = None

    def summary(self) -> str:
        if self.ok and self.response is not None:
            return f"ok intent={self.response.intent} conf={self.response.confidence:.2f}"
        return f"invalid {self.failure.value if self.failure else 'unknown'}: {'; '.join(self.errors)}"


def parse_response(
    raw: str,
    allowed_intents: list[str] | set[str] | None = None,
) -> ValidationOutcome:
    """
    Turn raw model text into a validated :class:`AssistantResponse`.

    Parameters
    ----------
    raw:
        The model's completion, prose and fences included.
    allowed_intents:
        The dataset's 77 intent names. When supplied, an intent outside this
        set is rejected as ``UNKNOWN_INTENT``. This is the guard against the
        model inventing a plausible-sounding label, which is our most likely
        hallucination mode on this task.

    The four failure kinds are distinguished deliberately so E4 can report
    *why* outputs fail, not merely how often.
    """
    block = extract_json_block(raw)
    if block is None:
        return ValidationOutcome(
            ok=False,
            failure=FailureKind.NO_JSON_FOUND,
            errors=["no balanced JSON object found in completion"],
        )

    try:
        payload = json.loads(block)
    except json.JSONDecodeError as exc:
        return ValidationOutcome(
            ok=False,
            failure=FailureKind.MALFORMED_JSON,
            errors=[f"{exc.msg} at position {exc.pos}"],
            extracted_json=block,
        )

    try:
        response = AssistantResponse.model_validate(payload)
    except ValidationError as exc:
        return ValidationOutcome(
            ok=False,
            failure=FailureKind.SCHEMA_VIOLATION,
            errors=[
                f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
                for err in exc.errors()
            ],
            extracted_json=block,
        )

    if allowed_intents is not None and response.intent not in set(allowed_intents):
        return ValidationOutcome(
            ok=False,
            failure=FailureKind.UNKNOWN_INTENT,
            errors=[f"intent '{response.intent}' is not a BANKING77 label"],
            extracted_json=block,
        )

    return ValidationOutcome(ok=True, response=response, extracted_json=block)


# --------------------------------------------------------------------------
# Repair
# --------------------------------------------------------------------------

_REPAIR_TEMPLATE = """Your previous reply was rejected by a strict JSON validator.

Previous reply:
{raw}

Validator errors:
{errors}

Reply again with ONE JSON object and nothing else. No prose, no code fences.
Required shape:
{{"intent": "<one exact BANKING77 label>", "confidence": <float 0.0-1.0>,
  "response": "<customer-facing reply>", "tool_call": null,
  "requires_human": false}}"""


def build_repair_prompt(raw: str, outcome: ValidationOutcome) -> str:
    """
    Build a corrective prompt that shows the model its own invalid output.

    Feeding the validator's errors back is what lifts the structured-output
    validity rate; E4 reports the rate before and after this repair loop.
    """
    errors = "\n".join(f"- {err}" for err in outcome.errors) or "- unspecified"
    return _REPAIR_TEMPLATE.format(raw=raw.strip()[:800], errors=errors)
