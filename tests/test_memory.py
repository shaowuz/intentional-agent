"""Tests for per-agent memory and its isolation."""

import unittest

from ipd.memory import AgentMemory


class TestMemory(unittest.TestCase):
    def _play_game(self, mem, payoffs, actions, start_index=0, opponent="other"):
        mem.start_game(start_index, opponent, "fixed", 3, None)
        entries = []
        for r, (pay, (own, opp)) in enumerate(zip(payoffs, actions), start=1):
            entries.append(mem.observe_round(r, own, opp, pay, f"reason{r}"))
        return entries, mem.close_game(0.4, "belief reason")

    def test_cumulative_payoffs(self):
        mem = AgentMemory("a", 0.1, "0.1", "fixed")
        entries, game = self._play_game(
            mem,
            payoffs=[3, 0, 5],
            actions=[("C", "C"), ("C", "D"), ("D", "C")],
        )
        self.assertEqual([e.cum_game_payoff for e in entries], [3, 3, 8])
        self.assertEqual([e.lifetime_cum_payoff for e in entries], [3, 3, 8])
        self.assertEqual(game.total_payoff, 8)
        self.assertEqual(mem.total_payoff, 8)
        self.assertEqual(game.n_rounds, 3)
        self.assertAlmostEqual(game.coop_rate, 2 / 3)

    def test_lifetime_accumulates_across_games(self):
        mem = AgentMemory("a", 0.1, "0.1", "fixed")
        self._play_game(mem, [3, 3], [("C", "C"), ("C", "C")], start_index=0)
        self._play_game(mem, [5, 5], [("D", "C"), ("D", "C")], start_index=1)
        self.assertEqual(mem.total_payoff, 16)
        self.assertEqual(mem.n_games_completed, 2)
        self.assertEqual(mem.games[1].cum_payoff_after, 16)

    def test_open_game_guard(self):
        mem = AgentMemory("a", 0.1, "0.1", "fixed")
        mem.start_game(0, "o", "fixed", 3, None)
        with self.assertRaises(RuntimeError):
            mem.start_game(1, "o", "fixed", 3, None)

    def test_observe_without_open_game_raises(self):
        mem = AgentMemory("a", 0.1, "0.1", "fixed")
        with self.assertRaises(RuntimeError):
            mem.observe_round(1, "C", "C", 3)

    def test_isolation_between_agents(self):
        a = AgentMemory("a", 0.1, "0.1", "fixed")
        b = AgentMemory("b", 0.9, "0.9", "fixed")
        self._play_game(a, [3, 3], [("C", "C"), ("C", "C")])
        self.assertEqual(a.total_payoff, 6)
        self.assertEqual(b.total_payoff, 0)
        self.assertEqual(b.n_games_completed, 0)
        self.assertEqual(b.games, [])
        # Mutating a's memory must not affect b's.
        a.games[0].belief_defect_prob = 0.99
        self.assertEqual(b.games, [])
        self.assertEqual(len(a.games), 1)

    def test_serialisation_roundtrip(self):
        mem = AgentMemory("a", 0.3, "0.3", "random")
        self._play_game(mem, [3, 1], [("C", "C"), ("D", "D")])
        restored = AgentMemory.from_dict(mem.to_dict())
        self.assertEqual(restored.agent_id, "a")
        self.assertEqual(restored.total_payoff, mem.total_payoff)
        self.assertEqual(restored.n_games_completed, 1)
        self.assertEqual(restored.games[0].n_rounds, 2)
        self.assertEqual(restored.games[0].rounds[1].own_action, "D")

    def test_rendering(self):
        mem = AgentMemory("a", 0.1, "0.1", "fixed")
        self.assertIn("first game", mem.render_completed_games())
        mem.start_game(0, "o", "fixed", 3, None)
        self.assertIn("No rounds played yet", mem.render_current_game())
        mem.observe_round(1, "C", "D", 0, "r")
        current = mem.render_current_game()
        self.assertIn("you=C", current)
        self.assertIn("opp=D", current)
        mem.close_game(0.5, "x")
        completed = mem.render_completed_games()
        self.assertIn("Game 1", completed)
        self.assertIn("opp_first_move=D", completed)
        self.assertIn("0.50", mem.render_belief_trend())

    def test_completed_game_view_is_lossless_for_long_games(self):
        mem = AgentMemory("a", 0.5, "0.5", "random")
        n = 150
        own = ["C", "D"] * (n // 2)
        opp = ["D", "C"] * (n // 2)
        mem.start_game(0, "o", "random", None, 0.95)
        for i in range(n):
            mem.observe_round(i + 1, own[i], opp[i], 0)
        mem.close_game(0.5, "x")

        text = mem.render_completed_games()  # default: unlimited
        self.assertIn("you_moves=" + "".join(own), text)
        self.assertIn("opp_moves=" + "".join(opp), text)
        # No truncation marker is ever produced.
        self.assertNotIn("...(+", text)

    def test_current_game_view_lossless_beyond_window(self):
        mem = AgentMemory("a", 0.5, "0.5", "random")
        n = 100
        own = ["C", "D"] * (n // 2)
        opp = ["D", "D"] * (n // 2)
        mem.start_game(0, "o", "random", None, 0.95)
        for i in range(n):
            mem.observe_round(i + 1, own[i], opp[i], 0)

        # With a window, the full sequences are still present (lossless).
        windowed = mem.render_current_game(recent_limit=10)
        self.assertIn("you=" + "".join(own), windowed)
        self.assertIn("opp=" + "".join(opp), windowed)

        # With no window, every round is shown individually.
        full = mem.render_current_game(recent_limit=0)
        round_lines = [ln for ln in full.splitlines() if ln.startswith("R") and ":" in ln]
        self.assertEqual(len(round_lines), n)


if __name__ == "__main__":
    unittest.main()
