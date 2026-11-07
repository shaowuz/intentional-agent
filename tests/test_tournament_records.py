"""Tests for match records, payoff bookkeeping and memory isolation."""

import os
import tempfile
import unittest

from ipd.game import payoff
from ipd.tournament import play_match
from ipd.utils import rng_for
from tests.helpers import make_agents, make_config


class TestMatchRecords(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _play(self, fixed_rounds=4):
        config = make_config(
            os.path.join(self.tmp, f"m{fixed_rounds}"),
            fixed_rounds=fixed_rounds,
            games_per_agent=1,
        )
        agents, by_id, usage = make_agents(config, "fixed")
        a, b = agents
        result = play_match(a, b, 0, 0, "fixed", config, rng_for(1, "m"))
        return result, a, b, config

    def test_record_structure_and_payoffs(self):
        result, a, b, config = self._play(fixed_rounds=4)
        rec = result["game_record"]
        self.assertEqual(set(rec["participants"]), {a.agent_id, b.agent_id})
        self.assertEqual(rec["horizon"], "fixed")
        self.assertEqual(rec["planned_rounds"], 4)
        self.assertIsNone(rec["continue_prob"])

        a_sum = 0
        b_sum = 0
        for rnd in rec["rounds"]:
            aa = rnd["actions"][a.agent_id]
            bb = rnd["actions"][b.agent_id]
            self.assertEqual(rnd["payoffs"][a.agent_id], payoff(aa, bb))
            self.assertEqual(rnd["payoffs"][b.agent_id], payoff(bb, aa))
            a_sum += rnd["payoffs"][a.agent_id]
            b_sum += rnd["payoffs"][b.agent_id]

        self.assertEqual(rec["totals"][a.agent_id]["game_payoff"], a_sum)
        self.assertEqual(rec["totals"][b.agent_id]["game_payoff"], b_sum)
        self.assertEqual(a.total_payoff, a_sum)
        self.assertEqual(b.total_payoff, b_sum)

    def test_round_records_denormalised(self):
        result, a, b, _ = self._play(fixed_rounds=3)
        rr = result["round_records"]
        self.assertEqual(len(rr), 6)  # 3 rounds x 2 agents
        for r in rr:
            self.assertIn(r["own_action"], ("C", "D"))
            self.assertIn(r["opp_action"], ("C", "D"))
            self.assertIn("lifetime_cum_payoff", r)
            self.assertIn("opponent_id", r)

    def test_beliefs_present_and_valid(self):
        result, a, b, _ = self._play(fixed_rounds=3)
        beliefs = result["game_record"]["beliefs"]
        for aid in (a.agent_id, b.agent_id):
            val = beliefs[aid]["defect_probability"]
            self.assertIsNotNone(val)
            self.assertGreaterEqual(val, 0.0)
            self.assertLessEqual(val, 1.0)
        self.assertEqual(len(result["belief_records"]), 2)

    def test_memory_isolation_between_opponents(self):
        result, a, b, _ = self._play(fixed_rounds=3)
        self.assertEqual(a.memory.n_games_completed, 1)
        self.assertEqual(b.memory.n_games_completed, 1)
        self.assertIsNot(a.memory, b.memory)
        # Each agent's view of the opponent's actions matches the other's views.
        a_game = a.memory.games[0]
        b_game = b.memory.games[0]
        for ra, rb in zip(a_game.rounds, b_game.rounds):
            self.assertEqual(ra.opp_action, rb.own_action)
            self.assertEqual(ra.own_action, rb.opp_action)
        # Opponent ids are stored internally but never equal one's own id.
        self.assertEqual(a_game.opponent_id, b.agent_id)
        self.assertEqual(b_game.opponent_id, a.agent_id)


if __name__ == "__main__":
    unittest.main()
