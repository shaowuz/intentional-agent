"""Pure game state. Never pass the evaluator state directly to a model."""

import copy
import hashlib
import random

from .config import Config

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
    candidate = random.Random(derived_seed(config.seed, "roles")).choice(players)
    selfish = candidate if config.selfish_count else None
    return {
        "players": players,
        "roles": {p: "selfish" if p == selfish else "good" for p in players},
        "schedule": make_schedule(players, config.rounds, config.seed),
        "round": 1,
        "phase": "action",
        "pending": {},
        "completed": False,
        "encounters": [],
        "discussions": [],
        "belief_records": [],
        "final_reports": {},
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
        posts = event["posts"]
        if config.communication == "none":
            posts = [p for p in posts if p["sender"] == player]
        discussion.append({"after_round": event["after_round"], "posts": posts})
    opponent = None
    if state["phase"] == "action":
        pair = next(p for p in state["schedule"][state["round"] - 1] if player in p)
        opponent = next(p for p in pair if p != player)
    reports = [b for b in state["belief_records"] if b["player"] == player]
    return copy.deepcopy(
        {
            "player": player,
            "players": state["players"],
            "objective": state["roles"][player],
            "round": state["round"],
            "total_rounds": config.rounds,
            "phase": state["phase"],
            "communication": config.communication,
            "opponent": opponent,
            "own_cumulative_payoff": state["payoffs"][player],
            "encounters": encounters,
            "discussion_history": discussion,
            "own_previous_reports": reports,
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
        state["phase"] = "discussion" if round_number < config.rounds else "final"
    elif state["phase"] == "discussion":
        state["discussions"].append(
            {
                "after_round": round_number,
                "visibility": config.communication,
                "posts": [
                    {"sender": p, "content": pending[p]["content"]} for p in state["players"]
                ],
            }
        )
        state["round"] += 1
        state["phase"] = "action"
    else:
        state["final_reports"] = copy.deepcopy(pending)
        for player, response in pending.items():
            state["belief_records"].append(
                {"player": player, "round": round_number, "phase": "final", **response}
            )
        state["completed"] = True
        state["phase"] = "complete"
    state["pending"] = {}
