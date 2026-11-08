"""Structured-output parsing tests for the ranked tournament."""

import unittest

from ranked_tournament.parsing import (
    parse_action_strict,
    parse_reflection_strict,
)


class TestRankedActionParsing(unittest.TestCase):
    def test_valid_json(self):
        action, meta = parse_action_strict(
            '{"action": "D", "reasoning": "because"}'
        )
        self.assertEqual(action, "D")
        self.assertEqual(meta["parse_status"], "ok")
        self.assertEqual(meta["reasoning"], "because")

    def test_fenced_json(self):
        action, meta = parse_action_strict(
            'Here:\n```json\n{"action": "C"}\n```'
        )
        self.assertEqual(action, "C")
        self.assertEqual(meta["parse_status"], "ok")

    def test_words_accepted(self):
        self.assertEqual(
            parse_action_strict('{"action": "cooperate"}')[0], "C"
        )
        self.assertEqual(parse_action_strict('{"action": "defect"}')[0], "D")

    def test_prose_rejected_for_structured_run(self):
        action, meta = parse_action_strict("I will cooperate.")
        self.assertIsNone(action)
        self.assertEqual(meta["parse_status"], "failed")

    def test_invalid_value_rejected(self):
        action, meta = parse_action_strict('{"action": "maybe"}')
        self.assertIsNone(action)
        self.assertEqual(meta["parse_status"], "failed")


class TestRankedReflectionParsing(unittest.TestCase):
    def test_valid_reflection(self):
        parsed, meta = parse_reflection_strict(
            '{"change_strategy": true, "reason": "r", '
            '"strategy_for_next_round": "s"}'
        )
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed["change_strategy"])
        self.assertEqual(parsed["reason"], "r")
        self.assertEqual(parsed["strategy_for_next_round"], "s")
        self.assertEqual(meta["parse_status"], "ok")

    def test_string_boolean_accepted(self):
        parsed, _ = parse_reflection_strict(
            '{"change_strategy": "false", "reason": "r", '
            '"strategy_for_next_round": "s"}'
        )
        self.assertFalse(parsed["change_strategy"])

    def test_missing_strategy_rejected(self):
        parsed, meta = parse_reflection_strict(
            '{"change_strategy": false, "reason": "r"}'
        )
        self.assertIsNone(parsed)
        self.assertEqual(meta["parse_status"], "failed")

    def test_empty_strategy_rejected(self):
        parsed, _ = parse_reflection_strict(
            '{"change_strategy": false, "reason": "r", '
            '"strategy_for_next_round": "  "}'
        )
        self.assertIsNone(parsed)

    def test_missing_change_flag_rejected(self):
        parsed, _ = parse_reflection_strict(
            '{"reason": "r", "strategy_for_next_round": "s"}'
        )
        self.assertIsNone(parsed)


if __name__ == "__main__":
    unittest.main()
