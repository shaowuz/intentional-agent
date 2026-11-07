"""Tests for game termination (fixed and random horizons)."""

import os
import tempfile
import unittest

from ipd.tournament import play_match
from ipd.utils import rng_for
from tests.helpers import make_agents, make_config


class TestTermination(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _play(self, config, condition, game_index=0, seed=1):
        agents, by_id, usage = make_agents(config, condition)
        a, b = agents
        rng = rng_for(seed, "test", condition, game_index)
        result = play_match(a, b, game_index, 0, condition, config, rng)
        return result, a, b

    def test_fixed_horizon_exact_length(self):
        config = make_config(os.path.join(self.tmp, "fixed"), fixed_rounds=5, games_per_agent=1)
        result, a, b = self._play(config, "fixed")
        rec = result["game_record"]
        self.assertEqual(rec["actual_rounds"], 5)
        self.assertFalse(rec["capped"])
        self.assertEqual(len(rec["rounds"]), 5)
        # 2 agents x 5 rounds
        self.assertEqual(len(result["round_records"]), 10)

    def test_random_horizon_within_bounds_and_expected_length(self):
        config = make_config(
            os.path.join(self.tmp, "random"),
            conditions=["random"],
            continue_prob=0.95,
            max_rounds_random=200,
        )
        lengths = []
        for g in range(150):
            result, _, _ = self._play(config, "random", game_index=g)
            rec = result["game_record"]
            self.assertGreaterEqual(rec["actual_rounds"], 1)
            self.assertLessEqual(rec["actual_rounds"], 200)
            self.assertFalse(rec["capped"])
            lengths.append(rec["actual_rounds"])
        mean_len = sum(lengths) / len(lengths)
        # Expected length of a geometric(0.05) count is 20; allow sampling noise.
        self.assertTrue(10 <= mean_len <= 32, f"mean length {mean_len}")

    def test_random_horizon_respects_cap(self):
        config = make_config(
            os.path.join(self.tmp, "cap"),
            conditions=["random"],
            continue_prob=0.999,
            max_rounds_random=5,
            games_per_agent=1,
        )
        result, _, _ = self._play(config, "random")
        rec = result["game_record"]
        self.assertTrue(rec["capped"])
        self.assertEqual(rec["actual_rounds"], 5)

    def test_random_horizon_is_reproducible_for_same_seed(self):
        config = make_config(
            os.path.join(self.tmp, "det"),
            conditions=["random"],
            continue_prob=0.8,
            games_per_agent=1,
        )
        r1, _, _ = self._play(config, "random", game_index=3, seed=99)
        r2, _, _ = self._play(config, "random", game_index=3, seed=99)
        self.assertEqual(r1["game_record"]["actual_rounds"], r2["game_record"]["actual_rounds"])


if __name__ == "__main__":
    unittest.main()
