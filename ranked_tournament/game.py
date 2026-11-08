"""Game rules and helpers for the ranked tournament.

The payoff matrix and action constants are re-used from :mod:`ipd.game` so the
experiment uses exactly the same Prisoner's Dilemma as the rest of the
repository.  The only new rule here is the *shared hidden game length*: one
geometric length is sampled per tournament round and used for both pair-games.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from ipd.game import (  # re-exported for convenience
    ACTIONS,
    COOPERATE,
    DEFECT,
    PAYOFF_MATRIX,
    payoff,
)
from ipd.utils import rng_for

Pair = Tuple[str, str]


def sample_round_length(
    seed: int,
    round_index: int,
    continue_prob: float,
    max_stages: int,
) -> Tuple[int, bool]:
    """Sample the shared length of both pair-games in a round.

    The number of stages is geometric: stage 1 is always played, and after each
    stage the game continues with probability ``continue_prob``.  The sampled
    length is not shown to agents.  ``max_stages`` is a safety cap: if the
    continuation process would exceed it, the returned flag is ``True``.

    The draw is seeded deterministically from ``(seed, round_index)`` so a
    resumed run reproduces the same lengths without replaying every stage.
    """
    if not (0.0 < continue_prob < 1.0):
        raise ValueError("continue_prob must be in (0, 1).")
    if max_stages < 1:
        raise ValueError("max_stages must be >= 1.")

    rng = rng_for(seed, "round_length", round_index)
    length = 1
    capped = False
    while rng.random() < continue_prob:
        if length >= max_stages:
            capped = True
            break
        length += 1
    return length, capped


def cooperation_rate(stage_records: List[dict]) -> float:
    """Fraction of all actions (both players) that are C."""
    total = 0
    coop = 0
    for rec in stage_records:
        for action in rec["actions"].values():
            total += 1
            if action == COOPERATE:
                coop += 1
    return coop / total if total else float("nan")


def mutual_cooperation_rate(stage_records: List[dict]) -> float:
    """Fraction of stages in which both players chose C."""
    if not stage_records:
        return float("nan")
    mutual = sum(
        1
        for rec in stage_records
        if all(a == COOPERATE for a in rec["actions"].values())
    )
    return mutual / len(stage_records)


def per_agent_cooperation(stage_records: List[dict]) -> Dict[str, Tuple[int, int]]:
    """Return ``agent -> (n_cooperate, n_actions)`` for stage records."""
    counts: Dict[str, List[int]] = {}
    for rec in stage_records:
        for agent_id, action in rec["actions"].items():
            bucket = counts.setdefault(agent_id, [0, 0])
            bucket[1] += 1
            if action == COOPERATE:
                bucket[0] += 1
    return {aid: (c, n) for aid, (c, n) in counts.items()}
