"""Seeded random pairing for each tournament round."""

from __future__ import annotations

from typing import List, Sequence, Tuple

from ipd.utils import rng_for

Pair = Tuple[str, str]


def sample_pairs(
    agent_ids: Sequence[str], seed: int, round_index: int
) -> List[Pair]:
    """Return a uniformly random perfect matching for one round.

    Pairings are sampled independently across rounds, so repeat encounters are
    allowed.  The matching is a deterministic function of ``(seed, round)``,
    which makes the pairing schedule reproducible.  Agents never see this
    schedule or any persistent opponent identifier.
    """
    ids = list(agent_ids)
    if len(ids) % 2 != 0:
        raise ValueError("Number of agents must be even.")
    if len(ids) != len(set(ids)):
        raise ValueError("Agent labels must be unique.")
    order = list(ids)
    rng_for(seed, "pairing", round_index).shuffle(order)
    return [
        (order[i], order[i + 1]) for i in range(0, len(order), 2)
    ]
