"""LLM-backed agent with isolated memory and bounded structured-output retries."""

from __future__ import annotations

from typing import Callable, Optional

from ipd.llm import build_client
from ipd.usage import UsageTracker

from .config import TournamentConfig
from .memory import AgentMemory, ReflectionRecord
from .mock import RankedMockClient
from .parsing import parse_action_strict, parse_reflection_strict
from .prompts import (
    build_action_correction_prompt,
    build_decision_prompt,
    build_reflection_correction_prompt,
    build_reflection_prompt,
    build_system_prompt,
)


class MalformedResponseError(RuntimeError):
    """Raised when a model repeatedly fails to produce valid structured output."""

    def __init__(
        self,
        agent_id: str,
        task: str,
        attempts: int,
        last_response: str,
    ):
        self.agent_id = agent_id
        self.task = task
        self.attempts = attempts
        self.last_response = last_response
        super().__init__(
            f"Agent {agent_id} failed to produce valid {task} output after "
            f"{attempts} attempt(s). Last response: {last_response[:500]!r}"
        )


def build_ranked_client(config: TournamentConfig):
    """Build the LLM client, using the offline mock only when requested."""
    if config.llm.provider.lower() == "mock":
        return RankedMockClient(model=config.llm.model)
    return build_client(config.llm)


class RankedAgent:
    """One persistent tournament agent with private memory."""

    def __init__(
        self,
        agent_id: str,
        config: TournamentConfig,
        client,
        usage: UsageTracker,
        call_logger: Optional[Callable[[dict], None]] = None,
    ):
        self.agent_id = agent_id
        self.config = config
        self.client = client
        self.usage = usage
        self.call_logger = call_logger
        self.system_prompt = build_system_prompt(config)
        self.memory = AgentMemory(agent_id)

    # ------------------------------------------------------------------ #
    # Memory lifecycle
    # ------------------------------------------------------------------ #
    def begin_game(
        self, round_index: int, game_index: int, continue_prob: float
    ) -> None:
        self.memory.begin_game(round_index, game_index, continue_prob)

    def observe_stage(
        self,
        stage: int,
        own_action: str,
        opp_action: str,
        own_payoff: int,
        opp_payoff: int,
        own_reasoning: str = "",
    ):
        return self.memory.observe_stage(
            stage=stage,
            own_action=own_action,
            opp_action=opp_action,
            own_payoff=own_payoff,
            opp_payoff=opp_payoff,
            own_reasoning=own_reasoning,
        )

    def end_game(self, capped: bool = False):
        return self.memory.end_game(capped=capped)

    def record_round_result(
        self, round_index: int, payoff: int, points: float
    ) -> None:
        self.memory.record_round_result(round_index, payoff, points)

    def record_reflection(self, reflection: ReflectionRecord) -> None:
        self.memory.record_reflection(reflection)

    @property
    def current_strategy(self) -> Optional[str]:
        return self.memory.current_strategy

    # ------------------------------------------------------------------ #
    # Prompt construction
    # ------------------------------------------------------------------ #
    def build_decision_prompt(self, round_index: int, stage: int) -> str:
        return build_decision_prompt(
            memory=self.memory,
            round_index=round_index,
            n_rounds=self.config.n_rounds,
            stage=stage,
            continue_prob=self.config.continue_prob,
        )

    # ------------------------------------------------------------------ #
    # LLM calls
    # ------------------------------------------------------------------ #
    def _call_and_log(
        self,
        task: str,
        prompt: str,
        round_index: int,
        stage: Optional[int],
        attempt: int,
    ):
        response = self.client.complete(self.system_prompt, prompt)
        usage_record = self.usage.log(
            self.agent_id,
            task,
            response,
            meta={
                "round": round_index,
                "stage": stage,
                "attempt": attempt,
            },
        )
        call_record = {
            "round": round_index,
            "agent_id": self.agent_id,
            "task": task,
            "stage": stage,
            "attempt": attempt,
            "system_prompt": self.system_prompt,
            "user_prompt": prompt,
            "response_text": response.text,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
            "model": response.model,
            "provider": response.provider,
            "cost_usd": usage_record["cost_usd"],
            "parse_status": "pending",
        }
        return response, call_record

    def _log_call(self, record: dict) -> None:
        if self.call_logger is not None:
            self.call_logger(record)

    # ------------------------------------------------------------------ #
    # Decisions
    # ------------------------------------------------------------------ #
    def choose_action(
        self, prompt: str, round_index: int, stage: int
    ) -> dict:
        last_response = ""
        attempts = self.config.max_decision_retries + 1
        for attempt in range(attempts):
            current_prompt = (
                prompt
                if attempt == 0
                else build_action_correction_prompt(prompt, last_response)
            )
            response, call_record = self._call_and_log(
                "decision", current_prompt, round_index, stage, attempt
            )
            action, meta = parse_action_strict(response.text)
            call_record["parse_status"] = meta["parse_status"]
            call_record["normalised_action"] = action
            self._log_call(call_record)
            if action is not None:
                return {
                    "action": action,
                    "reasoning": meta.get("reasoning", ""),
                    "parse_status": "ok",
                    "attempts": attempt + 1,
                    "response_text": response.text,
                }
            last_response = response.text
        raise MalformedResponseError(
            self.agent_id, "action", attempts, last_response
        )

    # ------------------------------------------------------------------ #
    # Reflection
    # ------------------------------------------------------------------ #
    def reflect(
        self,
        round_index: int,
        round_payoff: int,
        round_points: float,
        prior_strategy: Optional[str],
    ) -> dict:
        prompt = build_reflection_prompt(
            memory=self.memory,
            round_index=round_index,
            n_rounds=self.config.n_rounds,
            round_payoff=round_payoff,
            round_points=round_points,
            prior_strategy=prior_strategy,
        )
        last_response = ""
        attempts = self.config.max_reflection_retries + 1
        for attempt in range(attempts):
            current_prompt = (
                prompt
                if attempt == 0
                else build_reflection_correction_prompt(
                    prompt, last_response
                )
            )
            response, call_record = self._call_and_log(
                "reflection", current_prompt, round_index, None, attempt
            )
            parsed, meta = parse_reflection_strict(response.text)
            call_record["parse_status"] = meta["parse_status"]
            self._log_call(call_record)
            if parsed is not None:
                parsed["attempts"] = attempt + 1
                parsed["response_text"] = response.text
                return parsed
            last_response = response.text
        raise MalformedResponseError(
            self.agent_id, "reflection", attempts, last_response
        )

