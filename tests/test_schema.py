"""
Experiment E4 - structured output and validation.

Evidence for rubric component 5 and Requirement 9. Each failure mode in
``schema.FailureKind`` gets an explicit test, because E4 reports *why* model
outputs fail rather than only how often, and that table is only trustworthy if
the classifier behind it is itself tested.

Owner: Kishore
"""

from __future__ import annotations

import json
import unittest

from safebank import config
from safebank.schema import (
    AssistantResponse,
    FailureKind,
    ToolCall,
    ToolName,
    build_repair_prompt,
    extract_json_block,
    parse_response,
    response_json_schema,
)

ALLOWED = ["card_arrival", "lost_or_stolen_card", "atm_support"]


def valid_payload(**overrides: object) -> dict:
    """A minimal schema-valid response payload."""
    payload: dict = {
        "intent": "card_arrival",
        "confidence": 0.82,
        "response": "Your card is on its way.",
        "tool_call": None,
        "requires_human": False,
    }
    payload.update(overrides)
    return payload


def valid_json(**overrides: object) -> str:
    return json.dumps(valid_payload(**overrides))


class TestExtractJsonBlock(unittest.TestCase):
    """The brace scanner that pulls JSON out of chatty model output."""

    def test_bare_object(self):
        self.assertEqual(extract_json_block('{"a": 1}'), '{"a": 1}')

    def test_strips_leading_prose(self):
        raw = 'Sure! Here is the result:\n{"a": 1}'
        self.assertEqual(extract_json_block(raw), '{"a": 1}')

    def test_strips_trailing_prose(self):
        raw = '{"a": 1}\nHope that helps!'
        self.assertEqual(extract_json_block(raw), '{"a": 1}')

    def test_handles_code_fence(self):
        raw = '```json\n{"a": 1}\n```'
        self.assertEqual(extract_json_block(raw), '{"a": 1}')

    def test_nested_objects_are_balanced(self):
        raw = 'x {"a": {"b": 2}} y'
        self.assertEqual(extract_json_block(raw), '{"a": {"b": 2}}')

    def test_brace_inside_string_does_not_terminate_scan(self):
        """A closing brace inside a string literal must not end the object."""
        raw = '{"response": "use the } key"}'
        self.assertEqual(extract_json_block(raw), raw)

    def test_escaped_quote_inside_string(self):
        raw = '{"response": "say \\"hi\\" now"}'
        self.assertEqual(extract_json_block(raw), raw)

    def test_returns_none_when_no_brace(self):
        self.assertIsNone(extract_json_block("no json at all"))

    def test_returns_none_when_unbalanced(self):
        self.assertIsNone(extract_json_block('{"a": 1'))

    def test_first_object_wins(self):
        raw = '{"a": 1} {"b": 2}'
        self.assertEqual(extract_json_block(raw), '{"a": 1}')


class TestAssistantResponseModel(unittest.TestCase):
    """The pydantic contract itself."""

    def test_valid_payload_accepted(self):
        response = AssistantResponse.model_validate(valid_payload())
        self.assertEqual(response.intent, "card_arrival")
        self.assertAlmostEqual(response.confidence, 0.82)

    def test_disclaimer_defaults_from_config(self):
        """The disclaimer is application-enforced, not model-supplied."""
        response = AssistantResponse.model_validate(valid_payload())
        self.assertEqual(response.disclaimer, config.SAFETY_DISCLAIMER)

    def test_requires_human_defaults_false(self):
        payload = valid_payload()
        del payload["requires_human"]
        self.assertFalse(AssistantResponse.model_validate(payload).requires_human)

    def test_tool_call_parsed_into_model(self):
        payload = valid_payload(
            tool_call={
                "name": "check_card_delivery_status",
                "args": {"card_id": "CARD_0417"},
            }
        )
        response = AssistantResponse.model_validate(payload)
        self.assertIsInstance(response.tool_call, ToolCall)
        self.assertIs(response.tool_call.name, ToolName.CHECK_CARD_DELIVERY_STATUS)

    def test_json_schema_exposes_all_fields(self):
        schema = response_json_schema()
        self.assertIsInstance(schema, dict)
        for field in (
            "intent",
            "confidence",
            "response",
            "tool_call",
            "requires_human",
            "disclaimer",
        ):
            self.assertIn(field, schema["properties"], field)


class TestParseResponseSuccess(unittest.TestCase):
    def test_clean_json_validates(self):
        outcome = parse_response(valid_json(), ALLOWED)
        self.assertTrue(outcome.ok)
        self.assertIsNotNone(outcome.response)
        self.assertIsNone(outcome.failure)

    def test_json_wrapped_in_prose_validates(self):
        raw = f"Certainly, here you go:\n```json\n{valid_json()}\n```\nThanks!"
        self.assertTrue(parse_response(raw, ALLOWED).ok)

    def test_extracted_json_is_recorded(self):
        outcome = parse_response(f"noise {valid_json()}", ALLOWED)
        self.assertIsNotNone(outcome.extracted_json)
        self.assertTrue(outcome.extracted_json.startswith("{"))

    def test_summary_reports_intent_and_confidence(self):
        summary = parse_response(valid_json(), ALLOWED).summary()
        self.assertIn("card_arrival", summary)
        self.assertIn("0.82", summary)

    def test_intent_check_skipped_when_allowed_is_none(self):
        """allowed_intents=None disables the guard; used before the data loads."""
        outcome = parse_response(valid_json(intent="anything_at_all"), None)
        self.assertTrue(outcome.ok)


class TestParseResponseFailureKinds(unittest.TestCase):
    """One test per FailureKind member. These are the E4 table rows."""

    def test_no_json_found(self):
        outcome = parse_response("I think the card is lost.", ALLOWED)
        self.assertFalse(outcome.ok)
        self.assertIs(outcome.failure, FailureKind.NO_JSON_FOUND)
        self.assertTrue(outcome.errors)

    def test_malformed_json(self):
        outcome = parse_response('{"intent": "card_arrival",}', ALLOWED)
        self.assertFalse(outcome.ok)
        self.assertIs(outcome.failure, FailureKind.MALFORMED_JSON)

    def test_schema_violation_on_missing_required_field(self):
        outcome = parse_response('{"intent": "card_arrival"}', ALLOWED)
        self.assertFalse(outcome.ok)
        self.assertIs(outcome.failure, FailureKind.SCHEMA_VIOLATION)

    def test_schema_violation_on_confidence_out_of_range(self):
        outcome = parse_response(valid_json(confidence=1.5), ALLOWED)
        self.assertIs(outcome.failure, FailureKind.SCHEMA_VIOLATION)

    def test_schema_violation_on_empty_response_text(self):
        outcome = parse_response(valid_json(response=""), ALLOWED)
        self.assertIs(outcome.failure, FailureKind.SCHEMA_VIOLATION)

    def test_schema_violation_on_invented_field(self):
        """extra='forbid' turns a hallucinated field into a countable failure."""
        outcome = parse_response(valid_json(account_balance="4210.00"), ALLOWED)
        self.assertIs(outcome.failure, FailureKind.SCHEMA_VIOLATION)

    def test_schema_violation_on_hallucinated_tool_name(self):
        """A tool outside the enum is caught here, never reaching the router."""
        outcome = parse_response(
            valid_json(tool_call={"name": "wire_transfer_funds", "args": {}}),
            ALLOWED,
        )
        self.assertIs(outcome.failure, FailureKind.SCHEMA_VIOLATION)

    def test_unknown_intent(self):
        outcome = parse_response(valid_json(intent="refund_my_mortgage"), ALLOWED)
        self.assertFalse(outcome.ok)
        self.assertIs(outcome.failure, FailureKind.UNKNOWN_INTENT)
        self.assertIn("refund_my_mortgage", outcome.errors[0])

    def test_failure_summary_names_the_kind(self):
        summary = parse_response("nothing here", ALLOWED).summary()
        self.assertIn("no_json_found", summary)

    def test_all_failure_kinds_are_reachable(self):
        """Guard against adding a FailureKind with no test and no producer."""
        produced = {
            parse_response("prose only", ALLOWED).failure,
            parse_response('{"a":,}', ALLOWED).failure,
            parse_response('{"intent": "x"}', ALLOWED).failure,
            parse_response(valid_json(intent="not_real"), ALLOWED).failure,
        }
        self.assertSetEqual(produced, set(FailureKind))


class TestRepairPrompt(unittest.TestCase):
    """The repair-retry loop's corrective prompt (E4 validity-rate lift)."""

    def test_includes_validator_errors(self):
        outcome = parse_response('{"intent": "card_arrival"}', ALLOWED)
        prompt = build_repair_prompt('{"intent": "card_arrival"}', outcome)
        self.assertIn("rejected", prompt.lower())
        for err in outcome.errors:
            self.assertIn(err, prompt)

    def test_includes_the_offending_output(self):
        raw = "here is some broken output {"
        prompt = build_repair_prompt(raw, parse_response(raw, ALLOWED))
        self.assertIn("broken output", prompt)

    def test_truncates_very_long_output(self):
        """Keeps the repair prompt inside the context budget."""
        raw = "x" * 5000
        self.assertLess(len(build_repair_prompt(raw, parse_response(raw, ALLOWED))), 2000)

    def test_handles_outcome_with_no_errors(self):
        outcome = parse_response(valid_json(), ALLOWED)
        self.assertIn("unspecified", build_repair_prompt("{}", outcome))

    def test_demands_a_single_json_object(self):
        outcome = parse_response("nope", ALLOWED)
        prompt = build_repair_prompt("nope", outcome).lower()
        self.assertIn("one json object", prompt)


if __name__ == "__main__":
    unittest.main()
