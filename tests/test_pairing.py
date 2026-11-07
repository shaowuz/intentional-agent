"""Tests for pairing schedules."""

import unittest

from ipd.pairing import (
    PairingManager,
    build_round_robin_schedule,
    random_pairing,
)


def _assert_perfect_matching(test, pairs, n):
    flat = [x for pair in pairs for x in pair]
    test.assertEqual(sorted(flat), list(range(n)))
    for a, b in pairs:
        test.assertNotEqual(a, b)


class TestRoundRobin(unittest.TestCase):
    def test_perfect_matching_each_game(self):
        schedule = build_round_robin_schedule(6, 6, seed=1)
        for pairs in schedule:
            _assert_perfect_matching(self, pairs, 6)

    def test_no_repeated_pairs_within_n_minus_1_games(self):
        n = 6
        schedule = build_round_robin_schedule(n, n - 1, seed=3)
        seen = set()
        for pairs in schedule:
            for pair in pairs:
                self.assertNotIn(pair, seen)
                seen.add(pair)
        self.assertEqual(len(seen), n * (n - 1) // 2)

    def test_all_agents_meet_everyone_once(self):
        n = 8
        schedule = build_round_robin_schedule(n, n - 1, seed=5)
        partners = {i: set() for i in range(n)}
        for pairs in schedule:
            for a, b in pairs:
                partners[a].add(b)
                partners[b].add(a)
        for i in range(n):
            self.assertEqual(partners[i], set(range(n)) - {i})

    def test_deterministic_for_seed(self):
        a = build_round_robin_schedule(10, 5, seed=42)
        b = build_round_robin_schedule(10, 5, seed=42)
        self.assertEqual(a, b)

    def test_cycles_when_games_exceed_rounds(self):
        # n=4 -> 3 distinct rounds; a 5th game repeats the first round.
        schedule = build_round_robin_schedule(4, 5, seed=1)
        self.assertEqual(schedule[0], schedule[3])

    def test_odd_agents_raise(self):
        with self.assertRaises(ValueError):
            build_round_robin_schedule(5, 3, seed=1)


class TestRandomAndManager(unittest.TestCase):
    def test_random_pairing_is_perfect_matching(self):
        for g in range(5):
            pairs = random_pairing(10, seed=2, game_index=g)
            _assert_perfect_matching(self, pairs, 10)

    def test_manager_round_robin(self):
        mgr = PairingManager("round_robin", 6, 4, seed=9)
        for g in range(4):
            pairs = mgr.pairs_for_game(g)
            _assert_perfect_matching(self, pairs, 6)

    def test_manager_random(self):
        mgr = PairingManager("random", 8, 4, seed=9)
        for g in range(4):
            pairs = mgr.pairs_for_game(g)
            _assert_perfect_matching(self, pairs, 8)

    def test_out_of_range(self):
        mgr = PairingManager("round_robin", 4, 2, seed=9)
        with self.assertRaises(IndexError):
            mgr.pairs_for_game(2)
        with self.assertRaises(IndexError):
            mgr.pairs_for_game(-1)

    def test_unknown_strategy(self):
        with self.assertRaises(ValueError):
            PairingManager("nope", 4, 2, seed=1)


if __name__ == "__main__":
    unittest.main()
