"""Per-agent memory.

Memory is stored in a complete, structured form (every round of every game is
kept in the object and can be serialised), while :meth:`render_*` methods
produce a *compact* textual view for the prompt.  Completed games are summarised
at the game level and the in-progress game is shown round-by-round (bounded by a
configurable window).  Nothing is discarded from the underlying data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


def _compact_moves(rounds: List["RoundEntry"], attr: str) -> str:
    """Join a game's actions into a compact, **lossless** string.

    Payoffs are fully determined by the joint action sequence, so the two move
    strings for a completed game reconstruct its entire history.  They are never
    truncated, which keeps the prompt view lossless.
    """
    return "".join(getattr(r, attr) for r in rounds)


@dataclass
class RoundEntry:
    round: int
    own_action: str
    opp_action: str
    own_payoff: int
    cum_game_payoff: int
    lifetime_cum_payoff: int
    own_reasoning: str = ""

    def to_dict(self) -> dict:
        return {
            "round": self.round,
            "own_action": self.own_action,
            "opp_action": self.opp_action,
            "own_payoff": self.own_payoff,
            "cum_game_payoff": self.cum_game_payoff,
            "lifetime_cum_payoff": self.lifetime_cum_payoff,
            "own_reasoning": self.own_reasoning,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RoundEntry":
        return cls(
            round=d["round"],
            own_action=d["own_action"],
            opp_action=d["opp_action"],
            own_payoff=d["own_payoff"],
            cum_game_payoff=d.get("cum_game_payoff", 0),
            lifetime_cum_payoff=d.get("lifetime_cum_payoff", 0),
            own_reasoning=d.get("own_reasoning", ""),
        )


@dataclass
class GameRecord:
    game_index: int  # 0-based index of the game (batch)
    opponent_id: str
    condition: str
    horizon: str
    planned_rounds: Optional[int]
    continue_prob: Optional[float]
    rounds: List[RoundEntry] = field(default_factory=list)
    total_payoff: int = 0
    cum_payoff_after: int = 0
    belief_defect_prob: Optional[float] = None
    belief_reasoning: str = ""

    @property
    def n_rounds(self) -> int:
        return len(self.rounds)

    @property
    def coop_rate(self) -> float:
        if not self.rounds:
            return float("nan")
        return sum(r.own_action == "C" for r in self.rounds) / len(self.rounds)

    @property
    def opp_coop_rate(self) -> float:
        if not self.rounds:
            return float("nan")
        return sum(r.opp_action == "C" for r in self.rounds) / len(self.rounds)

    def to_dict(self) -> dict:
        return {
            "game_index": self.game_index,
            "opponent_id": self.opponent_id,
            "condition": self.condition,
            "horizon": self.horizon,
            "planned_rounds": self.planned_rounds,
            "continue_prob": self.continue_prob,
            "rounds": [r.to_dict() for r in self.rounds],
            "total_payoff": self.total_payoff,
            "cum_payoff_after": self.cum_payoff_after,
            "belief_defect_prob": self.belief_defect_prob,
            "belief_reasoning": self.belief_reasoning,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GameRecord":
        return cls(
            game_index=d["game_index"],
            opponent_id=d["opponent_id"],
            condition=d["condition"],
            horizon=d["horizon"],
            planned_rounds=d.get("planned_rounds"),
            continue_prob=d.get("continue_prob"),
            rounds=[RoundEntry.from_dict(r) for r in d.get("rounds", [])],
            total_payoff=d.get("total_payoff", 0),
            cum_payoff_after=d.get("cum_payoff_after", 0),
            belief_defect_prob=d.get("belief_defect_prob"),
            belief_reasoning=d.get("belief_reasoning", ""),
        )


class AgentMemory:
    """Complete, isolated memory for a single agent."""

    def __init__(self, agent_id: str, prior: float, prior_group: str, condition: str):
        self.agent_id = agent_id
        self.prior = float(prior)
        self.prior_group = prior_group
        self.condition = condition
        self.games: List[GameRecord] = []
        self.total_payoff: int = 0
        self._current: Optional[GameRecord] = None

    # ------------------------------------------------------------------ #
    # Mutation
    # ------------------------------------------------------------------ #
    def start_game(
        self,
        game_index: int,
        opponent_id: str,
        condition: str,
        planned_rounds: Optional[int],
        continue_prob: Optional[float],
    ) -> None:
        if self._current is not None:
            raise RuntimeError(
                f"Agent {self.agent_id} already has an open game; close it first."
            )
        self._current = GameRecord(
            game_index=game_index,
            opponent_id=opponent_id,
            condition=condition,
            horizon=condition,
            planned_rounds=planned_rounds,
            continue_prob=continue_prob,
        )

    def observe_round(
        self,
        round_number: int,
        own_action: str,
        opp_action: str,
        own_payoff: int,
        own_reasoning: str = "",
    ) -> RoundEntry:
        if self._current is None:
            raise RuntimeError("observe_round called with no open game.")
        self.total_payoff += own_payoff
        game_cum = sum(r.own_payoff for r in self._current.rounds) + own_payoff
        entry = RoundEntry(
            round=round_number,
            own_action=own_action,
            opp_action=opp_action,
            own_payoff=own_payoff,
            cum_game_payoff=game_cum,
            lifetime_cum_payoff=self.total_payoff,
            own_reasoning=own_reasoning,
        )
        self._current.rounds.append(entry)
        return entry

    def close_game(
        self, belief_defect_prob: Optional[float], belief_reasoning: str = ""
    ) -> GameRecord:
        if self._current is None:
            raise RuntimeError("close_game called with no open game.")
        game = self._current
        game.total_payoff = sum(r.own_payoff for r in game.rounds)
        game.cum_payoff_after = self.total_payoff
        game.belief_defect_prob = belief_defect_prob
        game.belief_reasoning = belief_reasoning
        self.games.append(game)
        self._current = None
        return game

    @property
    def n_games_completed(self) -> int:
        return len(self.games)

    # ------------------------------------------------------------------ #
    # Rendering (compact views for prompts)
    # ------------------------------------------------------------------ #
    def render_completed_games(self, max_lines: int = 0) -> str:
        if not self.games:
            return "None yet. This is your first game."
        games = self.games
        truncated = False
        if max_lines and len(games) > max_lines:
            games = games[-max_lines:]
            truncated = True
        lines = []
        if truncated:
            lines.append(
                f"(Showing the most recent {max_lines} of {len(self.games)} games.)"
            )
        for g in games:
            first_opp = g.rounds[0].opp_action if g.rounds else "?"
            belief = (
                f"{g.belief_defect_prob:.2f}"
                if g.belief_defect_prob is not None
                else "n/a"
            )
            lines.append(
                f"Game {g.game_index + 1} | horizon={g.horizon} | "
                f"rounds={g.n_rounds} | you_coop={g.coop_rate:.0%} | "
                f"opp_coop={g.opp_coop_rate:.0%} | your_payoff={g.total_payoff} | "
                f"opp_first_move={first_opp} | "
                f"you_moves={_compact_moves(g.rounds, 'own_action')} | "
                f"opp_moves={_compact_moves(g.rounds, 'opp_action')} | "
                f"your_end_belief_new_opp_defects={belief}"
            )
        return "\n".join(lines)

    def render_belief_trend(self) -> str:
        vals = [
            f"G{g.game_index + 1}={g.belief_defect_prob:.2f}"
            for g in self.games
            if g.belief_defect_prob is not None
        ]
        if not vals:
            return "No belief estimates yet."
        return ", ".join(vals)

    def render_current_game(self, recent_limit: int = 30) -> str:
        if self._current is None:
            return "No game in progress."
        game = self._current
        header = f"Game {game.game_index + 1} (in progress) | horizon={game.horizon}"
        if game.horizon == "fixed" and game.planned_rounds:
            header += f" | fixed {game.planned_rounds} rounds"
        elif game.horizon == "random" and game.continue_prob is not None:
            header += f" | continues with probability {game.continue_prob}"
        if not game.rounds:
            return header + "\nNo rounds played yet in this game."
        rounds = game.rounds
        lines = [header]
        if recent_limit and len(rounds) > recent_limit:
            earlier = rounds[:-recent_limit]
            coop = sum(r.own_action == "C" for r in earlier) / len(earlier)
            lines.append(
                f"Earlier this game (rounds {earlier[0].round}-"
                f"{earlier[-1].round}): your coop rate {coop:.0%}, "
                f"your game payoff so far {earlier[-1].cum_game_payoff}. "
                f"Full sequences so far: "
                f"you={_compact_moves(rounds, 'own_action')} "
                f"opp={_compact_moves(rounds, 'opp_action')}"
            )
            rounds = rounds[-recent_limit:]
        for r in rounds:
            lines.append(
                f"R{r.round}: you={r.own_action} opp={r.opp_action} "
                f"your_payoff={r.own_payoff} (game_cum={r.cum_game_payoff})"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Serialisation
    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "prior": self.prior,
            "prior_group": self.prior_group,
            "condition": self.condition,
            "total_payoff": self.total_payoff,
            "games": [g.to_dict() for g in self.games],
            "current": self._current.to_dict() if self._current else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AgentMemory":
        mem = cls(
            agent_id=d["agent_id"],
            prior=d["prior"],
            prior_group=d["prior_group"],
            condition=d["condition"],
        )
        mem.total_payoff = d.get("total_payoff", 0)
        mem.games = [GameRecord.from_dict(g) for g in d.get("games", [])]
        if d.get("current"):
            mem._current = GameRecord.from_dict(d["current"])
        return mem


