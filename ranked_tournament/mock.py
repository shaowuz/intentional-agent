"""Deterministic offline mock for pipeline tests.

This client is **not** a model of LLM behaviour and its outputs are never used
as scientific findings.  It exists so that the prompt construction, simultaneous
play, scoring, reflection storage, logging and analysis can be exercised
without network access.
"""

from __future__ import annotations

import random
import re
from typing import Optional

from ipd.usage import LLMResponse
from ipd.utils import stable_seed_from_text

from .parsing import normalise_action  # noqa: F401  (documented helper)

_STAGE_RE = re.compile(
    r"Stage\s+(\d+):\s+you=([CD])\s+opp=([CD])"
)
_ROUND_RE = re.compile(r"tournament round\s+(\d+)\s+of\s+(\d+)")


class RankedMockClient:
    """A prompt-driven deterministic mock backend for the ranked tournament."""

    provider = "mock"
    model = "mock-ranked"

    def __init__(self, model: str = "mock-ranked", noise: float = 0.10):
        self.model = model
        self.noise = noise

    def complete(self, system: str, user: str, **kwargs) -> LLMResponse:
        if "TASK: RANKED_REFLECTION" in user:
            text = self._reflection(user)
        elif "TASK: RANKED_ACTION" in user:
            text = self._action(user)
        else:
            text = '{"error": "unknown mock task"}'
        input_tokens = max(1, (len(system) + len(user)) // 4)
        output_tokens = max(1, len(text) // 4)
        return LLMResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.model,
            provider=self.provider,
            raw=None,
        )

    # ------------------------------------------------------------------ #
    def _action(self, user: str) -> str:
        rounds = _STAGE_RE.findall(user)
        rng = random.Random(stable_seed_from_text(user))
        if not rounds:
            action = "C" if rng.random() < 0.65 else "D"
            reasoning = "First stage of a new pair-game; mock exploratory opener."
        else:
            last_opp = rounds[-1][2]
            if rng.random() < self.noise:
                action = rng.choice(["C", "D"])
                reasoning = "Mock exploration."
            else:
                action = last_opp
                reasoning = (
                    "Mock noisy reciprocity: mirror the opponent's previous "
                    f"action ({last_opp})."
                )
        return '{"action": "%s", "reasoning": "%s"}' % (action, reasoning)

    def _reflection(self, user: str) -> str:
        match = _ROUND_RE.search(user)
        round_index = int(match.group(1)) if match else 1
        change = bool(round_index == 1 or round_index % 2 == 0)
        strategy = (
            "Mock strategy: mirror the opponent's previous action with "
            f"occasional exploration (updated after round {round_index})."
        )
        reason = (
            "Mock reflection for pipeline validation; no scientific meaning."
        )
        return (
            '{"change_strategy": %s, "reason": "%s", '
            '"strategy_for_next_round": "%s"}'
            % ("true" if change else "false", reason, strategy)
        )
