"""
Experiment E7 - integrated end-to-end workflow.

Evidence for rubric components 5 and 6, and for Requirement 13 (responsible
use). These are the most important tests in the suite: they exercise the
control flow a grader will ask about in the demo, including the paths that are
supposed to *refuse* to act.

Everything runs offline. ``FakeGenerator`` scripts the completions, so the
repair-retry loop, the confidence gate and the destructive-tool refusal are all
testable with no torch, no GPU and no network.

Owner: Kishore
"""

from __future__ import annotations

import json
import unittest

from safebank import config
from safebank.generator import DecodeConfig, DecodeStrategy, FakeGenerator
from safebank.pipeline import SafeBankPipeline
from safebank.prompts import PromptStrategy
from safebank.schema import FailureKind
from safebank.tools import ToolName, execute_tool

ALLOWED = [
    "card_arrival",
    "card_delivery_estimate",
    "lost_or_stolen_card",
    "compromised_card",
    "atm_support",
    "transfer_timing",
    "top_up_failed",
]


def response_json(**overrides: object) -> str:
    """Build a schema-valid completion for the fake generator to return."""
    payload: dict = {
        "intent": "card_arrival",
        "confidence": 0.85,
        "response": "Your card is on its way.",
        "tool_call": None,
        "requires_human": False,
    }
    payload.update(overrides)
    return json.dumps(payload)


def build(scripted=None, **kwargs) -> SafeBankPipeline:
    return SafeBankPipeline(FakeGenerator(scripted), list(ALLOWED), **kwargs)


class TestHappyPath(unittest.TestCase):
    def setUp(self):
        self.pipe = build([response_json()])
        self.result = self.pipe.run("My card has not arrived")

    def test_succeeds(self):
        self.assertTrue(self.result.ok)
        self.assertIsNotNone(self.result.response)

    def test_predicts_the_intent(self):
        self.assertEqual(self.result.response.intent, "card_arrival")

    def test_single_attempt_no_repair(self):
        self.assertEqual(self.result.n_attempts, 1)
        self.assertFalse(self.result.needed_repair)

    def test_not_escalated(self):
        self.assertFalse(self.result.escalated)
        self.assertIsNone(self.result.escalation_reason)

    def test_disclaimer_always_present(self):
        """Responsible-use control: provenance on every customer-facing reply."""
        self.assertIn(config.SAFETY_DISCLAIMER, self.result.final_text)

    def test_latency_recorded(self):
        self.assertGreater(self.result.latency_ms, 0)

    def test_prompt_was_actually_built_and_sent(self):
        self.assertIn("card_arrival", self.result.attempts[0].prompt)
        self.assertIn("My card has not arrived", self.result.attempts[0].prompt)

    def test_row_response_is_the_model_reply_not_the_envelope(self):
        """
        Criterion 4 screens what the *model* wrote.

        ``final_text`` also carries the system-lookup trace and the mandatory
        disclaimer, which the application adds. Screening those as
        model-invented account facts would be a false positive, so ``to_row()``
        exposes the model's own reply instead.
        """
        row = self.result.to_row()
        self.assertEqual(row["response"], self.result.response.response)
        self.assertNotIn(config.SAFETY_DISCLAIMER, row["response"])
        self.assertNotIn("system lookup", row["response"])
        self.assertIn(config.SAFETY_DISCLAIMER, self.result.final_text)

    def test_row_response_is_none_when_run_failed(self):
        result = build(["bad", "worse", "worst"]).run("q")
        self.assertFalse(result.ok)
        self.assertIsNone(result.to_row()["response"])

    def test_row_export_shape(self):
        row = self.result.to_row()
        for key in (
            "query",
            "ok",
            "intent",
            "confidence",
            "response",
            "attempts",
            "needed_repair",
            "first_failure",
            "tool",
            "tool_ok",
            "escalated",
            "latency_ms",
        ):
            self.assertIn(key, row)


class TestRepairRetry(unittest.TestCase):
    """E4's validity-rate lift, measured through the pipeline."""

    def test_malformed_then_valid_recovers(self):
        result = build(["I think it is lost.", response_json()]).run("where is my card")
        self.assertTrue(result.ok)
        self.assertEqual(result.n_attempts, 2)
        self.assertTrue(result.needed_repair)

    def test_first_failure_is_recorded_even_after_recovery(self):
        """The failure still counts in E4 even though the pipeline recovered."""
        result = build(["no json here", response_json()]).run("where is my card")
        self.assertIs(result.first_failure, FailureKind.NO_JSON_FOUND)

    def test_second_attempt_uses_a_repair_prompt(self):
        result = build(["garbage", response_json()]).run("where is my card")
        self.assertFalse(result.attempts[0].is_repair)
        self.assertTrue(result.attempts[1].is_repair)
        self.assertIn("rejected", result.attempts[1].prompt.lower())

    def test_exhausted_repairs_escalate(self):
        result = build(["bad one", "bad two", "bad three"]).run("where is my card")
        self.assertFalse(result.ok)
        self.assertTrue(result.escalated)
        self.assertIn("could not obtain valid structured output", result.escalation_reason)

    def test_attempt_count_respects_max_repair_attempts(self):
        result = build(["b1", "b2", "b3"]).run("q")
        self.assertEqual(result.n_attempts, 1 + config.REPAIR_MAX_ATTEMPTS)

    def test_repair_limit_is_configurable(self):
        pipe = build(["b1", "b2", "b3", "b4"], max_repair_attempts=3)
        self.assertEqual(pipe.run("q").n_attempts, 4)

    def test_failed_run_still_carries_a_safe_reply(self):
        result = build(["b1", "b2", "b3"]).run("q")
        self.assertIn(config.SAFETY_DISCLAIMER, result.final_text)
        self.assertIn("human colleague", result.final_text)


class TestConfidenceGate(unittest.TestCase):
    """Low-confidence predictions must not drive action."""

    def test_low_confidence_escalates(self):
        result = build([response_json(confidence=0.20)]).run("q")
        self.assertTrue(result.escalated)
        self.assertIn("below threshold", result.escalation_reason)

    def test_low_confidence_suppresses_tool_execution(self):
        result = build([response_json(confidence=0.10)]).run("q")
        self.assertIsNone(result.tool_result)

    def test_high_confidence_does_not_escalate(self):
        self.assertFalse(build([response_json(confidence=0.95)]).run("q").escalated)

    def test_threshold_is_configurable(self):
        pipe = build([response_json(confidence=0.60)], confidence_threshold=0.90)
        self.assertTrue(pipe.run("q").escalated)

    def test_model_requested_escalation_is_honoured(self):
        result = build([response_json(requires_human=True)]).run("q")
        self.assertTrue(result.escalated)
        self.assertIn("model requested", result.escalation_reason)

    def test_escalation_is_visible_to_the_customer(self):
        result = build([response_json(confidence=0.10)]).run("q")
        self.assertIn("escalated", result.final_text)


class TestToolRouting(unittest.TestCase):
    def test_routes_on_intent_and_executes(self):
        result = build([response_json(intent="card_arrival")]).run("q")
        self.assertIsNotNone(result.tool_result)
        self.assertIs(result.tool_result.tool, ToolName.CHECK_CARD_DELIVERY_STATUS)
        self.assertTrue(result.tool_result.ok)

    def test_no_tool_for_text_only_intent(self):
        result = build([response_json(intent="transfer_timing")]).run("q")
        self.assertIsNone(result.tool_result)

    def test_tool_output_surfaced_in_final_text(self):
        result = build([response_json(intent="card_arrival")]).run("q")
        self.assertIn("system lookup", result.final_text)

    def test_missing_arguments_are_filled_with_synthetic_values(self):
        """No real account data: placeholders keep E5 demonstrable and compliant."""
        result = build([response_json(intent="card_arrival", tool_call=None)]).run("q")
        self.assertTrue(result.tool_result.ok)

    def test_model_supplied_arguments_are_used(self):
        result = build(
            [
                response_json(
                    intent="card_arrival",
                    tool_call={
                        "name": "check_card_delivery_status",
                        "args": {"card_id": "CARD_9999"},
                    },
                )
            ]
        ).run("q")
        direct = execute_tool(
            ToolName.CHECK_CARD_DELIVERY_STATUS, {"card_id": "CARD_9999"}
        )
        self.assertTrue(result.tool_result.ok)
        self.assertEqual(result.tool_result.output, direct.output)

    def test_intent_overrides_a_mismatched_tool_request(self):
        """
        Routing authority sits with the validated intent, not the model.

        The model asks for find_branch while predicting card_arrival. The
        pipeline must execute the card tool, which is what stops a
        hallucinated tool request from reaching an executor.
        """
        result = build(
            [
                response_json(
                    intent="card_arrival",
                    tool_call={"name": "find_branch", "args": {"pincode": "560001"}},
                )
            ]
        ).run("q")
        self.assertIs(result.tool_result.tool, ToolName.CHECK_CARD_DELIVERY_STATUS)


class TestDestructiveToolRefusal(unittest.TestCase):
    """Requirement 13. An LLM prediction must not trigger an irreversible act."""

    def test_block_card_not_executed_by_default(self):
        result = build([response_json(intent="lost_or_stolen_card")]).run("q")
        self.assertIsNone(result.tool_result)

    def test_block_card_escalates_with_a_reason(self):
        result = build([response_json(intent="lost_or_stolen_card")]).run("q")
        self.assertTrue(result.escalated)
        self.assertIn("changes account state", result.escalation_reason)

    def test_refusal_holds_even_at_maximum_confidence(self):
        result = build([response_json(intent="compromised_card", confidence=1.0)]).run("q")
        self.assertIsNone(result.tool_result)
        self.assertTrue(result.escalated)

    def test_executes_only_with_explicit_opt_in(self):
        pipe = build(
            [response_json(intent="lost_or_stolen_card")],
            auto_execute_destructive=True,
        )
        result = pipe.run("q")
        self.assertIsNotNone(result.tool_result)
        self.assertIs(result.tool_result.tool, ToolName.BLOCK_CARD)
        self.assertTrue(result.tool_result.output["blocked"])

    def test_default_is_refusal(self):
        self.assertFalse(build().auto_execute_destructive)


class TestHallucinationGuards(unittest.TestCase):
    def test_invented_intent_is_rejected(self):
        result = build(
            [response_json(intent="refund_my_mortgage"), response_json(intent="still_fake"), response_json(intent="nope")]
        ).run("q")
        self.assertFalse(result.ok)
        self.assertIs(result.first_failure, FailureKind.UNKNOWN_INTENT)

    def test_invented_field_is_rejected(self):
        bad = json.dumps(
            {
                "intent": "card_arrival",
                "confidence": 0.9,
                "response": "Your balance is 4210.00",
                "account_balance": "4210.00",
                "requires_human": False,
            }
        )
        result = build([bad, response_json()]).run("q")
        self.assertIs(result.first_failure, FailureKind.SCHEMA_VIOLATION)


class TestPromptKwargsPassthrough(unittest.TestCase):
    """
    Strategy parameters must reach the prompt builder.

    Found during the PR #2 review: the pipeline called ``build_prompt`` with
    no keyword arguments, so ``examples=`` could never reach
    ``build_few_shot_prompt`` and every few-shot run silently used the small
    illustrative fallback bank. The E2 few-shot column would not have been
    few-shot on real data at all, and nothing in the output would have said so.
    """

    EXAMPLES = [
        ("my card has not turned up", '{"intent": "card_arrival"}'),
        ("where is the nearest atm", '{"intent": "atm_support"}'),
    ]

    def test_examples_reach_the_few_shot_builder(self):
        pipe = SafeBankPipeline(
            FakeGenerator([response_json()]),
            list(ALLOWED),
            strategy=PromptStrategy.FEW_SHOT,
            prompt_kwargs={"examples": self.EXAMPLES},
        )
        prompt = pipe.run("q").attempts[0].prompt
        for example_query, _ in self.EXAMPLES:
            self.assertIn(example_query, prompt)

    def test_zero_shot_unaffected_by_empty_kwargs(self):
        pipe = build([response_json()])
        self.assertEqual(pipe.prompt_kwargs, {})
        self.assertTrue(pipe.run("q").ok)

    def test_few_shot_without_examples_warns(self):
        """The silent fallback must become visible."""
        with self.assertWarns(UserWarning) as ctx:
            SafeBankPipeline(
                FakeGenerator([response_json()]),
                list(ALLOWED),
                strategy=PromptStrategy.FEW_SHOT,
            )
        self.assertIn("examples", str(ctx.warning))

    def test_few_shot_with_examples_does_not_warn(self):
        import warnings as _w

        with _w.catch_warnings():
            _w.simplefilter("error")  # any warning becomes a test failure
            SafeBankPipeline(
                FakeGenerator([response_json()]),
                list(ALLOWED),
                strategy=PromptStrategy.FEW_SHOT,
                prompt_kwargs={"examples": self.EXAMPLES},
            )

    def test_unknown_prompt_kwarg_surfaces_as_type_error(self):
        pipe = SafeBankPipeline(
            FakeGenerator([response_json()]),
            list(ALLOWED),
            prompt_kwargs={"not_a_real_kwarg": 1},
        )
        with self.assertRaises(TypeError):
            pipe.run("q")


class TestDecodeConfigPlumbing(unittest.TestCase):
    """E3 must be able to vary decoding without touching the pipeline."""

    def test_default_decode_config_is_used(self):
        pipe = build([response_json()])
        pipe.run("q")
        self.assertIs(pipe.generator.calls[0][1].strategy, DecodeStrategy.GREEDY)

    def test_supplied_decode_config_reaches_the_generator(self):
        pipe = build([response_json()])
        decode = DecodeConfig(strategy=DecodeStrategy.TOP_P, temperature=0.7, top_p=0.9)
        pipe.run("q", decode)
        self.assertIs(pipe.generator.calls[0][1], decode)

    def test_strategy_selection_is_honoured(self):
        pipe = build([response_json()], strategy=PromptStrategy.ZERO_SHOT)
        self.assertIs(pipe.strategy, PromptStrategy.ZERO_SHOT)


if __name__ == "__main__":
    unittest.main()
