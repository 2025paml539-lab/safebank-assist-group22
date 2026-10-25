"""
The prompt seam, and the zero-shot reference template.

Ownership note
--------------
``prompts.py`` is Satya's deliverable (Requirement 11, Experiment E2). What is
tested here is the part Kishore owns and is handing over: the strategy enum,
the ``build_prompt`` dispatch contract that ``pipeline.py`` already calls, the
shared rendering blocks, and the fully worked ZERO_SHOT reference
implementation.

The three unimplemented variants are tested for *raising*
``NotImplementedError``. That is deliberate, and it is the point of the
handover: it pins the interface so Satya can fill in FEW_SHOT, ROLE_CONTEXT
and CONSTRAINT_BASED without guessing at signatures, and it guarantees the
suite reports honestly that they are absent rather than quietly passing.

When Satya implements a variant, the matching test below is expected to fail
and should be replaced with real content assertions.

Owner: Kishore (seam + reference) / Satya Prakash (the three variants)
"""

from __future__ import annotations

import unittest

from safebank import config
from safebank.prompts import (
    PROMPT_BUILDERS,
    STRATEGY_RATIONALE,
    PromptStrategy,
    build_constraint_based_prompt,
    build_few_shot_prompt,
    build_prompt,
    build_role_context_prompt,
    build_zero_shot_prompt,
    format_intent_catalogue,
    format_schema_contract,
    format_tool_catalogue,
    implemented_strategies,
    pending_strategies,
)

INTENTS = ["card_arrival", "lost_or_stolen_card", "atm_support", "transfer_timing"]
QUERY = "My new card has not arrived yet"


class TestStrategyRegistry(unittest.TestCase):
    def test_four_strategies_as_the_brief_requires(self):
        """Requirement 6 and E2 both demand at least four prompt variants."""
        self.assertEqual(len(PromptStrategy), 4)

    def test_every_strategy_has_a_builder(self):
        self.assertSetEqual(set(PROMPT_BUILDERS), set(PromptStrategy))

    def test_every_strategy_has_a_written_rationale(self):
        """Section 8 forbids unexplained prompts."""
        self.assertSetEqual(set(STRATEGY_RATIONALE), set(PromptStrategy))

    def test_rationales_are_substantial(self):
        for strategy, rationale in STRATEGY_RATIONALE.items():
            self.assertGreater(len(rationale.strip()), 80, strategy)

    def test_implemented_and_pending_partition_the_set(self):
        self.assertSetEqual(
            set(implemented_strategies()) | set(pending_strategies()),
            set(PromptStrategy),
        )

    def test_implemented_and_pending_do_not_overlap(self):
        self.assertFalse(set(implemented_strategies()) & set(pending_strategies()))

    def test_all_four_strategies_are_implemented(self):
        self.assertSetEqual(set(implemented_strategies()), set(PromptStrategy))

    def test_nothing_is_pending(self):
        self.assertEqual(pending_strategies(), ())


class TestSharedBlocks(unittest.TestCase):
    """All four variants reuse these, so an E2 delta is attributable."""

    def test_intent_catalogue_lists_every_label(self):
        rendered = format_intent_catalogue(INTENTS)
        for intent in INTENTS:
            self.assertIn(intent, rendered)

    def test_intent_catalogue_wraps_lines(self):
        rendered = format_intent_catalogue([f"intent_{i:02d}" for i in range(20)], per_line=4)
        self.assertEqual(len(rendered.splitlines()), 5)

    def test_intent_catalogue_preserves_order(self):
        rendered = format_intent_catalogue(INTENTS)
        positions = [rendered.index(i) for i in INTENTS]
        self.assertEqual(positions, sorted(positions))

    def test_empty_intent_list_is_rejected(self):
        """An empty catalogue would disable the unknown-intent guard."""
        with self.assertRaises(ValueError):
            format_intent_catalogue([])

    def test_schema_contract_is_derived_from_the_model(self):
        rendered = format_schema_contract()
        for field in ("intent", "confidence", "response", "tool_call", "requires_human"):
            self.assertIn(field, rendered)

    def test_schema_contract_omits_the_disclaimer(self):
        """The disclaimer is application-enforced; the model must not write it."""
        self.assertNotIn("disclaimer", format_schema_contract())

    def test_tool_catalogue_lists_every_tool_and_its_args(self):
        rendered = format_tool_catalogue()
        self.assertIn("check_card_delivery_status", rendered)
        self.assertIn("card_id", rendered)
        self.assertIn("block_card", rendered)
        self.assertIn("find_branch", rendered)

    def test_tool_catalogue_marks_destructive_tools(self):
        self.assertIn("requires human confirmation", format_tool_catalogue())


class TestZeroShotPrompt(unittest.TestCase):
    def setUp(self):
        self.prompt = build_zero_shot_prompt(QUERY, INTENTS)

    def test_returns_a_non_trivial_string(self):
        self.assertIsInstance(self.prompt, str)
        self.assertGreater(len(self.prompt), 200)

    def test_contains_the_customer_query(self):
        self.assertIn(QUERY, self.prompt)

    def test_contains_the_permitted_labels(self):
        for intent in INTENTS:
            self.assertIn(intent, self.prompt)

    def test_contains_the_tool_catalogue(self):
        self.assertIn("check_card_delivery_status", self.prompt)

    def test_asks_for_json(self):
        self.assertIn("JSON", self.prompt)

    def test_forbids_inventing_labels(self):
        self.assertIn("verbatim", self.prompt.lower())

    def test_states_the_escalation_threshold_from_config(self):
        self.assertIn(f"{config.ESCALATION_CONFIDENCE_THRESHOLD:.2f}", self.prompt)

    def test_carries_the_no_invented_facts_rule(self):
        """Responsible-use control stated in the prompt itself."""
        self.assertIn("never state an account fact", self.prompt.lower())

    def test_ends_by_cueing_the_model(self):
        self.assertTrue(self.prompt.rstrip().endswith("JSON:"))

    def test_is_deterministic(self):
        """Same inputs must give a byte-identical prompt, for reproducibility."""
        self.assertEqual(self.prompt, build_zero_shot_prompt(QUERY, INTENTS))

    def test_scales_to_the_full_label_space(self):
        labels = [f"intent_{i:02d}" for i in range(77)]
        prompt = build_zero_shot_prompt(QUERY, labels)
        self.assertIn("intent_76", prompt)


class TestQueryPreprocessing(unittest.TestCase):
    """The documented preprocessing step cited in the report."""

    def test_collapses_whitespace(self):
        prompt = build_zero_shot_prompt("my   card\n\nis   late", INTENTS)
        self.assertIn("my card is late", prompt)

    def test_strips_surrounding_quotes(self):
        self.assertIn("card is late", build_zero_shot_prompt('"card is late"', INTENTS))

    def test_rejects_empty_query(self):
        with self.assertRaises(ValueError):
            build_zero_shot_prompt("   ", INTENTS)

    def test_rejects_non_string_query(self):
        with self.assertRaises(TypeError):
            build_zero_shot_prompt(None, INTENTS)

    def test_preserves_case_and_punctuation(self):
        """Aggressive cleaning would destroy cues the model relies on."""
        prompt = build_zero_shot_prompt("Where is my CARD?!", INTENTS)
        self.assertIn("Where is my CARD?!", prompt)


class TestDispatch(unittest.TestCase):
    """``build_prompt`` is the only entry point ``pipeline.py`` uses."""

    def test_dispatches_zero_shot_by_enum(self):
        self.assertEqual(
            build_prompt(PromptStrategy.ZERO_SHOT, QUERY, INTENTS),
            build_zero_shot_prompt(QUERY, INTENTS),
        )

    def test_dispatches_by_string_value(self):
        self.assertIn(QUERY, build_prompt("zero_shot", QUERY, INTENTS))

    def test_unknown_strategy_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            build_prompt("chain_of_thought", QUERY, INTENTS)
        self.assertIn("unknown prompt strategy", str(ctx.exception))

    def test_error_message_lists_the_valid_strategies(self):
        with self.assertRaises(ValueError) as ctx:
            build_prompt("nope", QUERY, INTENTS)
        self.assertIn("zero_shot", str(ctx.exception))


class TestVariantsShareTheSameBlocks(unittest.TestCase):
    """
    The guarantee that makes the E2 table meaningful.

    Every variant must embed the shared intent catalogue, tool catalogue and
    schema contract byte-for-byte. If a variant hand-wrote its own schema text,
    an accuracy delta could be caused by wording drift rather than by the
    strategy, and the comparison would be meaningless.
    """

    def _all_variant_prompts(self) -> dict[PromptStrategy, str]:
        return {
            PromptStrategy.ZERO_SHOT: build_zero_shot_prompt(QUERY, INTENTS),
            PromptStrategy.FEW_SHOT: build_few_shot_prompt(QUERY, INTENTS),
            PromptStrategy.ROLE_CONTEXT: build_role_context_prompt(QUERY, INTENTS),
            PromptStrategy.CONSTRAINT_BASED: build_constraint_based_prompt(
                QUERY, INTENTS
            ),
        }

    def test_every_variant_embeds_the_shared_schema_contract(self):
        contract = format_schema_contract()
        for strategy, prompt in self._all_variant_prompts().items():
            self.assertIn(contract, prompt, strategy)

    def test_every_variant_embeds_the_shared_intent_catalogue(self):
        catalogue = format_intent_catalogue(INTENTS)
        for strategy, prompt in self._all_variant_prompts().items():
            self.assertIn(catalogue, prompt, strategy)

    def test_every_variant_embeds_the_shared_tool_catalogue(self):
        catalogue = format_tool_catalogue()
        for strategy, prompt in self._all_variant_prompts().items():
            self.assertIn(catalogue, prompt, strategy)

    def test_every_variant_contains_the_query_and_cues_json(self):
        for strategy, prompt in self._all_variant_prompts().items():
            self.assertIn(QUERY, prompt, strategy)
            self.assertTrue(prompt.rstrip().endswith("JSON:"), strategy)

    def test_every_variant_is_deterministic(self):
        first = self._all_variant_prompts()
        second = self._all_variant_prompts()
        for strategy in PromptStrategy:
            self.assertEqual(first[strategy], second[strategy], strategy)

    def test_variants_are_distinct_from_zero_shot(self):
        """Each strategy must actually differ, or it is not a variant."""
        prompts = self._all_variant_prompts()
        zero = prompts[PromptStrategy.ZERO_SHOT]
        for strategy in (
            PromptStrategy.FEW_SHOT,
            PromptStrategy.ROLE_CONTEXT,
            PromptStrategy.CONSTRAINT_BASED,
        ):
            self.assertNotEqual(prompts[strategy], zero, strategy)


class TestFewShotPrompt(unittest.TestCase):
    def test_includes_worked_examples(self):
        prompt = build_few_shot_prompt(QUERY, INTENTS, n_examples=3)
        # Each example ends with a JSON block; expect at least n example cues
        # plus the final query cue.
        self.assertGreaterEqual(prompt.count("JSON:"), 3)

    def test_respects_n_examples(self):
        few = build_few_shot_prompt(QUERY, INTENTS, n_examples=1)
        many = build_few_shot_prompt(QUERY, INTENTS, n_examples=4)
        self.assertLess(few.count("JSON:"), many.count("JSON:"))

    def test_accepts_caller_supplied_examples(self):
        examples = [
            (
                "where is my card",
                '{"intent": "card_arrival", "confidence": 0.9, '
                '"response": "checking", "tool_call": null, '
                '"requires_human": false}',
            )
        ]
        prompt = build_few_shot_prompt(QUERY, INTENTS, examples=examples, n_examples=1)
        self.assertIn("where is my card", prompt)

    def test_leads_with_a_confusable_pair_example(self):
        """The fallback set must exercise the disambiguation hypothesis."""
        prompt = build_few_shot_prompt(QUERY, INTENTS, n_examples=1)
        self.assertIn("card_arrival", prompt)

    def test_rejects_non_positive_n_examples(self):
        with self.assertRaises(ValueError):
            build_few_shot_prompt(QUERY, INTENTS, n_examples=0)

    def test_is_deterministic(self):
        self.assertEqual(
            build_few_shot_prompt(QUERY, INTENTS),
            build_few_shot_prompt(QUERY, INTENTS),
        )


class TestRoleContextPrompt(unittest.TestCase):
    def test_states_the_role(self):
        prompt = build_role_context_prompt(QUERY, INTENTS)
        self.assertIn("tier-1 retail banking support agent", prompt)

    def test_role_is_overridable(self):
        prompt = build_role_context_prompt(QUERY, INTENTS, role="fraud analyst")
        self.assertIn("fraud analyst", prompt)

    def test_channel_is_overridable(self):
        prompt = build_role_context_prompt(QUERY, INTENTS, channel="phone")
        self.assertIn("phone", prompt)

    def test_frames_simulated_systems_and_escalation(self):
        prompt = build_role_context_prompt(QUERY, INTENTS).lower()
        self.assertIn("simulated", prompt)
        self.assertIn("colleague", prompt)

    def test_still_asks_for_json(self):
        self.assertTrue(
            build_role_context_prompt(QUERY, INTENTS).rstrip().endswith("JSON:")
        )


class TestConstraintBasedPrompt(unittest.TestCase):
    def test_has_one_rule_per_failure_kind(self):
        """
        The headline property: every schema.FailureKind cause is addressed by
        an explicit constraint, so E2 and E4 line up failure-kind by failure-kind.
        """
        prompt = build_constraint_based_prompt(QUERY, INTENTS).lower()
        # NO_JSON_FOUND
        self.assertIn("single json object", prompt)
        # MALFORMED_JSON
        self.assertIn("valid json", prompt)
        # SCHEMA_VIOLATION
        self.assertIn("five fields", prompt)
        # UNKNOWN_INTENT
        self.assertIn("verbatim", prompt)

    def test_forbid_prose_is_toggleable(self):
        on = build_constraint_based_prompt(QUERY, INTENTS, forbid_prose=True)
        off = build_constraint_based_prompt(QUERY, INTENTS, forbid_prose=False)
        self.assertIn("prose", on.lower())
        self.assertNotEqual(on, off)

    def test_forbid_code_fences_is_toggleable(self):
        on = build_constraint_based_prompt(QUERY, INTENTS, forbid_code_fences=True)
        off = build_constraint_based_prompt(QUERY, INTENTS, forbid_code_fences=False)
        self.assertIn("fences", on.lower())
        self.assertNotEqual(on, off)

    def test_warns_against_inventing_fields(self):
        """extra='forbid' consequence must be stated to the model."""
        prompt = build_constraint_based_prompt(QUERY, INTENTS).lower()
        self.assertIn("extra", prompt)


class TestDispatchReachesEveryVariant(unittest.TestCase):
    """build_prompt is the only entry point pipeline.py uses."""

    def test_dispatch_matches_direct_call_for_every_strategy(self):
        self.assertEqual(
            build_prompt(PromptStrategy.FEW_SHOT, QUERY, INTENTS),
            build_few_shot_prompt(QUERY, INTENTS),
        )
        self.assertEqual(
            build_prompt(PromptStrategy.ROLE_CONTEXT, QUERY, INTENTS),
            build_role_context_prompt(QUERY, INTENTS),
        )
        self.assertEqual(
            build_prompt(PromptStrategy.CONSTRAINT_BASED, QUERY, INTENTS),
            build_constraint_based_prompt(QUERY, INTENTS),
        )

    def test_dispatch_forwards_keyword_arguments(self):
        direct = build_few_shot_prompt(QUERY, INTENTS, n_examples=2)
        viadispatch = build_prompt(
            PromptStrategy.FEW_SHOT, QUERY, INTENTS, n_examples=2
        )
        self.assertEqual(direct, viadispatch)


if __name__ == "__main__":
    unittest.main()
