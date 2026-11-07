"""Pairing of agents into games.

Two strategies are provided:

* ``round_robin`` (default): a randomised round-robin schedule built with the
  circle method.  For ``n`` agents it produces ``n - 1`` rounds in which every
  pair of agents meets exactly once.  This satisfies "randomly pair agents,
  preferably avoiding repeated pairings": the mapping of agents to schedule
  slots is randomised once (seeded), and no pairing repeats until every other
  agent has been met.  Games beyond ``n - 1`` cycle through the schedule again.
* ``random``: fresh uniformly random pairings each game (seeded).  Repeats are
  possible; this is useful as a robustness check.
"""

from __future__ import annotations

from typing import List, Tuple

from .utils import rng_for

Pair = Tuple[int, int]


def _circle_method_rounds(n: int) -> List[List[Pair]]:
    """Return ``n - 1`` perfect matchings (each pair meets exactly once)."""
    if n % 2 != 0:
        raise ValueError("Circle method requires an even number of agents.")
    teams = list(range(n))
    rounds: List[List[Pair]] = []
    for _ in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a = teams[i]
            b = teams[n - 1 - i]
            pairs.append((min(a, b), max(a, b)))
        rounds.append(pairs)
        # Rotate all teams except the first one.
        teams = [teams[0], teams[-1]] + teams[1:-1]
    return rounds


def build_round_robin_schedule(
    n_agents: int, n_games: int, seed: int
) -> List[List[Pair]]:
    """Build a seeded round-robin schedule of ``n_games`` matchings."""
    if n_agents % 2 != 0:
        raise ValueError("Number of agents must be even.")
    base_rounds = _circle_method_rounds(n_agents)

    # Randomly permute the agent labels once so *who* meets *whom* early is random.
    perm = list(range(n_agents))
    rng_for(seed, "round_robin_perm").shuffle(perm)
    permuted = [
        [(perm[a], perm[b]) for (a, b) in rnd] for rnd in base_rounds
    ]

    schedule: List[List[Pair]] = []
    for g in range(n_games):
        rnd = permuted[g % len(permuted)]
        # Normalise pair ordering and order of pairs for determinism.
        normalised = [tuple(sorted(p)) for p in rnd]
        schedule.append(normalised)
    return schedule


def random_pairing(n_agents: int, seed: int, game_index: int) -> List[Pair]:
    """Return a uniformly random perfect matching for one game."""
    if n_agents % 2 != 0:
        raise ValueError("Number of agents must be even.")
    order = list(range(n_agents))
    rng_for(seed, "random_pairing", game_index).shuffle(order)
    pairs = [
        (order[i], order[i + 1]) for i in range(0, n_agents, 2)
    ]
    return [tuple(sorted(p)) for p in pairs]


class PairingManager:
    """Provides the list of pairs for each game index."""

    def __init__(
        self,
        strategy: str,
        n_agents: int,
        n_games: int,
        seed: int,
    ) -> None:
        if strategy not in ("round_robin", "random"):
            raise ValueError(f"Unknown pairing strategy {strategy!r}.")
        self.strategy = strategy
        self.n_agents = n_agents
        self.n_games = n_games
        self.seed = seed
        if strategy == "round_robin":
            self._schedule = build_round_robin_schedule(n_agents, n_games, seed)
        else:
            self._schedule = None

    def pairs_for_game(self, game_index: int) -> List[Pair]:
        if not (0 <= game_index < self.n_games):
            raise IndexError(
                f"game_index {game_index} out of range [0, {self.n_games})."
            )
        if self.strategy == "round_robin":
            return list(self._schedule[game_index])
        return random_pairing(self.n_agents, self.seed, game_index)
