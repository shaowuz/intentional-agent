"""LLM-backed agent.

Each agent owns an isolated :class:`~ipd.memory.AgentMemory`, an identical
system prompt except for the initial prior, and a reference to the shared LLM
client and usage tracker.  The agent only ever sees its own memory; opponent
identities are never revealed in prompts.
"""

from __future__ import annotations

from typing import Optional, Tuple

from .llm.base import LLMClient
from .memory import AgentMemory
from .parsing import parse_action, parse_belief
from .prompts import build_action_prompt, build_belief_prompt, build_system_prompt
from .usage import UsageTracker


class LLMAgent:
    def __init__(
        self,
        agent_id: str,
        prior: float,
        prior_group: str,
        condition: str,
        client: LLMClient,
        usage_tracker: UsageTracker,
        fixed_rounds: int = 20,
        continue_prob: float = 0.95,
        recent_rounds_in_prompt: int = 30,
        max_completed_game_lines: int = 200,
    ):
        self.agent_id = agent_id
        self.prior = float(prior)
        self.prior_group = prior_group
        self.condition = condition
        self.client = client
        self.usage = usage_tracker
        self.fixed_rounds = fixed_rounds
        self.continue_prob = continue_prob
        self.recent_rounds_in_prompt = recent_rounds_in_prompt
        self.max_completed_game_lines = max_completed_game_lines
        self.memory = AgentMemory(
            agent_id=agent_id,
            prior=prior,
            prior_group=prior_group,
            condition=condition,
        )
        self.system_prompt = build_system_prompt(
            prior=prior,
            condition=condition,
            fixed_rounds=fixed_rounds,
            continue_prob=continue_prob,
        )

    # ------------------------------------------------------------------ #
    # Game lifecycle helpers (thin wrappers over memory).
    # ------------------------------------------------------------------ #
    def start_game(self, game_index, opponent_id, planned_rounds, continue_prob):
        self.memory.start_game(
            game_index=game_index,
            opponent_id=opponent_id,
            condition=self.condition,
            planned_rounds=planned_rounds,
            continue_prob=continue_prob,
        )

    def observe(self, round_number, own_action, opp_action, own_payoff, reasoning=""):
        return self.memory.observe_round(
            round_number=round_number,
            own_action=own_action,
            opp_action=opp_action,
            own_payoff=own_payoff,
            own_reasoning=reasoning,
        )

    def end_game(self, belief_value: Optional[float], belief_reasoning: str = ""):
        return self.memory.close_game(belief_value, belief_reasoning)

    @property
    def total_payoff(self) -> int:
        return self.memory.total_payoff

    # ------------------------------------------------------------------ #
    # Decisions
    # ------------------------------------------------------------------ #
    def choose_action(self, round_number: int) -> dict:
        user = build_action_prompt(
            memory=self.memory,
            condition=self.condition,
            round_number=round_number,
            fixed_rounds=self.fixed_rounds,
            continue_prob=self.continue_prob,
            recent_limit=self.recent_rounds_in_prompt,
            max_completed_lines=self.max_completed_game_lines,
        )
        response = self.client.complete(self.system_prompt, user)
        self.usage.log(self.agent_id, "action", response)
        action, meta = parse_action(response.text)
        return {
            "action": action,
            "reasoning": meta.get("reasoning", ""),
            "parse_status": meta.get("parse_status", "unknown"),
            "response_text": response.text[:1000],
            "prompt": user,
        }

    def estimate_belief(self) -> Tuple[Optional[float], dict]:
        user = build_belief_prompt(
            memory=self.memory,
            recent_limit=self.recent_rounds_in_prompt,
            max_completed_lines=self.max_completed_game_lines,
        )
        response = self.client.complete(self.system_prompt, user)
        self.usage.log(self.agent_id, "belief", response)
        value, meta = parse_belief(response.text)
        meta["response_text"] = response.text[:1000]
        return value, meta
