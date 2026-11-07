"""A deterministic, offline mock backend.

The mock is *not* a model of what a real LLM would do.  It exists so the whole
pipeline (prompts, simultaneous play, memory, recording, analysis) can be tested
without any network access.  It is stateless: its output is a deterministic
function of the prompt text, which makes results fully reproducible.
"""

from __future__ import annotations

import random
import re
from typing import List, Optional, Tuple

from ..usage import LLMResponse
from ..utils import stable_seed_from_text
from .base import LLMClient

_ROUND_RE = re.compile(r"R(\d+): you=([CD]) opp=([CD])")
_FIRST_MOVE_RE = re.compile(r"opp_first_move=([CD])")
_PRIOR_RE = re.compile(
    r"defects in the first round with probability\s+([0-9]+(?:\.[0-9]+)?)"
)


class MockClient(LLMClient):
    """A prompt-driven deterministic mock."""

    provider = "mock"
    model = "mock-strategic"

    def __init__(self, model: str = "mock-strategic", noise: float = 0.05):
        self.model = model
        self.noise = noise

    # ------------------------------------------------------------------ #
    def complete(self, system: str, user: str, **kwargs) -> LLMResponse:
        rng = random.Random(stable_seed_from_text(system + "\n" + user))
        if "TASK: BELIEF_ESTIMATE" in user:
            text = self._belief(system, user)
        else:
            text = self._action(system, user, rng)
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
    def _parse_prior(self, system: str) -> float:
        m = _PRIOR_RE.search(system)
        return float(m.group(1)) if m else 0.5

    def _current_rounds(self, user: str) -> List[Tuple[int, str, str]]:
        section = user
        if "=== CURRENT GAME ===" in user:
            section = user.split("=== CURRENT GAME ===", 1)[1]
        if "=== YOUR DECISION ===" in section:
            section = section.split("=== YOUR DECISION ===", 1)[0]
        return [(int(m.group(1)), m.group(2), m.group(3)) for m in _ROUND_RE.finditer(section)]

    def _action(self, system: str, user: str, rng: random.Random) -> str:
        prior = self._parse_prior(system)
        rounds = self._current_rounds(user)
        if not rounds:
            # First round of a game: defect with probability ~ prior.
            action = "D" if rng.random() < prior else "C"
            reasoning = (
                f"First round of a new game; my prior says a new opponent defects "
                f"with probability {prior:.2f}."
            )
        else:
            last_opp = rounds[-1][2]
            # Noisy tit-for-tat: mirror the opponent's previous action.
            if rng.random() < self.noise:
                action = rng.choice(["C", "D"])
                why = "exploring"
            else:
                action = last_opp
                why = "matching opponent's last action"
            reasoning = f"Rounds played={len(rounds)}; {why} (last opp={last_opp})."
        return (
            '{"action": "%s", "reasoning": "%s"}' % (action, reasoning)
        )

    def _belief(self, system: str, user: str) -> str:
        prior = self._parse_prior(system)
        firsts = _FIRST_MOVE_RE.findall(user)
        if firsts:
            observed = sum(a == "D" for a in firsts) / len(firsts)
            # Shrink the prior as evidence accumulates.
            weight = 3.0 / (3.0 + len(firsts))
            est = weight * prior + (1.0 - weight) * observed
        else:
            est = prior
        est = max(0.0, min(1.0, est))
        return (
            '{"defect_probability": %.3f, "reasoning": "mock estimate from %d '
            'observed first moves and prior %.2f."}'
            % (est, len(firsts), prior)
        )
