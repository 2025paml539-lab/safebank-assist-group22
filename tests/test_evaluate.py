"""
Evaluation metrics and failure analysis (E6).

Every metric is exercised against hand-built ``to_row()``-shaped records and
against real ``FakeGenerator``-driven pipeline output, so the whole of
``evaluate.py`` is verified with no model present - which is the point of the
seam. scikit-learn is required only for the macro-F1 assertions; the rest run
on stdlib plus pydantic.

Owner: Satya Prakash (E6)
"""

from __future__ import annotations

import unittest

from safebank import FakeGenerator, SafeBankPipeline
from safebank.evaluate import (
    EvalRecord,
    analyse_failures,
    confusion_counts,
    evaluate_run,
    flag_unsafe_responses,
    intent_accuracy,
    latency_and_cost,
    records_from_rows,
    schema_validity,
    self_consistency,
    tool_routing,
)
from safebank.schema import FailureKind


def row(
    *,
    ok=True,
    intent="card_arrival",
    confidence=0.8,
    attempts=1,
    needed_repair=False,
    first_failure=None,
    tool=None,
    tool_ok=None,
    escalated=False,
    latency_ms=12.0,
):
    """Build one PipelineResult.to_row()-shaped dict."""
    return {
        "query": "q",
        "ok": ok,
        "intent": intent,
        "confidence": confidence,
        "attempts": attempts,
        "needed_repair": needed_repair,
        "first_failure": first_failure,
        "tool": tool,
        "tool_ok": tool_ok,
        "escalated": escalated,
        "latency_ms": latency_ms,
    }


class TestRecordConstruction(unittest.TestCase):
    def test_correct_requires_valid_and_matching(self):
        r = EvalRecord("card_arrival", row(ok=True, intent="card_arrival"))
        self.assertTrue(r.correct)

    def test_wrong_intent_is_not_correct(self):
        r = EvalRecord("card_arrival", row(ok=True, intent="atm_support"))
        self.assertFalse(r.correct)

    def test_invalid_run_is_not_correct(self):
        r = EvalRecord("card_arrival", row(ok=False, intent=None))
        self.assertFalse(r.correct)

    def test_zip_length_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            records_from_rows([row(), row()], ["card_arrival"])


class TestIntentAccuracy(unittest.TestCase):
    def test_accuracy_counts_only_valid_matches(self):
        records = [
            EvalRecord("card_arrival", row(intent="card_arrival")),
            EvalRecord("atm_support", row(intent="atm_support")),
            EvalRecord("card_arrival", row(intent="atm_support")),
            EvalRecord("card_arrival", row(ok=False, intent=None)),
        ]
        rep = intent_accuracy(records)
        self.assertEqual(rep.n, 4)
        self.assertEqual(rep.n_correct, 2)
        self.assertAlmostEqual(rep.accuracy, 0.5)

    def test_macro_f1_is_between_zero_and_one(self):
        records = [
            EvalRecord("card_arrival", row(intent="card_arrival")),
            EvalRecord("atm_support", row(intent="atm_support")),
            EvalRecord("atm_support", row(intent="card_arrival")),
        ]
        rep = intent_accuracy(records)
        self.assertGreaterEqual(rep.macro_f1, 0.0)
        self.assertLessEqual(rep.macro_f1, 1.0)

    def test_perfect_predictions_give_f1_one(self):
        records = [
            EvalRecord("card_arrival", row(intent="card_arrival")),
            EvalRecord("atm_support", row(intent="atm_support")),
        ]
        self.assertAlmostEqual(intent_accuracy(records).macro_f1, 1.0)

    def test_empty_records_rejected(self):
        with self.assertRaises(ValueError):
            intent_accuracy([])

    def test_confusion_counts_records_mismatches(self):
        records = [
            EvalRecord("card_arrival", row(intent="card_delivery_estimate")),
            EvalRecord("card_arrival", row(intent="card_arrival")),
        ]
        counts = confusion_counts(records)
        self.assertEqual(counts[("card_arrival", "card_delivery_estimate")], 1)


class TestSchemaValidity(unittest.TestCase):
    def test_splits_first_attempt_and_repaired(self):
        records = [
            EvalRecord("card_arrival", row(ok=True, needed_repair=False)),
            EvalRecord("card_arrival", row(ok=True, needed_repair=True)),
            EvalRecord("card_arrival", row(ok=False, intent=None)),
        ]
        rep = schema_validity(records)
        self.assertEqual(rep.valid_final, 2)
        self.assertEqual(rep.valid_first_attempt, 1)
        self.assertEqual(rep.repaired, 1)

    def test_repair_lift_is_final_minus_first(self):
        records = [
            EvalRecord("card_arrival", row(ok=True, needed_repair=True)),
            EvalRecord("card_arrival", row(ok=True, needed_repair=False)),
        ]
        rep = schema_validity(records)
        self.assertAlmostEqual(rep.final_rate, 1.0)
        self.assertAlmostEqual(rep.first_attempt_rate, 0.5)
        self.assertAlmostEqual(rep.repair_lift, 0.5)


class TestToolRouting(unittest.TestCase):
    def test_correct_routing(self):
        records = [
            EvalRecord("card_arrival", row(intent="card_arrival", tool="check_card_delivery_status")),
        ]
        rep = tool_routing(records)
        self.assertEqual(rep.n_should_call, 1)
        self.assertEqual(rep.n_routed_correctly, 1)
        self.assertAlmostEqual(rep.routing_accuracy, 1.0)

    def test_missed_tool_when_none_ran(self):
        records = [EvalRecord("card_arrival", row(intent="card_arrival", tool=None))]
        rep = tool_routing(records)
        self.assertEqual(rep.n_missed, 1)

    def test_wrong_tool_when_other_ran(self):
        records = [
            EvalRecord("card_arrival", row(intent="atm_support", tool="find_branch")),
        ]
        rep = tool_routing(records)
        self.assertEqual(rep.n_wrong_tool, 1)

    def test_spurious_tool_for_text_only_intent(self):
        # transfer_timing routes to no tool.
        records = [
            EvalRecord("transfer_timing", row(intent="atm_support", tool="find_branch")),
        ]
        rep = tool_routing(records)
        self.assertEqual(rep.n_spurious, 1)
        self.assertEqual(rep.n_should_call, 0)

    def test_accuracy_is_one_when_nothing_should_call(self):
        records = [EvalRecord("transfer_timing", row(intent="transfer_timing", tool=None))]
        self.assertAlmostEqual(tool_routing(records).routing_accuracy, 1.0)

    def test_withheld_destructive_call_is_not_a_miss(self):
        """
        lost_or_stolen_card routes to block_card (destructive). The pipeline
        escalates instead of auto-executing, so tool is None + escalated=True.
        That is the responsible-use control working, not a routing failure.
        """
        records = [
            EvalRecord(
                "lost_or_stolen_card",
                row(intent="lost_or_stolen_card", tool=None, escalated=True),
            )
        ]
        rep = tool_routing(records)
        self.assertEqual(rep.n_correctly_withheld, 1)
        self.assertEqual(rep.n_missed, 0)
        self.assertAlmostEqual(rep.routing_accuracy, 1.0)

    def test_all_destructive_intents_correct_score_full_accuracy(self):
        """
        The exact scenario from review: every intent predicted correctly,
        including the three that route to block_card. Routing accuracy must be
        1.0, not capped at 0.25.
        """
        records = [
            EvalRecord("card_arrival", row(intent="card_arrival", tool="check_card_delivery_status")),
            EvalRecord("lost_or_stolen_card", row(intent="lost_or_stolen_card", tool=None, escalated=True)),
            EvalRecord("compromised_card", row(intent="compromised_card", tool=None, escalated=True)),
            EvalRecord("card_swallowed", row(intent="card_swallowed", tool=None, escalated=True)),
        ]
        rep = tool_routing(records)
        self.assertEqual(rep.n_should_call, 4)
        self.assertEqual(rep.n_routed_correctly, 1)
        self.assertEqual(rep.n_correctly_withheld, 3)
        self.assertEqual(rep.n_missed, 0)
        self.assertAlmostEqual(rep.routing_accuracy, 1.0)

    def test_destructive_intent_without_escalation_is_still_a_miss(self):
        """
        A destructive route with no tool AND no escalation is a genuine miss -
        the withholding credit requires the escalation flag, so a dropped call
        cannot hide behind the destructive exemption.
        """
        records = [
            EvalRecord(
                "lost_or_stolen_card",
                row(intent="lost_or_stolen_card", tool=None, escalated=False),
            )
        ]
        rep = tool_routing(records)
        self.assertEqual(rep.n_correctly_withheld, 0)
        self.assertEqual(rep.n_missed, 1)

    def test_non_destructive_missed_call_is_not_credited_as_withheld(self):
        """A withheld NON-destructive call (e.g. low-confidence escalation on
        card_arrival) is a real miss, not a safety withholding."""
        records = [
            EvalRecord(
                "card_arrival",
                row(intent="card_arrival", tool=None, escalated=True),
            )
        ]
        rep = tool_routing(records)
        self.assertEqual(rep.n_correctly_withheld, 0)
        self.assertEqual(rep.n_missed, 1)


class TestToolRoutingAgainstRealPipeline(unittest.TestCase):
    """Drive the pipeline into a real destructive refusal and score it."""

    def test_pipeline_destructive_refusal_scores_as_withheld(self):
        # Script a valid response whose intent routes to block_card. The
        # pipeline must refuse to auto-execute and escalate.
        scripted = [
            '{"intent": "lost_or_stolen_card", "confidence": 0.9, '
            '"response": "I can help secure your card.", "tool_call": '
            '{"name": "block_card", "args": {"account_id": "ACC_SIM_0001", '
            '"reason": "lost"}}, "requires_human": false}'
        ]
        gen = FakeGenerator(scripted=scripted)
        pipe = SafeBankPipeline(gen, ["lost_or_stolen_card", "card_arrival"])
        result = pipe.run("my card was stolen")
        row_dict = result.to_row()
        # Confirm the pipeline actually withheld and escalated.
        self.assertIsNone(row_dict["tool"])
        self.assertTrue(row_dict["escalated"])
        # The metric must read that as a correct withholding, not a miss.
        rep = tool_routing([EvalRecord("lost_or_stolen_card", row_dict)])
        self.assertEqual(rep.n_correctly_withheld, 1)
        self.assertEqual(rep.n_missed, 0)
        self.assertAlmostEqual(rep.routing_accuracy, 1.0)


class TestResponseSafety(unittest.TestCase):
    def test_flags_invented_balance(self):
        replies = [
            "Your balance is £4,210.00.",
            "Let me check the delivery status of your card.",
        ]
        self.assertEqual(flag_unsafe_responses(replies), [0])

    def test_safe_replies_are_not_flagged(self):
        replies = ["I will look into that and a colleague will follow up."]
        self.assertEqual(flag_unsafe_responses(replies), [])

    def test_matching_is_case_insensitive(self):
        self.assertEqual(flag_unsafe_responses(["I HAVE BLOCKED your card"]), [0])


class TestLatencyAndCost(unittest.TestCase):
    def test_summarises_latency_and_attempts(self):
        records = [
            EvalRecord("card_arrival", row(latency_ms=10.0, attempts=1)),
            EvalRecord("card_arrival", row(latency_ms=20.0, attempts=2)),
            EvalRecord("card_arrival", row(latency_ms=30.0, attempts=1, escalated=True)),
        ]
        rep = latency_and_cost(records)
        self.assertAlmostEqual(rep.mean_latency_ms, 20.0)
        self.assertAlmostEqual(rep.mean_attempts, 4 / 3)
        self.assertAlmostEqual(rep.escalation_rate, 1 / 3)

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            latency_and_cost([])


class TestSelfConsistency(unittest.TestCase):
    def test_full_agreement(self):
        preds = [["card_arrival", "card_arrival", "card_arrival"]]
        rep = self_consistency(preds)
        self.assertAlmostEqual(rep.mean_agreement, 1.0)
        self.assertAlmostEqual(rep.fully_stable_fraction, 1.0)

    def test_partial_agreement(self):
        preds = [["card_arrival", "card_arrival", "atm_support"]]
        rep = self_consistency(preds)
        self.assertAlmostEqual(rep.mean_agreement, 2 / 3)
        self.assertAlmostEqual(rep.fully_stable_fraction, 0.0)

    def test_none_predictions_count_as_a_label(self):
        preds = [[None, None, "card_arrival"]]
        rep = self_consistency(preds)
        self.assertAlmostEqual(rep.mean_agreement, 2 / 3)

    def test_uneven_run_counts_rejected(self):
        with self.assertRaises(ValueError):
            self_consistency([["a", "a"], ["b"]])

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            self_consistency([])


class TestFailureAnalysis(unittest.TestCase):
    def test_counts_validation_failure_kinds(self):
        records = [
            EvalRecord("card_arrival", row(ok=False, intent=None, first_failure=FailureKind.NO_JSON_FOUND.value)),
            EvalRecord("card_arrival", row(ok=False, intent=None, first_failure=FailureKind.UNKNOWN_INTENT.value)),
        ]
        analysis = analyse_failures(records)
        self.assertEqual(analysis.failure_kind_counts[FailureKind.NO_JSON_FOUND.value], 1)
        self.assertEqual(analysis.failure_kind_counts[FailureKind.UNKNOWN_INTENT.value], 1)

    def test_flags_confusable_pair_misclassification(self):
        # card_arrival <-> card_delivery_estimate is a declared confusable pair.
        records = [
            EvalRecord("card_arrival", row(ok=True, intent="card_delivery_estimate")),
        ]
        analysis = analyse_failures(records)
        self.assertEqual(len(analysis.cases), 1)
        self.assertTrue(analysis.cases[0].is_confusable_pair)

    def test_correct_runs_produce_no_cases(self):
        records = [EvalRecord("card_arrival", row(ok=True, intent="card_arrival"))]
        self.assertEqual(analyse_failures(records).cases, [])

    def test_as_dict_is_serialisable_shape(self):
        records = [
            EvalRecord("card_arrival", row(ok=False, intent=None, first_failure=FailureKind.MALFORMED_JSON.value)),
        ]
        d = analyse_failures(records).as_dict()
        self.assertIn("failure_kind_counts", d)
        self.assertIn("cases", d)


class TestEvaluateRunSummary(unittest.TestCase):
    def test_summary_carries_every_metric_family(self):
        records = [
            EvalRecord("card_arrival", row(intent="card_arrival", tool="check_card_delivery_status")),
            EvalRecord("atm_support", row(intent="atm_support", tool="find_branch")),
        ]
        summary = evaluate_run(records)
        for key in ("accuracy", "macro_f1", "schema_final_rate", "tool_routing_accuracy", "mean_latency_ms"):
            self.assertIn(key, summary)

    def test_summary_without_macro_f1(self):
        records = [EvalRecord("card_arrival", row(intent="card_arrival"))]
        summary = evaluate_run(records, with_macro_f1=False)
        self.assertNotIn("macro_f1", summary)
        self.assertIn("accuracy", summary)


class TestAgainstRealPipelineOutput(unittest.TestCase):
    """End-to-end: drive the pipeline with FakeGenerator, evaluate its rows."""

    def _intents(self):
        return ["card_arrival", "atm_support", "transfer_timing"]

    def test_metrics_run_on_pipeline_rows(self):
        gen = FakeGenerator()  # default completion predicts card_arrival + tool
        pipe = SafeBankPipeline(gen, self._intents())
        rows = [pipe.run("where is my card").to_row() for _ in range(3)]
        records = records_from_rows(rows, ["card_arrival", "card_arrival", "card_arrival"])

        acc = intent_accuracy(records)
        self.assertEqual(acc.n, 3)
        self.assertEqual(acc.n_correct, 3)

        validity = schema_validity(records)
        self.assertEqual(validity.valid_final, 3)

        routing = tool_routing(records)
        self.assertEqual(routing.n_routed_correctly, 3)

    def test_repair_path_is_measured(self):
        """A malformed first completion should show up as repaired, still valid."""
        gen = FakeGenerator(
            scripted=[
                "not json at all",  # first attempt fails -> triggers repair
            ]
        )
        pipe = SafeBankPipeline(gen, self._intents())
        result = pipe.run("where is my card")
        record = EvalRecord("card_arrival", result.to_row())
        rep = schema_validity([record])
        # It recovered via the repair loop, so it is valid but needed repair.
        self.assertTrue(record.ok)
        self.assertEqual(rep.repaired, 1)
        self.assertEqual(rep.valid_first_attempt, 0)


if __name__ == "__main__":
    unittest.main()
