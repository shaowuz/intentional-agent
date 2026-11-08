"""Dot-strip chart of payoffs by condition across the personality experiments.

PYTHONPATH=backend python scripts/payoff_strip.py <out png>
One dot = one game (mean payoff per encounter of the agents in that row); bar = mean of games.
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SURFACE, INK, INK2, GRID, BAR = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#1f2a37"
PANEL_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]
SEEDS = set(range(100))


def games(path, seeds=SEEDS):
    for p in sorted(Path(path).glob("seed-*.json")):
        e = json.loads(p.read_text(encoding="utf-8"))
        if e.get("status") == "complete" and e["seed"] in seeds:
            yield e


def per_game(path, select=lambda traits: True, seeds=SEEDS):
    vals = []
    for e in games(path, seeds):
        pts = [e["points"][p] / e["settings"]["rounds"] for p in e["players"] if select(e["personalities"][p])]
        if pts:
            vals.append(float(np.mean(pts)))
    return vals


def evolution(arm, gen=3):
    vals = []
    for g in sorted(Path("results/evolution").glob(f"{arm}-rep*/gen-{gen:02d}/game-*.json")):
        e = json.loads(g.read_text(encoding="utf-8"))
        if e.get("status") == "complete":
            vals.append(float(np.mean([v / 10 for v in e["points"].values()])))
    return vals


def main(out):
    low = lambda t: t.get("Honesty-Humility", 5) <= 3
    high = lambda t: t.get("Honesty-Humility", 5) >= 8
    conds = [("Luna, short messages", "results/personality-main/episodes"),
             ("Luna, conversations", "results/convo-luna-main/episodes"),
             ("Terra, conversations", "results/convo-terra-main/episodes")]
    panels = [
        ("Whole swarm", [
            ("No personality (Luna)", per_game("results/personality-neutral/episodes", seeds=set(range(24)))),
            *[(n, per_game(p)) for n, p in conds]]),
        ("Dishonest vs honest agents", [
            (f"{n} · {lab}", per_game(p, sel)) for n, p in conds
            for lab, sel in (("low honesty (1-3)", low), ("high honesty (8-10)", high))]),
        ("Evolution, generation 4", [
            ("No oversight", evolution("none")),
            ("Monitor reads public chat", evolution("public")),
            ("Monitor reads private reasoning", evolution("private"))]),
    ]
    rows = sum(len(p[1]) for p in panels)
    fig, axes = plt.subplots(len(panels), 1, figsize=(11, 0.62 * rows + 2.6), sharex=True,
                             gridspec_kw={"height_ratios": [len(p[1]) for p in panels], "hspace": 0.12})
    fig.patch.set_facecolor(SURFACE)
    fig.text(0.5, 0.995, "Personality in agent swarms — payoffs by condition", ha="center", va="top",
             fontsize=15, color=INK)
    fig.text(0.5, 0.968, "Matched games (seeds 0–99; control 0–23) · 10 agents, 10 rounds · "
             "dashed line = 3.0, everyone cooperates; 1.0 = everyone betrays; one agent can earn up to 5 by betraying cooperators",
             ha="center", va="top", fontsize=10, color=INK2)
    rng = np.random.default_rng(0)
    allv = [v for _, items in panels for _, vals in items for v in vals]
    lo, hi = np.floor(min(allv) * 5) / 5 - 0.05, np.ceil(max(allv) * 5) / 5 + 0.05
    summary = []
    for ax, (pname, items), color in zip(axes, panels, PANEL_COLORS):
        ax.set_facecolor(SURFACE)
        for i, (label, vals) in enumerate(items):
            y = len(items) - 1 - i
            if not vals:
                continue
            ax.scatter(vals, y + rng.uniform(-0.18, 0.18, len(vals)), s=16, color=color, alpha=0.45,
                       edgecolor="white", linewidth=0.4, zorder=2)
            m = float(np.mean(vals))
            ax.plot([m, m], [y - 0.32, y + 0.32], color=BAR, lw=3.2, zorder=3)
            ax.text(1.015, y, f"{m:.2f}", va="center", fontsize=10.5, color=INK, fontweight="bold",
                    transform=ax.get_yaxis_transform())
            summary.append((pname, label, round(m, 2), len(vals)))
        ax.set_yticks(range(len(items)), [l for l, _ in items][::-1], fontsize=10.5)
        ax.set_ylim(-0.6, len(items) - 0.4)
        ax.set_xlim(lo, hi)
        ax.grid(axis="x", color=GRID)
        ax.grid(axis="y", visible=False)
        ax.set_axisbelow(True)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
        ax.tick_params(colors=INK2, length=0)
        ax.text(-0.01, 1.0, pname, transform=ax.transAxes, ha="right", va="bottom", fontsize=11,
                fontweight="bold", color=INK)
    axes[-1].set_xticks(np.arange(np.ceil(lo * 5) / 5, hi, 0.2))
    for ax in axes:
        ax.axvline(3.0, color=INK2, lw=0.8, ls="--", zorder=1)
    axes[-1].set_xlabel("Average payoff per encounter", fontsize=11.5, color=INK)
    h1 = plt.Line2D([], [], marker="o", ls="", color="#8a8984", label="One game")
    h2 = plt.Line2D([], [], marker="|", ls="", color=BAR, markersize=16, mew=3, label="Mean of games")
    fig.legend(handles=[h1, h2], loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.0))
    fig.text(0.5, -0.02, "Right-hand numbers are means. One dot = mean payoff of the agents in that row in one game. Vertical jitter only; every game retained.",
             ha="center", fontsize=9, color=INK2)
    fig.subplots_adjust(left=0.36, right=0.92, top=0.93, bottom=0.08)
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor=SURFACE)
    for row in summary:
        print(row)


if __name__ == "__main__":
    main(sys.argv[1])
