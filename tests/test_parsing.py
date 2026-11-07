"""Tests for output parsing."""

import unittest

from ipd.parsing import parse_action, parse_belief


class TestParseAction(unittest.TestCase):
    def test_json_ok(self):
        action, meta = parse_action('{"action": "D", "reasoning": "because"}')
        self.assertEqual(action, "D")
        self.assertEqual(meta["parse_status"], "ok")
        self.assertEqual(meta["reasoning"], "because")

    def test_lowercase_and_words(self):
        self.assertEqual(parse_action('{"action": "cooperate"}')[0], "C")
        self.assertEqual(parse_action('{"action": "defect"}')[0], "D")

    def test_fenced_json(self):
        action, meta = parse_action('Here you go:\n```json\n{"action": "C"}\n```')
        self.assertEqual(action, "C")
        self.assertEqual(meta["parse_status"], "ok")

    def test_prose_fallback(self):
        action, meta = parse_action('I will choose action: C to cooperate.')
        self.assertEqual(action, "C")
        self.assertEqual(meta["parse_status"], "fallback")

    def test_bare_letter_fallback(self):
        self.assertEqual(parse_action("Final answer: D")[0], "D")

    def test_unparseable_default(self):
        action, meta = parse_action("???", default="C")
        self.assertEqual(action, "C")
        self.assertEqual(meta["parse_status"], "failed")


class TestParseBelief(unittest.TestCase):
    def test_json_ok(self):
        value, meta = parse_belief('{"defect_probability": 0.35, "reasoning": "x"}')
        self.assertAlmostEqual(value, 0.35)
        self.assertEqual(meta["parse_status"], "ok")

    def test_probability_alias(self):
        self.assertAlmostEqual(parse_belief('{"probability": 0.6}')[0], 0.6)

    def test_percentage(self):
        value, meta = parse_belief("I estimate about 40%.")
        self.assertAlmostEqual(value, 0.40)
        self.assertEqual(meta["parse_status"], "fallback")

    def test_bare_number(self):
        self.assertAlmostEqual(parse_belief("my estimate is 0.72")[0], 0.72)

    def test_out_of_range_becomes_fraction(self):
        self.assertAlmostEqual(parse_belief("about 70 out of 100 -> 70")[0], 0.70)

    def test_none_when_no_number(self):
        value, meta = parse_belief("no idea")
        self.assertIsNone(value)
        self.assertEqual(meta["parse_status"], "failed")


if __name__ == "__main__":
    unittest.main()
