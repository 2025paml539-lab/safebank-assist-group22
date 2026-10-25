"""
The E3 decoding grid.

These tests pin the behaviour Satya's ``decoding.py`` must keep: it builds on
the frozen ``DecodeConfig`` / ``DecodeStrategy`` from ``generator.py`` rather
than redefining them, it covers every strategy Requirement 7 demands, and it
produces a reproducible self-consistency run set for evaluation criterion 6.

Owner: Satya Prakash (E3)
"""

from __future__ import annotations

import unittest

from safebank import config
from safebank.decoding import (
    DEFAULT_SEEDS,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P,
    GridPoint,
    build_decoding_grid,
    grid_configs,
    seed_variations,
    self_consistency_configs,
)
from safebank.generator import DecodeConfig, DecodeStrategy


class TestGridCoversTheRequiredStrategies(unittest.TestCase):
    def setUp(self):
        self.grid = build_decoding_grid()

    def test_grid_has_six_points(self):
        """PROJECT_PLAN E3: a six-configuration grid."""
        self.assertEqual(len(self.grid), 6)

    def test_every_point_is_a_grid_point(self):
        for point in self.grid:
            self.assertIsInstance(point, GridPoint)

    def test_every_required_strategy_is_present(self):
        strategies = {point.strategy for point in self.grid}
        self.assertSetEqual(
            strategies,
            {
                DecodeStrategy.GREEDY,
                DecodeStrategy.TEMPERATURE,
                DecodeStrategy.TOP_K,
                DecodeStrategy.TOP_P,
            },
        )

    def test_exactly_one_greedy_reference(self):
        greedy = [p for p in self.grid if p.strategy is DecodeStrategy.GREEDY]
        self.assertEqual(len(greedy), 1)

    def test_configs_are_frozen_decode_configs(self):
        """It must reuse the seam's DecodeConfig, not a redefinition."""
        for point in self.grid:
            self.assertIsInstance(point.config, DecodeConfig)

    def test_labels_are_unique(self):
        labels = [p.label for p in self.grid]
        self.assertEqual(len(labels), len(set(labels)))

    def test_every_point_has_a_substantial_rationale(self):
        """Section 8 forbids unexplained decoding choices."""
        for point in self.grid:
            self.assertGreater(len(point.rationale.strip()), 60, point.label)


class TestGridParametersFlowIntoGenerateKwargs(unittest.TestCase):
    """The grid must drive the HF generate knobs correctly per strategy."""

    def setUp(self):
        self.by_strategy = {}
        for point in build_decoding_grid():
            self.by_strategy.setdefault(point.strategy, []).append(point.config)

    def test_greedy_does_not_sample(self):
        cfg = self.by_strategy[DecodeStrategy.GREEDY][0]
        kwargs = cfg.to_generate_kwargs()
        self.assertFalse(kwargs["do_sample"])
        self.assertNotIn("temperature", kwargs)

    def test_temperature_configs_emit_temperature(self):
        for cfg in self.by_strategy[DecodeStrategy.TEMPERATURE]:
            kwargs = cfg.to_generate_kwargs()
            self.assertTrue(kwargs["do_sample"])
            self.assertIn("temperature", kwargs)

    def test_top_k_emits_top_k(self):
        cfg = self.by_strategy[DecodeStrategy.TOP_K][0]
        kwargs = cfg.to_generate_kwargs()
        self.assertEqual(kwargs["top_k"], DEFAULT_TOP_K)
        self.assertNotIn("top_p", kwargs)

    def test_top_p_emits_top_p(self):
        cfg = self.by_strategy[DecodeStrategy.TOP_P][0]
        kwargs = cfg.to_generate_kwargs()
        self.assertEqual(kwargs["top_p"], DEFAULT_TOP_P)
        self.assertNotIn("top_k", kwargs)


class TestGridOverrides(unittest.TestCase):
    def test_build_is_deterministic(self):
        self.assertEqual(build_decoding_grid(), build_decoding_grid())

    def test_max_new_tokens_override_propagates(self):
        grid = build_decoding_grid(max_new_tokens=32)
        for point in grid:
            self.assertEqual(point.config.max_new_tokens, 32)

    def test_seed_override_propagates(self):
        grid = build_decoding_grid(seed=123)
        for point in grid:
            self.assertEqual(point.config.seed, 123)

    def test_default_seed_is_the_project_seed(self):
        for point in build_decoding_grid():
            self.assertEqual(point.config.seed, config.SEED)

    def test_grid_configs_returns_only_configs(self):
        cfgs = grid_configs()
        self.assertEqual(len(cfgs), 6)
        for cfg in cfgs:
            self.assertIsInstance(cfg, DecodeConfig)


class TestSelfConsistency(unittest.TestCase):
    def test_sampled_config_varies_across_seeds(self):
        base = DecodeConfig(strategy=DecodeStrategy.TOP_P, top_p=0.9)
        variants = seed_variations(base, seeds=(1, 2, 3))
        self.assertEqual(len(variants), 3)
        self.assertEqual([v.seed for v in variants], [1, 2, 3])

    def test_greedy_collapses_to_a_single_run(self):
        """Varying a deterministic strategy's seed cannot change its output."""
        base = DecodeConfig(strategy=DecodeStrategy.GREEDY)
        variants = seed_variations(base, seeds=(1, 2, 3))
        self.assertEqual(len(variants), 1)

    def test_empty_seeds_rejected_for_sampled_config(self):
        base = DecodeConfig(strategy=DecodeStrategy.TEMPERATURE, temperature=0.7)
        with self.assertRaises(ValueError):
            seed_variations(base, seeds=())

    def test_seed_variations_preserve_strategy_and_knobs(self):
        base = DecodeConfig(
            strategy=DecodeStrategy.TOP_K, temperature=0.7, top_k=40
        )
        for variant in seed_variations(base, seeds=(7, 8)):
            self.assertIs(variant.strategy, DecodeStrategy.TOP_K)
            self.assertEqual(variant.top_k, 40)
            self.assertEqual(variant.temperature, 0.7)

    def test_default_seeds_derive_from_project_seed(self):
        self.assertEqual(DEFAULT_SEEDS[0], config.SEED)
        self.assertEqual(len(set(DEFAULT_SEEDS)), len(DEFAULT_SEEDS))

    def test_self_consistency_configs_cover_every_label(self):
        grid = build_decoding_grid()
        mapping = self_consistency_configs(grid)
        self.assertSetEqual(set(mapping), {p.label for p in grid})

    def test_self_consistency_greedy_has_one_run_sampled_have_many(self):
        mapping = self_consistency_configs()
        for label, cfgs in mapping.items():
            if label == "greedy":
                self.assertEqual(len(cfgs), 1)
            else:
                self.assertEqual(len(cfgs), len(DEFAULT_SEEDS))


if __name__ == "__main__":
    unittest.main()
