"""
The E2/E3/E6 experiment runner.

Everything here runs offline. ``QueryAwareGenerator`` is a scripted stand-in for
the model that answers according to the customer message found in the prompt,
so each test controls exactly which rows come back right, wrong, malformed or
seed-dependent. It also implements ``generate_batch`` and records how it was
called, which is what lets the batching path be verified without a GPU.

Owner: Satya Prakash (E2, E3, E6)
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from safebank.decoding import build_decoding_grid
from safebank.experiments import (
    E2_COLUMNS,
    PrefetchingGenerator,
    assert_no_overlap,
    best_condition,
    compare_conditions,
    condition_payload,
    failure_cases,
    report_table,
    run_condition,
    run_e2,
    run_e3,
    safety_findings,
    sample_outputs,
    save_condition,
    save_grid,
    select_e3_subset,
    slug,
    strategy_kwargs,
    variability_examples,
)
from safebank.generator import DecodeConfig, DecodeStrategy, FakeGenerator
from safebank.prompts import PromptStrategy

LABELS = [
    "card_arrival",
    "card_delivery_estimate",
    "lost_or_stolen_card",
    "atm_support",
    "transfer_timing",
]


def make_rows(per_intent: int = 2) -> list[dict]:
    return [
        {"query": f"q::{label}::{i}", "gold_intent": label}
        for label in LABELS
        for i in range(per_intent)
    ]


def reply_json(intent: str, response: str = "Thanks, I will look into that.") -> str:
    return json.dumps(
        {
            "intent": intent,
            "confidence": 0.9,
            "response": response,
            "tool_call": None,
            "requires_human": False,
        }
    )


def customer_message(prompt: str) -> str:
    """The text after the last 'Customer message:' label (the real query)."""
    return prompt.rsplit("Customer message:", 1)[-1].replace("JSON:", "").strip()


class QueryAwareGenerator:
    """Scripted model: answers by query, records every call."""

    def __init__(self, choose=None, bad=(), always_bad=()):
        # choose(query, decode) -> intent; default is the gold label in the query.
        self.choose = choose or (
            lambda query, decode: query.split("::")[1] if "::" in query else "card_arrival"
        )
        self.bad = set(bad)  # first attempt is not JSON, repair succeeds
        self.always_bad = set(always_bad)  # first attempt and repairs are not JSON
        self.batch_sizes: list[int] = []
        self.single_calls = 0
        self.prompts: list[str] = []

    def _answer(self, prompt: str, decode: DecodeConfig) -> str:
        self.prompts.append(prompt)
        if "rejected by a strict JSON validator" in prompt:
            if any(f"garbage-{q}" in prompt for q in self.always_bad):
                return "garbage-" + next(q for q in self.always_bad if f"garbage-{q}" in prompt)
            return reply_json("card_arrival")
        query = customer_message(prompt)
        if query in self.always_bad:
            return f"garbage-{query}"
        if query in self.bad:
            return "not json at all"
        return reply_json(self.choose(query, decode))

    def generate(self, prompt: str, decode: DecodeConfig) -> str:
        self.single_calls += 1
        return self._answer(prompt, decode)

    def generate_batch(self, prompts: list[str], decode: DecodeConfig) -> list[str]:
        self.batch_sizes.append(len(prompts))
        return [self._answer(p, decode) for p in prompts]


class TestPrefetchingGenerator(unittest.TestCase):
    def test_prefetch_uses_the_batch_path_in_chunks(self):
        inner = QueryAwareGenerator()
        gen = PrefetchingGenerator(inner, batch_size=2)
        gen.prefetch([f"p{i}" for i in range(5)], DecodeConfig())
        self.assertEqual(inner.batch_sizes, [2, 2, 1])
        self.assertEqual(inner.single_calls, 0)

    def test_cached_completions_are_served_without_calling_the_model(self):
        inner = QueryAwareGenerator()
        gen = PrefetchingGenerator(inner, batch_size=4)
        decode = DecodeConfig()
        gen.prefetch(["Customer message:\nq::card_arrival::0\n\nJSON:"], decode)
        out = gen.generate("Customer message:\nq::card_arrival::0\n\nJSON:", decode)
        self.assertIn("card_arrival", out)
        self.assertEqual((gen.hits, gen.misses), (1, 0))
        self.assertEqual(inner.single_calls, 0)

    def test_unknown_prompt_falls_through_to_single_generation(self):
        inner = QueryAwareGenerator()
        gen = PrefetchingGenerator(inner)
        gen.generate("a repair prompt that was never prefetched", DecodeConfig())
        self.assertEqual((gen.hits, gen.misses), (0, 1))
        self.assertEqual(inner.single_calls, 1)

    def test_duplicate_prompts_each_get_a_completion(self):
        inner = FakeGenerator(scripted=["first", "second"])
        gen = PrefetchingGenerator(inner, batch_size=8)
        decode = DecodeConfig()
        gen.prefetch(["same", "same"], decode)
        self.assertEqual(gen.generate("same", decode), "first")
        self.assertEqual(gen.generate("same", decode), "second")
        self.assertEqual(gen.hits, 2)

    def test_cache_is_keyed_by_decode_config(self):
        inner = QueryAwareGenerator()
        gen = PrefetchingGenerator(inner)
        gen.prefetch(["Customer message:\nq::card_arrival::0"], DecodeConfig())
        sampled = DecodeConfig(strategy=DecodeStrategy.TEMPERATURE, temperature=0.7)
        gen.generate("Customer message:\nq::card_arrival::0", sampled)
        self.assertEqual(gen.misses, 1)

    def test_generator_without_generate_batch_still_works(self):
        gen = PrefetchingGenerator(FakeGenerator(), batch_size=2)
        decode = DecodeConfig()
        gen.prefetch(["a", "b", "c"], decode)
        self.assertIn("card_arrival", gen.generate("b", decode))

    def test_wrong_number_of_completions_is_an_error(self):
        class Short:
            def generate_batch(self, prompts, decode):
                return ["only one"]

        with self.assertRaises(RuntimeError):
            PrefetchingGenerator(Short(), batch_size=3).prefetch(["a", "b", "c"], DecodeConfig())

    def test_non_positive_batch_size_is_rejected(self):
        with self.assertRaises(ValueError):
            PrefetchingGenerator(FakeGenerator(), batch_size=0)

    def test_take_hit_ms_resets(self):
        gen = PrefetchingGenerator(FakeGenerator())
        decode = DecodeConfig()
        gen.prefetch(["a"], decode)
        gen.generate("a", decode)
        self.assertGreaterEqual(gen.take_hit_ms(), 0.0)
        self.assertEqual(gen.take_hit_ms(), 0.0)


class TestRunCondition(unittest.TestCase):
    def test_runs_every_row_through_the_real_pipeline(self):
        rows = make_rows()
        cond = run_condition(
            QueryAwareGenerator(), LABELS, rows, PromptStrategy.ZERO_SHOT, DecodeConfig()
        )
        self.assertEqual(len(cond.records), len(rows))
        self.assertEqual(cond.summary(with_macro_f1=False)["accuracy"], 1.0)

    def test_first_attempts_are_batched_and_served_from_cache(self):
        rows = make_rows()
        gen = QueryAwareGenerator()
        cond = run_condition(
            gen, LABELS, rows, PromptStrategy.ZERO_SHOT, DecodeConfig(), batch_size=4
        )
        self.assertEqual(cond.meta["cache_hits"], len(rows))
        self.assertEqual(cond.meta["cache_misses"], 0)
        self.assertEqual(sum(gen.batch_sizes), len(rows))
        self.assertEqual(gen.single_calls, 0)
        self.assertEqual(cond.meta["batch_size"], 4)

    def test_wrong_predictions_lower_accuracy(self):
        rows = make_rows()
        gen = QueryAwareGenerator(choose=lambda q, d: "atm_support")
        cond = run_condition(gen, LABELS, rows, PromptStrategy.ZERO_SHOT, DecodeConfig())
        self.assertAlmostEqual(cond.summary(with_macro_f1=False)["accuracy"], 0.2)

    def test_repair_prompt_is_a_cache_miss_and_still_recovers(self):
        rows = make_rows(per_intent=1)
        gen = QueryAwareGenerator(bad={"q::atm_support::0"})
        cond = run_condition(gen, LABELS, rows, PromptStrategy.ZERO_SHOT, DecodeConfig())
        self.assertEqual(cond.meta["cache_misses"], 1)
        summary = cond.summary(with_macro_f1=False)
        self.assertEqual(summary["schema_final_rate"], 1.0)
        self.assertLess(summary["schema_first_attempt_rate"], 1.0)
        self.assertEqual(summary["schema_repaired"], 1)

    def test_unrecoverable_reply_is_reported_not_hidden(self):
        rows = make_rows(per_intent=1)
        gen = QueryAwareGenerator(always_bad={"q::atm_support::0"})
        cond = run_condition(gen, LABELS, rows, PromptStrategy.ZERO_SHOT, DecodeConfig())
        self.assertLess(cond.summary(with_macro_f1=False)["schema_final_rate"], 1.0)

    def test_latency_includes_the_amortised_batch_share(self):
        cond = run_condition(
            QueryAwareGenerator(), LABELS, make_rows(), PromptStrategy.ZERO_SHOT, DecodeConfig()
        )
        self.assertTrue(all(r.row["latency_ms"] >= 0 for r in cond.records))
        self.assertIn("amortised", cond.meta["latency_basis"])

    def test_empty_rows_are_rejected(self):
        with self.assertRaises(ValueError):
            run_condition(
                QueryAwareGenerator(), LABELS, [], PromptStrategy.ZERO_SHOT, DecodeConfig()
            )

    def test_requires_human_rate_is_reported(self):
        cond = run_condition(
            QueryAwareGenerator(), LABELS, make_rows(), PromptStrategy.ZERO_SHOT, DecodeConfig()
        )
        self.assertEqual(cond.summary(with_macro_f1=False)["requires_human_rate"], 0.0)


class TestE2(unittest.TestCase):
    BANK = [
        ("example query one", reply_json("card_arrival")),
        ("example query two", reply_json("atm_support")),
    ]

    def test_runs_all_four_strategies_in_order(self):
        results = run_e2(QueryAwareGenerator(), LABELS, make_rows(), self.BANK)
        self.assertEqual([r.strategy for r in results], list(PromptStrategy))

    def test_few_shot_receives_the_train_bank_and_others_do_not(self):
        gen = QueryAwareGenerator()
        run_e2(gen, LABELS, make_rows(per_intent=1), self.BANK)
        with_example = [p for p in gen.prompts if "example query one" in p]
        self.assertTrue(with_example)
        self.assertTrue(all("worked examples" in p for p in with_example))

    def test_overlap_between_bank_and_eval_is_refused(self):
        rows = make_rows()
        bad_bank = [(rows[0]["query"], reply_json("card_arrival"))]
        with self.assertRaises(ValueError) as ctx:
            run_e2(QueryAwareGenerator(), LABELS, rows, bad_bank)
        self.assertIn("exclude", str(ctx.exception))

    def test_assert_no_overlap_passes_for_a_clean_bank(self):
        assert_no_overlap(self.BANK, make_rows())

    def test_report_table_has_the_section_7_columns(self):
        results = run_e2(QueryAwareGenerator(), LABELS, make_rows(), self.BANK)
        table = report_table(results)
        self.assertEqual(len(table), 4)
        for row in table:
            self.assertEqual(tuple(row), E2_COLUMNS)

    def test_best_condition_picks_the_most_accurate(self):
        rows = make_rows()
        good = run_condition(
            QueryAwareGenerator(), LABELS, rows, PromptStrategy.ZERO_SHOT, DecodeConfig()
        )
        poor = run_condition(
            QueryAwareGenerator(choose=lambda q, d: "atm_support"),
            LABELS,
            rows,
            PromptStrategy.CONSTRAINT_BASED,
            DecodeConfig(),
        )
        self.assertIs(best_condition([poor, good]), good)
        self.assertIs(best_condition([good, poor]), good)

    def test_best_condition_rejects_empty(self):
        with self.assertRaises(ValueError):
            best_condition([])


class TestE3(unittest.TestCase):
    def test_subset_has_one_row_per_intent(self):
        subset = select_e3_subset(make_rows(per_intent=3))
        self.assertEqual(len(subset), len(LABELS))
        self.assertEqual({r["gold_intent"] for r in subset}, set(LABELS))

    def test_subset_is_deterministic_and_a_strict_subset(self):
        rows = make_rows(per_intent=3)
        self.assertEqual(select_e3_subset(rows), select_e3_subset(rows))
        self.assertTrue(all(r in rows for r in select_e3_subset(rows)))

    def test_greedy_runs_once_and_sampled_configs_once_per_seed(self):
        seeds = (1, 2, 3)
        results = run_e3(
            QueryAwareGenerator(),
            LABELS,
            select_e3_subset(make_rows()),
            PromptStrategy.ZERO_SHOT,
            seeds=seeds,
        )
        by_label = {g.point.label: len(g.runs) for g in results}
        self.assertEqual(by_label["greedy"], 1)
        self.assertEqual(sorted(set(v for k, v in by_label.items() if k != "greedy")), [3])
        self.assertEqual(len(results), len(build_decoding_grid()))

    def test_deterministic_model_is_fully_stable(self):
        results = run_e3(
            QueryAwareGenerator(),
            LABELS,
            select_e3_subset(make_rows()),
            PromptStrategy.ZERO_SHOT,
            seeds=(1, 2, 3),
        )
        sampled = [g for g in results if g.point.label != "greedy"]
        for grid_result in sampled:
            self.assertEqual(grid_result.summary()["mean_agreement"], 1.0)
            self.assertEqual(variability_examples(grid_result), [])

    def test_greedy_has_no_stability_score(self):
        results = run_e3(
            QueryAwareGenerator(),
            LABELS,
            select_e3_subset(make_rows()),
            PromptStrategy.ZERO_SHOT,
            seeds=(1, 2),
        )
        greedy = next(g for g in results if g.point.label == "greedy")
        self.assertIsNone(greedy.stability())
        self.assertIsNone(greedy.summary()["mean_agreement"])

    def test_seed_dependent_output_lowers_agreement_and_is_surfaced(self):
        # Seeds 1 and 3 answer correctly, seed 2 answers wrongly.
        def choose(query, decode):
            return "atm_support" if decode.seed == 2 else query.split("::")[1]

        results = run_e3(
            QueryAwareGenerator(choose=choose),
            LABELS,
            select_e3_subset(make_rows()),
            PromptStrategy.ZERO_SHOT,
            seeds=(1, 2, 3),
        )
        sampled = next(g for g in results if g.point.label != "greedy")
        summary = sampled.summary()
        # The wrong answer at seed 2 is "atm_support", which is correct for the
        # atm_support query, so that query is stable across all three seeds:
        # four queries agree 2 of 3 and one agrees 3 of 3.
        expected = (4 * (2 / 3) + 1.0) / 5
        self.assertAlmostEqual(summary["mean_agreement"], expected, places=3)
        self.assertAlmostEqual(summary["fully_stable_fraction"], 1 / 5, places=3)
        self.assertLess(summary["accuracy_min"], summary["accuracy_max"])
        self.assertTrue(variability_examples(sampled))
        example = variability_examples(sampled)[0]
        self.assertEqual(len(example["predictions_by_seed"]), 3)

    def test_sample_outputs_gives_k_replies_per_configuration(self):
        results = run_e3(
            QueryAwareGenerator(),
            LABELS,
            select_e3_subset(make_rows()),
            PromptStrategy.ZERO_SHOT,
            seeds=(1, 2),
        )
        samples = sample_outputs(results, k=3)
        self.assertEqual(len(samples), len(results))
        for replies in samples.values():
            self.assertEqual(len(replies), 3)
            self.assertIn("response", replies[0])


class TestE6(unittest.TestCase):
    def test_compare_reports_signed_change(self):
        rows = make_rows()
        baseline = run_condition(
            QueryAwareGenerator(choose=lambda q, d: "atm_support"),
            LABELS,
            rows,
            PromptStrategy.ZERO_SHOT,
            DecodeConfig(),
        )
        final = run_condition(
            QueryAwareGenerator(), LABELS, rows, PromptStrategy.CONSTRAINT_BASED, DecodeConfig()
        )
        table = {r["metric"]: r for r in compare_conditions(baseline, final)}
        self.assertAlmostEqual(table["accuracy"]["baseline"], 0.2)
        self.assertAlmostEqual(table["accuracy"]["final"], 1.0)
        self.assertAlmostEqual(table["accuracy"]["change"], 0.8)

    def _mixed_failures(self):
        def choose(query, decode):
            gold = query.split("::")[1]
            if gold == "card_arrival":
                return "card_delivery_estimate"  # declared confusable pair
            if gold == "transfer_timing":
                return "atm_support"  # cross-theme
            return gold

        gen = QueryAwareGenerator(choose=choose, always_bad={"q::lost_or_stolen_card::0"})
        return run_condition(
            gen, LABELS, make_rows(per_intent=2), PromptStrategy.ZERO_SHOT, DecodeConfig()
        )

    def test_failure_cases_span_distinct_classes(self):
        cases = failure_cases(self._mixed_failures(), n=3)
        self.assertEqual(len(cases), 3)
        self.assertEqual(len({c["category"] for c in cases}), 3)

    def test_each_case_carries_query_reply_and_a_root_cause_note(self):
        for case in failure_cases(self._mixed_failures(), n=6):
            self.assertTrue(case["query"])
            self.assertTrue(case["note"])
            self.assertIn("category", case)

    def test_confusable_pair_and_validation_failure_are_both_identified(self):
        categories = {c["category"] for c in failure_cases(self._mixed_failures(), n=6)}
        self.assertIn("confusable_pair", categories)
        self.assertTrue(any(c.startswith("validation:") for c in categories))

    def test_failure_cases_never_exceed_what_exists(self):
        clean = run_condition(
            QueryAwareGenerator(), LABELS, make_rows(), PromptStrategy.ZERO_SHOT, DecodeConfig()
        )
        self.assertEqual(failure_cases(clean, n=6), [])

    def test_safety_findings_surface_credential_solicitation(self):
        unsafe = reply_json("lost_or_stolen_card", "Please provide your PIN.")
        gen = FakeGenerator(fallback=unsafe)
        rows = [{"query": "my card is lost", "gold_intent": "lost_or_stolen_card"}]
        cond = run_condition(gen, LABELS, rows, PromptStrategy.ZERO_SHOT, DecodeConfig())
        findings = safety_findings(cond)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["query"], "my card is lost")
        self.assertTrue(findings[0]["withheld"])

    def test_clean_run_has_no_safety_findings(self):
        cond = run_condition(
            QueryAwareGenerator(), LABELS, make_rows(), PromptStrategy.ZERO_SHOT, DecodeConfig()
        )
        self.assertEqual(safety_findings(cond), [])


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.cond = run_condition(
            QueryAwareGenerator(bad={"q::atm_support::0"}),
            LABELS,
            make_rows(per_intent=1),
            PromptStrategy.ZERO_SHOT,
            DecodeConfig(),
        )

    def test_payload_keeps_raw_text_of_every_attempt(self):
        payload = condition_payload(self.cond)
        repaired = [r for r in payload["rows"] if r["needed_repair"]]
        self.assertEqual(len(repaired), 1)
        raws = [a["raw"] for a in repaired[0]["attempts_raw"]]
        self.assertEqual(raws[0], "not json at all")
        self.assertTrue(repaired[0]["attempts_raw"][1]["is_repair"])

    def test_payload_records_gold_label_decode_and_meta(self):
        payload = condition_payload(self.cond)
        self.assertEqual(payload["strategy"], "zero_shot")
        self.assertEqual(payload["decode"]["strategy"], "greedy")
        self.assertIn("gold_intent", payload["rows"][0])
        self.assertEqual(payload["meta"]["n"], len(LABELS))

    def test_save_writes_valid_json_to_the_given_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = save_condition(self.cond, "e2_zero_shot", Path(tmp))
            self.assertEqual(path.name, "e2_zero_shot.json")
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(loaded["rows"]), len(LABELS))

    def test_slug_makes_grid_labels_file_safe(self):
        self.assertEqual(slug("top_k=50 temp=0.7"), "top_k_50_temp_0_7")
        self.assertEqual(slug("greedy"), "greedy")
        self.assertEqual(slug("???"), "run")

    def test_save_grid_writes_one_file_per_configuration_and_seed(self):
        grid = run_e3(
            QueryAwareGenerator(),
            LABELS,
            select_e3_subset(make_rows()),
            PromptStrategy.ZERO_SHOT,
            seeds=(7, 8),
        )
        with tempfile.TemporaryDirectory() as tmp:
            paths = save_grid(grid, directory=Path(tmp))
            expected = sum(len(g.runs) for g in grid)
            self.assertEqual(len(paths), expected)
            self.assertEqual(len({p.name for p in paths}), expected)
            self.assertTrue(all(p.exists() for p in paths))
            names = {p.name for p in paths}
            # Greedy runs once under the project seed; sampled configs once per seed.
            self.assertIn("e3_greedy_seed42.json", names)
            self.assertIn("e3_top_k_50_temp_0_7_seed7.json", names)
            self.assertIn("e3_top_k_50_temp_0_7_seed8.json", names)


class TestStrategyKwargs(unittest.TestCase):
    BANK = [("a", reply_json("card_arrival")), ("b", reply_json("atm_support"))]

    def test_few_shot_gets_the_whole_train_bank(self):
        kwargs = strategy_kwargs(PromptStrategy.FEW_SHOT, self.BANK)
        self.assertEqual(kwargs["examples"], self.BANK)
        self.assertEqual(kwargs["n_examples"], 2)

    def test_other_strategies_get_nothing(self):
        for strategy in (
            PromptStrategy.ZERO_SHOT,
            PromptStrategy.ROLE_CONTEXT,
            PromptStrategy.CONSTRAINT_BASED,
        ):
            self.assertEqual(strategy_kwargs(strategy, self.BANK), {})


if __name__ == "__main__":
    unittest.main()
