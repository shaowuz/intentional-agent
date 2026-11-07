"""Personality swarm game: N agents, no hidden roles, public chat, rotating Prisoner's Dilemma.

Every agent has the same goal (as many points as possible for itself) and its own
randomly drawn personality. Reuses the team's schedule, payoffs and OpenRouter provider.
"""

import json
import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from types import SimpleNamespace

import jsonschema

from swarm_game.game import PAYOFFS, derived_seed, make_schedule
from swarm_game.providers import Completion, OpenRouterProvider

from .traits import describe, sample_personality

MESSAGE_CHARS = 500
REASON_CHARS = 300

RULES = """You are a player in a multi-round game. Return only the requested JSON.
The player view in the user message is all the game information you have. You have no tools.

There are {players} players and exactly {rounds} rounds. Each round you are paired with one
other player and you both choose at the same time: C (cooperate) or D (defect).
Points (your action, their action -> your points, their points):
C,C -> 3,3; D,C -> 5,0; C,D -> 0,5; D,D -> 1,1.
A rotation makes you meet every other player about once before meeting anyone again.
You only see the result of your own games. Nobody can verify claims made in messages.

YOUR GOAL: earn as many points as possible for yourself over the whole game.

Before every round, every player may post one public message that all players read.
Messages are at most {words} words and may be empty. Anyone may lie.

YOUR PERSONALITY. Each trait has a level from 1 (very low) to 10 (very high); 5 is average.
A low level means the opposite of the description. Act as a person with exactly this
personality would act: let it shape what you say, how much you say, whom you believe,
and what you choose.
{personality}
"""

NEUTRAL = "(No personality is specified. Play as you see fit.)"

PHASE_TEXT = {
    "message": "Write your public message for round {round} (it can be empty).",
    "action": "Choose your action against {opponent} for round {round}. Also rate how much you "
    "trust each other player (0 = not at all, 10 = completely) and give a short private reason "
    "(at most 300 characters).",
    "final": "The game is over. This report is private and does not change points. Rate your "
    "trust in each other player, list who you believe betrayed others most, describe each other "
    "player's personality in a few words, rate yourself honestly, and summarize your strategy.",
}


@dataclass
class Request:
    player: str
    round: int
    phase: str
    view: dict
    messages: list
    schema: dict


@dataclass
class Settings:
    players: int = 10
    rounds: int = 10
    model: str = "openai/gpt-6-luna"
    provider: str = "openai"
    reasoning_effort: str = "medium"
    max_completion_tokens: int = 4096
    words: int = 60
    neutral: bool = False
    backend: str = "openrouter"
    extra: dict = field(default_factory=dict)


def _ratings(others, lo=0, hi=10):
    return {
        "type": "object",
        "properties": {p: {"type": "integer", "minimum": lo, "maximum": hi} for p in others},
        "required": list(others),
        "additionalProperties": False,
    }


def schema(phase, player, players):
    others = [p for p in players if p != player]
    if phase == "message":
        props = {"message": {"type": "string"}}
    elif phase == "action":
        props = {
            "action": {"type": "string", "enum": ["C", "D"]},
            "trust": _ratings(others),
            "reason": {"type": "string"},
        }
    else:
        props = {
            "trust": _ratings(others),
            "betrayers": {"type": "array", "items": {"type": "string", "enum": others}},
            "personality_guess": {
                "type": "object",
                "properties": {p: {"type": "string"} for p in others},
                "required": others,
                "additionalProperties": False,
            },
            "self_rating": {
                "type": "object",
                "properties": {
                    k: {"type": "integer", "minimum": 1, "maximum": 10}
                    for k in ("honesty", "fairness", "cooperativeness")
                },
                "required": ["honesty", "fairness", "cooperativeness"],
                "additionalProperties": False,
            },
            "strategy": {"type": "string"},
        }
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


def new_episode(seed, settings: Settings):
    players = [f"P{i + 1}" for i in range(settings.players)]
    return {
        "seed": seed,
        "settings": {k: v for k, v in settings.__dict__.items() if k != "extra"},
        "players": players,
        "personalities": {
            p: ({} if settings.neutral else sample_personality(seed, p)) for p in players
        },
        "schedule": make_schedule(players, settings.rounds, seed),
        "messages": [],
        "actions": [],
        "trust": [],
        "final": {},
        "points": dict.fromkeys(players, 0),
        "requests": [],
        "status": "running",
    }


def opponent_of(ep, player, rnd):
    for a, b in ep["schedule"][rnd - 1]:
        if player in (a, b):
            return b if player == a else a
    raise KeyError(player)


def view(ep, player, rnd, phase):
    mine = []
    for e in ep["actions"]:
        if player in e["players"]:
            i = e["players"].index(player)
            mine.append({
                "round": e["round"],
                "opponent": e["players"][1 - i],
                "you": e["actions"][i],
                "them": e["actions"][1 - i],
                "your_points": e["points"][i],
            })
    v = {
        "you": player,
        "players": ep["players"],
        "round": rnd,
        "rounds_total": ep["settings"]["rounds"],
        "your_total_points": ep["points"][player],
        "your_games": mine,
        "public_messages": [
            {"round": m["round"], "from": m["player"], "text": m["text"]}
            for m in ep["messages"] if m["text"].strip()
        ],
        "your_past_reasons": [
            {"round": t["round"], "reason": t["reason"]} for t in ep["trust"] if t["player"] == player
        ],
    }
    if phase == "action":
        v["current_opponent"] = opponent_of(ep, player, rnd)
    return v


def build_request(ep, player, rnd, phase):
    s = ep["settings"]
    traits = ep["personalities"][player]
    system = RULES.format(
        players=s["players"], rounds=s["rounds"], words=s["words"],
        personality=describe(traits) if traits else NEUTRAL,
    )
    v = view(ep, player, rnd, phase)
    instr = PHASE_TEXT[phase].format(round=rnd, opponent=v.get("current_opponent"))
    messages = [
        {"role": "system", "content": system + "\n" + instr},
        {"role": "user", "content": json.dumps(v, ensure_ascii=False)},
    ]
    return Request(player, rnd, phase, v, messages, schema(phase, player, ep["players"]))


class ScriptedProvider:
    """Free offline stand-in: behavior loosely follows Selfishness/Talkativeness."""

    def complete(self, request, messages=None, on_event=None):
        traits_seed = derived_seed(request.round, request.player + request.phase)
        rng = random.Random(traits_seed)
        others = list(request.schema["properties"].get("trust", {}).get("properties", {}))
        if request.phase == "message":
            data = {"message": "" if rng.random() < 0.3 else "I plan to cooperate."}
        elif request.phase == "action":
            data = {"action": rng.choice("CCD"), "trust": {p: rng.randint(0, 10) for p in others},
                    "reason": "scripted"}
        else:
            data = {"trust": {p: 5 for p in others}, "betrayers": others[:1],
                    "personality_guess": {p: "unknown" for p in others},
                    "self_rating": {"honesty": 5, "fairness": 5, "cooperativeness": 5},
                    "strategy": "scripted"}
        return Completion(json.dumps(data), {"model": "scripted", "provider": "scripted",
                                             "usage": {}, "reported_cost_usd": 0.0})


def make_provider(settings: Settings):
    if settings.backend == "scripted":
        return ScriptedProvider()
    return OpenRouterProvider(SimpleNamespace(
        model=settings.model, provider=settings.provider,
        reasoning_effort=settings.reasoning_effort,
        max_completion_tokens=settings.max_completion_tokens,
    ))


def validate(data, req):
    jsonschema.validate(data, req.schema)
    if req.phase == "message" and len(data["message"]) > MESSAGE_CHARS:
        raise ValueError(f"message longer than {MESSAGE_CHARS} characters")
    if req.phase == "action" and len(data["reason"]) > REASON_CHARS * 2:
        raise ValueError("reason too long")


def call(provider, req, log):
    """One request with one correction attempt. Returns parsed data."""
    messages = list(req.messages)
    for attempt in range(2):
        comp = provider.complete(req, messages)
        meta = comp.metadata
        entry = {"player": req.player, "round": req.round, "phase": req.phase,
                 "attempt": attempt + 1, "cost": meta.get("reported_cost_usd"),
                 "usage": meta.get("usage"), "model": meta.get("model"),
                 "provider": meta.get("provider"), "content": comp.content}
        try:
            data = json.loads(comp.content)
            validate(data, req)
            entry["valid"] = True
            log.append(entry)
            return data
        except (ValueError, jsonschema.ValidationError) as exc:
            entry["valid"] = False
            entry["error"] = str(exc)[:300]
            log.append(entry)
            messages = messages + [
                {"role": "assistant", "content": comp.content},
                {"role": "user", "content": "That response was invalid "
                 f"({str(exc)[:200]}). Return corrected JSON only."},
            ]
    raise RuntimeError(f"{req.player} round {req.round} {req.phase}: invalid twice")


def run_phase(provider, ep, rnd, phase, pool):
    reqs = [build_request(ep, p, rnd, phase) for p in ep["players"]]
    logs = [[] for _ in reqs]
    futures = [pool.submit(call, provider, r, lg) for r, lg in zip(reqs, logs)]
    results = [f.result() for f in futures]
    for lg in logs:
        ep["requests"].extend(lg)
    return dict(zip(ep["players"], results))


def play(ep, provider, on_progress=lambda msg: None):
    rounds = ep["settings"]["rounds"]
    with ThreadPoolExecutor(max_workers=len(ep["players"])) as pool:
        for rnd in range(1, rounds + 1):
            msgs = run_phase(provider, ep, rnd, "message", pool)
            for p, d in msgs.items():
                ep["messages"].append({"round": rnd, "player": p, "text": d["message"].strip()})
            acts = run_phase(provider, ep, rnd, "action", pool)
            for p, d in acts.items():
                ep["trust"].append({"round": rnd, "player": p, "trust": d["trust"],
                                    "reason": d["reason"][:REASON_CHARS], "action": d["action"]})
            for a, b in ep["schedule"][rnd - 1]:
                pa, pb = PAYOFFS[(acts[a]["action"], acts[b]["action"])]
                ep["points"][a] += pa
                ep["points"][b] += pb
                ep["actions"].append({"round": rnd, "players": [a, b],
                                      "actions": [acts[a]["action"], acts[b]["action"]],
                                      "points": [pa, pb]})
            on_progress(f"seed {ep['seed']} round {rnd}/{rounds}")
        ep["final"] = run_phase(provider, ep, rounds, "final", pool)
    ep["status"] = "complete"
    return ep
