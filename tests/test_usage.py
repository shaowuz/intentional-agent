"""Tests for usage tracking and cost reporting."""

import unittest

from ipd.usage import LLMResponse, UsageTracker


def _resp(input_tokens=1000, output_tokens=1000):
    return LLMResponse(
        text="x",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model="m",
        provider="p",
    )


class TestUsageTracker(unittest.TestCase):
    def test_unconfigured_pricing_is_flagged_not_silently_zero(self):
        tracker = UsageTracker()
        tracker.log("a", "action", _resp())
        summary = tracker.summary()
        self.assertFalse(summary["pricing_configured"])
        self.assertEqual(summary["estimated_cost_usd"], 0.0)
        self.assertIn("cost_note", summary)
        self.assertIn("pricing not configured", summary["cost_note"])

    def test_configured_pricing_computes_cost(self):
        tracker = UsageTracker(input_per_1k=1.0, output_per_1k=2.0)
        tracker.log("a", "action", _resp(input_tokens=1000, output_tokens=1000))
        summary = tracker.summary()
        self.assertTrue(summary["pricing_configured"])
        self.assertAlmostEqual(summary["estimated_cost_usd"], 3.0)
        self.assertNotIn("cost_note", summary)

    def test_no_tokens_no_cost_note(self):
        tracker = UsageTracker()
        summary = tracker.summary()
        self.assertFalse(summary["pricing_configured"])
        self.assertNotIn("cost_note", summary)


if __name__ == "__main__":
    unittest.main()
