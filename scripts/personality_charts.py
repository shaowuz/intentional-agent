"""Charts for the personality study findings page.

python scripts/personality_charts.py <run analysis dir> <output charts dir>
Reads agents.csv, control_agents.csv, trait_effects.csv written by personality.analyze.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
DIVERGING = LinearSegmentedColormap.from_list(
    "div", ["#1c5cab", "#6da7ec", "#f0efec", "#ec8a89", "#b52f2e"])

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10.5, "axes.titlesize": 11.5, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True, "font.family": "DejaVu Sans",
})


def title(fig, text, sub=None):
    fig.text(0.02, 0.98, text, ha="left", va="top", fontsize=13.5, fontweight="bold", color=INK)
    if sub:
        fig.text(0.02, 0.925, sub, ha="left", va="top", fontsize=10, color=INK2)


def bars(ax, labels, values, colors, fmt):
    b = ax.bar(labels, values, color=colors, width=0.55)
    for rect, v in zip(b, values):
        ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height(), fmt(v),
                ha="center", va="bottom", fontsize=10.5, color=INK, fontweight="bold")
    ax.grid(axis="x", visible=False)


def by_level(df, trait, metric):
    col = f"trait:{trait}"
    return df.groupby(col)[metric].mean().reindex(range(1, 11))


def save(fig, out, name):
    fig.savefig(out / name, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main(src, out):
    src, out = Path(src), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    d = pd.read_csv(src / "agents.csv")
    c = pd.read_csv(src / "control_agents.csv")
    eff = pd.read_csv(src / "trait_effects.csv")

    # 1. Headline: personality vs control
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.6))
    title(fig, "Same model, same goal: personality changes the swarm",
          "Neutral control (240 agents) vs agents with 18 random traits (3,000 agents)")
    for ax, (m, lab, f) in zip(axes, [("coop_rate", "Cooperation rate", lambda v: f"{v:.0%}"),
                                     ("points", "Points per agent", lambda v: f"{v:.1f}"),
                                     ("trust_accuracy", "Trust accuracy (r)", lambda v: f"{v:.2f}")]):
        bars(ax, ["No personality", "Personality"], [c[m].mean(), d[m].mean()], [MUTED, BLUE], f)
        ax.set_title(lab, loc="left")
        ax.set_ylim(0, max(c[m].mean(), d[m].mean()) * 1.25)
        if m == "coop_rate":
            ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    fig.subplots_adjust(top=0.78, wspace=0.35)
    save(fig, out, "1_headline.png")

    # 2. Honesty-Humility trade-off, small multiples
    lv = np.arange(1, 11)
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.4))
    title(fig, "Honesty-Humility: cooperative and truthful, but exploited",
          "Mean per agent at each trait level (n = 3,000 agents, ~300 per level)")
    for ax, (m, lab, pct) in zip(axes.flat, [
            ("coop_rate", "Cooperation rate", True),
            ("broken_promise_rate", "Broke a promise to cooperate", True),
            ("exploited", "Times betrayed while cooperating", False),
            ("points", "Points earned", False)]):
        y = by_level(d, "Honesty-Humility", m)
        color = ORANGE if m == "points" else BLUE
        ax.plot(lv, y.values, color=color, lw=2, marker="o", ms=5)
        ax.set_title(lab, loc="left")
        ax.set_xticks(lv)
        ax.set_xlabel("Honesty-Humility level")
        if pct:
            ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
        for x in (1, 10):
            v = y.loc[x]
            ax.annotate(f"{v:.0%}" if pct else f"{v:.1f}", (x, v), textcoords="offset points",
                        xytext=(0, 8), ha="center", fontsize=9.5, color=INK)
        ax.margins(y=0.2)
    fig.subplots_adjust(top=0.86, hspace=0.55, wspace=0.25)
    save(fig, out, "2_honesty_tradeoff.png")

    # 3. Individual vs group: the social dilemma
    g = d.groupby("seed").agg(hh=("trait:Honesty-Humility", "mean"), pts=("points", "sum"))
    g["q"] = pd.qcut(g["hh"], 4, labels=["Least honest\n25% of games", "2nd", "3rd",
                                         "Most honest\n25% of games"])
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9))
    title(fig, "Dishonesty pays the individual, honesty pays the group",
          "Left: each agent's points by its own level. Right: total points of all 10 agents, "
          "games grouped by average Honesty-Humility")
    y = by_level(d, "Honesty-Humility", "points")
    axes[0].plot(lv, y.values, color=ORANGE, lw=2, marker="o", ms=5)
    axes[0].set_xticks(lv)
    axes[0].set_xlabel("Agent's own Honesty-Humility level")
    axes[0].set_title("Individual points", loc="left")
    gq = g.groupby("q", observed=True)["pts"].mean()
    bars(axes[1], list(gq.index), gq.values, [BLUE] * 4, lambda v: f"{v:.0f}")
    axes[1].set_ylim(0, 215)
    axes[1].set_title("Group total points per game", loc="left")
    fig.subplots_adjust(top=0.76, wspace=0.3)
    save(fig, out, "3_individual_vs_group.png")

    # 4. Honest agents vs number of dishonest agents in the game
    d["n_low"] = d["seed"].map(d.assign(low=d["trait:Honesty-Humility"] <= 3).groupby("seed")["low"].sum())
    hi = d[d["trait:Honesty-Humility"] >= 8].copy()
    hi["bucket"] = np.minimum(hi["n_low"], 5)
    s = hi.groupby("bucket")["points"].agg(["mean", "count"])
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    title(fig, "Each dishonest agent in the swarm costs the honest ones",
          "Points of honest agents (Honesty-Humility 8-10) by number of dishonest agents (1-3) in the same game")
    labels = [f"{int(k)}{'+' if k == 5 else ''}\n(n={int(n)})" for k, n in zip(s.index, s["count"])]
    bars(ax, labels, s["mean"].values, [BLUE] * len(s), lambda v: f"{v:.1f}")
    ax.set_xlabel("Dishonest agents in the game")
    ax.set_ylabel("Honest agent's points")
    ax.set_ylim(0, s["mean"].max() * 1.2)
    fig.subplots_adjust(top=0.8)
    save(fig, out, "4_dishonest_neighbors.png")

    # 5. Heatmap of trait effects
    metrics = {"coop_rate": "Cooperate", "points": "Points", "exploited": "Gets exploited",
               "exploiter": "Exploits others", "broken_promise_rate": "Breaks promises",
               "revenge": "Revenge", "accused_by": "Accused by others", "self_honesty": "Self-rated honesty"}
    sig = eff[eff["q_fdr"] < 0.05]
    top = (sig[sig["metric"].isin(metrics)].groupby("trait")["r"].apply(lambda r: r.abs().max())
           .sort_values(ascending=False).head(18).index)
    grid = eff[eff["metric"].isin(metrics) & eff["trait"].isin(top)].copy()
    grid.loc[grid["q_fdr"] >= 0.05, "r"] = np.nan
    mat = grid.pivot(index="trait", columns="metric", values="r").reindex(index=top, columns=list(metrics))
    fig, ax = plt.subplots(figsize=(10, 7.4))
    title(fig, "Which traits move which behaviors",
          "Correlation between trait level and behavior; blank = no reliable effect (FDR q >= 0.05). "
          "Top 18 traits.")
    ax.grid(False)
    im = ax.imshow(mat.values, cmap=DIVERGING, vmin=-0.6, vmax=0.6, aspect="auto")
    ax.set_xticks(range(len(metrics)), list(metrics.values()), rotation=30, ha="right")
    ax.set_yticks(range(len(top)), list(top))
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:+.2f}", ha="center", va="center", fontsize=8.5,
                        color="white" if abs(v) > 0.38 else INK)
    for s_ in ax.spines.values():
        s_.set_visible(False)
    cb = fig.colorbar(im, ax=ax, shrink=0.6, pad=0.02)
    cb.set_label("r  (blue = less, red = more)")
    cb.outline.set_visible(False)
    fig.subplots_adjust(top=0.9)
    save(fig, out, "5_trait_heatmap.png")

    # 6. Which trait groups matter
    from personality.traits import GROUPS
    rows = []
    for gname, members in GROUPS.items():
        hit = sum(t in set(sig["trait"]) for t in members)
        rows.append((gname, hit / len(members), hit, len(members)))
    rows.sort(key=lambda r: r[1])
    fig, ax = plt.subplots(figsize=(8.5, 4))
    title(fig, "Values move behavior; thinking style barely does",
          "Share of traits in each group with at least one reliable effect (FDR q < 0.05)")
    yb = ax.barh([r[0] for r in rows], [r[1] for r in rows], color=BLUE, height=0.55)
    for rect, r in zip(yb, rows):
        ax.text(rect.get_width() + 0.01, rect.get_y() + rect.get_height() / 2, f"{r[2]}/{r[3]}",
                va="center", fontsize=10, color=INK)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_xlim(0, 1.12)
    ax.grid(axis="y", visible=False)
    fig.subplots_adjust(top=0.82, left=0.25)
    save(fig, out, "6_trait_groups.png")

    # 7. Private self-report as a deception signal
    x = d.dropna(subset=["broken_promise_rate"]).copy()
    x["breaker"] = x["broken_promise_rate"] >= 0.5
    pos, neg = -x.loc[x["breaker"], "self_honesty"].values, -x.loc[~x["breaker"], "self_honesty"].values
    auc = ((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())
    dist = x.groupby(["breaker", "self_honesty"]).size().unstack(0).fillna(0)
    dist = dist / dist.sum()
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    title(fig, f"Agents admit it privately: self-rated honesty flags promise-breakers (AUC {auc:.2f})",
          f"Final private self-rating among agents that made promises (n = {len(x)}); "
          "breaker = broke at least half its promises")
    w = 0.38
    ax.bar(dist.index - w / 2 - 0.02, dist.get(False, 0), width=w, color=BLUE, label="Kept most promises")
    ax.bar(dist.index + w / 2 + 0.02, dist.get(True, 0), width=w, color=ORANGE, label="Broke most promises")
    ax.set_xticks(range(1, 11))
    ax.set_xlabel("Self-rated honesty (1-10)")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.legend(frameon=False, loc="upper center")
    ax.grid(axis="x", visible=False)
    fig.subplots_adjust(top=0.8)
    save(fig, out, "7_self_report_detector.png")

    # 9. Most and least successful traits (points)
    p = eff[eff["metric"] == "points"].copy()
    p["gap"] = p["mean_high_8_10"] - p["mean_low_1_3"]
    p = p.sort_values("gap")
    pick = pd.concat([p.head(10), p.tail(10)])
    fig, ax = plt.subplots(figsize=(9.5, 7.2))
    title(fig, "Most and least successful traits",
          "Points of agents with the trait at 8-10 minus agents at 1-3. "
          "Solid = reliable effect (FDR q < 0.05); faded = not reliable")
    colors = [(BLUE if g > 0 else ORANGE) for g in pick["gap"]]
    alphas = [1.0 if q < 0.05 else 0.35 for q in pick["q_fdr"]]
    yb = ax.barh(range(len(pick)), pick["gap"], color=colors, height=0.6)
    for rect, a, g in zip(yb, alphas, pick["gap"]):
        rect.set_alpha(a)
        ax.text(g + (0.12 if g > 0 else -0.12), rect.get_y() + rect.get_height() / 2,
                f"{g:+.1f}", va="center", ha="left" if g > 0 else "right", fontsize=9.5, color=INK)
    ax.set_yticks(range(len(pick)), pick["trait"])
    ax.axvline(0, color=INK2, lw=1)
    ax.set_xlabel("Point difference, high vs low level (average agent earns 17.2)")
    lim = pick["gap"].abs().max() * 1.25
    ax.set_xlim(-lim, lim)
    ax.grid(axis="y", visible=False)
    fig.subplots_adjust(top=0.88, left=0.3)
    save(fig, out, "9_successful_traits.png")
    p.to_csv(out / "trait_points_gap.csv", index=False)

    # 8. Manipulation check
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    y = by_level(d, "Talkativeness", "message_chars")
    title(fig, "Manipulation check: agents follow their assigned traits",
          "Average public message length by Talkativeness level (r = 0.94)")
    bars(ax, [str(i) for i in lv], y.values, [BLUE] * 10, lambda v: f"{v:.0f}")
    ax.set_xlabel("Talkativeness level")
    ax.set_ylabel("Characters")
    ax.set_ylim(0, y.max() * 1.18)
    fig.subplots_adjust(top=0.8)
    save(fig, out, "8_talkativeness_check.png")
    print("auc", round(auc, 3))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
