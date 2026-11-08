"""Private persistent memory for one tournament agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


def _fmt_rate(value: float) -> str:
    if value != value:  # NaN
        return "n/a"
    return f"{value:.0%}"


def _compact(values: List[str]) -> str:
    return "".join(values) if values else "-"


def _compact_numbers(values: List[int]) -> str:
    return " ".join(str(v) for v in values) if values else "-"


@dataclass
class StageEntry:
    stage: int
    own_action: str
    opp_action: str
    own_payoff: int
    opp_payoff: int
    cum_game_own: int
    cum_game_opp: int
    own_reasoning: str = ""

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "own_action": self.own_action,
            "opp_action": self.opp_action,
            "own_payoff": self.own_payoff,
            "opp_payoff": self.opp_payoff,
            "cum_game_own": self.cum_game_own,
            "cum_game_opp": self.cum_game_opp,
            "own_reasoning": self.own_reasoning,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "StageEntry":
        return cls(
            stage=int(d["stage"]),
            own_action=d["own_action"],
            opp_action=d["opp_action"],
            own_payoff=int(d["own_payoff"]),
            opp_payoff=int(d["opp_payoff"]),
            cum_game_own=int(d.get("cum_game_own", 0)),
            cum_game_opp=int(d.get("cum_game_opp", 0)),
            own_reasoning=d.get("own_reasoning", ""),
        )


@dataclass
class GameRecord:
    """One pair-game from this agent's perspective.

    The opponent is deliberately *not* identified.  Only joint actions and
    payoffs are retained, so the agent can never look up who it played.
    """

    round_index: int
    game_index: int
    continue_prob: float
    capped: bool = False
    stages: List[StageEntry] = field(default_factory=list)
    total_own: int = 0
    total_opp: int = 0

    @property
    def n_stages(self) -> int:
        return len(self.stages)

    @property
    def own_coop_rate(self) -> float:
        if not self.stages:
            return float("nan")
        return sum(s.own_action == "C" for s in self.stages) / len(self.stages)

    @property
    def opp_coop_rate(self) -> float:
        if not self.stages:
            return float("nan")
        return sum(s.opp_action == "C" for s in self.stages) / len(self.stages)

    @property
    def mutual_coop_rate(self) -> float:
        if not self.stages:
            return float("nan")
        return sum(
            s.own_action == "C" and s.opp_action == "C" for s in self.stages
        ) / len(self.stages)

    def to_dict(self) -> dict:
        return {
            "round": self.round_index,
            "game_index": self.game_index,
            "continue_prob": self.continue_prob,
            "capped": self.capped,
            "stages": [s.to_dict() for s in self.stages],
            "total_own": self.total_own,
            "total_opp": self.total_opp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GameRecord":
        return cls(
            round_index=int(d["round"]),
            game_index=int(d.get("game_index", 0)),
            continue_prob=float(d.get("continue_prob", 0.95)),
            capped=bool(d.get("capped", False)),
            stages=[StageEntry.from_dict(s) for s in d.get("stages", [])],
            total_own=int(d.get("total_own", 0)),
            total_opp=int(d.get("total_opp", 0)),
        )


@dataclass
class ReflectionRecord:
    round_index: int
    change_strategy: bool
    reason: str
    strategy_for_next_round: str
    strategy_before: Optional[str] = None
    parse_status: str = "ok"
    response_text: str = ""
    attempts: int = 1

    def to_dict(self) -> dict:
        return {
            "round": self.round_index,
            "change_strategy": self.change_strategy,
            "reason": self.reason,
            "strategy_for_next_round": self.strategy_for_next_round,
            "strategy_before": self.strategy_before,
            "parse_status": self.parse_status,
            "response_text": self.response_text,
            "attempts": self.attempts,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ReflectionRecord":
        return cls(
            round_index=int(d["round"]),
            change_strategy=bool(d["change_strategy"]),
            reason=d.get("reason", ""),
            strategy_for_next_round=d.get("strategy_for_next_round", ""),
            strategy_before=d.get("strategy_before"),
            parse_status=d.get("parse_status", "ok"),
            response_text=d.get("response_text", ""),
            attempts=int(d.get("attempts", 1)),
        )


class AgentMemory:
    """Complete, isolated memory for a single agent."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.games: List[GameRecord] = []
        self.reflections: List[ReflectionRecord] = []
        self.round_payoffs: Dict[int, int] = {}
        self.round_ranking_points: Dict[int, float] = {}
        self.total_payoff: int = 0
        self.total_ranking_points: float = 0.0
        self._current: Optional[GameRecord] = None

    # ------------------------------------------------------------------ #
    # Mutation
    # ------------------------------------------------------------------ #
    def begin_game(
        self, round_index: int, game_index: int, continue_prob: float
    ) -> None:
        if self._current is not None:
            raise RuntimeError(
                f"Agent {self.agent_id} already has an open game."
            )
        self._current = GameRecord(
            round_index=round_index,
            game_index=game_index,
            continue_prob=continue_prob,
        )

    def observe_stage(
        self,
        stage: int,
        own_action: str,
        opp_action: str,
        own_payoff: int,
        opp_payoff: int,
        own_reasoning: str = "",
    ) -> StageEntry:
        if self._current is None:
            raise RuntimeError("observe_stage called with no open game.")
        if stage != len(self._current.stages) + 1:
            raise ValueError(
                f"Stage {stage} observed out of order for agent {self.agent_id}."
            )
        prior = self._current.stages
        cum_own = sum(s.own_payoff for s in prior) + int(own_payoff)
        cum_opp = sum(s.opp_payoff for s in prior) + int(opp_payoff)
        entry = StageEntry(
            stage=stage,
            own_action=own_action,
            opp_action=opp_action,
            own_payoff=int(own_payoff),
            opp_payoff=int(opp_payoff),
            cum_game_own=cum_own,
            cum_game_opp=cum_opp,
            own_reasoning=own_reasoning,
        )
        self._current.stages.append(entry)
        return entry

    def end_game(self, capped: bool = False) -> GameRecord:
        if self._current is None:
            raise RuntimeError("end_game called with no open game.")
        game = self._current
        game.capped = capped
        game.total_own = sum(s.own_payoff for s in game.stages)
        game.total_opp = sum(s.opp_payoff for s in game.stages)
        self.games.append(game)
        self._current = None
        return game

    def record_round_result(
        self, round_index: int, payoff: int, points: float
    ) -> None:
        self.round_payoffs[round_index] = int(payoff)
        self.round_ranking_points[round_index] = float(points)
        self.total_payoff += int(payoff)
        self.total_ranking_points += float(points)

    def record_reflection(self, reflection: ReflectionRecord) -> None:
        self.reflections.append(reflection)

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #
    @property
    def current_game(self) -> Optional[GameRecord]:
        return self._current

    @property
    def current_strategy(self) -> Optional[str]:
        for reflection in reversed(self.reflections):
            if reflection.strategy_for_next_round.strip():
                return reflection.strategy_for_next_round.strip()
        return None

    @property
    def n_games_completed(self) -> int:
        return len(self.games)

    # ------------------------------------------------------------------ #
    # Prompt views (own information only)
    # ------------------------------------------------------------------ #
    def render_previous_games(self, exclude_round: Optional[int] = None) -> str:
        games = [
            g
            for g in self.games
            if exclude_round is None or g.round_index != exclude_round
        ]
        if not games:
            return "None yet. This is your first pair-game."
        lines = []
        for g in games:
            cap = " (length cap reached)" if g.capped else ""
            lines.append(
                f"Round {g.round_index} | stages={g.n_stages} | "
                f"your_payoff={g.total_own} | opponent_payoff={g.total_opp} | "
                f"your_coop={_fmt_rate(g.own_coop_rate)} | "
                f"opponent_coop={_fmt_rate(g.opp_coop_rate)}{cap}"
            )
            lines.append(
                "  your moves:    "
                + _compact([s.own_action for s in g.stages])
            )
            lines.append(
                "  opponent moves:"
                + _compact([s.opp_action for s in g.stages])
            )
            lines.append(
                "  your payoffs:  "
                + _compact_numbers([s.own_payoff for s in g.stages])
            )
        return "\n".join(lines)

    def render_current_game(self) -> str:
        game = self._current
        if game is None:
            return "No game in progress."
        if not game.stages:
            return "No stages played yet in this pair-game."
        lines = []
        for s in game.stages:
            lines.append(
                f"Stage {s.stage}: you={s.own_action} opp={s.opp_action} | "
                f"your_payoff={s.own_payoff} opponent_payoff={s.opp_payoff} | "
                f"game_totals you={s.cum_game_own} opp={s.cum_game_opp}"
            )
        return "\n".join(lines)

    def render_round_game(self, round_index: int) -> str:
        matches = [g for g in self.games if g.round_index == round_index]
        if not matches:
            return "No completed pair-game for this round."
        game = matches[-1]
        cap = " (length cap reached)" if game.capped else ""
        lines = [
            f"Your pair-game in round {round_index}: stages={game.n_stages} | "
            f"your_payoff={game.total_own} | opponent_payoff={game.total_opp}{cap}"
        ]
        for s in game.stages:
            lines.append(
                f"Stage {s.stage}: you={s.own_action} opp={s.opp_action} | "
                f"your_payoff={s.own_payoff} opponent_payoff={s.opp_payoff}"
            )
        return "\n".join(lines)

    def render_round_results(self) -> str:
        if not self.round_payoffs:
            return "No completed tournament rounds yet."
        lines = []
        for r in sorted(self.round_payoffs):
            lines.append(
                f"Round {r}: raw payoff={self.round_payoffs[r]} | "
                f"ranking points={self.round_ranking_points.get(r, 0):g}"
            )
        return "\n".join(lines)

    def render_reflection_history(self) -> str:
        if not self.reflections:
            return "No strategy reflections yet."
        lines = []
        for ref in self.reflections:
            changed = "yes" if ref.change_strategy else "no"
            lines.append(
                f"After round {ref.round_index}: changed={changed} | "
                f"reason: {ref.reason} | strategy for next round: "
                f"{ref.strategy_for_next_round}"
            )
        return "\n".join(lines)


    # ------------------------------------------------------------------ #
    # Serialisation
    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "total_payoff": self.total_payoff,
            "total_ranking_points": self.total_ranking_points,
            "round_payoffs": {str(k): v for k, v in self.round_payoffs.items()},
            "round_ranking_points": {
                str(k): v for k, v in self.round_ranking_points.items()
            },
            "games": [g.to_dict() for g in self.games],
            "reflections": [r.to_dict() for r in self.reflections],
            "current_strategy": self.current_strategy,
            "current": self._current.to_dict() if self._current else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AgentMemory":
        memory = cls(agent_id=d["agent_id"])
        memory.total_payoff = int(d.get("total_payoff", 0))
        memory.total_ranking_points = float(
            d.get("total_ranking_points", 0.0)
        )
        memory.round_payoffs = {
            int(k): int(v) for k, v in d.get("round_payoffs", {}).items()
        }
        memory.round_ranking_points = {
            int(k): float(v)
            for k, v in d.get("round_ranking_points", {}).items()
        }
        memory.games = [GameRecord.from_dict(g) for g in d.get("games", [])]
        memory.reflections = [
            ReflectionRecord.from_dict(r) for r in d.get("reflections", [])
        ]
        if d.get("current"):
            memory._current = GameRecord.from_dict(d["current"])
        return memory

    def summary(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "total_payoff": self.total_payoff,
            "total_ranking_points": self.total_ranking_points,
            "n_games": len(self.games),
            "n_reflections": len(self.reflections),
            "current_strategy": self.current_strategy,
        }

