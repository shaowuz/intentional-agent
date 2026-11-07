"""Data loading, statistics, strategy classification and plotting.

All quantitative results are computed from recorded JSONL data; nothing is
hard-coded.  Plots are written with the non-interactive Agg backend.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Tuple

import numpy as np

from .recorder import read_jsonl
from .utils import ensure_dir

STRATEGY_LABELS = [
    "Always Cooperate",
    "Always Defect",
    "Tit-for-Tat",
    "Grim Trigger",
    "Tit-for-Two-Tats (Forgiving)",
    "Mixed/Other",
]


# ---------------------------------------------------------------------- #
# Loading
# ---------------------------------------------------------------------- #
def load_condition(results_root: str, condition: str) -> Dict[str, object]:
    """Load the recorded data for one condition into plain lists / DataFrames."""
    import pandas as pd

    cdir = os.path.join(results_root, condition)
    rounds = read_jsonl(os.path.join(cdir, "rounds.jsonl"))
    games = read_jsonl(os.path.join(cdir, "games.jsonl"))
    beliefs = read_jsonl(os.path.join(cdir, "beliefs.jsonl"))
    usage = read_jsonl(os.path.join(cdir, "usage.jsonl"))

    games_flat = []
    for g in games:
        parts = g["participants"]
        for aid in parts:
            other = parts[0] if parts[1] == aid else parts[1]
            b = g.get("beliefs", {}).get(aid, {})
            games_flat.append(
                {
                    "condition": g["condition"],
                    "game_index": g["game_index"],
                    "pair_index": g.get("pair_index"),
                    "agent_id": aid,
                    "opponent_id": other,
                    "prior": g["prior"][aid],
                    "prior_group": g["prior_group"][aid],
                    "opp_prior_group": g["prior_group"][other],
                    "horizon": g["horizon"],
                    "actual_rounds": g["actual_rounds"],
                    "capped": g.get("capped", False),
                    "game_payoff": g["totals"][aid]["game_payoff"],
                    "lifetime_cum_payoff": g["totals"][aid]["lifetime_cum_payoff"],
                    "coop_rate": g["totals"][aid]["coop_rate"],
                    "belief_defect_prob": b.get("defect_probability"),
                    "belief_parse_status": b.get("parse_status"),
                }
            )

    return {
        "rounds": pd.DataFrame(rounds),
        "games": pd.DataFrame(games_flat),
        "beliefs": pd.DataFrame(beliefs),
        "usage": pd.DataFrame(usage),
    }


def load_roster(results_root: str):
    import pandas as pd

    path = os.path.join(results_root, "roster.json")
    if not os.path.exists(path):
        return pd.DataFrame([])
    with open(path, "r", encoding="utf-8") as fh:
        return pd.DataFrame(json.load(fh))


# ---------------------------------------------------------------------- #
# Strategy classification (heuristic, descriptive only)
# ---------------------------------------------------------------------- #
def _predictions(own: List[str], opp: List[str], strategy: str) -> List[str]:
    n = len(opp)
    pred = []
    for t in range(n):
        if t == 0:
            pred.append("C" if strategy != "Always Defect" else "D")
            continue
        if strategy == "Always Cooperate":
            pred.append("C")
        elif strategy == "Always Defect":
            pred.append("D")
        elif strategy == "Tit-for-Tat":
            pred.append(opp[t - 1])
        elif strategy == "Grim Trigger":
            pred.append("D" if "D" in opp[:t] else "C")
        elif strategy == "Tit-for-Two-Tats (Forgiving)":
            # Retaliate only after two consecutive opponent defections.
            pred.append("D" if t >= 2 and opp[t - 1] == "D" and opp[t - 2] == "D" else "C")
        else:
            pred.append("C")
    return pred


def classify_strategy(
    own: List[str],
    opp: List[str],
    threshold: float = 0.75,
    min_rounds: int = 4,
    tol: float = 1e-9,
) -> Tuple[str, Dict[str, float]]:
    """Return ``(label, scores)`` for one action/opponent-action sequence.

    Each candidate strategy is scored by the fraction of rounds (from round 2
    onward) in which its prediction matches the agent's actual action.  If the
    best score is below ``threshold`` the label is ``Mixed/Other``.  If two or
    more strategies tie for the best score, the label is
    ``"Tie: A | B | ..."`` rather than arbitrarily forcing a single strategy ---
    this is common when the opponent never defects (Always Cooperate,
    Tit-for-Tat, Grim Trigger and Tit-for-Two-Tats then make identical
    predictions).  This is a descriptive heuristic, not a claim about internal
    computation.
    """
    if len(own) < min_rounds:
        return "Mixed/Other", {}
    candidates = STRATEGY_LABELS[:-1]
    scores = {}
    for strat in candidates:
        pred = _predictions(own, opp, strat)
        matches = sum(1 for t in range(1, len(own)) if pred[t] == own[t])
        scores[strat] = matches / max(1, len(own) - 1)
    best_score = max(scores.values())
    if best_score < threshold:
        return "Mixed/Other", scores
    tied = [s for s in candidates if scores[s] >= best_score - tol]
    if len(tied) == 1:
        return tied[0], scores
    return "Tie: " + " | ".join(tied), scores


# ---------------------------------------------------------------------- #
# Statistics
# ---------------------------------------------------------------------- #
def mean_ci(values) -> Tuple[float, float, float]:
    """Mean and 95% CI half-width using the normal approximation (SEM)."""
    arr = np.asarray([v for v in values if v is not None and not np.isnan(v)], dtype=float)
    if arr.size == 0:
        return float("nan"), float("nan"), float("nan")
    m = float(arr.mean())
    if arr.size < 2:
        return m, float("nan"), float("nan")
    sem = float(arr.std(ddof=1) / np.sqrt(arr.size))
    half = 1.96 * sem
    return m, m - half, m + half


def coop_by_agent_game(rounds):
    """Mean cooperation rate per (condition, prior_group, agent, game)."""
    df = rounds.copy()
    df["is_c"] = (df["own_action"] == "C").astype(float)
    return (
        df.groupby(
            ["condition", "prior", "prior_group", "agent_id", "game_index"],
            as_index=False,
        )["is_c"]
        .mean()
        .rename(columns={"is_c": "coop_rate"})
    )


def group_game_stats(agent_game, value_col: str):
    """Group mean and 95% CI of ``value_col`` per (condition, prior_group, game)."""
    import pandas as pd

    records = []
    for (cond, grp, gidx), sub in agent_game.groupby(
        ["condition", "prior_group", "game_index"]
    ):
        m, lo, hi = mean_ci(sub[value_col].tolist())
        records.append(
            {
                "condition": cond,
                "prior_group": grp,
                "prior": float(grp),
                "game_index": int(gidx),
                "mean": m,
                "ci_low": lo,
                "ci_high": hi,
                "n": len(sub),
            }
        )
    out = pd.DataFrame(records)
    if not out.empty:
        out = out.sort_values(["condition", "prior", "game_index"]).reset_index(drop=True)
    return out


def conditional_coop(rounds):
    """Return per-agent and grouped P(own C | previous joint outcome)."""
    import pandas as pd

    keys = ["condition", "game_index", "agent_id"]
    df = rounds.sort_values(keys + ["round"]).copy()
    df["prev_own"] = df.groupby(keys)["own_action"].shift(1)
    df["prev_opp"] = df.groupby(keys)["opp_action"].shift(1)
    df = df.dropna(subset=["prev_own", "prev_opp"])
    df["prev_outcome"] = df["prev_own"].astype(str) + df["prev_opp"].astype(str)
    df["is_c"] = (df["own_action"] == "C").astype(float)

    per_agent = (
        df.groupby(
            ["condition", "prior_group", "agent_id", "prev_outcome"], as_index=False
        )["is_c"]
        .mean()
        .rename(columns={"is_c": "p_coop"})
    )
    stats = (
        per_agent.groupby(["condition", "prior_group", "prev_outcome"])["p_coop"]
        .agg(["mean", "std", "count"])
        .reset_index()
        .rename(columns={"mean": "p_coop", "count": "n_agents"})
    )
    stats["ci"] = 1.96 * stats["std"].fillna(0.0) / np.sqrt(
        stats["n_agents"].clip(lower=1)
    )
    return per_agent, stats


def strategy_by_agent_game(rounds):
    """Classify each (agent, game) sequence, then take a weighted majority per agent."""
    import pandas as pd

    rows = []
    for (cond, aid, gidx), sub in rounds.groupby(
        ["condition", "agent_id", "game_index"]
    ):
        sub = sub.sort_values("round")
        own = list(sub["own_action"])
        opp = list(sub["opp_action"])
        label, scores = classify_strategy(own, opp)
        rows.append(
            {
                "condition": cond,
                "agent_id": aid,
                "game_index": gidx,
                "prior": float(sub["prior"].iloc[0]),
                "prior_group": sub["prior_group"].iloc[0],
                "strategy": label,
                "best_score": max(scores.values()) if scores else float("nan"),
                "n_rounds": len(own),
            }
        )
    per_game = pd.DataFrame(rows)

    # Weighted majority per agent: sum rounds per strategy, keep the largest.
    per_agent = (
        per_game.groupby(
            ["condition", "prior", "prior_group", "agent_id", "strategy"]
        )["n_rounds"]
        .sum()
        .reset_index()
        .sort_values("n_rounds")
        .drop_duplicates(["condition", "prior", "prior_group", "agent_id"], keep="last")
        [["condition", "prior", "prior_group", "agent_id", "strategy"]]
        .reset_index(drop=True)
    )
    return per_game, per_agent


# ---------------------------------------------------------------------- #
# Plotting
# ---------------------------------------------------------------------- #
def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _prior_cmap(priors):
    plt = _plt()
    cmap = plt.get_cmap("viridis")
    n = max(1, len(priors) - 1)
    return {p: cmap(i / n) for i, p in enumerate(priors)}


def plot_metric_by_game(agent_game, group_stats, value_col, ylabel, title, path):
    """Panel per condition: group mean +/- CI and faint individual trajectories."""
    plt = _plt()
    conditions = list(group_stats["condition"].unique())
    if not conditions:
        return
    fig, axes = plt.subplots(
        1, len(conditions), figsize=(6 * len(conditions), 4.2), squeeze=False
    )
    for ax, cond in zip(axes[0], conditions):
        gs = group_stats[group_stats["condition"] == cond]
        ag = agent_game[agent_game["condition"] == cond]
        priors = sorted(gs["prior"].unique())
        colors = _prior_cmap(priors)
        for p in priors:
            color = colors[p]
            sub = ag[ag["prior"].astype(float) == p]
            for _, s in sub.groupby("agent_id"):
                s = s.sort_values("game_index")
                ax.plot(
                    s["game_index"] + 1, s[value_col], color=color, alpha=0.12, lw=0.7
                )
            g = gs[gs["prior"] == p].sort_values("game_index")
            ax.plot(
                g["game_index"] + 1, g["mean"], color=color, lw=2.0, label=f"prior={p}"
            )
            ax.fill_between(
                g["game_index"] + 1, g["ci_low"], g["ci_high"], color=color, alpha=0.18
            )
        ax.set_title(f"{cond} horizon")
        ax.set_xlabel("game number")
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.25)
        ax.legend(fontsize=7, title="initial prior")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_conditional_coop(stats, path):
    plt = _plt()
    outcomes = ["CC", "CD", "DC", "DD"]
    conditions = list(stats["condition"].unique())
    if not conditions:
        return
    fig, axes = plt.subplots(
        1, len(conditions), figsize=(6 * len(conditions), 4.2), squeeze=False
    )
    for ax, cond in zip(axes[0], conditions):
        sub = stats[stats["condition"] == cond]
        priors = sorted(sub["prior_group"].unique(), key=float)
        colors = _prior_cmap([float(p) for p in priors])
        width = 0.8 / max(1, len(priors))
        x = np.arange(len(outcomes))
        for i, p in enumerate(priors):
            vals, errs = [], []
            for o in outcomes:
                row = sub[(sub["prior_group"] == p) & (sub["prev_outcome"] == o)]
                vals.append(row["p_coop"].iloc[0] if not row.empty else np.nan)
                errs.append(row["ci"].iloc[0] if not row.empty else 0.0)
            ax.bar(
                x + (i - (len(priors) - 1) / 2) * width,
                vals,
                width,
                yerr=errs,
                capsize=2,
                color=colors[float(p)],
                label=f"prior={p}",
            )
        ax.set_xticks(x)
        ax.set_xticklabels([f"prev {o}" for o in outcomes])
        ax.set_ylim(0, 1)
        ax.set_ylabel("P(cooperate this round)")
        ax.set_title(f"{cond} horizon | conditional cooperation")
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _strategy_label_order(observed):
    """Order strategy labels: canonical ones first, then tie/other labels."""
    observed = set(observed)
    ordered = [s for s in STRATEGY_LABELS if s in observed]
    extras = sorted(s for s in observed if s not in STRATEGY_LABELS)
    return ordered + extras


def plot_strategy_distribution(per_agent, path):
    plt = _plt()
    import pandas as pd

    conditions = list(per_agent["condition"].unique())
    if not conditions:
        return
    labels = _strategy_label_order(per_agent["strategy"].unique())
    fig, axes = plt.subplots(
        1, len(conditions), figsize=(6 * len(conditions), 4.2), squeeze=False
    )
    for ax, cond in zip(axes[0], conditions):
        sub = per_agent[per_agent["condition"] == cond]
        priors = sorted(sub["prior_group"].unique(), key=float)
        ctab = pd.crosstab(
            sub["prior_group"], sub["strategy"], normalize="index"
        ).reindex(index=priors, columns=labels, fill_value=0.0)
        bottom = np.zeros(len(priors))
        cmap = plt.get_cmap("tab20")
        for k, label in enumerate(labels):
            vals = ctab[label].values
            ax.bar(
                [float(p) for p in priors],
                vals,
                bottom=bottom,
                width=0.07,
                color=cmap(k % 20),
                label=label,
            )
            bottom += vals
        ax.set_xlabel("initial prior")
        ax.set_ylabel("fraction of agents")
        ax.set_ylim(0, 1)
        ax.set_title(f"{cond} horizon | strategy mix")
        ax.legend(fontsize=6, loc="upper left", bbox_to_anchor=(1.0, 1.0))
        ax.grid(alpha=0.2, axis="y")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_final_beliefs(games, path):
    plt = _plt()
    conditions = list(games["condition"].unique())
    if not conditions:
        return
    fig, axes = plt.subplots(
        1, len(conditions), figsize=(6 * len(conditions), 4.2), squeeze=False
    )
    for ax, cond in zip(axes[0], conditions):
        sub = games[games["condition"] == cond]
        max_game = sub["game_index"].max()
        final = sub[sub["game_index"] == max_game]
        priors = sorted(final["prior_group"].unique(), key=float)
        data = [
            final[final["prior_group"] == p]["belief_defect_prob"].dropna().values
            for p in priors
        ]
        positions = range(1, len(priors) + 1)
        ax.boxplot(data, positions=list(positions))
        ax.set_xticks(list(positions))
        ax.set_xticklabels([f"{p}" for p in priors])
        ax.plot(
            list(positions),
            [float(p) for p in priors],
            "r--",
            marker="o",
            ms=4,
            label="initial prior",
        )
        ax.set_xlabel("initial prior")
        ax.set_ylabel("final belief: new opp defects (P)")
        ax.set_ylim(-0.02, 1.02)
        ax.set_title(f"{cond} horizon | final beliefs")
        ax.legend(fontsize=7)
        ax.grid(alpha=0.25, axis="y")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_horizon_comparison(coop_agent_game, belief_agent_game, path):
    """Pooled cooperation and belief trajectories: fixed vs random horizon."""
    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), squeeze=False)

    def _pooled(agent_game, value_col):
        rows = []
        for (cond, gidx), sub in agent_game.groupby(["condition", "game_index"]):
            vals = sub[value_col].dropna().values
            if len(vals) == 0:
                continue
            m, lo, hi = mean_ci(vals.tolist())
            rows.append(
                {
                    "condition": cond,
                    "game_index": gidx,
                    "mean": m,
                    "lo": lo,
                    "hi": hi,
                }
            )
        import pandas as pd

        return pd.DataFrame(rows)

    pooled_coop = _pooled(coop_agent_game, "coop_rate")
    pooled_belief = _pooled(belief_agent_game, "belief_defect_prob")

    for ax, pooled, ylabel, title in (
        (axes[0][0], pooled_coop, "cooperation rate", "Cooperation: fixed vs random"),
        (axes[0][1], pooled_belief, "belief (P new opp defects)", "Beliefs: fixed vs random"),
    ):
        colors = {"fixed": "#1f77b4", "random": "#d62728"}
        for cond, sub in pooled.groupby("condition"):
            sub = sub.sort_values("game_index")
            ax.plot(
                sub["game_index"] + 1,
                sub["mean"],
                color=colors.get(cond, None),
                lw=2,
                label=cond,
            )
            ax.fill_between(
                sub["game_index"] + 1,
                sub["lo"],
                sub["hi"],
                color=colors.get(cond, None),
                alpha=0.2,
            )
        ax.set_xlabel("game number")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(alpha=0.25)
        ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------------- #
# Orchestration
# ---------------------------------------------------------------------- #
def analyze_all(results_root: str, figures_dir: str, tables_dir: str) -> dict:
    """Load all conditions, compute tables, save CSVs and figures."""
    import pandas as pd

    ensure_dir(figures_dir)
    ensure_dir(tables_dir)

    cond_dirs = sorted(
        d
        for d in os.listdir(results_root)
        if os.path.isdir(os.path.join(results_root, d))
        and os.path.exists(os.path.join(results_root, d, "games.jsonl"))
    )
    if not cond_dirs:
        raise FileNotFoundError(f"No condition data found under {results_root}")

    frames = {c: load_condition(results_root, c) for c in cond_dirs}
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        all_rounds = pd.concat(
            [frames[c]["rounds"] for c in cond_dirs], ignore_index=True
        )
        all_games = pd.concat(
            [frames[c]["games"] for c in cond_dirs], ignore_index=True
        )

    coop_agent_game = coop_by_agent_game(all_rounds)
    belief_agent_game = all_games[
        ["condition", "prior", "prior_group", "agent_id", "game_index", "belief_defect_prob"]
    ].copy()
    payoff_agent_game = all_games[
        ["condition", "prior", "prior_group", "agent_id", "game_index", "game_payoff"]
    ].copy()
    cum_agent_game = all_games[
        ["condition", "prior", "prior_group", "agent_id", "game_index", "lifetime_cum_payoff"]
    ].copy()

    tables = {}
    tables["coop_by_agent_game"] = coop_agent_game
    tables["coop_group_stats"] = group_game_stats(coop_agent_game, "coop_rate")
    tables["belief_group_stats"] = group_game_stats(belief_agent_game, "belief_defect_prob")
    tables["payoff_group_stats"] = group_game_stats(payoff_agent_game, "game_payoff")
    tables["cumulative_payoff_group_stats"] = group_game_stats(
        cum_agent_game, "lifetime_cum_payoff"
    )

    _, cond_stats = conditional_coop(all_rounds)
    tables["conditional_coop_stats"] = cond_stats

    strat_game, strat_agent = strategy_by_agent_game(all_rounds)
    tables["strategy_per_game"] = strat_game
    tables["strategy_per_agent"] = strat_agent

    final_rows = []
    for _, sub in all_games.groupby("condition"):
        max_game = sub["game_index"].max()
        final_rows.append(sub[sub["game_index"] == max_game])
    final_beliefs = pd.concat(final_rows, ignore_index=True)[
        ["condition", "prior", "prior_group", "agent_id", "belief_defect_prob"]
    ]
    tables["final_beliefs"] = final_beliefs

    horizon_rows = []
    for cond in cond_dirs:
        g = all_games[all_games["condition"] == cond]
        c = coop_agent_game[coop_agent_game["condition"] == cond]
        horizon_rows.append(
            {
                "condition": cond,
                "n_agents": g["agent_id"].nunique(),
                "mean_coop_rate": c["coop_rate"].mean(),
                "mean_game_payoff": g["game_payoff"].mean(),
                "mean_belief": g["belief_defect_prob"].mean(),
                "mean_actual_rounds": g["actual_rounds"].mean(),
                "max_actual_rounds": g["actual_rounds"].max(),
                "capped_games": int(
                    g.drop_duplicates(["game_index", "pair_index"])["capped"].sum()
                ),
            }
        )
    tables["horizon_comparison"] = pd.DataFrame(horizon_rows)

    for name, df in tables.items():
        df.to_csv(os.path.join(tables_dir, f"{name}.csv"), index=False)

    plot_metric_by_game(
        coop_agent_game, tables["coop_group_stats"], "coop_rate", "cooperation rate",
        "Cooperation by game and initial prior",
        os.path.join(figures_dir, "cooperation_by_game.png"),
    )
    plot_metric_by_game(
        belief_agent_game, tables["belief_group_stats"], "belief_defect_prob",
        "belief (P new opp defects)", "Belief evolution by game and initial prior",
        os.path.join(figures_dir, "belief_by_game.png"),
    )
    plot_metric_by_game(
        payoff_agent_game, tables["payoff_group_stats"], "game_payoff", "payoff per game",
        "Per-game payoff by game and initial prior",
        os.path.join(figures_dir, "payoff_by_game.png"),
    )
    plot_metric_by_game(
        cum_agent_game, tables["cumulative_payoff_group_stats"], "lifetime_cum_payoff",
        "cumulative payoff", "Cumulative payoff by game and initial prior",
        os.path.join(figures_dir, "cumulative_payoff_by_game.png"),
    )
    plot_conditional_coop(cond_stats, os.path.join(figures_dir, "conditional_cooperation.png"))
    plot_strategy_distribution(strat_agent, os.path.join(figures_dir, "strategy_distribution.png"))
    plot_final_beliefs(all_games, os.path.join(figures_dir, "final_beliefs.png"))
    plot_horizon_comparison(
        coop_agent_game, belief_agent_game,
        os.path.join(figures_dir, "horizon_comparison.png"),
    )

    summary = {
        "conditions": cond_dirs,
        "horizon_comparison": tables["horizon_comparison"].to_dict(orient="records"),
        "final_belief_by_group": final_beliefs.groupby(["condition", "prior_group"])[
            "belief_defect_prob"
        ]
        .agg(["mean", "std", "count"])
        .reset_index()
        .to_dict(orient="records"),
        "strategy_counts": strat_agent.groupby(["condition", "strategy"])
        .size()
        .reset_index(name="n_agents")
        .to_dict(orient="records"),
    }
    tables["_meta_summary"] = summary
    return {"tables": tables, "summary": summary}


# ---------------------------------------------------------------------- #
# Report
# ---------------------------------------------------------------------- #
def _md_table(df, max_rows: int = 25) -> str:
    """Render a DataFrame as a Markdown table (fallback to a code block)."""
    try:
        return df.head(max_rows).to_markdown(index=False)
    except Exception:  # tabulate may be unavailable
        return "```\n" + df.head(max_rows).to_string(index=False) + "\n```"


def write_report(analysis_result: dict, path: str, results_root: str) -> str:
    """Write a concise Markdown research report from computed results."""
    import time

    import pandas as pd

    tables = analysis_result["tables"]
    summary = analysis_result["summary"]

    meta = {}
    meta_path = os.path.join(results_root, "experiment_meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as fh:
            meta = json.load(fh)
    provider = meta.get("llm_provider", "unknown")
    model = meta.get("llm_model", "unknown")

    final = tables["final_beliefs"]
    conv_rows = []
    for cond, sub in final.groupby("condition"):
        means = sub.groupby("prior_group")["belief_defect_prob"].mean()
        conv_rows.append(
            {
                "condition": cond,
                "group_mean_min": means.min(),
                "group_mean_max": means.max(),
                "between_group_range": means.max() - means.min(),
                "pooled_mean": sub["belief_defect_prob"].mean(),
                "pooled_std": sub["belief_defect_prob"].std(),
            }
        )
    convergence = pd.DataFrame(conv_rows)

    cond_pivot = tables["conditional_coop_stats"].pivot_table(
        index=["condition", "prior_group"], columns="prev_outcome", values="p_coop"
    ).reset_index()
    strat_counts = (
        tables["strategy_per_agent"]
        .groupby(["condition", "strategy"])
        .size()
        .reset_index(name="n_agents")
    )

    lines = []
    lines.append("# Iterated Prisoner's Dilemma LLM experiment - research report")
    lines.append("")
    lines.append(f"_Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}_")
    lines.append("")
    lines.append("## Data provenance")
    lines.append("")
    lines.append(
        _md_table(
            pd.DataFrame(
                [
                    {"field": "experiment", "value": meta.get("experiment", "n/a")},
                    {"field": "seed", "value": meta.get("seed", "n/a")},
                    {"field": "llm_provider", "value": provider},
                    {"field": "llm_model", "value": model},
                    {
                        "field": "agents_per_condition",
                        "value": meta.get("n_agents_per_condition", "n/a"),
                    },
                    {"field": "games_per_agent", "value": meta.get("games_per_agent", "n/a")},
                    {"field": "fixed_rounds", "value": meta.get("fixed_rounds", "n/a")},
                    {"field": "continue_prob", "value": meta.get("continue_prob", "n/a")},
                    {"field": "started_at", "value": meta.get("started_at", "n/a")},
                ]
            )
        )
    )
    lines.append("")
    if str(provider).lower() == "mock":
        lines.append(
            "> **IMPORTANT - MOCK BACKEND.** These results were produced with the "
            "offline `mock` backend. They validate the pipeline (memory, "
            "simultaneous play, recording, analysis) and are **not** scientific "
            "findings about LLM behaviour. Re-run with a real model to obtain "
            "substantive results."
        )
        lines.append("")

    lines.append("## 1. Cooperation by prior group and game")
    lines.append("")
    lines.append(_md_table(tables["horizon_comparison"]))
    lines.append("")
    lines.append("![cooperation](figures/cooperation_by_game.png)")
    lines.append("")

    lines.append("## 2. Evolution of agents' estimated beliefs")
    lines.append("")
    lines.append(_md_table(pd.DataFrame(summary["final_belief_by_group"])))
    lines.append("")
    lines.append("![beliefs](figures/belief_by_game.png)")
    lines.append("")

    lines.append("## 3. Payoffs")
    lines.append("")
    lines.append(
        "Per-game and cumulative payoff figures are in "
        "`figures/payoff_by_game.png` and `figures/cumulative_payoff_by_game.png`."
    )
    lines.append("")
    lines.append("![payoffs](figures/payoff_by_game.png)")
    lines.append("")

    lines.append("## 4. Conditional cooperation (P(cooperate | previous outcome))")
    lines.append("")
    lines.append(_md_table(cond_pivot))
    lines.append("")
    lines.append("![conditional](figures/conditional_cooperation.png)")
    lines.append("")

    lines.append("## 5. Emergence of recognizable strategies")
    lines.append("")
    lines.append(_md_table(strat_counts))
    lines.append("")
    lines.append("![strategies](figures/strategy_distribution.png)")
    lines.append("")
    lines.append(
        "Strategies are classified by a transparent heuristic: each candidate "
        "(AllC, AllD, Tit-for-Tat, Grim Trigger, Tit-for-Two-Tats) is scored by "
        "the fraction of rounds in which its predicted action matches the "
        "observed action. If the best score is below 0.75 the label is "
        "`Mixed/Other`. If several strategies tie, the label is reported as "
        "`Tie: A | B | ...` because the action sequence cannot distinguish them "
        "(e.g. when the opponent never defects, Always Cooperate, Tit-for-Tat, "
        "Grim Trigger and Tit-for-Two-Tats make identical predictions). This is "
        "descriptive and does not claim to read the model's internal algorithm."
    )
    lines.append("")

    lines.append("## 6. Do different priors converge?")
    lines.append("")
    lines.append(_md_table(convergence))
    lines.append("")
    lines.append(
        "A small `between_group_range` in final beliefs indicates convergence "
        "across prior groups; a large range indicates that initial priors "
        "persist."
    )
    lines.append("")

    lines.append("## 7. Fixed vs random horizon")
    lines.append("")
    lines.append(_md_table(tables["horizon_comparison"]))
    lines.append("")
    lines.append("![horizon](figures/horizon_comparison.png)")
    lines.append("")

    lines.append("## 8. Uncertainty, independence and limitations")
    lines.append("")
    lines.append(
        "- Error bars are 95% confidence intervals of the mean across agents "
        "within a prior group (normal approximation to the SEM). They reflect "
        "variability among agents in this run, not sampling error over "
        "independent repetitions of the whole experiment."
    )
    lines.append(
        "- Agents are repeatedly paired and interact, so observations across "
        "agents are **not independent**. CIs and comparisons are descriptive, "
        "not formal hypothesis tests."
    )
    lines.append(
        "- This is a **single run**. Any inferential claim requires repeating the "
        "entire experiment across multiple independent seeds (and ideally "
        "multiple model families) and analysing seed-level results."
    )
    lines.append("- No statistical significance is claimed anywhere in this report.")
    lines.append("")

    lines.append("## Figures")
    lines.append("")
    for fig in [
        "cooperation_by_game.png",
        "belief_by_game.png",
        "payoff_by_game.png",
        "cumulative_payoff_by_game.png",
        "conditional_cooperation.png",
        "strategy_distribution.png",
        "final_beliefs.png",
        "horizon_comparison.png",
    ]:
        lines.append(f"- `figures/{fig}`")
    lines.append("")

    text = "\n".join(lines)
    ensure_dir(os.path.dirname(os.path.abspath(path)))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path




