"""The tournament engine: pairings, simultaneous play, scoring and reflection."""

from __future__ import annotations

import traceback
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ipd.usage import UsageTracker

from .agent import RankedAgent, build_ranked_client
from .config import TournamentConfig
from .game import (
    COOPERATE,
    cooperation_rate,
    mutual_cooperation_rate,
    payoff,
    per_agent_cooperation,
    sample_round_length,
)
from .memory import AgentMemory, ReflectionRecord
from .pairing import sample_pairs
from .recorder import ResultsRecorder
from .scoring import assert_round_points_sum, ranking_points


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TournamentRunner:
    """Run one complete ranked tournament."""

    def __init__(
        self,
        config: TournamentConfig,
        resume: bool = False,
        verbose: bool = True,
        client=None,
    ):
        config.validate()
        self.config = config
        self.resume = resume
        self.verbose = verbose
        self.client = client or build_ranked_client(config)
        self.usage = UsageTracker(
            input_per_1k=config.llm.pricing.input_per_1k_tokens,
            output_per_1k=config.llm.pricing.output_per_1k_tokens,
        )
        self.recorder = ResultsRecorder(config.output_dir, config)
        self.agents: Dict[str, RankedAgent] = {
            agent_id: RankedAgent(
                agent_id,
                config,
                self.client,
                self.usage,
                call_logger=self.recorder.buffer_call,
            )
            for agent_id in config.agents
        }
        self.started_at: Optional[str] = None

    @property
    def mode(self) -> str:
        return (
            "mock"
            if self.config.llm.provider.lower() == "mock"
            else "live"
        )

    # ------------------------------------------------------------------ #
    # Top-level lifecycle
    # ------------------------------------------------------------------ #
    def run(self) -> dict:
        self.started_at = _now()
        checkpoint = self.recorder.initialize(self.resume)
        start_round = 1
        if self.resume and checkpoint:
            start_round = int(checkpoint.get("next_round", 1))
            if start_round > 1:
                self._load_memories(start_round - 1)

        self.recorder.write_meta(
            mode=self.mode, status="running", started_at=self.started_at
        )
        self.recorder.write_status(
            "running", completed_rounds=start_round - 1
        )
        try:
            for round_index in range(start_round, self.config.n_rounds + 1):
                self.play_round(round_index)
            summary = self._summary()
            usage_summary = self.usage.summary()
            self.recorder.write_status(
                "completed",
                usage_summary=usage_summary,
                completed_rounds=self.config.n_rounds,
            )
            self.recorder.write_meta(
                mode=self.mode,
                status="completed",
                started_at=self.started_at,
                finished_at=_now(),
                usage_summary=usage_summary,
            )
            return summary
        except Exception as exc:  # noqa: BLE001 - preserve evidence and re-raise
            self.recorder.flush()
            self.recorder._flush_usage(self.usage)
            error = traceback.format_exc()
            usage_summary = self.usage.summary()
            self.recorder.write_status(
                "failed", error=error[-8000:], usage_summary=usage_summary
            )
            self.recorder.write_meta(
                mode=self.mode,
                status="failed",
                started_at=self.started_at,
                finished_at=_now(),
                usage_summary=usage_summary,
                extra={
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:2000],
                },
            )
            raise

    def _load_memories(self, round_index: int) -> None:
        for agent_id, agent in self.agents.items():
            snapshot = self.recorder.load_memory_snapshot(
                agent_id, round_index
            )
            if snapshot is None:
                raise RuntimeError(
                    f"Cannot resume: missing memory snapshot for agent "
                    f"{agent_id} after round {round_index}."
                )
            agent.memory = AgentMemory.from_dict(snapshot)

    def _summary(self) -> dict:
        return {
            "experiment": self.config.name,
            "seed": self.config.seed,
            "output_dir": self.config.output_dir,
            "mode": self.mode,
            "n_rounds": self.config.n_rounds,
            "agents": {
                agent_id: agent.memory.summary()
                for agent_id, agent in self.agents.items()
            },
            "usage": self.usage.summary(),
            "completed_at": _now(),
        }

    # ------------------------------------------------------------------ #
    # One tournament round
    # ------------------------------------------------------------------ #
    def play_round(self, round_index: int) -> None:
        config = self.config
        pairs = sample_pairs(config.agents, config.seed, round_index)
        length, capped = sample_round_length(
            config.seed,
            round_index,
            config.continue_prob,
            config.max_stages,
        )
        self.recorder.buffer(
            "pairings",
            {
                "round": round_index,
                "pairs": [list(pair) for pair in pairs],
                "game_length": length,
                "capped": capped,
            },
        )

        pair_stage_records: Dict[int, List[dict]] = {}
        for game_index, (agent_x, agent_y) in enumerate(pairs, start=1):
            pair_stage_records[game_index] = []
            self.agents[agent_x].begin_game(
                round_index, game_index, config.continue_prob
            )
            self.agents[agent_y].begin_game(
                round_index, game_index, config.continue_prob
            )

        # Stage loop.  All four prompts are built *before* any model call and
        # all memories are updated only after all four actions are returned.
        # This guarantees simultaneous decisions within each pair-game and
        # across the two games of the round.
        for stage in range(1, length + 1):
            prompts = {
                agent_id: self.agents[agent_id].build_decision_prompt(
                    round_index, stage
                )
                for agent_id in config.agents
            }
            results = {
                agent_id: self.agents[agent_id].choose_action(
                    prompts[agent_id], round_index, stage
                )
                for agent_id in config.agents
            }

            for game_index, (agent_x, agent_y) in enumerate(pairs, start=1):
                action_x = results[agent_x]["action"]
                action_y = results[agent_y]["action"]
                payoff_x = payoff(action_x, action_y)
                payoff_y = payoff(action_y, action_x)

                self.agents[agent_x].observe_stage(
                    stage,
                    action_x,
                    action_y,
                    payoff_x,
                    payoff_y,
                    results[agent_x]["reasoning"],
                )
                self.agents[agent_y].observe_stage(
                    stage,
                    action_y,
                    action_x,
                    payoff_y,
                    payoff_x,
                    results[agent_y]["reasoning"],
                )

                game_x = self.agents[agent_x].memory.current_game
                game_y = self.agents[agent_y].memory.current_game
                stage_record = {
                    "round": round_index,
                    "game_index": game_index,
                    "stage": stage,
                    "participants": [agent_x, agent_y],
                    "actions": {agent_x: action_x, agent_y: action_y},
                    "payoffs": {agent_x: payoff_x, agent_y: payoff_y},
                    "reasoning": {
                        agent_x: results[agent_x]["reasoning"],
                        agent_y: results[agent_y]["reasoning"],
                    },
                    "parse_status": {
                        agent_x: results[agent_x]["parse_status"],
                        agent_y: results[agent_y]["parse_status"],
                    },
                    "attempts": {
                        agent_x: results[agent_x]["attempts"],
                        agent_y: results[agent_y]["attempts"],
                    },
                    "cum_game_payoff": {
                        agent_x: game_x.stages[-1].cum_game_own,
                        agent_y: game_y.stages[-1].cum_game_own,
                    },
                }
                pair_stage_records[game_index].append(stage_record)
                self.recorder.buffer("stages", stage_record)

        # Close both games and build experimenter-visible game records.
        raw_payoffs: Dict[str, int] = {}
        for game_index, (agent_x, agent_y) in enumerate(pairs, start=1):
            game_x = self.agents[agent_x].end_game(capped=capped)
            game_y = self.agents[agent_y].end_game(capped=capped)
            stage_records = pair_stage_records[game_index]
            game_record = {
                "round": round_index,
                "game_index": game_index,
                "participants": [agent_x, agent_y],
                "length": length,
                "capped": capped,
                "stages": stage_records,
                "totals": {
                    agent_x: game_x.total_own,
                    agent_y: game_y.total_own,
                },
                "cooperation": {
                    agent_x: game_x.own_coop_rate,
                    agent_y: game_y.own_coop_rate,
                },
                "mutual_cooperation_rate": mutual_cooperation_rate(
                    stage_records
                ),
            }
            self.recorder.buffer("games", game_record)
            raw_payoffs[agent_x] = game_x.total_own
            raw_payoffs[agent_y] = game_y.total_own


        # Independent per-round ranking: raw payoffs only, ties averaged.
        points = ranking_points(raw_payoffs, config.ranking_points)
        assert_round_points_sum(points, sum(config.ranking_points))
        strategy_before = {
            agent_id: self.agents[agent_id].current_strategy
            for agent_id in config.agents
        }
        for agent_id in config.agents:
            self.agents[agent_id].record_round_result(
                round_index, raw_payoffs[agent_id], points[agent_id]
            )

        all_stage_records = [
            rec
            for game_index in sorted(pair_stage_records)
            for rec in pair_stage_records[game_index]
        ]
        per_agent = per_agent_cooperation(all_stage_records)
        per_agent_coop = {
            agent_id: (
                (count / total) if total else float("nan")
            )
            for agent_id, (count, total) in per_agent.items()
        }

        # Reflection after the scores are assigned.  This is done for every
        # round, including the final one; the final reflection is recorded but
        # cannot affect any later game.
        reflection_records: Dict[str, ReflectionRecord] = {}
        for agent_id in config.agents:
            agent = self.agents[agent_id]
            parsed = agent.reflect(
                round_index,
                raw_payoffs[agent_id],
                points[agent_id],
                strategy_before[agent_id],
            )
            reflection = ReflectionRecord(
                round_index=round_index,
                change_strategy=bool(parsed["change_strategy"]),
                reason=parsed["reason"],
                strategy_for_next_round=parsed["strategy_for_next_round"],
                strategy_before=strategy_before[agent_id],
                parse_status=parsed["parse_status"],
                response_text=parsed.get("response_text", ""),
                attempts=int(parsed.get("attempts", 1)),
            )
            agent.record_reflection(reflection)
            reflection_records[agent_id] = reflection
            self.recorder.buffer(
                "reflections",
                {"agent_id": agent_id, **reflection.to_dict()},
            )
            self.recorder.buffer(
                "strategies",
                {
                    "round": round_index,
                    "agent_id": agent_id,
                    "strategy_before": strategy_before[agent_id],
                    "strategy_after": reflection.strategy_for_next_round,
                    "change_strategy": reflection.change_strategy,
                    "text_changed": (
                        strategy_before[agent_id]
                        != reflection.strategy_for_next_round
                    ),
                    "reason": reflection.reason,
                },
            )

        round_record = {
            "round": round_index,
            "game_length": length,
            "capped": capped,
            "pairs": [list(pair) for pair in pairs],
            "raw_payoffs": raw_payoffs,
            "ranking_points": points,
            "cumulative_raw_payoffs": {
                agent_id: self.agents[agent_id].memory.total_payoff
                for agent_id in config.agents
            },
            "cumulative_ranking_points": {
                agent_id: self.agents[
                    agent_id
                ].memory.total_ranking_points
                for agent_id in config.agents
            },
            "cooperation_rate": cooperation_rate(all_stage_records),
            "mutual_cooperation_rate": mutual_cooperation_rate(
                all_stage_records
            ),
            "per_agent_cooperation_rate": per_agent_coop,
            "strategy_before_round": strategy_before,
            "strategy_after_round": {
                agent_id: self.agents[agent_id].current_strategy
                for agent_id in config.agents
            },
            "reflection_change": {
                agent_id: reflection_records[agent_id].change_strategy
                for agent_id in config.agents
            },
        }
        self.recorder.buffer("rounds", round_record)
        self.recorder.commit_round(
            round_index, self.agents, self.usage
        )

        if self.verbose:
            points_text = " ".join(
                f"{agent_id}={points[agent_id]:g}"
                for agent_id in config.agents
            )
            payoffs_text = " ".join(
                f"{agent_id}={raw_payoffs[agent_id]}"
                for agent_id in config.agents
            )
            print(
                f"Round {round_index}/{config.n_rounds} | "
                f"length={length}{' (capped)' if capped else ''} | "
                f"payoffs: {payoffs_text} | points: {points_text}"
            )

