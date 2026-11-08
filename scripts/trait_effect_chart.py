"""Chart: effect of three personality traits on payoff, low (1-3) vs high (8-10), in each setting.

PYTHONPATH=backend python scripts/trait_effect_chart.py <comparison_agents.csv> <out png>
Dark traits = the mean level of an agent's two dark traits (every agent has two of:
Machiavellianism, Narcissism, Psychopathy, Sadism, Spitefulness, Dark personality (combined)).
"""

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
LOW, HIGH = "#eb6834", "#2a78d6"
CONDS = [("exp1", "Luna, short messages"), ("luna", "Luna, conversations"), ("terra", "Terra, conversations")]
DARK = ["Machiavellianism", "Narcissism", "Psychopathy", "Sadism", "Spitefulness", "Dark personality (combined)"]
ROWS = [("Cognitive reflection", "trait:Cognitive reflection"),
        ("Dark traits (combined)", "dark"),
        ("Honesty-Humility", "trait:Honesty-Humility")]


def stats(x):
    x = x.dropna()
    return x.mean(), 1.96 * x.std(ddof=1) / np.sqrt(len(x)), len(x)


def main(src, out):
    d = pd.read_csv(src)
    d["ppe"] = d["points"] / 10
    d["dark"] = d[[f"trait:{t}" for t in DARK]].mean(axis=1)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2), sharey=True)
    fig.patch.set_facecolor(SURFACE)
    fig.text(0.5, 1.0, "How personality changes an agent's payoff", ha="center", va="top", fontsize=15, color=INK)
    fig.text(0.5, 0.925, "Average payoff per encounter: low level (1-3) vs high level (8-10). Lines = 95% confidence "
             "intervals. Same 98 games and personalities in every panel.", ha="center", va="top", fontsize=10, color=INK2)
    y = np.arange(len(ROWS))[::-1]
    for ax, (k, name) in zip(axes, CONDS):
        x = d[d["cond"] == k]
        ax.set_facecolor(SURFACE)
        ax.axvline(x["ppe"].mean(), color=INK2, lw=0.9, ls="--", zorder=1)
        for yi, (label, col) in zip(y, ROWS):
            lo_m, lo_ci, _ = stats(x[x[col] <= 3]["ppe"])
            hi_m, hi_ci, _ = stats(x[x[col] >= 8]["ppe"])
            ax.plot([lo_m, hi_m], [yi, yi], color=GRID, lw=5, zorder=1, solid_capstyle="round")
            ax.errorbar(lo_m, yi + 0.1, xerr=lo_ci, fmt="o", color=LOW, ms=9, elinewidth=1.5, capsize=0, zorder=3)
            ax.errorbar(hi_m, yi - 0.1, xerr=hi_ci, fmt="o", color=HIGH, ms=9, elinewidth=1.5, capsize=0, zorder=3)
        ax.set_title(name, fontsize=12, fontweight="bold", color=INK, loc="left")
        ax.grid(axis="x", color=GRID)
        ax.grid(axis="y", visible=False)
        ax.set_axisbelow(True)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
        ax.tick_params(colors=INK2, length=0)
        ax.set_xlabel("Average payoff per encounter", color=INK)
        ax.set_ylim(-0.6, len(ROWS) - 0.4)
        ax.set_xlim(*((2.6, 3.05) if k == "terra" else (1.2, 2.25)))
    axes[0].set_yticks(y, [r[0] for r in ROWS], fontsize=11.5)
    handles = [plt.Line2D([], [], marker="o", ls="", color=LOW, ms=9, label="Low level (1-3)"),
               plt.Line2D([], [], marker="o", ls="", color=HIGH, ms=9, label="High level (8-10)"),
               plt.Line2D([], [], ls="--", color=INK2, label="Average of all agents")]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.55, -0.06))
    fig.text(0.5, -0.1, "Blue right of orange = a high level earns more. Dark traits = average of each agent's two dark "
             "traits. The Terra panel uses a narrower x-axis because nearly everyone cooperates.",
             ha="center", fontsize=9, color=INK2)
    fig.subplots_adjust(left=0.13, right=0.98, top=0.8, bottom=0.17, wspace=0.08)
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor=SURFACE)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
