#!/usr/bin/env python3
"""Validate a recorded results directory for internal consistency.

Checks (per condition):
  * every agent played the expected number of games;
  * every round's recorded payoff matches the payoff matrix;
  * per-round cumulative payoffs are monotone and match their sum;
  * each game's final lifetime cumulative payoff is consistent;
  * belief estimates are present and within [0, 1];
  * action/belief parse-status distribution is reported.

Exit code is non-zero if any hard check fails.

Usage: python scripts/validate_run.py --results results/pilot_mock
"""

import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ipd.game import payoff  # noqa: E402
from ipd.recorder import read_jsonl  # noqa: E402


def validate_condition(cdir, expected_games):
    problems = []
    games = read_jsonl(os.path.join(cdir, "games.jsonl"))
    rounds = read_jsonl(os.path.join(cdir, "rounds.jsonl"))
    beliefs = read_jsonl(os.path.join(cdir, "beliefs.jsonl"))

    if not games:
        problems.append("no games recorded")
        return games, rounds, beliefs, problems, {}

    # Games per agent.
    per_agent = collections.Counter()
    for g in games:
        for aid in g["participants"]:
            per_agent[aid] += 1
    for aid, n in per_agent.items():
        if n != expected_games:
            problems.append(f"agent {aid} played {n} games (expected {expected_games})")

    # Payoff / cumulative consistency per game.
    for g in games:
        a, b = g["participants"]
        a_sum = b_sum = 0
        for rnd in g["rounds"]:
            aa, bb = rnd["actions"][a], rnd["actions"][b]
            if rnd["payoffs"][a] != payoff(aa, bb):
                problems.append(
                    f"game {g['game_index']} pair {g.get('pair_index')} round "
                    f"{rnd['round']}: payoff mismatch for {a}"
                )
            if rnd["payoffs"][b] != payoff(bb, aa):
                problems.append(
                    f"game {g['game_index']} round {rnd['round']}: payoff "
                    f"mismatch for {b}"
                )
            a_sum += rnd["payoffs"][a]
            b_sum += rnd["payoffs"][b]
            if rnd["cum_game"][a] != a_sum:
                problems.append(f"game {g['game_index']}: cumulative mismatch for {a}")
            if rnd["cum_game"][b] != b_sum:
                problems.append(f"game {g['game_index']}: cumulative mismatch for {b}")
        if g["totals"][a]["game_payoff"] != a_sum:
            problems.append(f"game {g['game_index']}: total mismatch for {a}")
        if g["totals"][b]["game_payoff"] != b_sum:
            problems.append(f"game {g['game_index']}: total mismatch for {b}")

    # Beliefs in range and present.
    n_belief_none = 0
    for b in beliefs:
        v = b.get("defect_probability")
        if v is None:
            n_belief_none += 1
        elif not (0.0 <= v <= 1.0):
            problems.append(f"belief out of range: {v} ({b['agent_id']})")

    # Lifetime cumulative consistency: final lifetime == sum of game payoffs.
    life = {}
    for g in games:
        for aid in g["participants"]:
            life.setdefault(aid, 0)
            life[aid] += g["totals"][aid]["game_payoff"]
    for g in games:
        for aid in g["participants"]:
            if g["totals"][aid]["lifetime_cum_payoff"] != life.get(aid):
                # Only the last game per agent must match the total.
                pass
    # Check final per agent.
    last = {}
    for g in games:
        for aid in g["participants"]:
            if aid not in last or g["game_index"] >= last[aid]["game_index"]:
                last[aid] = g
    for aid, g in last.items():
        if g["totals"][aid]["lifetime_cum_payoff"] != life[aid]:
            problems.append(f"agent {aid}: final lifetime payoff inconsistent")

    stats = {
        "n_games": len(games),
        "n_rounds": len(rounds),
        "n_agents": len(per_agent),
        "belief_none": n_belief_none,
        "action_parse": dict(collections.Counter(r["parse_status"] for r in rounds)),
        "belief_parse": dict(collections.Counter(b.get("parse_status") for b in beliefs)),
        "round_len_min": min(g["actual_rounds"] for g in games),
        "round_len_max": max(g["actual_rounds"] for g in games),
    }
    return games, rounds, beliefs, problems, stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    args = parser.parse_args()

    meta_path = os.path.join(args.results, "experiment_meta.json")
    expected_games = None
    if os.path.exists(meta_path):
        import json

        with open(meta_path) as fh:
            expected_games = json.load(fh).get("games_per_agent")

    any_problem = False
    for cond in sorted(os.listdir(args.results)):
        cdir = os.path.join(args.results, cond)
        if not os.path.isdir(cdir) or not os.path.exists(
            os.path.join(cdir, "games.jsonl")
        ):
            continue
        games, rounds, beliefs, problems, stats = validate_condition(
            cdir, expected_games or 0
        )
        print(f"== condition: {cond}")
        for k, v in stats.items():
            print(f"   {k}: {v}")
        if problems:
            any_problem = True
            print(f"   PROBLEMS ({len(problems)}):")
            for p in problems[:20]:
                print(f"     - {p}")
        else:
            print("   OK: no consistency problems found")

    sys.exit(1 if any_problem else 0)


if __name__ == "__main__":
    main()
