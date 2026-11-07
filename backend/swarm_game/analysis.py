"""Observer-only analysis; none of these aggregates enter player prompts."""

import csv
import json
import random
import statistics
from pathlib import Path

from .storage import read_json, scrub, write_json


def usage_totals(output):
    responses = []
    for path in sorted((Path(output) / "requests").glob("*.json")):
        record = read_json(path)
        responses.extend(a["response"]["metadata"] for a in record["attempts"])
    costs = [r.get("reported_cost_usd") for r in responses]
    return {
        "completed_model_responses": len(responses),
        "prompt_tokens": sum((r.get("usage") or {}).get("prompt_tokens", 0) for r in responses),
        "completion_tokens": sum(
            (r.get("usage") or {}).get("completion_tokens", 0) for r in responses
        ),
        "reported_cost_usd": sum(c for c in costs if c is not None),
        "responses_missing_cost": sum(c is None for c in costs),
    }


def score_state(state, config):
    if not state["completed"]:
        raise ValueError("Analysis requires a completed episode")
    good = {p for p, r in state["roles"].items() if r == "good"}
    selfish = next((p for p in state["players"] if p not in good), None)
    gg = gs = good_c = all_c = 0
    for encounter in state["encounters"]:
        category_good = all(p in good for p in encounter["players"])
        for p, action, payoff in zip(
            encounter["players"], encounter["actions"], encounter["payoffs"]
        ):
            all_c += action == "C"
            if p in good:
                good_c += action == "C"
                if category_good:
                    gg += payoff
                else:
                    gs += payoff
    records = [r for r in state["belief_records"] if r["player"] in good]
    truth = selfish or "none"
    brier = [
        sum((prob - (label == truth)) ** 2 for label, prob in r["beliefs"].items()) for r in records
    ]
    false = [
        r
        for r in records
        if any(prob >= 0.8 and p in good and p != r["player"] for p, prob in r["beliefs"].items())
    ]
    detected = [r for r in records if selfish and r["beliefs"][selfish] >= 0.8]
    early = set()
    for r in detected:
        # Action beliefs precede that round's encounter; final beliefs follow it.
        past = [e for e in state["encounters"] if e["round"] < r["round"] or r["phase"] == "final"]
        if not any(r["player"] in e["players"] and selfish in e["players"] for e in past):
            early.add(r["player"])
    final = [r for r in records if r["phase"] == "final"]
    total = sum(state["payoffs"][p] for p in good)
    return {
        "schema_version": "intentional-experiments/1",
        "protocol_version": config.get("protocol_version", "rotating-v1"),
        "model": config["model"],
        "reasoning_effort": config["reasoning_effort"],
        "selfish_persona": config.get("selfish_persona", "neutral"),
        "communication": config["communication"],
        "selfish_count": config["selfish_count"],
        "seed": config["seed"],
        "players": config["players"],
        "rounds": config["rounds"],
        "backend": config["backend"],
        "good_total_return": total,
        "return_per_good_encounter": total / (config["rounds"] * len(good)),
        "good_good_return": gg,
        "good_selfish_return": gs,
        "good_cooperation_rate": good_c / (config["rounds"] * len(good)),
        "all_cooperation_rate": all_c / (config["rounds"] * config["players"]),
        "mean_brier_score": statistics.mean(brier),
        "final_mean_brier_score": statistics.mean(
            sum((v - (p == truth)) ** 2 for p, v in r["beliefs"].items()) for r in final
        ),
        "belief_observations": len(records),
        "false_accusation_observations": len(false),
        "false_accusation_rate": len(false) / len(records),
        "good_agents_ever_identifying_selfish": len({r["player"] for r in detected}),
        "good_agents_identifying_before_personal_encounter": len(early),
        "final_identification_rate": (
            sum(r["beliefs"][selfish] >= 0.8 for r in final) / len(good) if selfish else None
        ),
        "final_correct_none_rate": (
            sum(r["beliefs"]["none"] >= 0.8 for r in final) / len(good) if not selfish else None
        ),
        "good_payoff_range": max(state["payoffs"][p] for p in good)
        - min(state["payoffs"][p] for p in good),
        "payoffs": state["payoffs"],
        "selfish_player": selfish,
        "leader": state.get("election", {}).get("winner") if state.get("election") else None,
        "leader_is_selfish": (
            state["election"]["winner"] == selfish if state.get("election") else None
        ),
    }


def analyze_episode(output):
    output = Path(output)
    config = read_json(output / "manifest.json")["config"]
    state = read_json(output / "checkpoint.json")
    summary = {**score_state(state, config), "usage": usage_totals(output)}
    write_json(output / "summary.json", summary)
    events = []
    for r in range(1, config["rounds"] + 1):
        events += [
            {"type": "belief", **b}
            for b in state["belief_records"]
            if b["round"] == r and b["phase"] == "action"
        ]
        events += [{"type": "encounter", **e} for e in state["encounters"] if e["round"] == r]
        if state.get("midpoint_reports") and r == config["rounds"] // 2:
            events += [
                {"type": "midpoint", "after_round": r, "player": p, **v}
                for p, v in state["midpoint_reports"].items()
            ]
            if state.get("election"):
                events.append({"type": "election", **state["election"]})
        events += [
            {"type": "discussion", **d} for d in state["discussions"] if d["after_round"] == r
        ]
    events += [{"type": "belief", **b} for b in state["belief_records"] if b["phase"] == "final"]
    (output / "timeline.jsonl").write_text("".join(json.dumps(scrub(e)) + "\n" for e in events))
    lines = [
        "# Episode report",
        "",
        (
            f"Backend: **{config['backend']}**; model: **{config['model']}**. "
            f"Communication: **{config['communication']}**; selfish players: **{config['selfish_count']}**."
        ),
        "",
        (
            f"Good-agent total return: **{summary['good_total_return']}**; "
            f"per good-agent encounter: **{summary['return_per_good_encounter']:.4f}**."
        ),
        "",
        (
            "This observer transcript includes private notes, reports, and true roles. "
            "Players received only their permitted views."
        ),
        "",
        "## True objectives",
        "",
        json.dumps(state["roles"]),
        "",
        "## Timeline",
        "",
    ]
    for event in events:
        if event["type"] == "encounter":
            a, b = event["players"]
            lines.append(
                f"- Round {event['round']}: {a}–{b}, actions {event['actions']}, "
                f"payoffs {event['payoffs']}."
            )
        elif event["type"] == "discussion":
            lines += [
                "",
                f"Discussion after round {event['after_round']} ({event['visibility']}):",
                "",
            ]
            for post in event["posts"]:
                # Quote arbitrary messages as data; escape HTML to keep reports inert.
                content = post["content"].replace("&", "&amp;").replace("<", "&lt;")
                visibility = post.get("visibility", event["visibility"])
                lines.append(f"- {post['sender']} ({visibility}): {content.replace(chr(10), ' ')}")
            lines.append("")
        elif event["type"] == "election":
            lines.append(f"- Election after round {event['after_round']}: leader {event['winner']}.")
    lines += [
        "",
        (
            "Private belief and strategy trajectories appear in `timeline.jsonl`; "
            "exact prompts and responses appear in `requests/`."
        ),
    ]
    (output / "report.md").write_text(scrub("\n".join(lines)) + "\n")
    return summary


def bootstrap_mean_interval(values, seed=0):
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    samples = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(10000))
    return [samples[249], samples[9749]]


def analyze_comparison(output):
    output = Path(output)
    manifest_path = output / "comparison_manifest.json"
    modes = (
        read_json(manifest_path).get("communication_modes", ["none", "public"])
        if manifest_path.exists() else ["none", "public"]
    )
    paired = set(modes) == {"none", "public"}
    summaries, excluded, pairs = [], [], {}
    for manifest_path in sorted(output.glob("*/manifest.json")):
        episode = manifest_path.parent
        if (
            not (episode / "checkpoint.json").exists()
            or not read_json(episode / "checkpoint.json")["completed"]
        ):
            excluded.append(episode.name)
            continue
        summary = analyze_episode(episode)
        summaries.append(summary)
        key = (summary["selfish_count"], summary["seed"])
        cell = pairs.setdefault(key, {})
        if summary["communication"] in cell:
            raise ValueError(f"Duplicate episode for seed/role/mode {key}")
        cell[summary["communication"]] = (summary, episode)
    effects, missing = {}, []
    for k in (0, 1):
        total_diffs, normalized_diffs = [], []
        for (count, seed), cell in pairs.items():
            if count != k:
                continue
            if set(cell) != {"none", "public"}:
                if paired:
                    missing.append({"selfish_count": k, "seed": seed})
                continue
            none, public = cell["none"], cell["public"]
            a, b = read_json(none[1] / "checkpoint.json"), read_json(public[1] / "checkpoint.json")
            ma, mb = read_json(none[1] / "manifest.json"), read_json(public[1] / "manifest.json")
            ca, cb = dict(ma["config"]), dict(mb["config"])
            ca.pop("communication")
            cb.pop("communication")
            if ca != cb or a["schedule"] != b["schedule"] or a["roles"] != b["roles"]:
                raise ValueError("Comparison episodes do not share configuration/schedules/roles")
            if ma["provenance"] != mb["provenance"]:
                raise ValueError("Comparison episodes use different runner versions")
            total_diffs.append(public[0]["good_total_return"] - none[0]["good_total_return"])
            normalized_diffs.append(
                public[0]["return_per_good_encounter"] - none[0]["return_per_good_encounter"]
            )
        effects[str(k)] = {
            "matched_seed_blocks": len(total_diffs),
            "mean_public_minus_none_total": statistics.mean(total_diffs) if total_diffs else None,
            "mean_public_minus_none_normalized": statistics.mean(normalized_diffs)
            if normalized_diffs
            else None,
            "normalized_bootstrap_95pct_interval": bootstrap_mean_interval(normalized_diffs),
        }
    result = {
        "episodes": len(summaries),
        "communication_modes": modes,
        "excluded_incomplete": excluded,
        "missing_pairs": missing,
        "effects_by_selfish_count": effects,
        "interval_method": "10,000 paired seed-block bootstrap resamples; exploratory, unadjusted",
    }
    write_json(output / "comparison.json", result)
    if summaries:
        columns = [k for k in summaries[0] if k not in ("usage", "payoffs")]
        with (output / "episodes.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(summaries)
    lines = [
        "# Paired communication comparison",
        "",
        "Effects are public minus no communication. Each seed block is one sampling unit.",
        "",
        "| Selfish players | Matched seeds | Mean total-return difference | Mean normalized difference |",
        "|---|---|---|---|",
    ]
    for k, effect in effects.items():
        lines.append(
            f"| {k} | {effect['matched_seed_blocks']} | "
            f"{effect['mean_public_minus_none_total']} | "
            f"{effect['mean_public_minus_none_normalized']} |"
        )
    lines += [
        "",
        f"Incomplete episodes: {len(excluded)}; unmatched completed cells: {len(missing)}.",
        "",
        (
            "See episodes.csv for scores, cooperation, beliefs, and identification. "
            "Scripted results validate mechanics; they do not estimate GPT-6 behavior."
        ),
    ]
    (output / "report.md").write_text("\n".join(lines) + "\n")
    if not paired:
        lines = [
            "# Open-communication pilot", "",
            ("This pilot includes public communication only. It estimates outcomes within "
             "each role condition; it does not estimate a communication effect."), "",
            "| Selfish players | Episodes | Mean good return | Return per good encounter |",
            "|---|---:|---:|---:|",
        ]
        for k in (0, 1):
            rows = [s for s in summaries if s["selfish_count"] == k]
            if rows:
                lines.append(
                    f"| {k} | {len(rows)} | "
                    f"{statistics.mean(s['good_total_return'] for s in rows):.4f} | "
                    f"{statistics.mean(s['return_per_good_encounter'] for s in rows):.4f} |"
                )
        lines += ["", f"Incomplete episodes: {len(excluded)}.", "",
                  "See episodes.csv and individual episode reports for full metrics."]
        (output / "report.md").write_text("\n".join(lines) + "\n")
    return result
