"""End-to-end and contract tests for the ranked tournament."""

import json
import os
import re
import tempfile
import unittest

from ipd.config import LLMConfig, PricingConfig
from ipd.recorder import read_jsonl
from ipd.usage import LLMResponse, UsageTracker

from ranked_tournament.agent import MalformedResponseError, RankedAgent
from ranked_tournament.analysis import analyze_all, write_report
from ranked_tournament.config import TournamentConfig
from ranked_tournament.memory import ReflectionRecord
from ranked_tournament.mock import RankedMockClient
from ranked_tournament.tournament import TournamentRunner

AGENTS = ["A", "B", "C", "D"]


def make_config(
    output_dir, n_rounds=3, seed=7, max_stages=6, **overrides
):
    params = dict(
        name="test",
        seed=seed,
        output_dir=output_dir,
        n_rounds=n_rounds,
        agents=list(AGENTS),
        continue_prob=0.95,
        max_stages=max_stages,
        ranking_points=[3, 2, 1, 0],
        max_decision_retries=1,
        max_reflection_retries=1,
        llm=LLMConfig(
            provider="mock",
            model="mock-ranked",
            temperature=0.7,
            top_p=1.0,
            max_tokens=100,
            pricing=PricingConfig(),
        ),
    )
    params.update(overrides)
    return TournamentConfig(**params)


class RecordingClient(RankedMockClient):
    def __init__(self):
        super().__init__()
        self.user_prompts = []

    def complete(self, system, user, **kwargs):
        self.user_prompts.append(user)
        return super().complete(system, user, **kwargs)


class ScriptedClient:
    provider = "mock"
    model = "scripted"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.last = ""

    def complete(self, system, user, **kwargs):
        self.calls += 1
        text = self.responses.pop(0) if self.responses else self.last
        self.last = text
        return LLMResponse(
            text=text,
            input_tokens=1,
            output_tokens=1,
            model=self.model,
            provider=self.provider,
        )


class TestTournamentEngine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _read(self, name):
        return read_jsonl(os.path.join(self.tmp, f"{name}.jsonl"))

    def test_complete_pipeline(self):
        config = make_config(self.tmp, n_rounds=3)
        runner = TournamentRunner(
            config, verbose=False, client=RankedMockClient()
        )
        summary = runner.run()

        rounds = self._read("rounds")
        games = self._read("games")
        stages = self._read("stages")
        reflections = self._read("reflections")
        strategies = self._read("strategies")
        pairings = self._read("pairings")
        calls = self._read("calls")
        usage = self._read("usage")

        self.assertEqual(len(rounds), 3)
        self.assertEqual(len(games), 6)
        self.assertEqual(len(reflections), 12)
        self.assertEqual(len(strategies), 12)
        self.assertEqual(len(pairings), 3)
        self.assertEqual(
            len(stages), sum(2 * int(r["game_length"]) for r in rounds)
        )
        self.assertGreater(len(calls), 0)
        self.assertGreater(len(usage), 0)

        for round_rec in rounds:
            pairs = round_rec["pairs"]
            flat = [agent for pair in pairs for agent in pair]
            self.assertEqual(sorted(flat), AGENTS)
            for pair in pairs:
                self.assertEqual(len(pair), 2)
                self.assertNotEqual(pair[0], pair[1])
            self.assertAlmostEqual(
                sum(round_rec["ranking_points"].values()), 6.0
            )
            round_games = [
                g for g in games if g["round"] == round_rec["round"]
            ]
            self.assertEqual(len(round_games), 2)
            for game in round_games:
                self.assertEqual(
                    game["length"], round_rec["game_length"]
                )

        for agent_id in AGENTS:
            agent_summary = summary["agents"][agent_id]
            self.assertEqual(agent_summary["n_games"], 3)
            self.assertEqual(agent_summary["n_reflections"], 3)
            self.assertIsNotNone(agent_summary["current_strategy"])

        final_reflections = [r for r in reflections if r["round"] == 3]
        self.assertEqual(len(final_reflections), 4)

        for agent_id in AGENTS:
            path = os.path.join(
                self.tmp, "memory", f"agent_{agent_id}_round_3.json"
            )
            self.assertTrue(os.path.exists(path))
        with open(
            os.path.join(self.tmp, "run_status.json"), encoding="utf-8"
        ) as fh:
            status = json.load(fh)
        self.assertEqual(status["status"], "completed")
        with open(
            os.path.join(self.tmp, "experiment_meta.json"), encoding="utf-8"
        ) as fh:
            meta = json.load(fh)
        self.assertEqual(meta["seed"], 7)
        self.assertEqual(meta["agents"], AGENTS)
        self.assertEqual(meta["mode"], "mock")

    def test_analysis_and_report(self):
        config = make_config(self.tmp, n_rounds=2, max_stages=5)
        TournamentRunner(
            config, verbose=False, client=RankedMockClient()
        ).run()
        result = analyze_all(self.tmp)
        self.assertTrue(os.path.exists(result["summary_path"]))
        self.assertTrue(os.path.exists(result["tables"]["table1_md"]))
        self.assertTrue(os.path.exists(result["tables"]["table2_md"]))
        self.assertGreaterEqual(len(result["figures"]), 3)
        report = os.path.join(self.tmp, "report.md")
        write_report(result, report, self.tmp)
        with open(report, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("Table 1: Tournament Results", text)
        self.assertIn("Table 2: Strategy Evolution", text)
        self.assertIn("Qualitative Analysis", text)
        self.assertIn("Observations versus causal conclusions", text)

