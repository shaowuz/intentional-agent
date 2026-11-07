"""Tests for strategy classification, including tie (indistinguishability) handling."""

import unittest

from ipd.analysis import classify_strategy


class TestStrategyClassifier(unittest.TestCase):
    def test_tie_when_opponent_always_cooperates(self):
        own = ["C"] * 12
        opp = ["C"] * 12
        label, scores = classify_strategy(own, opp)
        self.assertTrue(label.startswith("Tie:"), label)
        for strategy in [
            "Always Cooperate",
            "Tit-for-Tat",
            "Grim Trigger",
            "Tit-for-Two-Tats (Forgiving)",
        ]:
            self.assertIn(strategy, label)
        # All tied strategies must share the maximal score.
        best = max(scores.values())
        for strategy in [
            "Always Cooperate",
            "Tit-for-Tat",
            "Grim Trigger",
            "Tit-for-Two-Tats (Forgiving)",
        ]:
            self.assertAlmostEqual(scores[strategy], best)

    def test_single_label_when_unambiguous_always_defect(self):
        own = ["D"] * 12
        opp = ["C"] * 12
        label, scores = classify_strategy(own, opp)
        self.assertEqual(label, "Always Defect")
        self.assertAlmostEqual(scores["Always Defect"], 1.0)

    def test_tie_among_defecting_strategies(self):
        own = ["D"] * 12
        opp = ["D"] * 12
        label, scores = classify_strategy(own, opp)
        self.assertTrue(label.startswith("Tie:"), label)
        for strategy in ["Always Defect", "Tit-for-Tat", "Grim Trigger"]:
            self.assertIn(strategy, label)

    def test_too_few_rounds_is_mixed(self):
        label, scores = classify_strategy(["C", "D", "C"], ["C", "D", "C"])
        self.assertEqual(label, "Mixed/Other")
        self.assertEqual(scores, {})


if __name__ == "__main__":
    unittest.main()
