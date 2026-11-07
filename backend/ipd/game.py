"""Game rules: actions, payoff matrix and horizon descriptions."""

from __future__ import annotations

from typing import Tuple

from swarm_game.game import PAYOFFS

COOPERATE = "C"
DEFECT = "D"
ACTIONS: Tuple[str, str] = (COOPERATE, DEFECT)

# Payoff matrix mapping (own_action, opponent_action) -> own payoff.
#          Opponent C   Opponent D
# Agent C    (3, 3)       (0, 5)
# Agent D    (5, 0)       (1, 1)

PAYOFF_MATRIX = {actions: values[0] for actions, values in PAYOFFS.items()}

# Conditions.
FIXED = "fixed"
RANDOM = "random"
CONDITIONS = (FIXED, RANDOM)


def payoff(own_action: str, opponent_action: str) -> int:
    """Return the payoff to an agent given its own and the opponent's action."""
    try:
        return PAYOFF_MATRIX[(own_action, opponent_action)]
    except KeyError as exc:  # pragma: no cover - defensive
        raise ValueError(
            f"Invalid actions: own={own_action!r}, opponent={opponent_action!r}. "
            f"Actions must be one of {ACTIONS}."
        ) from exc


def is_valid_action(action: str) -> bool:
    return action in ACTIONS


def horizon_system_description(
    condition: str, fixed_rounds: int, continue_prob: float
) -> str:
    """Human-readable description of the horizon used in the system prompt."""
    if condition == FIXED:
        return (
            f"This experiment uses a FIXED horizon: each game lasts exactly "
            f"{fixed_rounds} rounds. Both players know the total number of rounds."
        )
    if condition == RANDOM:
        pct = int(round(continue_prob * 100))
        return (
            "This experiment uses a RANDOM horizon: after each round the game "
            f"continues with probability {continue_prob} ({pct}%). Therefore the "
            "game length is variable and its expected length is roughly "
            f"{1.0 / (1.0 - continue_prob):.1f} rounds. Neither player knows in "
            "advance how many rounds the game will last."
        )
    raise ValueError(f"Unknown condition {condition!r}")
