"""
Sampling and example-bank logic in ``data_prep``, tested offline.

``load_banking77`` itself needs ``datasets`` and the network, so it is covered
by the Colab notebook run, not here. Everything downstream of it is duck-typed
against the split, so a tiny in-memory stand-in exercises the real logic: the
stratified 5-per-intent sample, its determinism, the train-only example bank
and its contamination guard.

Owner: Vishruth
"""

from __future__ import annotations

import json
import unittest

from safebank import config, tools
from safebank.data_prep import (
    build_eval_sample,
    build_example_bank,
    class_distribution,
    dataset_label_space,
    expected_json,
    preprocessing_record,
)
from safebank.intents import FOCUS_INTENTS, validate_label_space
from safebank.prompts import build_few_shot_prompt
from safebank.schema import parse_response

#: 77 names: every intent the tool router knows, the focus set, then filler.
LABELS = list(dict.fromkeys([*tools.INTENT_TO_TOOL, *FOCUS_INTENTS]))
LABELS += [f"other_intent_{i:02d}" for i in range(config.EXPECTED_N_INTENTS - len(LABELS))]


class _Names:
    def __init__(self, names):
        self.names = names


class FakeSplit:
    """Minimal stand-in for ``datasets.Dataset``: column access + features."""

    def __init__(self, rows_per_label: int, labels=LABELS, tag: str = "q"):
        self.features = {"label": _Names(list(labels))}
        self._cols = {"text": [], "label": []}
        for label_id, name in enumerate(labels):
            for j in range(rows_per_label):
                self._cols["text"].append(f"{tag} {name} #{j}")
                self._cols["label"].append(label_id)

    def __getitem__(self, column):
        return list(self._cols[column])


class TestLabelSpace(unittest.TestCase):
    def test_reads_names_from_features(self):
        self.assertEqual(dataset_label_space(FakeSplit(1)), LABELS)

    def test_rejects_wrong_count(self):
        with self.assertRaises(ValueError):
            dataset_label_space(FakeSplit(1, labels=LABELS[:76]))

    def test_synthetic_space_passes_guard(self):
        self.assertTrue(validate_label_space(LABELS).ok)

    def test_class_distribution(self):
        dist = class_distribution(FakeSplit(3), LABELS)
        self.assertEqual(len(dist), 77)
        self.assertEqual(set(dist.values()), {3})


class TestEvalSample(unittest.TestCase):
    def setUp(self):
        self.split = FakeSplit(40, tag="test")

    def test_385_rows_five_per_intent(self):
        rows = build_eval_sample(self.split, LABELS)
        self.assertEqual(len(rows), 385)
        counts = {}
        for r in rows:
            counts[r["gold_intent"]] = counts.get(r["gold_intent"], 0) + 1
        self.assertEqual(set(counts), set(LABELS))
        self.assertEqual(set(counts.values()), {config.EVAL_EXAMPLES_PER_INTENT})

    def test_row_shape(self):
        row = build_eval_sample(self.split, LABELS)[0]
        self.assertEqual(set(row), {"query", "gold_intent"})

    def test_query_matches_its_gold_label(self):
        for r in build_eval_sample(self.split, LABELS):
            self.assertIn(f" {r['gold_intent']} #", r["query"])

    def test_deterministic_under_seed(self):
        self.assertEqual(
            build_eval_sample(self.split, LABELS), build_eval_sample(self.split, LABELS)
        )

    def test_seed_changes_sample(self):
        self.assertNotEqual(
            build_eval_sample(self.split, LABELS, seed=1),
            build_eval_sample(self.split, LABELS, seed=2),
        )

    def test_too_few_rows_raises(self):
        with self.assertRaises(ValueError):
            build_eval_sample(FakeSplit(config.EVAL_EXAMPLES_PER_INTENT - 1), LABELS)


class TestExampleBank(unittest.TestCase):
    def setUp(self):
        self.train = FakeSplit(10, tag="train")

    def test_size_and_train_origin(self):
        bank = build_example_bank(self.train, LABELS, n=4)
        self.assertEqual(len(bank), 4)
        for query, _ in bank:
            self.assertTrue(query.startswith("train "))

    def test_covers_every_routing_outcome(self):
        bank = build_example_bank(self.train, LABELS, n=4)
        routes = {tools.route_intent(json.loads(j)["intent"]) for _, j in bank}
        self.assertEqual(
            routes,
            {
                tools.ToolName.CHECK_CARD_DELIVERY_STATUS,
                tools.ToolName.FIND_BRANCH,
                tools.ToolName.BLOCK_CARD,
                None,
            },
        )

    def test_distinct_intents(self):
        bank = build_example_bank(self.train, LABELS, n=8)
        intents = [json.loads(j)["intent"] for _, j in bank]
        self.assertEqual(len(intents), len(set(intents)))

    def test_deterministic(self):
        self.assertEqual(
            build_example_bank(self.train, LABELS), build_example_bank(self.train, LABELS)
        )

    def test_exclude_blocks_contamination(self):
        everything = set(self.train["text"])
        keep = {t for t in everything if t.endswith("#9")}
        bank = build_example_bank(self.train, LABELS, n=4, exclude=everything - keep)
        for query, _ in bank:
            self.assertTrue(query.endswith("#9"))

    def test_exclude_everything_raises(self):
        with self.assertRaises(ValueError):
            build_example_bank(self.train, LABELS, exclude=set(self.train["text"]))

    def test_non_positive_n_raises(self):
        with self.assertRaises(ValueError):
            build_example_bank(self.train, LABELS, n=0)

    def test_feeds_few_shot_prompt(self):
        bank = build_example_bank(self.train, LABELS)
        prompt = build_few_shot_prompt("where is my card", LABELS, examples=bank)
        for query, _ in bank:
            self.assertIn(query, prompt)


class TestExpectedJson(unittest.TestCase):
    """Every worked example must itself pass the E4 contract."""

    def test_every_intent_validates(self):
        for intent in LABELS:
            outcome = parse_response(expected_json(intent), LABELS)
            self.assertTrue(outcome.ok, f"{intent}: {outcome.summary()}")

    def test_destructive_intent_escalates_without_tool_call(self):
        payload = json.loads(expected_json("lost_or_stolen_card"))
        self.assertIsNone(payload["tool_call"])
        self.assertTrue(payload["requires_human"])

    def test_tool_intent_requests_routed_tool(self):
        payload = json.loads(expected_json("card_arrival"))
        self.assertEqual(payload["tool_call"]["name"], "check_card_delivery_status")
        self.assertFalse(payload["requires_human"])

    def test_text_only_intent_has_no_tool(self):
        payload = json.loads(expected_json(LABELS[-1]))
        self.assertIsNone(payload["tool_call"])


class TestPreprocessingRecord(unittest.TestCase):
    def test_static_fields(self):
        rec = preprocessing_record()
        self.assertEqual(rec["dataset_id"], config.DATASET_ID)
        self.assertEqual(rec["seed"], config.SEED)
        self.assertEqual(rec["eval_rows_total"], 385)
        self.assertTrue(rec["preprocessing"])

    def test_measured_fields(self):
        train, test = FakeSplit(10, tag="train"), FakeSplit(40, tag="test")
        rows = build_eval_sample(test, LABELS)
        rec = preprocessing_record(train, test, rows)
        self.assertEqual(rec["split_sizes"], {"train": 770, "test": 3080})
        self.assertEqual(rec["texts_in_both_splits"], 0)
        self.assertEqual(rec["eval_rows_actual"], 385)
        self.assertEqual(rec["eval_intents_covered"], 77)
        json.dumps(rec)  # must be serialisable for the results folder


if __name__ == "__main__":
    unittest.main()
