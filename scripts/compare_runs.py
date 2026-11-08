"""Compare experiment 1 (short single messages, Luna) with the open-conversation reruns.

PYTHONPATH=backend python scripts/compare_runs.py <charts dir>
Uses matched seeds: the same personalities appear in every condition.
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from personality.analyze import PROMISE, agent_rows, corr

CONDITIONS = {
    "exp1": ("Luna, short messages", "results/personality-main", "#8a8984"),
    "luna": ("Luna, conversations", "results/convo-luna-main", "#eb6834"),
    "terra": ("Terra, conversations", "results/convo-terra-main", "#2a78d6"),
}
TRAITS = ["Honesty-Humility", "Selfishness", "Machiavellianism", "Dark personality (combined)", "Altruism",
          "Fairness morality", "Conformity", "Gullibility", "Epistemic vigilance", "Trust", "Talkativeness",
          "Cognitive reflection"]
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10.5, "axes.titlesize": 11.5, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
    "axes.axisbelow": True,
})


def load(path, seeds):
    eps = []
    for p in sorted(Path(path, "episodes").glob("seed-*.json")):
        e = json.loads(p.read_text(encoding="utf-8"))
        if e.get("status") == "complete" and e["seed"] in seeds:
            eps.append(e)
    return eps


def title(fig, t, s):
    fig.text(0.02, 0.98, t, fontsize=13.5, fontweight="bold", va="top")
    fig.text(0.02, 0.925, s, fontsize=10, color=INK2, va="top")


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    seeds = set(range(100))
    eps = {k: load(v[1], seeds) for k, v in CONDITIONS.items()}
    common = set.intersection(*[{e["seed"] for e in v} for v in eps.values()])
    eps = {k: [e for e in v if e["seed"] in common] for k, v in eps.items()}
    print("matched games:", len(common))

    agents, rounds_, dms = [], [], []
    for k, lst in eps.items():
        for e in lst:
            rows, acts, msgs = agent_rows(e)
            for r in rows:
                r["cond"] = k
            agents += rows
            for p in e["players"]:
                for t, a in enumerate(acts[p]):
                    rounds_.append({"cond": k, "round": t + 1, "coop": a == "C"})
            act = {(p, ev["round"]): ev["actions"][ev["players"].index(p)] for ev in e["actions"] for p in ev["players"]}
            for c in e.get("conversation", []):
                if c["dm"]:
                    dms.append({"cond": k, "promise": bool(PROMISE.search(c["dm"])),
                                "action": act[(c["player"], c["round"])]})
    d = pd.DataFrame(agents)
    d.to_csv(out / "comparison_agents.csv", index=False)
    g = d.groupby(["cond", "seed"])["points"].sum().groupby("cond").mean()
    summary = d.groupby("cond").agg(coop=("coop_rate", "mean"), points=("points", "mean"),
                                    broken=("broken_promise_rate", "mean"), trust_acc=("trust_accuracy", "mean"),
                                    false_acc=("false_accusations", "mean"), chars=("message_chars", "mean"))
    summary["group_points"] = g
    if dms:
        dm = pd.DataFrame(dms)
        summary["dms_per_agent_round"] = dm.groupby("cond").size() / (len(common) * 100)
        pk = dm[dm["promise"]]
        summary["dm_promise_kept"] = pk.groupby("cond")["action"].apply(lambda s: (s == "C").mean())
    summary = summary.reindex(list(CONDITIONS))
    summary.to_csv(out / "comparison_summary.csv")
    print(summary.round(3).to_string())

    # effects of key traits per condition
    eff = []
    for k in CONDITIONS:
        x = d[d["cond"] == k]
        for t in TRAITS:
            col = f"trait:{t}"
            if col in x:
                sub = x[x[col].notna()]
                for m in ("coop_rate", "points"):
                    eff.append({"cond": k, "trait": t, "metric": m, "r": corr(sub[col], sub[m]), "n": len(sub)})
    eff = pd.DataFrame(eff)
    eff.to_csv(out / "comparison_trait_effects.csv", index=False)

    # paired: same personality, same seed and player
    piv = d.pivot_table(index=["seed", "player"], columns="cond", values="coop_rate")
    print("paired coop correlation exp1-terra:", round(piv["exp1"].corr(piv["terra"]), 3),
          " exp1-luna:", round(piv["exp1"].corr(piv["luna"]), 3), " luna-terra:", round(piv["luna"].corr(piv["terra"]), 3))

    # chart 12: headline
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8))
    title(fig, "Talking more and a smarter model change the swarm",
          f"Same {len(common)} games and personalities in every condition ({len(common) * 10} agents each)")
    for ax, (m, lab, f) in zip(axes, [("coop", "Cooperation rate", "{:.0%}"), ("points", "Points per agent", "{:.1f}"),
                                      ("broken", "Broke a promise to cooperate", "{:.0%}")]):
        vals = summary[m].values
        b = ax.bar([CONDITIONS[k][0].replace(", ", "\n") for k in CONDITIONS], vals,
                   color=[CONDITIONS[k][2] for k in CONDITIONS], width=0.6)
        for rect, v in zip(b, vals):
            ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height(), f.format(v), ha="center", va="bottom",
                    fontweight="bold")
        ax.set_title(lab, loc="left")
        ax.set_ylim(0, np.nanmax(vals) * 1.25)
        ax.grid(axis="x", visible=False)
        ax.tick_params(axis="x", labelsize=9)
        if "%" in f:
            ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    fig.subplots_adjust(top=0.78, wspace=0.3)
    fig.savefig(out / "12_conversation_headline.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    # chart 13: cooperation by round
    r = pd.DataFrame(rounds_).groupby(["cond", "round"])["coop"].mean().unstack(0)
    fig, ax = plt.subplots(figsize=(9, 4))
    title(fig, "Does conversation stop the collapse?", "Cooperation rate in each round")
    for k in CONDITIONS:
        ax.plot(r.index, r[k], color=CONDITIONS[k][2], lw=2.2, marker="o", ms=4, label=CONDITIONS[k][0])
    ax.set_xticks(range(1, 11))
    ax.set_xlabel("Round")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=False, loc="lower left")
    fig.subplots_adjust(top=0.82)
    fig.savefig(out / "13_conversation_rounds.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    # chart 14: trait effects on points across conditions
    e = eff[eff["metric"] == "points"].pivot(index="trait", columns="cond", values="r").reindex(TRAITS)
    fig, ax = plt.subplots(figsize=(9.5, 6))
    title(fig, "Do the same traits still win?",
          "Correlation between trait level and points earned, per condition (right = trait earns more)")
    y = np.arange(len(TRAITS))
    for i, k in enumerate(CONDITIONS):
        ax.scatter(e[k], y + (i - 1) * 0.22, color=CONDITIONS[k][2], s=46, label=CONDITIONS[k][0], zorder=3)
    ax.axvline(0, color=INK2, lw=1)
    ax.set_yticks(y, TRAITS)
    ax.invert_yaxis()
    ax.set_xlabel("r (trait level vs points)")
    ax.legend(frameon=False, loc="lower right", fontsize=9)
    ax.grid(axis="y", visible=False)
    fig.subplots_adjust(top=0.86, left=0.27)
    fig.savefig(out / "14_conversation_trait_effects.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    # chart 15: Honesty-Humility gradient per condition
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.9))
    title(fig, "Is honesty still punished?", "Mean per agent at each Honesty-Humility level")
    for ax, (m, lab) in zip(axes, [("coop_rate", "Cooperation rate"), ("points", "Points earned")]):
        for k in CONDITIONS:
            x = d[d["cond"] == k].groupby("trait:Honesty-Humility")[m].mean().reindex(range(1, 11))
            ax.plot(x.index, x.values, color=CONDITIONS[k][2], lw=2, marker="o", ms=4, label=CONDITIONS[k][0])
        ax.set_title(lab, loc="left")
        ax.set_xticks(range(1, 11))
        ax.set_xlabel("Honesty-Humility level")
        if m == "coop_rate":
            ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    axes[0].legend(frameon=False, fontsize=9)
    fig.subplots_adjust(top=0.78, wspace=0.25)
    fig.savefig(out / "15_conversation_honesty.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(e.round(2).to_string())

    # chart 16: the sleeper effect - when do low-honesty agents betray?
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.9), sharey=True)
    title(fig, "The smarter model hides its dark agents until the last round",
          "Defection rate in each round: low Honesty-Humility agents (1-3) vs everyone else")
    stats = {}
    for ax, k in zip(axes, ["exp1", "terra"]):
        rows = []
        for e in eps[k]:
            for p, t in e["personalities"].items():
                low = t.get("Honesty-Humility", 10) <= 3
                for x in e["trust"]:
                    if x["player"] == p:
                        rows.append({"round": x["round"], "low": low, "D": x["action"] == "D"})
        r = pd.DataFrame(rows).groupby(["low", "round"])["D"].mean().unstack(0)
        ax.plot(r.index, r[True], color="#eb6834", lw=2.2, marker="o", ms=4, label="Low honesty (1-3)")
        ax.plot(r.index, r[False], color="#2a78d6", lw=2.2, marker="o", ms=4, label="Everyone else")
        ax.set_title(CONDITIONS[k][0], loc="left")
        ax.set_xticks(range(1, 11))
        ax.set_xlabel("Round")
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
        ax.set_ylim(0, 1.05)
        stats[k] = (r[True].iloc[:9].mean(), r[True].iloc[9], r[False].iloc[:9].mean(), r[False].iloc[9])
    axes[1].legend(frameon=False, loc="upper left")
    fig.subplots_adjust(top=0.78, wspace=0.08)
    fig.savefig(out / "16_sleeper_effect.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("sleeper (low-HH rounds1-9, low-HH round10, others rounds1-9, others round10):",
          {k: tuple(round(v, 2) for v in s) for k, s in stats.items()})


if __name__ == "__main__":
    main(sys.argv[1])
