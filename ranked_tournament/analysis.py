"""Analysis, tables, figures and a readable Markdown report."""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Tuple

import numpy as np

from ipd.recorder import read_jsonl
from ipd.utils import ensure_dir


# ---------------------------------------------------------------------- #
# Loading
# ---------------------------------------------------------------------- #
def load_results(results_dir: str) -> dict:
    def load(name: str) -> List[dict]:
        return read_jsonl(os.path.join(results_dir, f"{name}.jsonl"))

    meta_path = os.path.join(results_dir, "experiment_meta.json")
    status_path = os.path.join(results_dir, "run_status.json")
    meta = {}
    status = {}
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as fh:
            meta = json.load(fh)
    if os.path.exists(status_path):
        with open(status_path, "r", encoding="utf-8") as fh:
            status = json.load(fh)

    return {
        "meta": meta,
        "status": status,
        "pairings": load("pairings"),
        "stages": load("stages"),
        "games": load("games"),
        "rounds": load("rounds"),
        "reflections": load("reflections"),
        "strategies": load("strategies"),
        "usage": load("usage"),
        "calls": load("calls"),
    }


def _agents(data: dict) -> List[str]:
    meta_agents = data.get("meta", {}).get("agents")
    if meta_agents:
        return list(meta_agents)
    found = set()
    for rec in data.get("rounds", []):
        found.update(rec.get("raw_payoffs", {}).keys())
    return sorted(found)


def _n_rounds(data: dict) -> int:
    meta_n = data.get("meta", {}).get("n_rounds")
    if meta_n:
        return int(meta_n)
    rounds = [int(r["round"]) for r in data.get("rounds", [])]
    return max(rounds) if rounds else 0


def _coop_counts(stage_records: List[dict], agents: List[str]):
    counts = {agent_id: [0, 0] for agent_id in agents}
    mutual = [0, 0]
    for rec in stage_records:
        for agent_id, action in rec.get("actions", {}).items():
            if agent_id in counts:
                counts[agent_id][1] += 1
                if action == "C":
                    counts[agent_id][0] += 1
        mutual[1] += 1
        if rec.get("actions") and all(
            a == "C" for a in rec["actions"].values()
        ):
            mutual[0] += 1
    return counts, mutual


def cooperation_by_round(
    data: dict, agents: List[str]
) -> Dict[int, dict]:
    n_rounds = _n_rounds(data)
    stages = data.get("stages", [])
    result: Dict[int, dict] = {}
    for r in range(1, n_rounds + 1):
        records = [rec for rec in stages if int(rec.get("round", 0)) == r]
        counts, mutual = _coop_counts(records, agents)
        total_c = sum(c for c, _ in counts.values())
        total_n = sum(n for _, n in counts.values())
        result[r] = {
            "per_agent": {
                agent_id: (c / n if n else float("nan"))
                for agent_id, (c, n) in counts.items()
            },
            "overall": (total_c / total_n if total_n else float("nan")),
            "mutual": (
                mutual[0] / mutual[1] if mutual[1] else float("nan")
            ),
            "n_stages": mutual[1],
        }
    return result


def overall_cooperation(
    data: dict, agents: List[str]
) -> Dict[str, float]:
    counts, mutual = _coop_counts(data.get("stages", []), agents)
    total_c = sum(c for c, _ in counts.values())
    total_n = sum(n for _, n in counts.values())
    result = {
        agent_id: (c / n if n else float("nan"))
        for agent_id, (c, n) in counts.items()
    }
    result["_overall"] = total_c / total_n if total_n else float("nan")
    result["_mutual"] = (
        mutual[0] / mutual[1] if mutual[1] else float("nan")
    )
    return result


# ---------------------------------------------------------------------- #
# Tables
# ---------------------------------------------------------------------- #
def build_table1(data: dict) -> dict:
    agents = _agents(data)
    n_rounds = _n_rounds(data)
    payoff: Dict[str, Dict[int, int]] = {a: {} for a in agents}
    points: Dict[str, Dict[int, float]] = {a: {} for a in agents}
    for rec in data.get("rounds", []):
        r = int(rec["round"])
        for agent_id in agents:
            if agent_id in rec.get("raw_payoffs", {}):
                payoff[agent_id][r] = rec["raw_payoffs"][agent_id]
            if agent_id in rec.get("ranking_points", {}):
                points[agent_id][r] = rec["ranking_points"][agent_id]
    coop = overall_cooperation(data, agents)
    total_points = {a: float(sum(points[a].values())) for a in agents}
    long_rows = []
    for agent_id in agents:
        for r in range(1, n_rounds + 1):
            long_rows.append(
                {
                    "agent": agent_id,
                    "round": r,
                    "raw_payoff": payoff[agent_id].get(r),
                    "ranking_points": points[agent_id].get(r),
                }
            )
    return {
        "agents": agents,
        "n_rounds": n_rounds,
        "payoff": payoff,
        "points": points,
        "total_points": total_points,
        "cooperation": coop,
        "long_rows": long_rows,
    }


def build_table2(data: dict) -> List[dict]:
    records = data.get("strategies", [])
    if not records:
        records = [
            {
                "round": rec.get("round"),
                "agent_id": rec.get("agent_id"),
                "strategy_before": rec.get("strategy_before"),
                "strategy_after": rec.get("strategy_for_next_round"),
                "change_strategy": rec.get("change_strategy"),
                "text_changed": (
                    rec.get("strategy_before")
                    != rec.get("strategy_for_next_round")
                ),
                "reason": rec.get("reason"),
            }
            for rec in data.get("reflections", [])
        ]
    rows = []
    for rec in sorted(
        records,
        key=lambda r: (int(r.get("round", 0)), str(r.get("agent_id", ""))),
    ):
        rows.append(
            {
                "agent": rec.get("agent_id"),
                "round": rec.get("round"),
                "strategy_before": rec.get("strategy_before"),
                "strategy_after": rec.get("strategy_after"),
                "change_strategy": bool(rec.get("change_strategy")),
                "text_changed": bool(rec.get("text_changed")),
                "reason": rec.get("reason", ""),
            }
        )
    return rows


def revisions_by_round(data: dict) -> Dict[int, dict]:
    agents = _agents(data)
    n_rounds = _n_rounds(data)
    result = {
        r: {"changed": 0, "text_changed": 0, "n_agents": len(agents)}
        for r in range(1, n_rounds + 1)
    }
    for rec in data.get("strategies", []):
        r = int(rec.get("round", 0))
        if r not in result:
            continue
        if rec.get("change_strategy"):
            result[r]["changed"] += 1
        if rec.get("text_changed"):
            result[r]["text_changed"] += 1
    return result


def cumulative_points_by_round(data: dict) -> Dict[str, Dict[int, float]]:
    agents = _agents(data)
    n_rounds = _n_rounds(data)
    cumulative = {a: {} for a in agents}
    running = {a: 0.0 for a in agents}
    by_round = {
        int(rec["round"]): rec for rec in data.get("rounds", [])
    }
    for r in range(1, n_rounds + 1):
        rec = by_round.get(r, {})
        for agent_id in agents:
            running[agent_id] += float(
                rec.get("ranking_points", {}).get(agent_id, 0.0)
            )
            cumulative[agent_id][r] = running[agent_id]
    return cumulative



# ---------------------------------------------------------------------- #
# Behavioural statistics
# ---------------------------------------------------------------------- #
def conditional_cooperation(data: dict, agents: List[str]) -> dict:
    """P(own C | previous opponent C) and P(own C | previous opponent D)."""
    condition: Dict[str, dict] = {
        a: {"after_C": [0, 0], "after_D": [0, 0]} for a in agents
    }
    for game in data.get("games", []):
        participants = game.get("participants", [])
        stages = game.get("stages", [])
        if len(participants) != 2 or len(stages) < 2:
            continue
        for agent_id in participants:
            opponent = (
                participants[0]
                if participants[1] == agent_id
                else participants[1]
            )
            for t in range(1, len(stages)):
                prev_opp = stages[t - 1]["actions"].get(opponent)
                own = stages[t]["actions"].get(agent_id)
                if prev_opp is None or own is None:
                    continue
                bucket = "after_C" if prev_opp == "C" else "after_D"
                condition[agent_id][bucket][1] += 1
                if own == "C":
                    condition[agent_id][bucket][0] += 1
    result = {}
    for agent_id in agents:
        after_c, n_c = condition[agent_id]["after_C"]
        after_d, n_d = condition[agent_id]["after_D"]
        result[agent_id] = {
            "p_coop_after_opp_C": after_c / n_c if n_c else float("nan"),
            "p_coop_after_opp_D": after_d / n_d if n_d else float("nan"),
            "n_after_C": n_c,
            "n_after_D": n_d,
        }
    return result


def first_stage_cooperation(data: dict, agents: List[str]) -> dict:
    """Per-round and per-agent cooperation on the first stage of a pair-game."""
    n_rounds = _n_rounds(data)
    per_round = {
        r: {"coop": float("nan"), "per_agent": {}}
        for r in range(1, n_rounds + 1)
    }
    per_agent_counts = {a: [0, 0] for a in agents}
    for rec in data.get("stages", []):
        if int(rec.get("stage", 0)) != 1:
            continue
        r = int(rec.get("round", 0))
        actions = rec.get("actions", {})
        c = sum(1 for a in actions.values() if a == "C")
        n = len(actions)
        if r in per_round and n:
            per_round[r]["coop"] = c / n
        for agent_id, action in actions.items():
            if agent_id in per_agent_counts:
                per_agent_counts[agent_id][1] += 1
                if action == "C":
                    per_agent_counts[agent_id][0] += 1
    for r in per_round:
        records = [
            rec
            for rec in data.get("stages", [])
            if int(rec.get("round", 0)) == r
            and int(rec.get("stage", 0)) == 1
        ]
        per_round[r]["per_agent"] = {
            agent_id: (
                sum(
                    1
                    for rec in records
                    if rec["actions"].get(agent_id) == "C"
                )
                / len(records)
                if records
                else float("nan")
            )
            for agent_id in agents
        }
    per_agent = {
        a: (c / n if n else float("nan"))
        for a, (c, n) in per_agent_counts.items()
    }
    return {"per_round": per_round, "per_agent": per_agent}



def revision_performance(data: dict) -> dict:
    """Compare next-round ranking points after changed vs unchanged reflections."""
    round_points = {
        int(rec["round"]): rec.get("ranking_points", {})
        for rec in data.get("rounds", [])
    }
    round_payoffs = {
        int(rec["round"]): rec.get("raw_payoffs", {})
        for rec in data.get("rounds", [])
    }
    buckets = {
        "changed": {"points": [], "payoffs": []},
        "unchanged": {"points": [], "payoffs": []},
    }
    for rec in data.get("strategies", []):
        r = int(rec.get("round", 0))
        agent_id = rec.get("agent_id")
        if r + 1 not in round_points:
            continue
        key = "changed" if rec.get("change_strategy") else "unchanged"
        if agent_id in round_points[r + 1]:
            buckets[key]["points"].append(
                float(round_points[r + 1][agent_id])
            )
        if agent_id in round_payoffs[r + 1]:
            buckets[key]["payoffs"].append(
                float(round_payoffs[r + 1][agent_id])
            )

    def _mean(values):
        return float(np.mean(values)) if values else float("nan")

    return {
        "changed": {
            "n": len(buckets["changed"]["points"]),
            "mean_next_points": _mean(buckets["changed"]["points"]),
            "mean_next_payoff": _mean(buckets["changed"]["payoffs"]),
        },
        "unchanged": {
            "n": len(buckets["unchanged"]["points"]),
            "mean_next_points": _mean(buckets["unchanged"]["points"]),
            "mean_next_payoff": _mean(buckets["unchanged"]["payoffs"]),
        },
    }


def distinct_strategies(data: dict, agents: List[str]) -> dict:
    latest: Dict[str, Optional[str]] = {a: None for a in agents}
    for rec in sorted(
        data.get("strategies", []), key=lambda r: int(r.get("round", 0))
    ):
        agent_id = rec.get("agent_id")
        if agent_id in latest:
            latest[agent_id] = rec.get("strategy_after")
    normalized = {
        a: " ".join((s or "").lower().split()) for a, s in latest.items()
    }
    unique = set(v for v in normalized.values() if v)
    return {
        "final_strategies": latest,
        "n_unique_final_strategies": len(unique),
        "n_agents_with_strategy": sum(1 for v in normalized.values() if v),
    }


def consistency_flags(
    data: dict,
    agents: List[str],
    coop: Dict[str, float],
    cond: dict,
) -> List[dict]:
    """Transparent, heuristic checks of stated strategy vs observed behaviour."""
    latest: Dict[str, str] = {}
    for rec in sorted(
        data.get("strategies", []), key=lambda r: int(r.get("round", 0))
    ):
        if rec.get("agent_id") in agents:
            latest[rec["agent_id"]] = rec.get("strategy_after") or ""
    flags = []
    for agent_id in agents:
        text = latest.get(agent_id, "").lower()
        rate = coop.get(agent_id, float("nan"))
        after_c = cond.get(agent_id, {}).get(
            "p_coop_after_opp_C", float("nan")
        )
        after_d = cond.get(agent_id, {}).get(
            "p_coop_after_opp_D", float("nan")
        )
        flags_for_agent = []
        if any(
            k in text
            for k in ("always defect", "always d", "never cooperate")
        ):
            if rate == rate and rate > 0.20:
                flags_for_agent.append(
                    "states always-defect but cooperated in "
                    f"{rate:.0%} of stages"
                )
        if any(
            k in text
            for k in ("always cooperate", "always c", "never defect")
        ):
            if rate == rate and rate < 0.80:
                flags_for_agent.append(
                    "states always-cooperate but cooperated in only "
                    f"{rate:.0%} of stages"
                )
        if any(k in text for k in ("tit-for-tat", "tit for tat", "reciproc")):
            if (
                after_c == after_c
                and after_d == after_d
                and (after_c - after_d) < 0.20
            ):
                flags_for_agent.append(
                    "states reciprocity but P(C|opp C) - P(C|opp D) is "
                    f"only {(after_c - after_d):+.2f}"
                )
        if "grim" in text:
            if after_d == after_d and after_d > 0.20:
                flags_for_agent.append(
                    "states grim trigger but cooperated "
                    f"{after_d:.0%} of the time after an opponent defection"
                )
        flags.append(
            {
                "agent": agent_id,
                "final_strategy": latest.get(agent_id, ""),
                "flags": flags_for_agent,
            }
        )
    return flags



# ---------------------------------------------------------------------- #
# Figures
# ---------------------------------------------------------------------- #
def make_figures(data: dict, figures_dir: str) -> List[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ensure_dir(figures_dir)
    agents = _agents(data)
    n_rounds = _n_rounds(data)
    if n_rounds < 1 or not agents:
        return []
    rounds = list(range(1, n_rounds + 1))
    coop_round = cooperation_by_round(data, agents)
    cumulative = cumulative_points_by_round(data)
    revisions = revisions_by_round(data)
    made = []

    colors = plt.rcParams["axes.prop_cycle"].by_key().get("color", [])
    def color(i):
        return colors[i % len(colors)] if colors else None

    # 1. Cooperation rate by round.
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, agent_id in enumerate(agents):
        ax.plot(
            rounds,
            [coop_round[r]["per_agent"].get(agent_id, np.nan) for r in rounds],
            marker="o",
            label=f"Agent {agent_id}",
            color=color(i),
        )
    ax.plot(
        rounds,
        [coop_round[r]["overall"] for r in rounds],
        linestyle="--",
        color="black",
        label="Population",
    )
    ax.plot(
        rounds,
        [coop_round[r]["mutual"] for r in rounds],
        linestyle=":",
        color="grey",
        label="Mutual cooperation",
    )
    ax.set_xlabel("Tournament round")
    ax.set_ylabel("Cooperation rate")
    ax.set_ylim(-0.02, 1.02)
    ax.set_title("Cooperation rate by round")
    ax.legend(fontsize=8, ncol=2)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    path = os.path.join(figures_dir, "cooperation_rate_by_round.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    made.append(path)

    # 2. Cumulative ranking points.
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, agent_id in enumerate(agents):
        ax.plot(
            rounds,
            [cumulative[agent_id].get(r, np.nan) for r in rounds],
            marker="o",
            label=f"Agent {agent_id}",
            color=color(i),
        )
    ax.set_xlabel("Tournament round")
    ax.set_ylabel("Cumulative ranking points")
    ax.set_title("Cumulative ranking points by round")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    path = os.path.join(
        figures_dir, "cumulative_ranking_points_by_round.png"
    )
    fig.savefig(path, dpi=150)
    plt.close(fig)
    made.append(path)

    # 3. Strategy revisions.
    fig, ax = plt.subplots(figsize=(8, 4.2))
    changed = [revisions[r]["changed"] for r in rounds]
    text_changed = [revisions[r]["text_changed"] for r in rounds]
    x = np.arange(len(rounds))
    width = 0.38
    ax.bar(x - width / 2, changed, width, label="Stated change")
    ax.bar(x + width / 2, text_changed, width, label="Text changed")
    ax.set_xticks(x)
    ax.set_xticklabels([str(r) for r in rounds])
    ax.set_xlabel("Tournament round")
    ax.set_ylabel("Number of agents")
    ax.set_title("Frequency of strategy revisions")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = os.path.join(figures_dir, "strategy_revisions_by_round.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    made.append(path)

    # 4. Raw payoff by round (useful diagnostic).
    table1 = build_table1(data)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, agent_id in enumerate(agents):
        ax.plot(
            rounds,
            [table1["payoff"][agent_id].get(r, np.nan) for r in rounds],
            marker="o",
            label=f"Agent {agent_id}",
            color=color(i),
        )
    ax.set_xlabel("Tournament round")
    ax.set_ylabel("Raw payoff")
    ax.set_title("Raw payoff by round")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    path = os.path.join(figures_dir, "raw_payoff_by_round.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    made.append(path)

    # 5. First-stage cooperation.
    first = first_stage_cooperation(data, agents)
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.plot(
        rounds,
        [first["per_round"][r]["coop"] for r in rounds],
        marker="o",
        color="black",
        label="First-stage cooperation",
    )
    ax.set_xlabel("Tournament round")
    ax.set_ylabel("Cooperation rate on stage 1")
    ax.set_ylim(-0.02, 1.02)
    ax.set_title("Opening-move cooperation by round")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    path = os.path.join(figures_dir, "first_stage_cooperation.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    made.append(path)

    return made



# ---------------------------------------------------------------------- #
# Qualitative summary
# ---------------------------------------------------------------------- #
def build_qualitative_summary(data: dict, table1: dict) -> dict:
    agents = table1["agents"]
    n_rounds = table1["n_rounds"]
    coop_round = cooperation_by_round(data, agents)
    cond = conditional_cooperation(data, agents)
    first = first_stage_cooperation(data, agents)
    revperf = revision_performance(data)
    distinct = distinct_strategies(data, agents)
    flags = consistency_flags(
        data, agents, table1["cooperation"], cond
    )

    overall = [
        coop_round[r]["overall"] for r in range(1, n_rounds + 1)
    ]
    half = max(1, n_rounds // 2)
    first_half = float(np.nanmean(overall[:half])) if overall else float("nan")
    second_half = (
        float(np.nanmean(overall[half:])) if overall else float("nan")
    )
    delta = second_half - first_half

    opportunistic = {}
    for agent_id in agents:
        values = cond.get(agent_id, {})
        after_c = values.get("p_coop_after_opp_C", float("nan"))
        after_d = values.get("p_coop_after_opp_D", float("nan"))
        opportunistic[agent_id] = {
            "difference": (
                after_c - after_d
                if after_c == after_c and after_d == after_d
                else float("nan")
            ),
            "after_C": after_c,
            "after_D": after_d,
        }
    diffs = [
        v["difference"]
        for v in opportunistic.values()
        if v["difference"] == v["difference"]
    ]
    pooled_reciprocity = float(np.mean(diffs)) if diffs else float("nan")

    first_rates = [
        first["per_round"][r]["coop"] for r in range(1, n_rounds + 1)
    ]
    first_half_open = (
        float(np.nanmean(first_rates[:half])) if first_rates else float("nan")
    )
    second_half_open = (
        float(np.nanmean(first_rates[half:])) if first_rates else float("nan")
    )
    opener_delta = second_half_open - first_half_open

    return {
        "cooperation_trend": {
            "first_half": first_half,
            "second_half": second_half,
            "delta": delta,
            "per_round": {r: coop_round[r]["overall"] for r in coop_round},
            "mutual_per_round": {
                r: coop_round[r]["mutual"] for r in coop_round
            },
        },
        "conditional_cooperation": cond,
        "reciprocity": {
            "per_agent": opportunistic,
            "pooled_mean_difference": pooled_reciprocity,
        },
        "first_stage": first,
        "opening_trend": {
            "first_half": first_half_open,
            "second_half": second_half_open,
            "delta": opener_delta,
        },
        "revision_performance": revperf,
        "distinct": distinct,
        "consistency": flags,
    }


# ---------------------------------------------------------------------- #
# Table files
# ---------------------------------------------------------------------- #
def _md_table(headers: List[str], rows: List[List[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _cell(value) -> str:
    if value is None:
        return "-"
    text = str(value).replace("|", "\\|").replace("\n", " ")
    return text if text else "-"


def _fmt_rate(value) -> str:
    if value is None or value != value:
        return "n/a"
    return f"{float(value):.0%}"


def _fmt_number(value, digits=2) -> str:
    if value is None or value != value:
        return "n/a"
    return f"{float(value):.{digits}f}"



def write_tables(
    data: dict,
    table1: dict,
    table2: List[dict],
    tables_dir: str,
) -> dict:
    import csv

    ensure_dir(tables_dir)
    agents = table1["agents"]
    n_rounds = table1["n_rounds"]

    # Long-format Table 1 CSV.
    path1_csv = os.path.join(tables_dir, "table1_tournament_results.csv")
    with open(path1_csv, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["agent", "round", "raw_payoff", "ranking_points"]
        )
        writer.writeheader()
        writer.writerows(table1["long_rows"])

    # Compact wide-format Table 1 Markdown.
    headers = ["Agent"] + [f"R{r}" for r in range(1, n_rounds + 1)]
    headers += ["Total points", "Overall coop rate"]
    rows = []
    for agent_id in agents:
        row = [f"Agent {agent_id}"]
        for r in range(1, n_rounds + 1):
            payoff = table1["payoff"][agent_id].get(r)
            points = table1["points"][agent_id].get(r)
            if payoff is None or points is None:
                row.append("-")
            else:
                row.append(f"{payoff} ({float(points):g})")
        row.append(f"{table1['total_points'][agent_id]:g}")
        row.append(_fmt_rate(table1["cooperation"].get(agent_id)))
        rows.append(row)
    path1_md = os.path.join(tables_dir, "table1_tournament_results.md")
    with open(path1_md, "w", encoding="utf-8") as fh:
        fh.write(
            "# Table 1: Tournament results\n\n"
            "Each cell is `raw payoff (ranking points)`.\n\n"
        )
        fh.write(_md_table(headers, rows) + "\n")

    # Table 2 CSV.
    path2_csv = os.path.join(
        tables_dir, "table2_strategy_evolution.csv"
    )
    with open(path2_csv, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "agent",
                "round",
                "change_strategy",
                "text_changed",
                "strategy_after",
                "reason",
            ],
        )
        writer.writeheader()
        for rec in table2:
            writer.writerow(
                {
                    "agent": rec["agent"],
                    "round": rec["round"],
                    "change_strategy": rec["change_strategy"],
                    "text_changed": rec["text_changed"],
                    "strategy_after": rec["strategy_after"],
                    "reason": rec["reason"],
                }
            )

    # Table 2 Markdown.
    path2_md = os.path.join(
        tables_dir, "table2_strategy_evolution.md"
    )
    with open(path2_md, "w", encoding="utf-8") as fh:
        fh.write("# Table 2: Strategy evolution\n\n")
        fh.write(
            _md_table(
                [
                    "Agent",
                    "Round",
                    "Changed?",
                    "Strategy after round",
                    "Reason",
                ],
                [
                    [
                        _cell(rec["agent"]),
                        _cell(rec["round"]),
                        "yes" if rec["change_strategy"] else "no",
                        _cell(rec["strategy_after"]),
                        _cell(rec["reason"]),
                    ]
                    for rec in table2
                ],
            )
            + "\n"
        )

    # Cooperation by round CSV.
    coop_round = cooperation_by_round(data, agents)
    path_coop = os.path.join(tables_dir, "cooperation_by_round.csv")
    with open(path_coop, "w", encoding="utf-8", newline="") as fh:
        fieldnames = (
            ["round"]
            + [f"agent_{a}_coop" for a in agents]
            + ["overall_coop", "mutual_coop", "n_stages"]
        )
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in range(1, n_rounds + 1):
            row = {"round": r}
            for a in agents:
                row[f"agent_{a}_coop"] = coop_round[r]["per_agent"].get(a)
            row["overall_coop"] = coop_round[r]["overall"]
            row["mutual_coop"] = coop_round[r]["mutual"]
            row["n_stages"] = coop_round[r]["n_stages"]
            writer.writerow(row)

    return {
        "table1_csv": path1_csv,
        "table1_md": path1_md,
        "table2_csv": path2_csv,
        "table2_md": path2_md,
        "cooperation_csv": path_coop,
    }



# ---------------------------------------------------------------------- #
# Report
# ---------------------------------------------------------------------- #
def _table1_markdown(table1: dict) -> str:
    agents = table1["agents"]
    n_rounds = table1["n_rounds"]
    headers = ["Agent"] + [f"R{r}" for r in range(1, n_rounds + 1)]
    headers += ["Total points", "Overall coop rate"]
    rows = []
    for agent_id in agents:
        row = [f"Agent {agent_id}"]
        for r in range(1, n_rounds + 1):
            payoff = table1["payoff"][agent_id].get(r)
            points = table1["points"][agent_id].get(r)
            if payoff is None or points is None:
                row.append("-")
            else:
                row.append(f"{payoff} ({float(points):g})")
        row.append(f"{table1['total_points'][agent_id]:g}")
        row.append(_fmt_rate(table1["cooperation"].get(agent_id)))
        rows.append(row)
    return _md_table(headers, rows)


def _table2_markdown(table2: List[dict]) -> str:
    return _md_table(
        ["Agent", "Round", "Changed?", "Strategy after round", "Reason"],
        [
            [
                _cell(rec["agent"]),
                _cell(rec["round"]),
                "yes" if rec["change_strategy"] else "no",
                _cell(rec["strategy_after"]),
                _cell(rec["reason"]),
            ]
            for rec in table2
        ],
    )


def write_report(result: dict, report_path: str, results_dir: str) -> str:
    data = result["data"]
    meta = data.get("meta", {})
    status = data.get("status", {})
    table1 = result["table1"]
    table2 = result["table2"]
    qual = result["qualitative"]
    usage = meta.get("usage_summary") or status.get("usage_summary") or {}
    agents = table1["agents"]
    n_rounds = table1["n_rounds"]
    mode = meta.get("mode", "unknown")
    run_status = status.get("status", meta.get("status", "unknown"))

    lines: List[str] = []
    lines.append(
        "# Emergent Strategies in a 4-Agent Prisoner's Dilemma Tournament"
    )
    lines.append("")
    lines.append("## Execution status")
    lines.append("")
    lines.append(f"- **Run status:** `{run_status}`")
    lines.append(f"- **Mode:** `{mode}`")
    lines.append(
        f"- **Provider / model:** `{meta.get('llm_provider', '?')}` / "
        f"`{meta.get('llm_model', '?')}`"
    )
    lines.append(f"- **Random seed:** `{meta.get('seed', '?')}`")
    lines.append(
        f"- **Tournament:** {n_rounds} rounds, agents "
        f"{', '.join(agents)}"
    )
    lines.append(
        f"- **Continuation probability:** "
        f"{meta.get('continue_prob', '?')}"
    )
    lines.append(f"- **Output directory:** `{results_dir}`")
    if meta.get("started_at"):
        lines.append(f"- **Started:** {meta['started_at']}")
    if meta.get("finished_at"):
        lines.append(f"- **Finished:** {meta['finished_at']}")
    if usage:
        lines.append(
            f"- **API usage:** {usage.get('n_calls', 0)} calls, "
            f"{usage.get('total_input_tokens', 0):,} input tokens, "
            f"{usage.get('total_output_tokens', 0):,} output tokens, "
            f"estimated cost ${usage.get('estimated_cost_usd', 0):.6f}"
        )
        if usage.get("cost_note"):
            lines.append(f"  - {usage['cost_note']}")
    lines.append("")

    if mode == "mock":
        lines.append(
            "> **IMPORTANT:** This report was generated with the deterministic "
            "offline mock backend. It validates the pipeline only and is "
            "**not** evidence about LLM behaviour."
        )
        lines.append("")
    if run_status == "failed":
        lines.append(
            "> **The run did not complete.** The recorded error is included "
            "below. No scientific claims should be drawn from partial data."
        )
        lines.append("")
        error = status.get("error") or meta.get("error")
        if error:
            lines.append("```")
            lines.append(str(error)[-4000:])
            lines.append("```")
            lines.append("")

    lines.append("## Experiment design")
    lines.append("")
    lines.append(
        "- Four persistent agents (A, B, C, D) used the same model, "
        "temperature, initial instructions and decision rules."
    )
    lines.append(
        "- Each round contained two simultaneous pair-games. Pairings were "
        "sampled independently each round from the seeded RNG; repeat "
        "encounters were allowed. Opponent identities were never shown to "
        "agents."
    )
    lines.append(
        "- Both games in a round used the same hidden geometric length "
        f"(continuation probability {meta.get('continue_prob', '?')})."
    )
    lines.append(
        "- After both games, the four agents were ranked by raw payoff in "
        "that round and received 3, 2, 1 or 0 points, with ties averaged. "
        "Each round was an independent objective."
    )
    lines.append(
        "- After every round, including the last, each agent produced a "
        "structured private reflection and could keep or revise its strategy."
    )
    lines.append("")


    lines.append("## Table 1: Tournament Results")
    lines.append("")
    lines.append(
        "Each cell is `raw payoff (ranking points)`. The last two columns "
        "give total ranking points across the tournament and the agent's "
        "overall cooperation rate."
    )
    lines.append("")
    lines.append(_table1_markdown(table1))
    lines.append("")
    lines.append(
        f"Population overall cooperation rate: "
        f"{_fmt_rate(table1['cooperation'].get('_overall'))}. "
        f"Mutual cooperation rate: "
        f"{_fmt_rate(table1['cooperation'].get('_mutual'))}."
    )
    lines.append("")

    lines.append("## Table 2: Strategy Evolution")
    lines.append("")
    lines.append(
        "The table lists each agent's stated strategy after every round, "
        "whether the agent said it was changing strategy, and its reason. "
        "Even when `Changed?` is `no`, `strategy_after` is the strategy the "
        "agent said it would use next round."
    )
    lines.append("")
    lines.append(_table2_markdown(table2))
    lines.append("")

    lines.append("## Figures")
    lines.append("")
    if result.get("figures"):
        for path in result["figures"]:
            rel = os.path.relpath(path, results_dir)
            lines.append(f"![{os.path.basename(path)}]({rel})")
            lines.append("")
    else:
        lines.append("No figures were generated (no completed rounds).")
        lines.append("")


    lines.append("## Qualitative Analysis")
    lines.append("")

    # 1. Distinct strategies.
    distinct = qual["distinct"]
    lines.append(
        "### 1. Did agents develop distinct strategies despite identical "
        "initial conditions?"
    )
    lines.append("")
    n_unique = distinct["n_unique_final_strategies"]
    if n_unique > 1:
        lines.append(
            f"Yes, at least in their stated strategies: "
            f"{n_unique} distinct final strategy descriptions were recorded "
            f"across {len(agents)} agents."
        )
    elif n_unique == 1:
        lines.append(
            "The final strategy descriptions were textually identical. This "
            "does not prove the behaviour was identical; compare the action "
            "and cooperation statistics below."
        )
    else:
        lines.append(
            "No final strategy descriptions were recorded (the run may not "
            "have completed a reflection)."
        )
    lines.append("")
    for agent_id in agents:
        strategy = distinct["final_strategies"].get(agent_id)
        rate = table1["cooperation"].get(agent_id)
        lines.append(
            f"- **Agent {agent_id}:** cooperation rate "
            f"{_fmt_rate(rate)}. Final strategy: {_cell(strategy)}"
        )
    lines.append("")

    # 2. Cooperation trend.
    trend = qual["cooperation_trend"]
    mutual = trend["mutual_per_round"]
    mutual_values = [mutual[r] for r in mutual]
    half = max(1, n_rounds // 2)
    mutual_first = (
        float(np.nanmean(mutual_values[:half]))
        if mutual_values
        else float("nan")
    )
    mutual_second = (
        float(np.nanmean(mutual_values[half:]))
        if mutual_values
        else float("nan")
    )
    lines.append("### 2. Did cooperation increase or decrease over time?")
    lines.append("")
    lines.append(
        f"Population cooperation averaged "
        f"{_fmt_rate(trend['first_half'])} in the first half of the "
        f"tournament and {_fmt_rate(trend['second_half'])} in the second "
        f"half (change {trend['delta']:+.2f}). Mutual cooperation averaged "
        f"{_fmt_rate(mutual_first)} and {_fmt_rate(mutual_second)} "
        f"respectively."
    )
    lines.append("")
    if trend["delta"] > 0.05:
        lines.append(
            "**Observation:** cooperation rose over the tournament in this "
            "run. The time series in `cooperation_rate_by_round.png` shows "
            "whether the rise was gradual or driven by a few rounds."
        )
    elif trend["delta"] < -0.05:
        lines.append(
            "**Observation:** cooperation fell over the tournament in this "
            "run. The time series in `cooperation_rate_by_round.png` shows "
            "whether the decline was gradual or driven by a few rounds."
        )
    else:
        lines.append(
            "**Observation:** there was no large first-half/second-half "
            "change in this run; round-to-round variation may still be "
            "substantial."
        )
    lines.append("")

    # 3. Reciprocity / retaliation.
    lines.append("### 3. Did agents discover reciprocity or retaliation?")
    lines.append("")
    lines.append(
        "The table reports, within pair-games, the probability that an "
        "agent cooperated on the stage after its opponent cooperated "
        "(`P(C|opp C)`) and after its opponent defected (`P(C|opp D)`). A "
        "positive difference is consistent with conditional cooperation; a "
        "low `P(C|opp D)` is consistent with retaliation."
    )
    lines.append("")
    cond_rows = []
    for agent_id in agents:
        values = qual["conditional_cooperation"].get(agent_id, {})
        after_c = values.get("p_coop_after_opp_C")
        after_d = values.get("p_coop_after_opp_D")
        diff = (
            after_c - after_d
            if after_c == after_c and after_d == after_d
            else float("nan")
        )
        cond_rows.append(
            [
                f"Agent {agent_id}",
                _fmt_rate(after_c),
                _fmt_rate(after_d),
                f"{diff:+.2f}" if diff == diff else "n/a",
                str(values.get("n_after_C", 0)),
                str(values.get("n_after_D", 0)),
            ]
        )
    lines.append(
        _md_table(
            [
                "Agent",
                "P(C | opp C)",
                "P(C | opp D)",
                "Difference",
                "n after C",
                "n after D",
            ],
            cond_rows,
        )
    )
    lines.append("")
    pooled = qual["reciprocity"]["pooled_mean_difference"]
    if pooled == pooled and pooled > 0.20:
        lines.append(
            f"**Observation:** the pooled difference is {pooled:+.2f}, "
            "consistent with reciprocal/conditional cooperation. This is a "
            "behavioural pattern, not proof that agents formed an explicit "
            "reciprocity rule."
        )
    elif pooled == pooled and pooled < -0.20:
        lines.append(
            f"**Observation:** the pooled difference is {pooled:+.2f}: agents "
            "were more likely to cooperate after an opponent defection than "
            "after cooperation, a pattern opposite to simple reciprocity."
        )
    else:
        lines.append(
            f"**Observation:** the pooled difference is "
            f"{pooled:+.2f}, so there is no strong simple reciprocity signal "
            "in this run. Individual agents may still differ."
        )
    lines.append("")


    # 4. Revisions and subsequent performance.
    rev = qual["revision_performance"]
    lines.append(
        "### 4. Were strategy revisions associated with improved subsequent "
        "performance?"
    )
    lines.append("")
    lines.append(
        f"After a stated strategy change, agents averaged "
        f"{_fmt_number(rev['changed']['mean_next_points'])} ranking points in "
        f"the next round (n={rev['changed']['n']} agent-round observations). "
        f"After no stated change, they averaged "
        f"{_fmt_number(rev['unchanged']['mean_next_points'])} points "
        f"(n={rev['unchanged']['n']}). Mean next-round raw payoffs were "
        f"{_fmt_number(rev['changed']['mean_next_payoff'])} and "
        f"{_fmt_number(rev['unchanged']['mean_next_payoff'])} respectively."
    )
    lines.append("")
    lines.append(
        "**Observation:** this is descriptive. Agents choose when to revise, "
        "rounds differ in opponent and game length, and observations are not "
        "independent. A difference here does **not** establish that "
        "reflection caused the subsequent performance."
    )
    lines.append("")

    # 5. Population adaptation.
    opening = qual["opening_trend"]
    lines.append(
        "### 5. Did agents adapt to the anonymous population rather than "
        "individual opponents?"
    )
    lines.append("")
    lines.append(
        f"First-stage cooperation averaged "
        f"{_fmt_rate(opening['first_half'])} in the first half and "
        f"{_fmt_rate(opening['second_half'])} in the second half "
        f"(change {opening['delta']:+.2f})."
    )
    lines.append("")
    lines.append(
        "Agents never received opponent identities and each saw only its own "
        "history. A change in opening behaviour is therefore consistent with "
        "learning about the anonymous population as a whole rather than about "
        "a named individual. It is not conclusive: within-game experience, "
        "model drift, and round composition can also move this statistic."
    )
    lines.append("")
    for agent_id in agents:
        lines.append(
            f"- Agent {agent_id}: first-stage cooperation "
            f"{_fmt_rate(qual['first_stage']['per_agent'].get(agent_id))}"
        )
    lines.append("")


    # 6. Consistency.
    lines.append(
        "### 6. Did some agents develop strategies inconsistent with their "
        "stated objectives?"
    )
    lines.append("")
    flags = qual["consistency"]
    any_flags = any(item["flags"] for item in flags)
    if not any_flags:
        lines.append(
            "No keyword-level inconsistencies were detected between the final "
            "strategy text and observed behaviour. This check is deliberately "
            "simple: strategies can be complex, and a strategy may be "
            "consistent with the current-round ranking objective without "
            "using words such as 'cooperate' or 'defect'."
        )
    else:
        for item in flags:
            if not item["flags"]:
                continue
            lines.append(
                f"- **Agent {item['agent']}:** " + "; ".join(item["flags"])
            )
        lines.append("")
        lines.append(
            "These flags are heuristic text/behaviour checks, not a claim "
            "about the agent's internal reasoning."
        )
    lines.append("")

    lines.append("### Observations versus causal conclusions")
    lines.append("")
    lines.append(
        "Everything above is descriptive. Agents interact, pairings repeat, "
        "and one tournament is a single realisation. The experiment cannot "
        "establish that reflection caused any improvement, that a particular "
        "strategy is optimal, or that the observed cooperation trend would "
        "generalise to other seeds or models. Independent replications across "
        "seeds (and ideally model families) are required for inferential "
        "claims."
    )
    lines.append("")

    lines.append("## Limitations")
    lines.append("")
    lines.append(
        "- Single tournament realisation; no independent replications across "
        "seeds or models."
    )
    lines.append(
        "- Agents are repeatedly paired, so stage-level observations are not "
        "independent."
    )
    lines.append(
        "- The ranking objective is relative: an agent's points depend on the "
        "other three agents' payoffs in that round, not only on its own "
        "cooperation."
    )
    lines.append(
        "- The strategy-consistency checks are transparent keyword "
        "heuristics, not a reading of the model's internal computation."
    )
    if mode == "mock":
        lines.append(
            "- **This run used the offline mock backend.** Its outputs are "
            "synthetic and must not be interpreted as LLM behaviour."
        )
    lines.append("")

    lines.append("## Files")
    lines.append("")
    raw_files = [
        "pairings.jsonl",
        "stages.jsonl",
        "games.jsonl",
        "rounds.jsonl",
        "reflections.jsonl",
        "strategies.jsonl",
        "usage.jsonl",
        "calls.jsonl",
        "checkpoint.json",
        "experiment_meta.json",
        "run_status.json",
        "config_snapshot.yaml",
    ]
    for name in raw_files:
        path = os.path.join(results_dir, name)
        if os.path.exists(path):
            lines.append(f"- `{name}`")
    lines.append(
        "- `tables/` (Table 1/2 CSV and Markdown, cooperation by round)"
    )
    lines.append("- `figures/` (cooperation, cumulative points, revisions)")
    lines.append("")
    lines.append("Reproduction command (after setting `OPENAI_API_KEY`):")
    lines.append("")
    lines.append("```bash")
    lines.append(
        "python3 -m ranked_tournament.cli run "
        "--config config/ranked_tournament.yaml"
    )
    lines.append(
        "python3 -m ranked_tournament.cli analyze "
        f"--results {results_dir}"
    )
    lines.append("```")
    lines.append("")

    text = "\n".join(lines)
    ensure_dir(os.path.dirname(os.path.abspath(report_path)))
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return report_path



# ---------------------------------------------------------------------- #
# Orchestration
# ---------------------------------------------------------------------- #
def _json_safe(obj):
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    return obj


def analyze_all(
    results_dir: str,
    figures_dir: Optional[str] = None,
    tables_dir: Optional[str] = None,
) -> dict:
    from collections import Counter

    data = load_results(results_dir)
    figures_dir = figures_dir or os.path.join(results_dir, "figures")
    tables_dir = tables_dir or os.path.join(results_dir, "tables")
    table1 = build_table1(data)
    table2 = build_table2(data)
    qualitative = build_qualitative_summary(data, table1)
    figures = make_figures(data, figures_dir)
    table_paths = write_tables(data, table1, table2, tables_dir)

    games = data.get("games", [])
    lengths = [float(g.get("length", 0)) for g in games if g.get("length")]
    calls = data.get("calls", [])
    decision_parse = Counter(
        c.get("parse_status")
        for c in calls
        if c.get("task") == "decision"
    )
    reflection_parse = Counter(
        c.get("parse_status")
        for c in calls
        if c.get("task") == "reflection"
    )
    stages = data.get("stages", [])
    revisions = revisions_by_round(data)
    stats = {
        "n_rounds": table1["n_rounds"],
        "n_agents": len(table1["agents"]),
        "n_games": len(games),
        "n_stages": len(stages),
        "n_reflections": len(data.get("reflections", [])),
        "n_calls": len(calls),
        "n_usage_records": len(data.get("usage", [])),
        "total_input_tokens": sum(
            int(u.get("input_tokens", 0)) for u in data.get("usage", [])
        ),
        "total_output_tokens": sum(
            int(u.get("output_tokens", 0)) for u in data.get("usage", [])
        ),
        "estimated_cost_usd": sum(
            float(u.get("cost_usd", 0.0)) for u in data.get("usage", [])
        ),
        "overall_cooperation_rate": table1["cooperation"].get("_overall"),
        "mutual_cooperation_rate": table1["cooperation"].get("_mutual"),
        "total_ranking_points": table1["total_points"],
        "game_length_min": min(lengths) if lengths else None,
        "game_length_max": max(lengths) if lengths else None,
        "game_length_mean": (
            float(np.mean(lengths)) if lengths else None
        ),
        "decisions_total": sum(decision_parse.values()),
        "decision_parse_status": dict(decision_parse),
        "reflection_parse_status": dict(reflection_parse),
        "strategy_revisions_stated": sum(
            revisions[r]["changed"] for r in revisions
        ),
        "strategy_revisions_text": sum(
            revisions[r]["text_changed"] for r in revisions
        ),
        "expected_reflections": (
            table1["n_rounds"] * len(table1["agents"])
        ),
    }

    summary = {
        "meta": data.get("meta", {}),
        "status": data.get("status", {}),
        "stats": stats,
        "table1": table1,
        "table2": table2,
        "qualitative": qualitative,
    }
    summary_path = os.path.join(results_dir, "analysis_summary.json")
    ensure_dir(os.path.dirname(os.path.abspath(summary_path)))
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(_json_safe(summary), fh, indent=2, ensure_ascii=False)

    return {
        "data": data,
        "table1": table1,
        "table2": table2,
        "qualitative": qualitative,
        "figures": figures,
        "tables": table_paths,
        "stats": stats,
        "summary_path": summary_path,
    }

