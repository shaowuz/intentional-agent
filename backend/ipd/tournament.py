"""Tournament runner: pairing, simultaneous play, termination, recording."""

from __future__ import annotations

import json
import os
import random
import time
from typing import Dict, List, Optional

from .agent import LLMAgent
from .config import ExperimentConfig, save_config_snapshot
from .game import FIXED, payoff
from .llm import build_client
from .pairing import PairingManager
from .recorder import ConditionRecorder, read_jsonl
from .usage import UsageTracker
from .utils import ensure_dir, rng_for


def make_agent_id(prior_index: int, agent_index: int) -> str:
    """Stable, compact agent id, e.g. ``p0_a3`` for prior #0, agent #3."""
    return f"p{prior_index}_a{agent_index}"


def prior_group_label(prior: float) -> str:
    return f"{prior:.1f}"


def build_agents(
    config: ExperimentConfig,
    condition: str,
    client,
    usage_tracker: UsageTracker,
) -> List[LLMAgent]:
    """Instantiate the population for one condition (fresh, isolated state)."""
    agents: List[LLMAgent] = []
    for pi, prior in enumerate(config.population.priors):
        for ai in range(config.population.agents_per_prior):
            agent_id = make_agent_id(pi, ai)
            agents.append(
                LLMAgent(
                    agent_id=agent_id,
                    prior=prior,
                    prior_group=prior_group_label(prior),
                    condition=condition,
                    client=client,
                    usage_tracker=usage_tracker,
                    fixed_rounds=config.fixed_rounds,
                    continue_prob=config.continue_prob,
                    recent_rounds_in_prompt=config.memory.recent_rounds_in_prompt,
                    max_completed_game_lines=config.memory.max_completed_game_lines,
                )
            )
    return agents


def roster_records(config: ExperimentConfig) -> List[dict]:
    """Return the full roster for all conditions (for provenance)."""
    records = []
    for condition in config.conditions:
        for pi, prior in enumerate(config.population.priors):
            for ai in range(config.population.agents_per_prior):
                records.append(
                    {
                        "experiment": config.name,
                        "condition": condition,
                        "agent_id": make_agent_id(pi, ai),
                        "prior": prior,
                        "prior_group": prior_group_label(prior),
                        "prior_index": pi,
                        "agent_index": ai,
                    }
                )
    return records


def rebuild_memories(agents_by_id: Dict[str, LLMAgent], games: List[dict]) -> None:
    """Rebuild each agent's memory from previously recorded game records."""
    from .memory import GameRecord, RoundEntry

    games_sorted = sorted(games, key=lambda g: g["game_index"])
    for game in games_sorted:
        parts = game["participants"]
        for aid in parts:
            other = parts[0] if parts[1] == aid else parts[1]
            agent = agents_by_id.get(aid)
            if agent is None:
                continue
            entries = []
            for rnd in game["rounds"]:
                entries.append(
                    RoundEntry(
                        round=rnd["round"],
                        own_action=rnd["actions"][aid],
                        opp_action=rnd["actions"][other],
                        own_payoff=rnd["payoffs"][aid],
                        cum_game_payoff=rnd["cum_game"][aid],
                        lifetime_cum_payoff=rnd["lifetime_cum"][aid],
                        own_reasoning=rnd.get("reasoning", {}).get(aid, ""),
                    )
                )
            belief = game.get("beliefs", {}).get(aid, {})
            rec = GameRecord(
                game_index=game["game_index"],
                opponent_id=other,
                condition=game["condition"],
                horizon=game["horizon"],
                planned_rounds=game.get("planned_rounds"),
                continue_prob=game.get("continue_prob"),
                rounds=entries,
                total_payoff=game["totals"][aid]["game_payoff"],
                cum_payoff_after=game["totals"][aid]["lifetime_cum_payoff"],
                belief_defect_prob=belief.get("defect_probability"),
                belief_reasoning=belief.get("reasoning", ""),
            )
            agent.memory.games.append(rec)
    for agent in agents_by_id.values():
        agent.memory.total_payoff = sum(g.total_payoff for g in agent.memory.games)


def play_match(
    agent_a: LLMAgent,
    agent_b: LLMAgent,
    game_index: int,
    pair_index: int,
    condition: str,
    config: ExperimentConfig,
    horizon_rng: random.Random,
) -> dict:
    """Play one complete game between two agents and return record dicts."""
    a_id, b_id = agent_a.agent_id, agent_b.agent_id
    fixed = condition == FIXED
    planned_rounds = config.fixed_rounds if fixed else None
    continue_prob = None if fixed else config.continue_prob

    agent_a.start_game(game_index, b_id, planned_rounds, continue_prob)
    agent_b.start_game(game_index, a_id, planned_rounds, continue_prob)

    rounds_records = []
    game_rounds = []
    capped = False
    round_no = 1
    while True:
        # --- simultaneous choice: both decide before any reveal ---------
        a_decision = agent_a.choose_action(round_no)
        b_decision = agent_b.choose_action(round_no)

        a_action, b_action = a_decision["action"], b_decision["action"]
        a_pay = payoff(a_action, b_action)
        b_pay = payoff(b_action, a_action)

        a_entry = agent_a.observe(
            round_no, a_action, b_action, a_pay, a_decision["reasoning"]
        )
        b_entry = agent_b.observe(
            round_no, b_action, a_action, b_pay, b_decision["reasoning"]
        )

        game_rounds.append(
            {
                "round": round_no,
                "actions": {a_id: a_action, b_id: b_action},
                "payoffs": {a_id: a_pay, b_id: b_pay},
                "cum_game": {
                    a_id: a_entry.cum_game_payoff,
                    b_id: b_entry.cum_game_payoff,
                },
                "lifetime_cum": {
                    a_id: a_entry.lifetime_cum_payoff,
                    b_id: b_entry.lifetime_cum_payoff,
                },
                "parse_status": {
                    a_id: a_decision["parse_status"],
                    b_id: b_decision["parse_status"],
                },
                "reasoning": {
                    a_id: a_decision["reasoning"][:200],
                    b_id: b_decision["reasoning"][:200],
                },
            }
        )

        # Denormalised per-agent round records for analysis.
        for aid, other, act, opp_act, pay, entry, decision in (
            (a_id, b_id, a_action, b_action, a_pay, a_entry, a_decision),
            (b_id, a_id, b_action, a_action, b_pay, b_entry, b_decision),
        ):
            agent = agent_a if aid == a_id else agent_b
            rounds_records.append(
                {
                    "experiment": config.name,
                    "condition": condition,
                    "game_index": game_index,
                    "pair_index": pair_index,
                    "round": round_no,
                    "agent_id": aid,
                    "prior": agent.prior,
                    "prior_group": agent.prior_group,
                    "opponent_id": other,
                    "horizon": condition,
                    "planned_rounds": planned_rounds,
                    "continue_prob": continue_prob,
                    "own_action": act,
                    "opp_action": opp_act,
                    "own_payoff": pay,
                    "cum_game_payoff": entry.cum_game_payoff,
                    "lifetime_cum_payoff": entry.lifetime_cum_payoff,
                    "parse_status": decision["parse_status"],
                    "reasoning": decision["reasoning"][:200],
                }
            )

        # --- termination ------------------------------------------------
        if fixed:
            if round_no >= config.fixed_rounds:
                break
        else:
            if round_no >= config.max_rounds_random:
                capped = True
                break
            if horizon_rng.random() >= config.continue_prob:
                break
        round_no += 1

    # --- End of game. Close first so the just-finished game is part of the
    #     memory view, then ask each agent for a belief about new opponents.
    agent_a.end_game(None, "")
    agent_b.end_game(None, "")
    a_belief, a_meta = agent_a.estimate_belief()
    b_belief, b_meta = agent_b.estimate_belief()
    agent_a.memory.games[-1].belief_defect_prob = a_belief
    agent_a.memory.games[-1].belief_reasoning = a_meta.get("reasoning", "")
    agent_b.memory.games[-1].belief_defect_prob = b_belief
    agent_b.memory.games[-1].belief_reasoning = b_meta.get("reasoning", "")

    beliefs = {
        a_id: {
            "defect_probability": a_belief,
            "reasoning": a_meta.get("reasoning", "")[:300],
            "parse_status": a_meta.get("parse_status", "unknown"),
        },
        b_id: {
            "defect_probability": b_belief,
            "reasoning": b_meta.get("reasoning", "")[:300],
            "parse_status": b_meta.get("parse_status", "unknown"),
        },
    }
    totals = {}
    for agent in (agent_a, agent_b):
        game = agent.memory.games[-1]
        totals[agent.agent_id] = {
            "game_payoff": game.total_payoff,
            "lifetime_cum_payoff": game.cum_payoff_after,
            "coop_rate": game.coop_rate,
        }

    game_record = {
        "experiment": config.name,
        "condition": condition,
        "game_index": game_index,
        "pair_index": pair_index,
        "horizon": condition,
        "planned_rounds": planned_rounds,
        "continue_prob": continue_prob,
        "actual_rounds": len(game_rounds),
        "capped": capped,
        "participants": [a_id, b_id],
        "prior": {a_id: agent_a.prior, b_id: agent_b.prior},
        "prior_group": {a_id: agent_a.prior_group, b_id: agent_b.prior_group},
        "rounds": game_rounds,
        "totals": totals,
        "beliefs": beliefs,
    }
    belief_records = []
    for agent in (agent_a, agent_b):
        belief_records.append(
            {
                "experiment": config.name,
                "condition": condition,
                "game_index": game_index,
                "agent_id": agent.agent_id,
                "prior": agent.prior,
                "prior_group": agent.prior_group,
                "defect_probability": beliefs[agent.agent_id]["defect_probability"],
                "parse_status": beliefs[agent.agent_id]["parse_status"],
                "reasoning": beliefs[agent.agent_id]["reasoning"],
                "n_games_completed": agent.memory.n_games_completed,
            }
        )
    return {
        "game_record": game_record,
        "round_records": rounds_records,
        "belief_records": belief_records,
    }


class ExperimentRunner:
    """Runs all conditions of an experiment, with checkpoint/resume support."""

    def __init__(
        self,
        config: ExperimentConfig,
        resume: bool = False,
        verbose: bool = True,
        conditions: Optional[List[str]] = None,
    ):
        self.config = config
        self.resume = resume
        self.verbose = verbose
        self.conditions = conditions or list(config.conditions)
        self.root = ensure_dir(config.output_dir)

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"[ipd] {msg}", flush=True)

    # ------------------------------------------------------------------ #
    def _write_root_files(self) -> None:
        save_config_snapshot(
            self.config, os.path.join(self.root, "config_snapshot.yaml")
        )
        with open(os.path.join(self.root, "roster.json"), "w", encoding="utf-8") as fh:
            json.dump(roster_records(self.config), fh, indent=2)

        meta_path = os.path.join(self.root, "experiment_meta.json")
        meta = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as fh:
                    meta = json.load(fh)
            except json.JSONDecodeError:
                meta = {}
        meta.setdefault("experiment", self.config.name)
        meta.setdefault("started_at", time.strftime("%Y-%m-%dT%H:%M:%S"))
        meta.update(
            {
                "seed": self.config.seed,
                "config_fingerprint": self.config.fingerprint(),
                "llm_provider": self.config.llm.provider,
                "llm_model": self.config.llm.model,
                "conditions": self.conditions,
                "n_agents_per_condition": self.config.population.n_agents(),
                "games_per_agent": self.config.games_per_agent,
                "fixed_rounds": self.config.fixed_rounds,
                "continue_prob": self.config.continue_prob,
                "last_updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
        )
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)

    # ------------------------------------------------------------------ #
    def run(self) -> Dict[str, dict]:
        self._write_root_files()
        summaries: Dict[str, dict] = {}
        for condition in self.conditions:
            summaries[condition] = self.run_condition(condition)
        self._log("Experiment complete.")
        return summaries

    # ------------------------------------------------------------------ #
    def run_condition(self, condition: str) -> dict:
        cfg = self.config
        client = build_client(cfg.llm)
        pricing = cfg.llm.pricing
        usage = UsageTracker(
            input_per_1k=pricing.input_per_1k_tokens,
            output_per_1k=pricing.output_per_1k_tokens,
        )
        agents = build_agents(cfg, condition, client, usage)
        by_id = {a.agent_id: a for a in agents}

        recorder = ConditionRecorder(
            base_dir=self.root,
            condition=condition,
            experiment_name=cfg.name,
            seed=cfg.seed,
            fingerprint=cfg.fingerprint(),
        )
        existing = recorder.read_checkpoint() if self.resume else None
        start_index = 0
        if existing:
            if (
                existing.get("seed") != cfg.seed
                or existing.get("config_fingerprint") != cfg.fingerprint()
            ):
                raise RuntimeError(
                    "Checkpoint exists for a different seed/config fingerprint; "
                    "refusing to resume. Delete the output dir or use a new one."
                )
            recorder.initialize(resume=True)
            start_index = int(existing.get("next_game_index", 0))
            recorder.truncate_to_game_index(start_index)
            rebuild_memories(by_id, recorder.load_games())
            for rec in read_jsonl(recorder.usage_path):
                usage.total_input_tokens += rec.get("input_tokens", 0)
                usage.total_output_tokens += rec.get("output_tokens", 0)
                usage.total_cost += rec.get("cost_usd", 0.0)
                usage.n_calls += 1
            self._log(
                f"Resuming {condition!r} at game {start_index + 1}/"
                f"{cfg.games_per_agent} ({len(agents)} agents)"
            )
        else:
            recorder.initialize(resume=False)
            self._log(
                f"Starting {condition!r}: {len(agents)} agents, "
                f"{cfg.games_per_agent} games each"
            )

        pairing = PairingManager(
            cfg.pairing_strategy, len(agents), cfg.games_per_agent, cfg.seed
        )

        for g in range(start_index, cfg.games_per_agent):
            pairs = pairing.pairs_for_game(g)
            for pair_index, (i, j) in enumerate(pairs):
                agent_a, agent_b = agents[i], agents[j]
                horizon_rng = rng_for(cfg.seed, condition, "horizon", g, pair_index)
                result = play_match(
                    agent_a, agent_b, g, pair_index, condition, cfg, horizon_rng
                )
                recorder.buffer_game(result["game_record"])
                for rr in result["round_records"]:
                    recorder.buffer_round(rr)
                for br in result["belief_records"]:
                    recorder.buffer_belief(br)
            recorder.buffer_usage(usage.drain())
            extra = usage.summary()
            extra["llm_provider"] = cfg.llm.provider
            extra["llm_model"] = cfg.llm.model
            recorder.commit_batch(g + 1, extra=extra)
            cost_str = (
                f"~${usage.total_cost:.4f}"
                if usage.pricing_configured
                else "n/a (pricing not configured)"
            )
            self._log(
                f"{condition}: completed game {g + 1}/{cfg.games_per_agent} "
                f"(cumulative est. cost {cost_str})"
            )

        summary = usage.summary()
        summary["condition"] = condition
        summary["games_completed"] = cfg.games_per_agent
        with open(
            os.path.join(recorder.dir, "usage_summary.json"), "w", encoding="utf-8"
        ) as fh:
            json.dump(summary, fh, indent=2)
        self._log(f"{condition}: done. {summary}")
        return summary





