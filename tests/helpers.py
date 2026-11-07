"""Helpers to build small experiments for tests."""

from __future__ import annotations

from ipd.config import (
    ExperimentConfig,
    LLMConfig,
    MemoryConfig,
    PopulationConfig,
)
from ipd.llm.mock import MockClient
from ipd.tournament import build_agents
from ipd.usage import UsageTracker


def make_config(output_dir: str, **overrides) -> ExperimentConfig:
    params = dict(
        name="test",
        seed=7,
        output_dir=output_dir,
        conditions=["fixed"],
        games_per_agent=3,
        fixed_rounds=3,
        continue_prob=0.95,
        max_rounds_random=50,
        pairing_strategy="round_robin",
        population=PopulationConfig(priors=[0.1, 0.9], agents_per_prior=1),
        llm=LLMConfig(provider="mock", model="mock-strategic"),
        memory=MemoryConfig(recent_rounds_in_prompt=10, max_completed_game_lines=50),
    )
    params.update(overrides)
    return ExperimentConfig(**params)


def make_agents(config: ExperimentConfig, condition: str = "fixed", client=None):
    client = client or MockClient()
    usage = UsageTracker()
    agents = build_agents(config, condition, client, usage)
    by_id = {a.agent_id: a for a in agents}
    return agents, by_id, usage
