"""Pure game state. Never pass the evaluator state directly to a model."""

import copy
import hashlib
import random

from .config import SELFISH_COUNTS, Config

PAYOFFS = {("C", "C"): (3, 3), ("D", "C"): (5, 0), ("C", "D"): (0, 5), ("D", "D"): (1, 1)}


def derived_seed(seed, label):
    return int.from_bytes(hashlib.sha256(f"{seed}:{label}".encode()).digest()[:8], "big")


def make_schedule(players, rounds, seed):
    schedule = []
    rng = random.Random(derived_seed(seed, "schedule"))
    while len(schedule) < rounds:
        ring = list(players)
        rng.shuffle(ring)
        cycle = []
        for _ in range(len(ring) - 1):
            cycle.append([[ring[i], ring[-i - 1]] for i in range(len(ring) // 2)])
            ring = [ring[0], ring[-1], *ring[1:-1]]
        rng.shuffle(cycle)
        schedule.extend(cycle)
    return schedule[:rounds]


def initial_state(config: Config):
    players = [f"P{i + 1}" for i in range(config.players)]
    rng = random.Random(derived_seed(config.seed, "roles"))
    if config.marginal_beliefs:
        # Prefixes give nested role rosters across counts while preserving uniform assignment.
        selfish = set(rng.sample(players, len(players))[:config.selfish_count])
    else:
        candidate = rng.choice(players)
        selfish = {candidate} if config.selfish_count else set()
    roles = {p: "selfish" if p in selfish else "good" for p in players}
    assignment = None
    if config.communication in ("good_leader", "selfish_leader"):
        required_role = "good" if config.communication == "good_leader" else "selfish"
        eligible = [p for p in players if roles[p] == required_role]
        leader = random.Random(derived_seed(config.seed, "leader_assignment")).choice(eligible)
        assignment = {"round": 1, "leader": leader, "role": required_role}
    return {
        "players": players,
        "roles": roles,
        "schedule": make_schedule(players, config.rounds, config.seed),
        "round": 1,
        "phase": (
            "pre_round" if config.protocol_version == "rotating-v4"
            or config.communication == "leader" else "action"
        ),
        "pending": {},
        "completed": False,
        "encounters": [],
        "discussions": [],
        "belief_records": [],
        "final_reports": {},
        "midpoint_reports": {},
        "election": None,
        "leader_assignment": assignment,
        "payoffs": dict.fromkeys(players, 0),
    }


def player_view(state, config, player):
    """Explicit allowlist: never include roster, team score, or future pairings."""
    encounters = []
    for event in state["encounters"]:
        if player not in event["players"]:
            continue
        index = event["players"].index(player)
        encounters.append(
            {
                "round": event["round"],
                "opponent": event["players"][1 - index],
                "action": event["actions"][index],
                "opponent_action": event["actions"][1 - index],
                "payoff": event["payoffs"][index],
                "opponent_payoff": event["payoffs"][1 - index],
            }
        )
    discussion = []
    for event in state["discussions"]:
        posts = [
            p for p in event["posts"]
            if p.get("visibility", event["visibility"]) == "public"
            or p["sender"] == player
            or p.get("recipient") == player
        ]
        discussion.append({"after_round": event["after_round"], "posts": posts})
    opponent = None
    if state["phase"] in ("action", "pre_round"):
        opponent = round_opponent(state, player)
    reports = [b for b in state["belief_records"] if b["player"] == player]
    return copy.deepcopy(
        {
            "player": player,
            "players": state["players"],
            "objective": state["roles"][player],
            **(
                {"belief_format": "marginal", "selfish_count_options": list(SELFISH_COUNTS)}
                if config.marginal_beliefs else {}
            ),
            "round": state["round"],
            "total_rounds": config.rounds,
            "phase": state["phase"],
            "communication": config.agent_communication,
            "opponent": opponent,
            "own_cumulative_payoff": state["payoffs"][player],
            "encounters": encounters,
            "discussion_history": discussion,
            "own_previous_reports": reports,
            "own_midpoint_report": state.get("midpoint_reports", {}).get(player),
            "leader": leader_identity(state),
        }
    )


def commit_phase(state, config):
    """Commit only after every player responds; collection never changes a view."""
    assert set(state["pending"]) == set(state["players"])
    pending, round_number = state["pending"], state["round"]
    if state["phase"] == "action":
        for player, response in pending.items():
            state["belief_records"].append(
                {"player": player, "round": round_number, "phase": "action", **response}
            )
        for pair in state["schedule"][round_number - 1]:
            actions = [pending[p]["action"] for p in pair]
            payoffs = list(PAYOFFS[tuple(actions)])
            state["encounters"].append(
                {"round": round_number, "players": pair, "actions": actions, "payoffs": payoffs}
            )
            for player, payoff in zip(pair, payoffs):
                state["payoffs"][player] += payoff
        if config.protocol_version == "rotating-v4":
            if round_number < config.rounds:
                state["round"] += 1
                state["phase"] = "pre_round"
            else:
                state["phase"] = "final"
        elif config.has_midpoint and round_number == config.midpoint_round:
            state["phase"] = "midpoint"
        elif config.communication == "leader" and round_number < config.midpoint_round:
            state["round"] += 1
            state["phase"] = "pre_round"
        else:
            state["phase"] = "discussion" if round_number < config.rounds else "final"
    elif state["phase"] == "midpoint":
        state["midpoint_reports"] = copy.deepcopy(pending)
        if config.communication == "leader":
            counts = {p: sum(r["vote"] == p for r in pending.values()) for p in state["players"]}
            tied = sorted(p for p, n in counts.items() if n == max(counts.values()))
            winner = random.Random(derived_seed(config.seed, "election_tie")).choice(tied)
            state["election"] = {
                "after_round": round_number, "winner": winner,
                "votes": {p: r["vote"] for p, r in pending.items()},
                "counts": counts, "tied_candidates": tied,
            }
        state["phase"] = "discussion"
    elif state["phase"] in ("pre_round", "discussion"):
        pre_round = state["phase"] == "pre_round"
        opponent_only = config.communication == "opponent" or (
            pre_round and config.protocol_version != "rotating-v4"
        )
        state["discussions"].append(
            {
                "after_round": round_number - 1 if pre_round else round_number,
                "phase": state["phase"],
                "visibility": config.communication,
                "posts": [
                    {"sender": p, "content": pending[p]["content"],
                     "recipient": round_opponent(state, p) if opponent_only else None,
                     "visibility": "opponent" if opponent_only else
                     ("public" if can_broadcast(state, config, p) else "private")}
                    for p in state["players"]
                ],
            }
        )
        if not pre_round:
            state["round"] += 1
        state["phase"] = "action"
    elif state["phase"] == "final":
        state["final_reports"] = copy.deepcopy(pending)
        for player, response in pending.items():
            state["belief_records"].append(
                {"player": player, "round": round_number, "phase": "final", **response}
            )
        state["completed"] = True
        state["phase"] = "complete"
    else:
        raise ValueError(f"Unknown phase {state['phase']}")
    state["pending"] = {}


def round_opponent(state, player):
    pair = next(p for p in state["schedule"][state["round"] - 1] if player in p)
    return next(p for p in pair if p != player)


def can_broadcast(state, config, player):
    if config.communication == "public":
        return True
    return config.agent_communication == "leader" and leader_identity(state) == player


def leader_identity(state):
    if state.get("leader_assignment"):
        return state["leader_assignment"]["leader"]
    return state["election"]["winner"] if state.get("election") else None
