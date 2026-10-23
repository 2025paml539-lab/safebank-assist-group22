"""
The generation seam - ``DecodeConfig``, the ``TextGenerator`` protocol and the
offline fake.

This is the architectural boundary that makes the whole project testable
without a model runtime, so it is worth testing in its own right. It is also
the contract Vishruth's ``model_loader.HFGenerator`` must satisfy and the
surface Satya's ``decoding.py`` grid will populate.

``to_generate_kwargs`` is tested per strategy because a greedy run that leaked
a temperature value would silently invalidate the E3 comparison table.

Owner: Kishore (seam)
"""

from __future__ import annotations

import dataclasses
import unittest

from safebank import config
from safebank.generator import (
    DecodeConfig,
    DecodeStrategy,
    FakeGenerator,
    TextGenerator,
)


class TestDecodeConfigDefaults(unittest.TestCase):
    def test_defaults_to_greedy(self):
        self.assertIs(DecodeConfig().strategy, DecodeStrategy.GREEDY)

    def test_defaults_pull_from_config(self):
        decode = DecodeConfig()
        self.assertEqual(decode.max_new_tokens, config.MAX_NEW_TOKENS)
        self.assertEqual(decode.seed, config.SEED)

    def test_is_frozen(self):
        """Immutability means every logged run is traceable to its exact config."""
        with self.assertRaises(dataclasses.FrozenInstanceError):
            DecodeConfig().temperature = 0.5


class TestDoSample(unittest.TestCase):
    def test_greedy_does_not_sample(self):
        self.assertFalse(DecodeConfig(strategy=DecodeStrategy.GREEDY).do_sample)

    def test_every_other_strategy_samples(self):
        for strategy in DecodeStrategy:
            if strategy is DecodeStrategy.GREEDY:
                continue
            self.assertTrue(DecodeConfig(strategy=strategy).do_sample, strategy)


class TestGenerateKwargs(unittest.TestCase):
    """Only the knobs relevant to the chosen strategy may be emitted."""

    def test_greedy_emits_no_sampling_knobs(self):
        kwargs = DecodeConfig(strategy=DecodeStrategy.GREEDY, temperature=0.7).to_generate_kwargs()
        self.assertFalse(kwargs["do_sample"])
        self.assertNotIn("temperature", kwargs)
        self.assertNotIn("top_k", kwargs)
        self.assertNotIn("top_p", kwargs)

    def test_temperature_emits_temperature_only(self):
        kwargs = DecodeConfig(
            strategy=DecodeStrategy.TEMPERATURE, temperature=0.8
        ).to_generate_kwargs()
        self.assertEqual(kwargs["temperature"], 0.8)
        self.assertNotIn("top_k", kwargs)
        self.assertNotIn("top_p", kwargs)

    def test_top_k_emits_top_k(self):
        kwargs = DecodeConfig(
            strategy=DecodeStrategy.TOP_K, top_k=50, temperature=0.8
        ).to_generate_kwargs()
        self.assertEqual(kwargs["top_k"], 50)
        self.assertNotIn("top_p", kwargs)

    def test_top_p_emits_top_p(self):
        kwargs = DecodeConfig(
            strategy=DecodeStrategy.TOP_P, top_p=0.9, temperature=0.8
        ).to_generate_kwargs()
        self.assertEqual(kwargs["top_p"], 0.9)
        self.assertNotIn("top_k", kwargs)

    def test_max_new_tokens_always_present(self):
        for strategy in DecodeStrategy:
            kwargs = DecodeConfig(strategy=strategy).to_generate_kwargs()
            self.assertIn("max_new_tokens", kwargs, strategy)


class TestLabels(unittest.TestCase):
    """Labels become the row headings in the E3 comparison table."""

    def test_every_strategy_has_a_distinct_label(self):
        labels = {
            DecodeConfig(strategy=DecodeStrategy.GREEDY).label(),
            DecodeConfig(strategy=DecodeStrategy.TEMPERATURE, temperature=0.7).label(),
            DecodeConfig(strategy=DecodeStrategy.TOP_K, top_k=50, temperature=0.7).label(),
            DecodeConfig(strategy=DecodeStrategy.TOP_P, top_p=0.9, temperature=0.7).label(),
        }
        self.assertEqual(len(labels), 4)

    def test_greedy_label(self):
        self.assertEqual(DecodeConfig().label(), "greedy")

    def test_top_k_label_mentions_k(self):
        label = DecodeConfig(strategy=DecodeStrategy.TOP_K, top_k=50).label()
        self.assertIn("50", label)


class TestWithSeed(unittest.TestCase):
    """Seed variation drives the E3 self-consistency measurement."""

    def test_returns_a_new_config_with_the_new_seed(self):
        self.assertEqual(DecodeConfig().with_seed(7).seed, 7)

    def test_original_is_unchanged(self):
        original = DecodeConfig()
        original.with_seed(7)
        self.assertEqual(original.seed, config.SEED)

    def test_other_fields_are_preserved(self):
        base = DecodeConfig(strategy=DecodeStrategy.TOP_P, top_p=0.9, temperature=0.8)
        varied = base.with_seed(99)
        self.assertIs(varied.strategy, DecodeStrategy.TOP_P)
        self.assertEqual(varied.top_p, 0.9)
        self.assertEqual(varied.temperature, 0.8)


class TestFakeGenerator(unittest.TestCase):
    def test_satisfies_the_protocol(self):
        """Structural check: the fake must be swappable for the real thing."""
        self.assertIsInstance(FakeGenerator(), TextGenerator)

    def test_returns_scripted_completions_in_order(self):
        gen = FakeGenerator(["first", "second"])
        decode = DecodeConfig()
        self.assertEqual(gen.generate("p", decode), "first")
        self.assertEqual(gen.generate("p", decode), "second")

    def test_falls_back_once_the_script_is_exhausted(self):
        gen = FakeGenerator(["only"])
        decode = DecodeConfig()
        gen.generate("p", decode)
        self.assertIn("card_arrival", gen.generate("p", decode))

    def test_default_fallback_is_schema_valid(self):
        """Lets the happy path be exercised with no scripting at all."""
        from safebank.schema import parse_response

        outcome = parse_response(FakeGenerator().generate("p", DecodeConfig()))
        self.assertTrue(outcome.ok)

    def test_custom_fallback_is_used(self):
        gen = FakeGenerator(fallback="custom text")
        self.assertEqual(gen.generate("p", DecodeConfig()), "custom text")

    def test_records_calls_for_assertions(self):
        gen = FakeGenerator()
        decode = DecodeConfig()
        gen.generate("prompt one", decode)
        self.assertEqual(gen.call_count, 1)
        self.assertEqual(gen.calls[0][0], "prompt one")
        self.assertIs(gen.calls[0][1], decode)


if __name__ == "__main__":
    unittest.main()
