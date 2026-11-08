"""Configuration tests for the ranked tournament."""

import os
import tempfile
import unittest

from ipd.config import LLMConfig
from ranked_tournament.config import (
    TournamentConfig,
    config_from_dict,
    load_config,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestRankedConfig(unittest.TestCase):
    def test_load_mock_config(self):
        config = load_config(
            os.path.join(REPO_ROOT, "config", "ranked_tournament_mock.yaml")
        )
        self.assertEqual(config.n_rounds, 15)
        self.assertEqual(config.agents, ["A", "B", "C", "D"])
        self.assertEqual(config.llm.provider, "mock")
        self.assertEqual(config.ranking_points, [3.0, 2.0, 1.0, 0.0])

    def test_fingerprint_stable_and_seed_sensitive(self):
        path = os.path.join(
            REPO_ROOT, "config", "ranked_tournament_mock.yaml"
        )
        c1 = load_config(path)
        c2 = load_config(path)
        c3 = load_config(path, {"seed": 999})
        self.assertEqual(c1.fingerprint(), c2.fingerprint())
        self.assertNotEqual(c1.fingerprint(), c3.fingerprint())

    def test_unknown_top_level_key_rejected(self):
        with self.assertRaises(ValueError):
            config_from_dict({"name": "x", "not_a_key": 1})

    def test_unknown_llm_key_rejected(self):
        with self.assertRaises(ValueError):
            config_from_dict({"llm": {"provider": "mock", "nope": 1}})

    def test_odd_agent_count_rejected(self):
        config = TournamentConfig(agents=["A", "B", "C"])
        with self.assertRaises(ValueError):
            config.validate()

    def test_wrong_ranking_points_length_rejected(self):
        config = TournamentConfig(ranking_points=[3, 2, 1])
        with self.assertRaises(ValueError):
            config.validate()

    def test_invalid_continue_prob_rejected(self):
        config = TournamentConfig(continue_prob=1.0)
        with self.assertRaises(ValueError):
            config.validate()

    def test_yaml_round_trip_overrides(self):
        config = load_config(
            os.path.join(REPO_ROOT, "config", "ranked_tournament_mock.yaml"),
            {"n_rounds": 3, "llm": {"max_tokens": 50}},
        )
        self.assertEqual(config.n_rounds, 3)
        self.assertEqual(config.llm.max_tokens, 50)


if __name__ == "__main__":
    unittest.main()
