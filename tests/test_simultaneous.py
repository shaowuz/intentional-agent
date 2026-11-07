"""Test that actions are chosen simultaneously (no look-ahead within a round)."""

import os
import re
import tempfile
import unittest

from ipd.llm.mock import MockClient
from ipd.tournament import play_match
from ipd.utils import rng_for
from tests.helpers import make_agents, make_config


class RecordingClient(MockClient):
    """Mock client that records the user prompts it receives."""

    def __init__(self):
        super().__init__()
        self.user_prompts = []

    def complete(self, system, user, **kwargs):
        self.user_prompts.append(user)
        return super().complete(system, user, **kwargs)


class TestSimultaneousActions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_no_current_round_information_before_reveal(self):
        config = make_config(
            os.path.join(self.tmp, "sim"),
            fixed_rounds=4,
            games_per_agent=1,
        )
        client = RecordingClient()
        agents, by_id, usage = make_agents(config, "fixed", client=client)
        a, b = agents
        rng = rng_for(1, "sim")
        play_match(a, b, 0, 0, "fixed", config, rng)

        action_prompts = [p for p in client.user_prompts if "TASK: ACTION" in p]
        # 4 rounds x 2 agents.
        self.assertEqual(len(action_prompts), 8)

        round_re = re.compile(r"This is round (\d+) of (\d+)")
        round_line_re = re.compile(r"R(\d+): you=([CD]) opp=([CD])")
        for prompt in action_prompts:
            m = round_re.search(prompt)
            self.assertIsNotNone(m)
            current_round = int(m.group(1))
            # Only previous rounds may appear in the current-game section.
            section = prompt.split("=== CURRENT GAME ===", 1)[1].split(
                "=== YOUR DECISION ===", 1
            )[0]
            seen = round_line_re.findall(section)
            self.assertEqual(len(seen), current_round - 1)
            if seen:
                self.assertEqual(max(int(r) for r, _, _ in seen), current_round - 1)

    def test_belief_prompt_includes_just_finished_game(self):
        config = make_config(
            os.path.join(self.tmp, "belief"),
            fixed_rounds=2,
            games_per_agent=1,
        )
        client = RecordingClient()
        agents, _, _ = make_agents(config, "fixed", client=client)
        a, b = agents
        play_match(a, b, 0, 0, "fixed", config, rng_for(2, "belief"))

        belief_prompts = [p for p in client.user_prompts if "TASK: BELIEF_ESTIMATE" in p]
        self.assertEqual(len(belief_prompts), 2)
        for prompt in belief_prompts:
            self.assertIn("Game 1", prompt)


if __name__ == "__main__":
    unittest.main()
