"""Ranking-point tests, including tie averaging."""

import unittest

from ranked_tournament.scoring import ranking_points


class TestRankingPoints(unittest.TestCase):
    def test_clear_ranking(self):
        points = ranking_points({"A": 40, "B": 30, "C": 20, "D": 10})
        self.assertEqual(points, {"A": 3.0, "B": 2.0, "C": 1.0, "D": 0.0})

    def test_two_tied_for_first(self):
        points = ranking_points({"A": 40, "B": 40, "C": 20, "D": 10})
        self.assertEqual(points["A"], 2.5)
        self.assertEqual(points["B"], 2.5)
        self.assertEqual(points["C"], 1.0)
        self.assertEqual(points["D"], 0.0)

    def test_two_tied_for_second(self):
        points = ranking_points({"A": 50, "B": 30, "C": 30, "D": 10})
        self.assertEqual(points["A"], 3.0)
        self.assertEqual(points["B"], 1.5)
        self.assertEqual(points["C"], 1.5)
        self.assertEqual(points["D"], 0.0)

    def test_three_way_tie_for_first(self):
        points = ranking_points({"A": 20, "B": 20, "C": 20, "D": 10})
        self.assertEqual(points["A"], 2.0)
        self.assertEqual(points["B"], 2.0)
        self.assertEqual(points["C"], 2.0)
        self.assertEqual(points["D"], 0.0)

    def test_all_tied(self):
        points = ranking_points({"A": 10, "B": 10, "C": 10, "D": 10})
        for value in points.values():
            self.assertEqual(value, 1.5)

    def test_points_sum_is_conserved(self):
        payoffs = {"A": 40, "B": 40, "C": 20, "D": 10}
        points = ranking_points(payoffs)
        self.assertAlmostEqual(sum(points.values()), 6.0)

    def test_wrong_number_of_point_values(self):
        with self.assertRaises(ValueError):
            ranking_points({"A": 1, "B": 2}, (3, 2, 1, 0))


if __name__ == "__main__":
    unittest.main()
