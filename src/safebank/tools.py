"""
Simulated tool / function layer (Requirement 10, Experiment E5).

Three tools, each with a declared input schema, output schema and a
deterministic simulated implementation. No network calls, no real banking data
and no credentials, per Section 8 of the assignment brief.

Determinism matters: results are derived from a hash of the input, so the same
argument always yields the same result. That keeps the notebook reproducible
for the grader.

Owner: Kishore (structured output + tool calling)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .schema import ToolName

# --------------------------------------------------------------------------
# Deterministic pseudo-randomness
# --------------------------------------------------------------------------

#: Fixed reference date so simulated dates never drift between runs.
_REFERENCE_DATE = date(2026, 10, 15)


def _stable_int(key: str, modulo: int) -> int:
    """Map a string to a stable integer in [0, modulo)."""
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


# --------------------------------------------------------------------------
# Tool 1: check_card_delivery_status
# --------------------------------------------------------------------------


class CardDeliveryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    card_id: str = Field(min_length=3, description="Synthetic card reference.")


class CardDeliveryOutput(BaseModel):
    status: str
    dispatched_on: str
    eta_days: int


_DELIVERY_STATES = ("in_transit", "dispatched", "out_for_delivery", "delayed")


def check_card_delivery_status(payload: CardDeliveryInput) -> CardDeliveryOutput:
    """Look up the delivery status of a replacement or new card."""
    bucket = _stable_int(payload.card_id, len(_DELIVERY_STATES))
    offset = _stable_int(payload.card_id + "days", 9)
    return CardDeliveryOutput(
        status=_DELIVERY_STATES[bucket],
        dispatched_on=(_REFERENCE_DATE - timedelta(days=offset + 1)).isoformat(),
        eta_days=max(1, 7 - offset),
    )


# --------------------------------------------------------------------------
# Tool 2: block_card  (destructive)
# --------------------------------------------------------------------------


class BlockReason(str, Enum):
    LOST = "lost"
    STOLEN = "stolen"
    COMPROMISED = "compromised"
    DAMAGED = "damaged"


class BlockCardInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: str = Field(min_length=3, description="Synthetic account reference.")
    reason: BlockReason = Field(description="Why the card is being blocked.")


class BlockCardOutput(BaseModel):
    blocked: bool
    ref_id: str
    replacement_eta_days: int


def block_card(payload: BlockCardInput) -> BlockCardOutput:
    """Block a card and raise a replacement. State-changing: see ``destructive``."""
    ref = _stable_int(payload.account_id + payload.reason.value, 900_000) + 100_000
    return BlockCardOutput(
        blocked=True,
        ref_id=f"BLK-{ref}",
        replacement_eta_days=5 + _stable_int(payload.account_id, 4),
    )


# --------------------------------------------------------------------------
# Tool 3: find_branch
# --------------------------------------------------------------------------


class BranchService(str, Enum):
    CASH_DEPOSIT = "cash_deposit"
    ATM = "atm"
    CARD_COLLECTION = "card_collection"
    IDENTITY_VERIFICATION = "identity_verification"


class FindBranchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pincode: str = Field(min_length=4, max_length=10, description="Area pincode.")
    service: BranchService = Field(description="Service the customer needs.")


class FindBranchOutput(BaseModel):
    branch_name: str
    address: str
    distance_km: float


_BRANCH_NAMES = ("Central", "Riverside", "Market Street", "Northgate", "Lakeview")


def find_branch(payload: FindBranchInput) -> FindBranchOutput:
    """Find the nearest branch or ATM offering a given service."""
    index = _stable_int(payload.pincode, len(_BRANCH_NAMES))
    distance = 0.4 + _stable_int(payload.pincode + payload.service.value, 70) / 10.0
    return FindBranchOutput(
        branch_name=f"{_BRANCH_NAMES[index]} Branch",
        address=f"{100 + index * 7} High Road, {payload.pincode}",
        distance_km=round(distance, 1),
    )


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolSpec:
    """Everything the pipeline and the report need to know about one tool."""

    name: ToolName
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Callable[[BaseModel], BaseModel]
    #: State-changing tools are never auto-executed; see ``pipeline``.
    destructive: bool = False

    def input_schema(self) -> dict:
        return self.input_model.model_json_schema()

    def output_schema(self) -> dict:
        return self.output_model.model_json_schema()


TOOL_REGISTRY: dict[ToolName, ToolSpec] = {
    ToolName.CHECK_CARD_DELIVERY_STATUS: ToolSpec(
        name=ToolName.CHECK_CARD_DELIVERY_STATUS,
        description="Return the courier status and ETA for a card in transit.",
        input_model=CardDeliveryInput,
        output_model=CardDeliveryOutput,
        handler=check_card_delivery_status,  # type: ignore[arg-type]
    ),
    ToolName.BLOCK_CARD: ToolSpec(
        name=ToolName.BLOCK_CARD,
        description="Block a card and raise a replacement. Changes account state.",
        input_model=BlockCardInput,
        output_model=BlockCardOutput,
        handler=block_card,  # type: ignore[arg-type]
        destructive=True,
    ),
    ToolName.FIND_BRANCH: ToolSpec(
        name=ToolName.FIND_BRANCH,
        description="Find the nearest branch or ATM offering a given service.",
        input_model=FindBranchInput,
        output_model=FindBranchOutput,
        handler=find_branch,  # type: ignore[arg-type]
    ),
}


# --------------------------------------------------------------------------
# Intent -> tool routing
# --------------------------------------------------------------------------

#: Which BANKING77 intents justify which tool. Intents absent from this map
#: are answered with text only - most of the 77 need no system lookup, and
#: inventing one would be a reliability risk rather than a feature.
INTENT_TO_TOOL: dict[str, ToolName] = {
    "card_arrival": ToolName.CHECK_CARD_DELIVERY_STATUS,
    "card_delivery_estimate": ToolName.CHECK_CARD_DELIVERY_STATUS,
    "order_physical_card": ToolName.CHECK_CARD_DELIVERY_STATUS,
    "getting_spare_card": ToolName.CHECK_CARD_DELIVERY_STATUS,
    "lost_or_stolen_card": ToolName.BLOCK_CARD,
    "compromised_card": ToolName.BLOCK_CARD,
    "card_swallowed": ToolName.BLOCK_CARD,
    "atm_support": ToolName.FIND_BRANCH,
    "cash_withdrawal_charge": ToolName.FIND_BRANCH,
    "declined_cash_withdrawal": ToolName.FIND_BRANCH,
}


def route_intent(intent: str) -> ToolName | None:
    """Return the tool an intent should trigger, or None for text-only."""
    return INTENT_TO_TOOL.get(intent)


# --------------------------------------------------------------------------
# Execution
# --------------------------------------------------------------------------


class ToolExecutionError(RuntimeError):
    """Raised when a tool cannot be executed as requested."""


@dataclass
class ToolResult:
    """Outcome of one tool invocation, including the failure case."""

    ok: bool
    tool: ToolName
    output: dict | None = None
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "tool": self.tool.value,
            "output": self.output,
            "error": self.error,
        }


def execute_tool(name: ToolName | str, args: dict) -> ToolResult:
    """
    Validate arguments against the tool's input schema, then execute.

    Argument validation is separate from response validation on purpose: the
    model can emit a schema-valid response that still carries nonsense tool
    arguments, and E5 reports those two failure sources independently.
    """
    try:
        tool_name = ToolName(name)
    except ValueError:
        return ToolResult(
            ok=False,
            tool=ToolName.CHECK_CARD_DELIVERY_STATUS,
            error=f"unknown tool '{name}'",
        )

    spec = TOOL_REGISTRY[tool_name]

    try:
        payload = spec.input_model.model_validate(args)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        )
        return ToolResult(ok=False, tool=tool_name, error=f"invalid args: {details}")

    try:
        result = spec.handler(payload)
    except Exception as exc:  # defensive: a tool must never crash the pipeline
        return ToolResult(ok=False, tool=tool_name, error=f"handler failed: {exc}")

    return ToolResult(ok=True, tool=tool_name, output=result.model_dump())


def tool_specs_json(indent: int = 2) -> str:
    """
    Export all three tool contracts as JSON.

    Dropped straight into the report appendix as the tool/function-calling
    specification required by deliverable 7.
    """
    payload = {
        spec.name.value: {
            "description": spec.description,
            "destructive": spec.destructive,
            "input_schema": spec.input_schema(),
            "output_schema": spec.output_schema(),
            "triggered_by": sorted(
                intent for intent, tool in INTENT_TO_TOOL.items() if tool == spec.name
            ),
        }
        for spec in TOOL_REGISTRY.values()
    }
    return json.dumps(payload, indent=indent)
