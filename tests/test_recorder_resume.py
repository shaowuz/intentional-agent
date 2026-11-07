"""Checkpoint/resume and raw-data recording tests."""

import json
import os
import tempfile
import unittest

from ipd.recorder import read_jsonl
from ipd.tournament import ExperimentRunner
from tests.helpers import make_config


def _write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


class TestRecorderResume(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = os.path.join(self.tmp, "results")
        self.config = make_config(
            self.out, games_per_agent=4, fixed_rounds=3, conditions=["fixed"]
        )

    def _paths(self):
        base = os.path.join(self.out, "fixed")
        return {
            "games": os.path.join(base, "games.jsonl"),
            "rounds": os.path.join(base, "rounds.jsonl"),
            "beliefs": os.path.join(base, "beliefs.jsonl"),
            "checkpoint": os.path.join(base, "checkpoint.json"),
        }

    def test_full_run_counts_and_checkpoint(self):
        ExperimentRunner(self.config, verbose=False).run()
        p = self._paths()
        games = read_jsonl(p["games"])
        rounds = read_jsonl(p["rounds"])
        beliefs = read_jsonl(p["beliefs"])
        # 2 agents -> 1 pair per game, 4 games.
        self.assertEqual(len(games), 4)
        # 4 games x 3 rounds x 2 agents.
        self.assertEqual(len(rounds), 24)
        self.assertEqual(len(beliefs), 8)
        with open(p["checkpoint"]) as fh:
            ckpt = json.load(fh)
        self.assertEqual(ckpt["next_game_index"], 4)
        for g in games:
            self.assertEqual(g["actual_rounds"], 3)

    def test_resume_after_completion_is_idempotent(self):
        ExperimentRunner(self.config, verbose=False).run()
        p = self._paths()
        before = len(read_jsonl(p["games"]))
        ExperimentRunner(self.config, resume=True, verbose=False).run()
        after = len(read_jsonl(p["games"]))
        self.assertEqual(before, after)

    def test_resume_continues_and_reproduces(self):
        ExperimentRunner(self.config, verbose=False).run()
        p = self._paths()

        original_games = read_jsonl(p["games"])
        original_actions = {
            g["game_index"]: [r["actions"] for r in g["rounds"]] for g in original_games
        }

        # Simulate an interruption after game index 1.
        keep_games = [g for g in original_games if g["game_index"] < 2]
        _write_jsonl(p["games"], keep_games)
        _write_jsonl(
            p["rounds"],
            [r for r in read_jsonl(p["rounds"]) if r["game_index"] < 2],
        )
        _write_jsonl(
            p["beliefs"],
            [r for r in read_jsonl(p["beliefs"]) if r["game_index"] < 2],
        )
        with open(p["checkpoint"]) as fh:
            ckpt = json.load(fh)
        ckpt["next_game_index"] = 2
        ckpt["games_completed"] = 2
        with open(p["checkpoint"], "w") as fh:
            json.dump(ckpt, fh)

        ExperimentRunner(self.config, resume=True, verbose=False).run()

        games = read_jsonl(p["games"])
        self.assertEqual(len(games), 4)
        self.assertEqual(len(read_jsonl(p["rounds"])), 24)
        self.assertEqual(len(read_jsonl(p["beliefs"])), 8)

        # Deterministic mock: replayed games must match the originals exactly.
        for g in games:
            if g["game_index"] >= 2:
                replayed_actions = [r["actions"] for r in g["rounds"]]
                self.assertEqual(replayed_actions, original_actions[g["game_index"]])


if __name__ == "__main__":
    unittest.main()
