"""Observer-only tables and reports for the canonical matched experiment matrix."""

import csv
import html
import itertools
import json
import statistics
from pathlib import Path

from .analysis import analyze_episode, bootstrap_mean_interval, usage_totals
from .config import Config
from .game import initial_state
from .storage import read_json, scrub, write_json

METRICS = (
    "good_total_return",
    "return_per_good_encounter",
    "good_good_return",
    "good_selfish_return",
    "good_cooperation_rate",
    "all_cooperation_rate",
    "mean_brier_score",
    "final_mean_brier_score",
    "final_identification_rate",
    "final_correct_none_rate",
    "false_accusation_rate",
    "leader_is_selfish",
    "pre_midpoint_return_per_good_encounter",
    "post_midpoint_return_per_good_encounter",
)
AXES = ("episode_id", "model", "communication", "selfish_count", "seed", "backend")


def write_csv(path, rows, columns=None):
    columns = columns or list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(scrub(rows))


def mean(values):
    values = [v for v in values if v is not None]
    return statistics.mean(values) if values else None


def contrast(kind, label, model, mode, count, pairs):
    # Each complete pair is one independent seed block, never an agent or turn.
    return {
        "kind": kind,
        "contrast": label,
        "model": model,
        "communication": mode,
        "selfish_count": count,
        "matched_seeds": len(pairs),
        "seed_ids": [seed for seed, _, _ in pairs],
        "mean_total_return_difference": mean(
            [b["good_total_return"] - a["good_total_return"] for _, a, b in pairs]
        ),
        "mean_normalized_difference": mean(
            [b["return_per_good_encounter"] - a["return_per_good_encounter"] for _, a, b in pairs]
        ),
        "normalized_bootstrap_95pct_interval": bootstrap_mean_interval(
            [b["return_per_good_encounter"] - a["return_per_good_encounter"] for _, a, b in pairs]
        ),
    }


def analyze_matrix(output):
    output = Path(output)
    manifest = read_json(output / "matrix_manifest.json")
    spec = manifest["spec"]
    summaries, statuses, actions, beliefs, messages, elections, usage, events = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    lookup = {}
    for entry in manifest["plan"]:
        name, config = entry["episode_id"], Config(**entry["config"])
        episode = output / "episodes" / name
        axes = {"episode_id": name, **{k: entry["config"][k] for k in AXES if k != "episode_id"}}
        checkpoint = episode / "checkpoint.json"
        state = read_json(checkpoint) if checkpoint.exists() else None
        if (episode / "manifest.json").exists():
            saved = read_json(episode / "manifest.json")
            if saved["config"] != entry["config"] or saved["provenance"] != manifest["provenance"]:
                raise ValueError(f"Episode configuration/provenance mismatch: {name}")
        if state:
            expected = initial_state(config)
            if any(state[k] != expected[k] for k in ("players", "roles", "schedule")):
                raise ValueError(f"Episode schedules/roles differ from the matched design: {name}")
        status = (
            "complete"
            if state and state["completed"]
            else "incomplete"
            if episode.exists()
            else "not_started"
        )
        totals = usage_totals(episode)
        statuses.append(
            {**axes, "status": status, "round": state["round"] if state else 0, **totals}
        )
        for path in sorted((episode / "requests").glob("*.json")):
            record = read_json(path)
            req = record["request"]
            for attempt, value in enumerate(record["attempts"], start=1):
                meta = value["response"]["metadata"]
                tokens = meta.get("usage") or {}
                usage.append(
                    {
                        **axes,
                        "request_id": path.stem,
                        "player": req["player"],
                        "round": req["round"],
                        "phase": req["phase"],
                        "attempt": attempt,
                        "accepted": record["complete"] and attempt == len(record["attempts"]),
                        "response_model": meta.get("model"),
                        "provider": meta.get("provider"),
                        "prompt_tokens": tokens.get("prompt_tokens"),
                        "completion_tokens": tokens.get("completion_tokens"),
                        "reported_cost_usd": meta.get("reported_cost_usd"),
                        "request_file": str(path.relative_to(output)),
                    }
                )
        if status != "complete":
            continue
        summary = {**axes, **analyze_episode(episode)}
        for prefix, chosen in (
            ("pre", [e for e in state["encounters"] if e["round"] <= config.midpoint_round]),
            ("post", [e for e in state["encounters"] if e["round"] > config.midpoint_round]),
        ):
            good_returns = [
                v
                for e in chosen
                for p, v in zip(e["players"], e["payoffs"])
                if state["roles"][p] == "good"
            ]
            summary[f"{prefix}_midpoint_return_per_good_encounter"] = mean(good_returns)
        summaries.append(summary)
        lookup[(config.model, config.communication, config.selfish_count, config.seed)] = summary
        cumulative = dict.fromkeys(state["players"], 0)
        for e in state["encounters"]:
            for i, player in enumerate(e["players"]):
                cumulative[player] += e["payoffs"][i]
                actions.append(
                    {
                        **axes,
                        "round": e["round"],
                        "player": player,
                        "role": state["roles"][player],
                        "opponent": e["players"][1 - i],
                        "action": e["actions"][i],
                        "opponent_action": e["actions"][1 - i],
                        "payoff": e["payoffs"][i],
                        "cumulative_payoff": cumulative[player],
                    }
                )
        truth = summary["selfish_player"] or "none"
        for b in state["belief_records"]:
            beliefs.extend(
                {
                    **axes,
                    "round": b["round"],
                    "phase": b["phase"],
                    "player": b["player"],
                    "role": state["roles"][b["player"]],
                    "target": target,
                    "probability": prob,
                    "is_true": target == truth,
                    "strategy": b["strategy"],
                }
                for target, prob in b["beliefs"].items()
            )
        for d in state["discussions"]:
            messages.extend(
                {**axes, "after_round": d["after_round"], "phase": "discussion", **p}
                for p in d["posts"]
            )
        messages.extend(
            {
                **axes,
                "after_round": config.midpoint_round,
                "phase": "midpoint",
                "sender": p,
                "visibility": "private",
                "content": value["content"],
            }
            for p, value in state.get("midpoint_reports", {}).items()
        )
        if state.get("election"):
            e = state["election"]
            elections.extend(
                {
                    **axes,
                    "after_round": e["after_round"],
                    "voter": p,
                    "vote": v,
                    "voter_role": state["roles"][p],
                    "winner": e["winner"],
                    "winner_role": state["roles"][e["winner"]],
                    "tie": len(e["tied_candidates"]) > 1,
                }
                for p, v in e["votes"].items()
            )
        events.extend(
            {**axes, **json.loads(line)}
            for line in (episode / "timeline.jsonl").read_text().splitlines()
        )
    cells = []
    for model, mode, count in itertools.product(
        spec["models"], spec["communication_modes"], spec["selfish_counts"]
    ):
        rows = [
            s
            for s in summaries
            if (s["model"], s["communication"], s["selfish_count"]) == (model, mode, count)
        ]
        cells.append(
            {
                "model": model,
                "communication": mode,
                "selfish_count": count,
                "completed_episodes": len(rows),
                "planned_episodes": len(spec["seeds"]),
                **{metric: mean([s[metric] for s in rows]) for metric in METRICS},
            }
        )
    effects = []
    for model, count in itertools.product(spec["models"], spec["selfish_counts"]):
        for a, b in itertools.combinations(spec["communication_modes"], 2):
            pairs = [
                (seed, lookup[(model, a, count, seed)], lookup[(model, b, count, seed)])
                for seed in spec["seeds"]
                if (model, a, count, seed) in lookup and (model, b, count, seed) in lookup
            ]
            effects.append(contrast("communication", f"{b} minus {a}", model, None, count, pairs))
    for mode, count in itertools.product(spec["communication_modes"], spec["selfish_counts"]):
        for a, b in itertools.combinations(spec["models"], 2):
            pairs = [
                (seed, lookup[(a, mode, count, seed)], lookup[(b, mode, count, seed)])
                for seed in spec["seeds"]
                if (a, mode, count, seed) in lookup and (b, mode, count, seed) in lookup
            ]
            effects.append(contrast("model", f"{b} minus {a}", None, mode, count, pairs))
    result = {
        "schema_version": manifest["schema_version"],
        "status": "complete" if len(summaries) == len(manifest["plan"]) else "incomplete",
        "backend": spec["game"]["backend"],
        "completed_episodes": len(summaries),
        "planned_episodes": len(manifest["plan"]),
        "cells": cells,
        "contrasts": effects,
        "missing_episodes": [s["episode_id"] for s in statuses if s["status"] != "complete"],
        "usage_including_incomplete": {
            k: sum(s[k] for s in statuses)
            for k in (
                "completed_model_responses",
                "prompt_tokens",
                "completion_tokens",
                "reported_cost_usd",
                "responses_missing_cost",
            )
        },
        "interval_method": "10000 paired seed-block bootstrap resamples; exploratory, unadjusted; null for fewer than two pairs",
    }
    write_json(output / "analysis.json", result)
    write_csv(
        output / "episodes.csv",
        [{**s, **s["usage"]} for s in summaries],
        [
            *AXES,
            "protocol_version",
            "players",
            "rounds",
            "reasoning_effort",
            "selfish_persona",
            *METRICS,
            "leader",
            "selfish_player",
            "completed_model_responses",
            "prompt_tokens",
            "completion_tokens",
            "reported_cost_usd",
            "responses_missing_cost",
        ],
    )
    write_csv(output / "cells.csv", cells)
    write_csv(output / "contrasts.csv", effects)
    write_csv(output / "status.csv", statuses)
    for name, rows, fields in (
        (
            "actions",
            actions,
            [
                *AXES,
                "round",
                "player",
                "role",
                "opponent",
                "action",
                "opponent_action",
                "payoff",
                "cumulative_payoff",
            ],
        ),
        (
            "beliefs",
            beliefs,
            [
                *AXES,
                "round",
                "phase",
                "player",
                "role",
                "target",
                "probability",
                "is_true",
                "strategy",
            ],
        ),
        ("messages", messages, [*AXES, "after_round", "phase", "sender", "visibility", "content"]),
        (
            "elections",
            elections,
            [*AXES, "after_round", "voter", "vote", "voter_role", "winner", "winner_role", "tie"],
        ),
        (
            "usage",
            usage,
            [
                *AXES,
                "request_id",
                "player",
                "round",
                "phase",
                "attempt",
                "accepted",
                "response_model",
                "provider",
                "prompt_tokens",
                "completion_tokens",
                "reported_cost_usd",
                "request_file",
            ],
        ),
    ):
        write_csv(output / f"{name}.csv", rows, fields)
    (output / "timeline.jsonl").write_text("".join(json.dumps(scrub(e)) + "\n" for e in events))
    render_report(output, result, summaries)
    return result


def render_report(output, result, summaries):
    def fmt(v):
        return "—" if v is None else f"{v:.4f}"

    title = "Model × communication experiment"
    note = (
        "Scripted test output validates mechanics; it does not measure model behavior."
        if result["backend"] == "scripted"
        else "Hosted-model experiment results."
    )
    lines = [
        f"# {title}",
        "",
        note,
        "",
        f"Status: **{result['status']}**; {result['completed_episodes']}/{result['planned_episodes']} episodes complete.",
        "",
        "| Model | Communication | Selfish players | Completed | Good total return | Return / good encounter |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for c in result["cells"]:
        lines.append(
            f"| {c['model']} | {c['communication']} | {c['selfish_count']} | {c['completed_episodes']} | {fmt(c['good_total_return'])} | {fmt(c['return_per_good_encounter'])} |"
        )
    lines += [
        "",
        "## Matched contrasts",
        "",
        "Differences pair identical seed, role roster, and schedules. Zero/one-selfish groups stay separate.",
        "",
        "| Contrast | Model / communication | Selfish players | Matched seeds | Total difference | Normalized difference |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for e in result["contrasts"]:
        lines.append(
            f"| {e['contrast']} | {e['model'] or e['communication']} | {e['selfish_count']} | {e['matched_seeds']} | {fmt(e['mean_total_return_difference'])} | {fmt(e['mean_normalized_difference'])} |"
        )
    lines += [
        "",
        "Intervals appear in analysis.json and contrasts.csv. Seeds, not agent-rounds, define sampling units.",
        "Incomplete cells and unmatched pairs remain explicit; zero completed episodes produce no estimates.",
        "",
        "Election happens after floor(rounds/2), before that round's discussion. Before election the leader condition has no public messages; afterward only the winner broadcasts. Other modes receive a private midpoint reflection to match the extra call. Ballots stay secret; the winner's identity is public.",
        "",
        "All observer exports contain true roles and private notes. Experimental agents receive only their permitted histories.",
        "",
        "Medium is the same requested reasoning setting; providers may spend different token budgets. Collective payoff and identity detection measure separate outcomes.",
        "",
        "## Files",
        "",
        "episodes.csv, cells.csv, contrasts.csv: scores and paired effects. actions.csv, beliefs.csv, messages.csv, elections.csv, timeline.jsonl: observer traces. usage.csv and status.csv include failed/incomplete episodes. Exact prompts and all response attempts remain under episodes/*/requests/.",
        "",
        "## Episode reports",
        "",
    ]
    lines.extend(f"- [{s['episode_id']}](episodes/{s['episode_id']}/report.md)" for s in summaries)
    (output / "report.md").write_text("\n".join(lines) + "\n")
    # A portable, script-free report; claims/content never execute as HTML.
    table = "<table><thead><tr><th>Model</th><th>Communication</th><th>Selfish</th><th>Complete</th><th>Good return</th><th>Return / encounter</th></tr></thead><tbody>"
    for c in result["cells"]:
        table += (
            "<tr>"
            + "".join(
                f"<td>{html.escape(str(v))}</td>"
                for v in (
                    c["model"],
                    c["communication"],
                    c["selfish_count"],
                    c["completed_episodes"],
                    fmt(c["good_total_return"]),
                    fmt(c["return_per_good_encounter"]),
                )
            )
            + "</tr>"
        )
    table += "</tbody></table>"
    body = f"<h1>{title}</h1><p>{html.escape(note)}</p><p>{result['status']}: {result['completed_episodes']}/{result['planned_episodes']} episodes</p>{table}"
    body += '<p><a href="report.md">Full report and episode index</a> · <a href="analysis.json">Structured analysis</a> · <a href="episodes.csv">Episode table</a> · <a href="contrasts.csv">Paired contrasts</a></p>'
    body += "<p>Zero/one-selfish groups remain separate. Every contrast uses matched seed blocks. See the full report for election rules, missing cells, and uncertainty.</p>"
    (output / "report.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Experiment report</title><style>body{font:16px system-ui;max-width:1150px;margin:40px auto;padding:0 20px;color:#162d3d;background:#f5f8fb}table{border-collapse:collapse;width:100%;background:white}th,td{padding:12px;text-align:left;border-bottom:1px solid #dbe3eb}th{background:#e7f0f5}a{color:#12628a}</style>'
        + body
        + "</html>"
    )
