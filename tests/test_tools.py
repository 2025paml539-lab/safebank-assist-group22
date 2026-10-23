"""
Experiment E5 - simulated tools, I/O schemas and routing.

Evidence for rubric component 5 and Requirement 10. Two things matter here and
are tested separately, because E5 reports them as distinct failure sources:
argument validation (does the tool reject nonsense input) and routing (does the
right intent reach the right tool).

Determinism is tested explicitly. The brief requires a reproducible notebook,
and these tools derive their results from a hash of the input rather than from
a random source precisely so a grader re-running the notebook sees identical
output.

Owner: Kishore
"""

from __future__ import annotations

import json
import unittest

from safebank.tools import (
    INTENT_TO_TOOL,
    TOOL_REGISTRY,
    BlockCardInput,
    BlockReason,
    BranchService,
    CardDeliveryInput,
    FindBranchInput,
    ToolName,
    execute_tool,
    route_intent,
    tool_specs_json,
)


class TestRegistryIntegrity(unittest.TestCase):
    """The registry is what the prompt, the router and the report all read."""

    def test_every_tool_name_has_a_spec(self):
        self.assertSetEqual(set(TOOL_REGISTRY), set(ToolName))

    def test_three_tools_as_documented(self):
        self.assertEqual(len(TOOL_REGISTRY), 3)

    def test_spec_key_matches_spec_name(self):
        for key, spec in TOOL_REGISTRY.items():
            self.assertIs(key, spec.name)

    def test_every_spec_has_a_description(self):
        for spec in TOOL_REGISTRY.values():
            self.assertTrue(spec.description.strip(), spec.name)

    def test_only_block_card_is_destructive(self):
        """Mislabelling this would let the pipeline auto-execute a card block."""
        destructive = {s.name for s in TOOL_REGISTRY.values() if s.destructive}
        self.assertSetEqual(destructive, {ToolName.BLOCK_CARD})

    def test_input_and_output_schemas_are_exportable(self):
        for spec in TOOL_REGISTRY.values():
            self.assertIn("properties", spec.input_schema())
            self.assertIn("properties", spec.output_schema())


class TestCardDeliveryTool(unittest.TestCase):
    def test_valid_call_succeeds(self):
        result = execute_tool(ToolName.CHECK_CARD_DELIVERY_STATUS, {"card_id": "CARD_0417"})
        self.assertTrue(result.ok)
        self.assertIsNone(result.error)

    def test_output_matches_declared_schema(self):
        result = execute_tool(ToolName.CHECK_CARD_DELIVERY_STATUS, {"card_id": "CARD_0417"})
        self.assertSetEqual(set(result.output), {"status", "dispatched_on", "eta_days"})

    def test_eta_is_positive(self):
        result = execute_tool(ToolName.CHECK_CARD_DELIVERY_STATUS, {"card_id": "CARD_0417"})
        self.assertGreaterEqual(result.output["eta_days"], 1)

    def test_rejects_short_card_id(self):
        result = execute_tool(ToolName.CHECK_CARD_DELIVERY_STATUS, {"card_id": "x"})
        self.assertFalse(result.ok)
        self.assertIn("invalid args", result.error)

    def test_rejects_missing_card_id(self):
        self.assertFalse(execute_tool(ToolName.CHECK_CARD_DELIVERY_STATUS, {}).ok)

    def test_rejects_extra_argument(self):
        """extra='forbid' stops a hallucinated argument reaching the handler."""
        result = execute_tool(
            ToolName.CHECK_CARD_DELIVERY_STATUS,
            {"card_id": "CARD_0417", "cvv": "123"},
        )
        self.assertFalse(result.ok)


class TestBlockCardTool(unittest.TestCase):
    def test_valid_call_succeeds(self):
        result = execute_tool(
            ToolName.BLOCK_CARD, {"account_id": "ACC_1", "reason": "lost"}
        )
        self.assertTrue(result.ok)
        self.assertTrue(result.output["blocked"])

    def test_ref_id_is_prefixed(self):
        result = execute_tool(
            ToolName.BLOCK_CARD, {"account_id": "ACC_1", "reason": "stolen"}
        )
        self.assertTrue(result.output["ref_id"].startswith("BLK-"))

    def test_rejects_unknown_reason(self):
        result = execute_tool(
            ToolName.BLOCK_CARD, {"account_id": "ACC_1", "reason": "bored"}
        )
        self.assertFalse(result.ok)

    def test_all_declared_reasons_accepted(self):
        for reason in BlockReason:
            result = execute_tool(
                ToolName.BLOCK_CARD,
                {"account_id": "ACC_1", "reason": reason.value},
            )
            self.assertTrue(result.ok, reason)


class TestFindBranchTool(unittest.TestCase):
    def test_valid_call_succeeds(self):
        result = execute_tool(
            ToolName.FIND_BRANCH, {"pincode": "560001", "service": "atm"}
        )
        self.assertTrue(result.ok)
        self.assertIn("Branch", result.output["branch_name"])

    def test_rejects_short_pincode(self):
        result = execute_tool(
            ToolName.FIND_BRANCH, {"pincode": "56", "service": "atm"}
        )
        self.assertFalse(result.ok)

    def test_rejects_overlong_pincode(self):
        result = execute_tool(
            ToolName.FIND_BRANCH, {"pincode": "5600011234567", "service": "atm"}
        )
        self.assertFalse(result.ok)

    def test_all_declared_services_accepted(self):
        for service in BranchService:
            result = execute_tool(
                ToolName.FIND_BRANCH,
                {"pincode": "560001", "service": service.value},
            )
            self.assertTrue(result.ok, service)

    def test_distance_is_non_negative(self):
        result = execute_tool(
            ToolName.FIND_BRANCH, {"pincode": "560001", "service": "atm"}
        )
        self.assertGreater(result.output["distance_km"], 0)


class TestDeterminism(unittest.TestCase):
    """Reproducibility: identical arguments must give identical results."""

    def test_card_delivery_is_deterministic(self):
        args = {"card_id": "CARD_0417"}
        first = execute_tool(ToolName.CHECK_CARD_DELIVERY_STATUS, args).output
        second = execute_tool(ToolName.CHECK_CARD_DELIVERY_STATUS, args).output
        self.assertEqual(first, second)

    def test_block_card_is_deterministic(self):
        args = {"account_id": "ACC_1", "reason": "lost"}
        self.assertEqual(
            execute_tool(ToolName.BLOCK_CARD, args).output,
            execute_tool(ToolName.BLOCK_CARD, args).output,
        )

    def test_find_branch_is_deterministic(self):
        args = {"pincode": "560001", "service": "atm"}
        self.assertEqual(
            execute_tool(ToolName.FIND_BRANCH, args).output,
            execute_tool(ToolName.FIND_BRANCH, args).output,
        )

    def test_different_inputs_give_different_results(self):
        """Determinism must not collapse into a constant."""
        outputs = {
            execute_tool(
                ToolName.CHECK_CARD_DELIVERY_STATUS, {"card_id": f"CARD_{i:04d}"}
            ).output["status"]
            for i in range(40)
        }
        self.assertGreater(len(outputs), 1)


class TestUnknownTool(unittest.TestCase):
    def test_unknown_tool_name_is_rejected(self):
        result = execute_tool("wire_transfer_funds", {})
        self.assertFalse(result.ok)
        self.assertIn("unknown tool", result.error)

    def test_accepts_string_name_for_known_tool(self):
        self.assertTrue(execute_tool("find_branch", {"pincode": "560001", "service": "atm"}).ok)


class TestRouting(unittest.TestCase):
    def test_mapped_intent_routes_to_expected_tool(self):
        self.assertIs(route_intent("card_arrival"), ToolName.CHECK_CARD_DELIVERY_STATUS)
        self.assertIs(route_intent("lost_or_stolen_card"), ToolName.BLOCK_CARD)
        self.assertIs(route_intent("atm_support"), ToolName.FIND_BRANCH)

    def test_unmapped_intent_returns_none(self):
        """Most of the 77 intents need no lookup; inventing one is a risk."""
        self.assertIsNone(route_intent("transfer_timing"))

    def test_unknown_intent_returns_none(self):
        self.assertIsNone(route_intent("not_an_intent_at_all"))

    def test_every_routed_tool_exists_in_registry(self):
        for intent, tool in INTENT_TO_TOOL.items():
            self.assertIn(tool, TOOL_REGISTRY, intent)

    def test_every_tool_is_reachable_from_some_intent(self):
        """A tool no intent routes to could never be demonstrated in E5."""
        self.assertSetEqual(set(INTENT_TO_TOOL.values()), set(ToolName))


class TestSpecExport(unittest.TestCase):
    """``tool_specs_json`` is deliverable 7, the tool/function specification."""

    def test_export_is_valid_json(self):
        payload = json.loads(tool_specs_json())
        self.assertEqual(len(payload), 3)

    def test_export_carries_schemas_and_triggers(self):
        payload = json.loads(tool_specs_json())
        for name, entry in payload.items():
            self.assertIn("input_schema", entry, name)
            self.assertIn("output_schema", entry, name)
            self.assertIn("triggered_by", entry, name)
            self.assertTrue(entry["triggered_by"], name)

    def test_block_card_flagged_destructive_in_export(self):
        payload = json.loads(tool_specs_json())
        self.assertTrue(payload["block_card"]["destructive"])


class TestInputModelsDirectly(unittest.TestCase):
    """The declared input schemas, independent of the executor."""

    def test_card_delivery_input_requires_card_id(self):
        with self.assertRaises(Exception):
            CardDeliveryInput()

    def test_block_card_input_coerces_reason_to_enum(self):
        payload = BlockCardInput(account_id="ACC_1", reason="compromised")
        self.assertIs(payload.reason, BlockReason.COMPROMISED)

    def test_find_branch_input_coerces_service_to_enum(self):
        payload = FindBranchInput(pincode="560001", service="cash_deposit")
        self.assertIs(payload.service, BranchService.CASH_DEPOSIT)


if __name__ == "__main__":
    unittest.main()
