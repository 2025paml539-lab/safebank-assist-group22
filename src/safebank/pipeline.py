"""
End-to-end orchestration (Experiment E7).

Implements the full workflow required by Section 5 of the brief:

    query -> prompt -> generator -> decode -> validate (+repair)
          -> intent -> tool routing -> tool result -> final response

Depends on the ``TextGenerator`` protocol, never on transformers directly, so
the entire control flow is testable offline.

Owner: Kishore (application lead)
"""

from __future__ import annotations

import time
import warnings
from dataclasses import dataclass, field

from . import config, prompts, tools
from .generator import DecodeConfig, TextGenerator
from .schema import (
    AssistantResponse,
    FailureKind,
    ValidationOutcome,
    build_repair_prompt,
    parse_response,
)
from .tools import ToolResult


@dataclass
class Attempt:
    """One generation attempt and how its output validated."""

    prompt: str
    raw: str
    outcome: ValidationOutcome
    is_repair: bool = False


@dataclass
class PipelineResult:
    """
    Full, auditable trace of one query through the system.

    Everything the report needs for E4, E5 and E7 is captured here rather than
    printed, so the notebook can tabulate runs instead of reading logs.
    """

    query: str
    attempts: list[Attempt] = field(default_factory=list)
    response: AssistantResponse | None = None
    tool_result: ToolResult | None = None
    final_text: str = ""
    escalated: bool = False
    escalation_reason: str | None = None
    latency_ms: float = 0.0

    @property
    def ok(self) -> bool:
        return self.response is not None

    @property
    def n_attempts(self) -> int:
        return len(self.attempts)

    @property
    def needed_repair(self) -> bool:
        return any(a.is_repair for a in self.attempts)

    @property
    def first_failure(self) -> FailureKind | None:
        for attempt in self.attempts:
            if not attempt.outcome.ok:
                return attempt.outcome.failure
        return None

    def to_row(self) -> dict:
        """
        Flatten into one record for the results DataFrame.

        ``response`` carries the model's own customer-facing reply, not the
        composed ``final_text``. Evaluation criterion 4 asks whether the model
        invented an account fact, so the screen must read what the *model*
        wrote. ``final_text`` additionally contains application-added content -
        the ``[system lookup: ...]`` trace and the mandatory disclaimer - which
        is provenance-controlled by us and would be a false positive if
        screened as a model-invented fact. Use ``PipelineResult.final_text``
        directly when you want the full composed envelope for an appendix
        sample.
        """
        return {
            "query": self.query,
            "ok": self.ok,
            "intent": self.response.intent if self.response else None,
            "confidence": self.response.confidence if self.response else None,
            "response": self.response.response if self.response else None,
            "attempts": self.n_attempts,
            "needed_repair": self.needed_repair,
            "first_failure": self.first_failure.value if self.first_failure else None,
            "tool": self.tool_result.tool.value if self.tool_result else None,
            "tool_ok": self.tool_result.ok if self.tool_result else None,
            "escalated": self.escalated,
            "latency_ms": round(self.latency_ms, 1),
        }


class SafeBankPipeline:
    """
    The SafeBank Assist application.

    Parameters
    ----------
    generator:
        Any ``TextGenerator``. A ``FakeGenerator`` offline, the real
        Qwen-backed one in the experiments.
    allowed_intents:
        The dataset's 77 intent names. Used to reject invented labels.
    strategy:
        Which prompt variant to use. The E2 comparison simply runs the same
        pipeline four times with different strategies.
    prompt_kwargs:
        Extra keyword arguments forwarded verbatim to
        ``prompts.build_prompt``. This is how a strategy's own parameters
        reach it - most importantly ``examples=`` for ``FEW_SHOT``, which
        must carry real BANKING77 *train*-split pairs from
        ``data_prep.build_example_bank()`` for any reported E2 number.

        Without this, ``build_few_shot_prompt`` receives ``examples=None``
        and quietly falls back to its small illustrative bank, so a
        "few-shot" row in the E2 table would not be few-shot on real data at
        all. A ``UserWarning`` is raised when ``FEW_SHOT`` is selected with
        no ``examples``, because that failure is otherwise invisible in the
        results.
    auto_execute_destructive:
        When False (the default) a state-changing tool such as ``block_card``
        is never executed automatically. The pipeline escalates and returns a
        confirmation request instead. This is a responsible-use control, not a
        limitation: an LLM's intent prediction must not be the sole authority
        for an irreversible account action.
    """

    def __init__(
        self,
        generator: TextGenerator,
        allowed_intents: list[str],
        strategy: prompts.PromptStrategy = prompts.PromptStrategy.ZERO_SHOT,
        *,
        prompt_kwargs: dict | None = None,
        auto_execute_destructive: bool = False,
        confidence_threshold: float = config.ESCALATION_CONFIDENCE_THRESHOLD,
        max_repair_attempts: int = config.REPAIR_MAX_ATTEMPTS,
    ) -> None:
        self.generator = generator
        self.allowed_intents = list(allowed_intents)
        self.strategy = strategy
        self.prompt_kwargs = dict(prompt_kwargs or {})
        self.auto_execute_destructive = auto_execute_destructive
        self.confidence_threshold = confidence_threshold
        self.max_repair_attempts = max_repair_attempts

        if (
            strategy is prompts.PromptStrategy.FEW_SHOT
            and not self.prompt_kwargs.get("examples")
        ):
            warnings.warn(
                "FEW_SHOT selected with no examples=; build_few_shot_prompt will "
                "fall back to its illustrative bank. Pass "
                "prompt_kwargs={'examples': data_prep.build_example_bank(...)} "
                "with real train-split pairs before reporting any E2 number.",
                UserWarning,
                stacklevel=2,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, query: str, decode: DecodeConfig | None = None) -> PipelineResult:
        """Process one customer query end to end."""
        decode = decode or DecodeConfig()
        result = PipelineResult(query=query)
        started = time.perf_counter()

        outcome = self._generate_and_validate(query, decode, result)

        if not outcome.ok:
            result.escalated = True
            result.escalation_reason = (
                f"could not obtain valid structured output after "
                f"{result.n_attempts} attempt(s): {outcome.summary()}"
            )
            result.final_text = self._escalation_text()
            result.latency_ms = (time.perf_counter() - started) * 1000
            return result

        assert outcome.response is not None
        result.response = outcome.response

        self._apply_confidence_gate(result)
        self._handle_tool(result)

        result.final_text = self._compose(result)
        result.latency_ms = (time.perf_counter() - started) * 1000
        return result

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _generate_and_validate(
        self, query: str, decode: DecodeConfig, result: PipelineResult
    ) -> ValidationOutcome:
        """Generate, validate, and retry with a repair prompt on failure."""
        prompt = prompts.build_prompt(
            self.strategy, query, self.allowed_intents, **self.prompt_kwargs
        )
        raw = self.generator.generate(prompt, decode)
        outcome = parse_response(raw, self.allowed_intents)
        result.attempts.append(Attempt(prompt=prompt, raw=raw, outcome=outcome))

        repairs = 0
        while not outcome.ok and repairs < self.max_repair_attempts:
            repairs += 1
            repair_prompt = build_repair_prompt(raw, outcome)
            raw = self.generator.generate(repair_prompt, decode)
            outcome = parse_response(raw, self.allowed_intents)
            result.attempts.append(
                Attempt(
                    prompt=repair_prompt, raw=raw, outcome=outcome, is_repair=True
                )
            )

        return outcome

    def _apply_confidence_gate(self, result: PipelineResult) -> None:
        """Escalate low-confidence predictions rather than acting on them."""
        response = result.response
        assert response is not None

        if response.requires_human:
            result.escalated = True
            result.escalation_reason = "model requested human handling"
            return

        if response.confidence < self.confidence_threshold:
            result.escalated = True
            result.escalation_reason = (
                f"confidence {response.confidence:.2f} below threshold "
                f"{self.confidence_threshold:.2f}"
            )

    def _handle_tool(self, result: PipelineResult) -> None:
        """
        Decide on and execute a tool.

        Routing is driven by the validated intent, not by the model's own
        ``tool_call`` field. The model may request a tool, but the intent-to-tool
        map is the authority, which stops a hallucinated tool request from
        reaching an executor.
        """
        response = result.response
        assert response is not None

        expected = tools.route_intent(response.intent)
        if expected is None:
            return

        spec = tools.TOOL_REGISTRY[expected]

        if spec.destructive and not self.auto_execute_destructive:
            result.escalated = True
            result.escalation_reason = (
                f"'{expected.value}' changes account state and requires "
                "explicit customer confirmation before execution"
            )
            return

        if result.escalated:
            # Do not act on a request we have already flagged for a human.
            return

        args = dict(response.tool_call.args) if response.tool_call else {}
        args = self._fill_missing_args(expected, args)
        result.tool_result = tools.execute_tool(expected, args)

    @staticmethod
    def _fill_missing_args(tool: tools.ToolName, args: dict) -> dict:
        """
        Supply synthetic placeholders for arguments the model omitted.

        A real deployment would read these from the authenticated session. In
        this simulation they are clearly synthetic, which keeps us compliant
        with the brief's prohibition on real financial data while still
        letting E5 demonstrate a complete invocation.
        """
        filled = dict(args)
        if tool is tools.ToolName.CHECK_CARD_DELIVERY_STATUS:
            filled.setdefault("card_id", "CARD_SIM_0001")
        elif tool is tools.ToolName.BLOCK_CARD:
            filled.setdefault("account_id", "ACC_SIM_0001")
            filled.setdefault("reason", "lost")
        elif tool is tools.ToolName.FIND_BRANCH:
            filled.setdefault("pincode", "560001")
            filled.setdefault("service", "atm")
        return filled

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def _compose(self, result: PipelineResult) -> str:
        """Build the customer-facing text, including provenance and escalation."""
        response = result.response
        assert response is not None

        parts = [response.response.strip()]

        if result.tool_result and result.tool_result.ok:
            parts.append(f"[system lookup: {result.tool_result.output}]")
        elif result.tool_result and not result.tool_result.ok:
            parts.append(
                "[system lookup unavailable; a colleague will confirm the details]"
            )

        if result.escalated:
            parts.append(f"[escalated to a human agent: {result.escalation_reason}]")

        parts.append(response.disclaimer)
        return "\n".join(parts)

    @staticmethod
    def _escalation_text() -> str:
        return (
            "I could not process that request reliably, so I am passing it to a "
            "human colleague who will follow up.\n" + config.SAFETY_DISCLAIMER
        )
