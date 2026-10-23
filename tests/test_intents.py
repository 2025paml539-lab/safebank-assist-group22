"""
Label-space integrity and the E6 focus subset.

Scope note
----------
The authoritative 77 BANKING77 names are read from the dataset at load time,
not hardcoded, so these tests cannot check the focus names against the real
dataset without ``datasets`` installed (it is deliberately absent). What they
*can* and do lock down is the structure the report claims - 5 themes of 4, 20
unique focus intents, confusable pairs drawn from that subset - plus the
behaviour of the guard that will catch a name typo the moment Vishruth's
``data_prep.py`` supplies the real label space.

Owner: Kishore
"""

from __future__ import annotations

import unittest

from safebank import config
from safebank.intents import (
    CONFUSABLE_PAIRS,
    FOCUS_INTENTS,
    INTENT_THEMES,
    LabelSpaceError,
    theme_of,
    validate_label_space,
)

#: A synthetic 77-label space: the 20 real focus names plus filler. Stands in
#: for the dataset's own label list so the guard can be tested offline.
SYNTHETIC_LABELS = list(FOCUS_INTENTS) + [
    f"other_intent_{i:02d}" for i in range(config.EXPECTED_N_INTENTS - len(FOCUS_INTENTS))
]


class TestThemeStructure(unittest.TestCase):
    def test_five_themes(self):
        self.assertEqual(len(INTENT_THEMES), 5)

    def test_four_intents_per_theme(self):
        for theme, members in INTENT_THEMES.items():
            self.assertEqual(len(members), 4, theme)

    def test_focus_set_is_twenty(self):
        self.assertEqual(len(FOCUS_INTENTS), 20)

    def test_focus_intents_are_unique(self):
        """A duplicate would silently shrink the E6 analysis set."""
        self.assertEqual(len(FOCUS_INTENTS), len(set(FOCUS_INTENTS)))

    def test_focus_set_is_exactly_the_flattened_themes(self):
        flattened = [i for members in INTENT_THEMES.values() for i in members]
        self.assertEqual(list(FOCUS_INTENTS), flattened)

    def test_no_intent_appears_in_two_themes(self):
        seen: set[str] = set()
        for members in INTENT_THEMES.values():
            for intent in members:
                self.assertNotIn(intent, seen, intent)
                seen.add(intent)


class TestThemeLookup(unittest.TestCase):
    def test_known_intent_resolves_to_its_theme(self):
        self.assertEqual(theme_of("card_arrival"), "card_delivery")
        self.assertEqual(theme_of("atm_support"), "cash_atm")

    def test_unknown_intent_returns_none(self):
        self.assertIsNone(theme_of("not_an_intent"))

    def test_every_focus_intent_has_a_theme(self):
        for intent in FOCUS_INTENTS:
            self.assertIsNotNone(theme_of(intent), intent)


class TestConfusablePairs(unittest.TestCase):
    """These pairs are the backbone of the E6 root-cause table."""

    def test_at_least_three_pairs(self):
        self.assertGreaterEqual(len(CONFUSABLE_PAIRS), 3)

    def test_both_members_are_focus_intents(self):
        for pair in CONFUSABLE_PAIRS:
            self.assertIn(pair.first, FOCUS_INTENTS, pair.first)
            self.assertIn(pair.second, FOCUS_INTENTS, pair.second)

    def test_pairs_are_not_self_referential(self):
        for pair in CONFUSABLE_PAIRS:
            self.assertNotEqual(pair.first, pair.second)

    def test_every_pair_states_a_reason(self):
        """The brief forbids unexplained claims; each confusion needs a cause."""
        for pair in CONFUSABLE_PAIRS:
            self.assertGreater(len(pair.reason.strip()), 30, pair)

    def test_pairs_are_unique(self):
        keys = {frozenset((p.first, p.second)) for p in CONFUSABLE_PAIRS}
        self.assertEqual(len(keys), len(CONFUSABLE_PAIRS))

    def test_pairs_are_immutable(self):
        import dataclasses

        with self.assertRaises(dataclasses.FrozenInstanceError):
            CONFUSABLE_PAIRS[0].first = "something_else"


class TestValidateLabelSpace(unittest.TestCase):
    def test_accepts_a_correct_label_space(self):
        report = validate_label_space(SYNTHETIC_LABELS)
        self.assertTrue(report.ok)
        self.assertEqual(report.n_intents, config.EXPECTED_N_INTENTS)
        self.assertEqual(report.missing_focus_intents, ())

    def test_rejects_wrong_intent_count(self):
        with self.assertRaises(LabelSpaceError) as ctx:
            validate_label_space(SYNTHETIC_LABELS[:50])
        self.assertIn("expected 77", str(ctx.exception))

    def test_rejects_missing_focus_intent(self):
        """A typo in a focus name must fail loudly, not skew E6 silently."""
        labels = [l for l in SYNTHETIC_LABELS if l != "card_arrival"] + ["filler_extra"]
        with self.assertRaises(LabelSpaceError) as ctx:
            validate_label_space(labels)
        self.assertIn("card_arrival", str(ctx.exception))

    def test_non_strict_mode_reports_instead_of_raising(self):
        report = validate_label_space(SYNTHETIC_LABELS[:50], strict=False)
        self.assertFalse(report.ok)
        self.assertEqual(report.n_intents, 50)

    def test_report_lists_the_missing_names(self):
        labels = [l for l in SYNTHETIC_LABELS if l != "atm_support"]
        report = validate_label_space(labels, strict=False)
        self.assertIn("atm_support", report.missing_focus_intents)

    def test_expected_count_matches_config(self):
        """Guards the claim 'all 77 intents' made throughout the report."""
        self.assertEqual(config.EXPECTED_N_INTENTS, 77)


if __name__ == "__main__":
    unittest.main()
