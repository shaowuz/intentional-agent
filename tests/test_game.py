"""Tests for the payoff matrix and game configuration."""

import unittest

from ipd.game import (
    ACTIONS,
    PAYOFF_MATRIX,
    horizon_system_description,
    payoff,
)


class TestPayoff(unittest.TestCase):
    def test_matrix_values(self):
        self.assertEqual(payoff("C", "C"), 3)
        self.assertEqual(payoff("C", "D"), 0)
        self.assertEqual(payoff("D", "C"), 5)
        self.assertEqual(payoff("D", "D"), 1)

    def test_full_matrix(self):
        expected = {
            ("C", "C"): 3,
            ("C", "D"): 0,
            ("D", "C"): 5,
            ("D", "D"): 1,
        }
        self.assertEqual(PAYOFF_MATRIX, expected)

    def test_zero_sum_symmetry_of_joint_outcome(self):
        # Each of these joint outcomes sums to the same total (6) except DD.
        self.assertEqual(payoff("C", "C") + payoff("C", "C"), 6)
        self.assertEqual(payoff("C", "D") + payoff("D", "C"), 5)
        self.assertEqual(payoff("D", "D") + payoff("D", "D"), 2)

    def test_invalid_action_raises(self):
        with self.assertRaises(ValueError):
            payoff("X", "C")
        with self.assertRaises(ValueError):
            payoff("C", "Y")

    def test_actions(self):
        self.assertEqual(set(ACTIONS), {"C", "D"})

    def test_horizon_descriptions(self):
        fixed = horizon_system_description("fixed", 20, 0.95)
        self.assertIn("FIXED", fixed)
        self.assertIn("20", fixed)
        rand = horizon_system_description("random", 20, 0.95)
        self.assertIn("RANDOM", rand)
        self.assertIn("0.95", rand)
        with self.assertRaises(ValueError):
            horizon_system_description("unknown", 20, 0.95)


if __name__ == "__main__":
    unittest.main()
