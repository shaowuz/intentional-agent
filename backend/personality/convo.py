"""Open-ended conversation version of the personality game.

Differences from game.py (experiment 1):
- Before every round there are TURNS conversation turns. In each turn every agent may post a
  public message (up to PUBLIC_WORDS words) and one private message to any one other player.
- The prompt is an append-only transcript per agent so provider prompt caching applies.
Personalities come from the same seeds as experiment 1, so agents are matched across runs.

python -m personality.convo --seeds 0-1 --output results/convo-pilot --model openai/gpt-6.1-terra --execute
"""

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from swarm_game.game import PAYOFFS

from .game import (REASON_CHARS, Request, ScriptedProvider, Settings, call, make_provider,
                   new_episode, opponent_of, schema)
from .run import load_key, parse_seeds, write_json
from .traits import describe

TURNS = 2
PUBLIC_WORDS = 150
DM_WORDS = 80

RULES = """You are a player in a multi-round game. Return only the requested JSON.
The transcript in the user message is everything you know. You have no tools.

There are {players} players and exactly {rounds} rounds. Each round you are paired with one
other player and you both choose at the same time: C (cooperate) or D (defect).
Points (your action, their action -> your points, their points):
C,C -> 3,3; D,C -> 5,0; C,D -> 0,5; D,D -> 1,1.
A rotation makes you meet every other player about once before meeting anyone again.
You only see the result of your own games. Nobody can verify claims made in messages.

YOUR GOAL: earn as many points as possible for yourself over the whole game.

CONVERSATION. Before every round there are {turns} conversation turns. In each turn you may:
- post one public message that every player reads (at most {pub} words, may be empty), and
- send one private message to any one other player that only they read (at most {dm} words,
  may be empty).
Talk about anything you like: plans, deals, alliances, accusations, questions, replies.
Anyone may lie, in public or in private.

YOUR PERSONALITY. Each trait has a level from 1 (very low) to 10 (very high); 5 is average.
A low level means the opposite of the description. Act as a person with exactly this
personality would act: let it shape what you say, how much you say, to whom, whom you
believe, and what you choose.
{personality}
"""

NEUTRAL = "(No personality is specified. Play as you see fit.)"


def talk_schema(player, players):
    others = [p for p in players if p != player]
    return {
        "type": "object",
        "properties": {
            "public": {"type": "string"},
            "dm_to": {"type": "string", "enum": ["none", *others]},
            "dm": {"type": "string"},
        },
        "required": ["public", "dm_to", "dm"],
        "additionalProperties": False,
    }


def words(text):
    return len(text.split())


def round_text(ep, player, rnd):
    """Everything this player saw in one round. Fixed once the round's results are in."""
    lines = [f"=== Round {rnd} ==="]
    conv = [c for c in ep["conversation"] if c["round"] == rnd]
    for turn in range(1, TURNS + 1):
        items = [c for c in conv if c["turn"] == turn]
        if not items:
            continue
        lines.append(f"-- Conversation turn {turn} --")
        for c in items:
            if c["public"]:
                lines.append(f"{c['player']} (public): {c['public']}")
        for c in items:
            if c["dm"] and c["dm_to"] == player:
                lines.append(f"{c['player']} (private to you): {c['dm']}")
            if c["dm"] and c["player"] == player:
                lines.append(f"You (private to {c['dm_to']}): {c['dm']}")
    mine = next((t for t in ep["trust"] if t["round"] == rnd and t["player"] == player), None)
    if mine:
        lines.append(f"Your private reason: {mine['reason']}")
    for e in ep["actions"]:
        if e["round"] == rnd and player in e["players"]:
            i = e["players"].index(player)
            lines.append(f"Result: you played {e['actions'][i]} vs {e['players'][1 - i]} who played "
                         f"{e['actions'][1 - i]}; you got {e['points'][i]} "
                         f"(your total {ep['running'][str(rnd)][player]}).")
    return "\n".join(lines) + "\n"


def round_done(ep, rnd):
    return any(e["round"] == rnd for e in ep["actions"])


def transcript_parts(ep, player):
    """One text part per round. The last two finished rounds carry cache breakpoints, so each
    request reads the cache written by earlier requests and only pays for the new round."""
    rounds = [r for r in range(1, ep["round_now"] + 1)
              if round_done(ep, r) or any(c["round"] == r for c in ep["conversation"])]
    if not rounds:
        return [{"type": "text", "text": "GAME TRANSCRIPT\n(The game is starting. Nothing has happened yet.)"}]
    parts = [{"type": "text", "text": ("GAME TRANSCRIPT\n" if i == 0 else "") + round_text(ep, player, r)}
             for i, r in enumerate(rounds)]
    done = [i for i, r in enumerate(rounds) if round_done(ep, r)]
    for i in done[-2:]:
        parts[i]["cache_control"] = {"type": "ephemeral"}
    return parts


def transcript(ep, player):
    return "".join(p["text"] for p in transcript_parts(ep, player))


def build(ep, player, rnd, phase, turn=None):
    s = ep["settings"]
    traits = ep["personalities"][player]
    system = RULES.format(players=s["players"], rounds=s["rounds"], turns=TURNS, pub=PUBLIC_WORDS,
                          dm=DM_WORDS, personality=describe(traits) if traits else NEUTRAL)
    system += f"\nYou are {player}. Players: {', '.join(ep['players'])}."
    if phase == "talk":
        instr = (f"Round {rnd}, conversation turn {turn} of {TURNS}. Write your public message and "
                 f"optionally one private message (dm_to = a player ID, or \"none\").")
        sch = talk_schema(player, ep["players"])
    elif phase == "action":
        opp = opponent_of(ep, player, rnd)
        instr = (f"Round {rnd}: choose your action against {opp}. Also rate how much you trust each other "
                 f"player (0 = not at all, 10 = completely) and give a short private reason "
                 f"(at most {REASON_CHARS} characters).")
        sch = schema("action", player, ep["players"])
    else:
        instr = ("The game is over. This report is private and does not change points. Rate your trust in "
                 "each other player, list who you believe betrayed others most, describe each other "
                 "player's personality in a few words, rate yourself honestly, and summarize your strategy.")
        sch = schema("final", player, ep["players"])
    messages = [
        {"role": "system", "content": system},
        # Instruction is the last part of the same user message so cache breakpoints stay aligned.
        {"role": "user", "content": transcript_parts(ep, player) + [{"type": "text", "text": "\n" + instr}]},
    ]
    return Request(player, rnd, "talk" if phase == "talk" else phase, {}, messages, sch)


def validate_talk(data, req):
    if words(data["public"]) > PUBLIC_WORDS * 1.2 or words(data["dm"]) > DM_WORDS * 1.2:
        raise ValueError(f"message too long (public <= {PUBLIC_WORDS} words, private <= {DM_WORDS})")
    if data["dm"].strip() and data["dm_to"] == "none":
        raise ValueError("dm text given but dm_to is none")


def run_phase(provider, ep, reqs, pool, check=None):
    logs = [[] for _ in reqs]

    def one(r, lg):
        for attempt in range(2):
            data = call(provider, r, lg)
            try:
                if check:
                    check(data, r)
                return data
            except ValueError as exc:
                if attempt:
                    raise RuntimeError(f"{r.player} {r.phase}: {exc}")
                r = Request(r.player, r.round, r.phase, r.view, r.messages + [
                    {"role": "assistant", "content": json.dumps(data)},
                    {"role": "user", "content": f"Invalid: {exc}. Return corrected JSON only."}], r.schema)

    results = [f.result() for f in [pool.submit(one, r, lg) for r, lg in zip(reqs, logs)]]
    for lg in logs:
        ep["requests"].extend(lg)
    return results


def play(ep, provider):
    rounds = ep["settings"]["rounds"]
    ep.update(conversation=[], running={"0": dict(ep["points"])}, round_now=1)
    with ThreadPoolExecutor(max_workers=len(ep["players"])) as pool:
        for rnd in range(1, rounds + 1):
            ep["round_now"] = rnd
            for turn in range(1, TURNS + 1):
                reqs = [build(ep, p, rnd, "talk", turn) for p in ep["players"]]
                out = run_phase(provider, ep, reqs, pool, validate_talk)
                for p, d in zip(ep["players"], out):
                    ep["conversation"].append({"round": rnd, "turn": turn, "player": p,
                                               "public": d["public"].strip(), "dm_to": d["dm_to"],
                                               "dm": d["dm"].strip() if d["dm_to"] != "none" else ""})
            for p in ep["players"]:  # experiment-1 compatible view: a round's public talk joined
                text = " ".join(c["public"] for c in ep["conversation"]
                                if c["round"] == rnd and c["player"] == p and c["public"])
                ep["messages"].append({"round": rnd, "player": p, "text": text})
            reqs = [build(ep, p, rnd, "action") for p in ep["players"]]
            acts = dict(zip(ep["players"], run_phase(provider, ep, reqs, pool)))
            for p, d in acts.items():
                ep["trust"].append({"round": rnd, "player": p, "trust": d["trust"],
                                    "reason": d["reason"][:REASON_CHARS], "action": d["action"]})
            for a, b in ep["schedule"][rnd - 1]:
                pa, pb = PAYOFFS[(acts[a]["action"], acts[b]["action"])]
                ep["points"][a] += pa
                ep["points"][b] += pb
                ep["actions"].append({"round": rnd, "players": [a, b],
                                      "actions": [acts[a]["action"], acts[b]["action"]], "points": [pa, pb]})
            ep["running"][str(rnd)] = dict(ep["points"])
        reqs = [build(ep, p, rounds, "final") for p in ep["players"]]
        ep["final"] = dict(zip(ep["players"], run_phase(provider, ep, reqs, pool)))
    ep["status"] = "complete"
    return ep


class ScriptedTalk(ScriptedProvider):
    def complete(self, request, messages=None, on_event=None):
        if request.phase == "talk":
            from swarm_game.providers import Completion
            others = request.schema["properties"]["dm_to"]["enum"][1:]
            return Completion(json.dumps({"public": "Let's cooperate.", "dm_to": others[0],
                                          "dm": "Deal: we both play C?"}),
                              {"model": "scripted", "provider": "scripted", "usage": {}, "reported_cost_usd": 0.0})
        return super().complete(request, messages, on_event)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", default="0-1")
    ap.add_argument("--output", required=True)
    ap.add_argument("--model", default="openai/gpt-6.1-terra")
    ap.add_argument("--provider", default="openai")
    ap.add_argument("--reasoning", default="medium")
    ap.add_argument("--backend", choices=["openrouter", "scripted"], default="openrouter")
    ap.add_argument("--neutral", action="store_true")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--max-cost", type=float, default=20.0)
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args(argv)
    settings = Settings(model=args.model, provider=args.provider, reasoning_effort=args.reasoning,
                        neutral=args.neutral, backend=args.backend, words=PUBLIC_WORDS)
    seeds = parse_seeds(args.seeds)
    out = Path(args.output)
    eps = out / "episodes"
    done = {int(p.stem.split("-")[1]) for p in eps.glob("seed-*.json")
            if json.loads(p.read_text(encoding="utf-8")).get("status") == "complete"} if eps.exists() else set()
    todo = [s for s in seeds if s not in done]
    print(json.dumps({"to_run": len(todo), "agents": 10 * len(todo), "model": args.model,
                      "requests_per_game": 10 * (10 * (TURNS + 1)) + 10}, indent=1))
    if not args.execute:
        print("Preview only. Add --execute to run.")
        return 0
    load_key()
    eps.mkdir(parents=True, exist_ok=True)
    provider = ScriptedTalk() if args.backend == "scripted" else make_provider(settings)
    spent = {"usd": sum(json.loads(p.read_text(encoding="utf-8")).get("cost_usd", 0)
                        for p in eps.glob("seed-*.json"))}
    lock = threading.Lock()

    def one(seed):
        with lock:
            if spent["usd"] >= args.max_cost or (out / "STOP").exists():
                return seed, "skipped (cost cap or STOP)"
        ep = new_episode(seed, settings)
        t0 = time.time()
        try:
            play(ep, provider)
        except Exception as exc:
            ep["status"], ep["error"] = "failed", f"{type(exc).__name__}: {str(exc)[:300]}"
        ep["cost_usd"] = sum((r.get("cost") or 0) for r in ep["requests"])
        ep["seconds"] = round(time.time() - t0, 1)
        write_json(eps / f"seed-{seed:04d}.json", ep)
        with lock:
            spent["usd"] += ep["cost_usd"]
            return seed, f"{ep['status']} ${ep['cost_usd']:.3f} {ep['seconds']}s total ${spent['usd']:.2f}"

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for f in as_completed([pool.submit(one, s) for s in todo]):
            seed, msg = f.result()
            print(time.strftime("%H:%M:%S"), f"seed {seed}: {msg}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
