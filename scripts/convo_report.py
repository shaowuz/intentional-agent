"""Charts and statistics for the conversation experiment (experiment 3) report.

PYTHONPATH=backend python scripts/convo_report.py <out dir>
Reads results/convo-{luna,terra}-main (run personality.analyze on each first).
"""

import json
import math
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from personality.analyze import PROMISE, corr
from personality.traits import ALL_TRAITS, GROUPS, TRAIT_GROUP

RUNS = {"luna": ("GPT-6 Luna", "results/convo-luna-main", "#eb6834"),
        "terra": ("GPT-6.1 Terra", "results/convo-terra-main", "#2a78d6")}
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE = "#2a78d6", "#eb6834"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10.5, "axes.titlesize": 11.5, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
    "axes.axisbelow": True,
})
ACCUSE = re.compile(r"\b(lied|liar|betray\w*|defected (on|against) me|broke (their|his|her|a) promise|backstab\w*)", re.I)
EXTRA = {"dms_sent": "Private messages sent", "dm_promise_broken": "Broke a private promise (share)",
         "accusations_made": "Public accusations made", "last_round_D": "Betrayed in the final round",
         "sleeper": "Cooperated 9 rounds, then betrayed", "public_words": "Public words per round"}


def title(fig, t, s):
    fig.text(0.02, 0.98, t, fontsize=13.5, fontweight="bold", va="top")
    fig.text(0.02, 0.93, s, fontsize=10, color=INK2, va="top")


def extra_rows(run):
    rows = []
    for p in sorted(Path(run, "episodes").glob("seed-*.json")):
        e = json.loads(p.read_text(encoding="utf-8"))
        if e.get("status") != "complete":
            continue
        act = {(q, ev["round"]): ev["actions"][ev["players"].index(q)] for ev in e["actions"] for q in ev["players"]}
        for pl in e["players"]:
            mine = [c for c in e["conversation"] if c["player"] == pl]
            dms = [c for c in mine if c["dm"]]
            prom = [c for c in dms if PROMISE.search(c["dm"])]
            seq = "".join(act[(pl, r)] for r in range(1, 11))
            rows.append({
                "seed": e["seed"], "player": pl,
                "dms_sent": len(dms),
                "dm_promise_broken": np.mean([act[(pl, c["round"])] == "D" for c in prom]) if prom else np.nan,
                "accusations_made": sum(bool(ACCUSE.search(c["public"])) for c in mine),
                "last_round_D": float(seq[-1] == "D"),
                "sleeper": float(seq == "C" * 9 + "D"),
                "public_words": np.mean([len(c["public"].split()) for c in mine]) / 1 * 2,
            })
    return pd.DataFrame(rows)


def effects(df, metrics):
    out = []
    for t in ALL_TRAITS:
        col = f"trait:{t}"
        if col not in df:
            continue
        sub = df[df[col].notna()]
        for m in metrics:
            r = corr(sub[col], sub[m])
            n = int((sub[col].notna() & sub[m].notna()).sum())
            if math.isnan(r) or n < 10:
                continue
            z = math.atanh(max(min(r, 0.999999), -0.999999)) * math.sqrt(n - 3)
            out.append({"trait": t, "group": TRAIT_GROUP[t], "metric": m, "n": n, "r": r,
                        "p": math.erfc(abs(z) / math.sqrt(2)),
                        "high": sub[sub[col] >= 8][m].mean(), "low": sub[sub[col] <= 3][m].mean()})
    eff = pd.DataFrame(out).sort_values("p").reset_index(drop=True)
    k = len(eff)
    eff["q_fdr"] = np.minimum.accumulate((eff["p"] * k / (np.arange(k) + 1))[::-1])[::-1].clip(upper=1)
    return eff


def main(out):
    out = Path(out)
    (out / "charts").mkdir(parents=True, exist_ok=True)
    data, effs = {}, {}
    for k, (_, run, _) in RUNS.items():
        a = pd.read_csv(Path(run, "analysis", "agents.csv"))
        x = extra_rows(run)
        d = a.merge(x, on=["seed", "player"])
        data[k] = d
        metrics = ["points", "coop_rate", "exploited", "exploiter", "broken_promise_rate", "revenge",
                   "forgiveness", "first_defection_round", "accused_by", "self_honesty", "trust_accuracy",
                   *EXTRA]
        effs[k] = effects(d, metrics)
        effs[k].to_csv(out / f"trait_effects_{k}.csv", index=False)
        d.to_csv(out / f"agents_{k}.csv", index=False)

    # 1. most and least successful traits, both models
    fig, axes = plt.subplots(1, 2, figsize=(13, 7.2))
    title(fig, "Which traits earned the most points in conversation games",
          "Points of agents with the trait at 8-10 minus agents at 1-3. Solid = reliable effect (FDR q < 0.05)")
    gaps = {}
    for ax, k in zip(axes, RUNS):
        p = effs[k][effs[k]["metric"] == "points"].copy()
        p["gap"] = p["high"] - p["low"]
        p = p.sort_values("gap")
        gaps[k] = p
        pick = pd.concat([p.head(8), p.tail(8)])
        bars = ax.barh(range(len(pick)), pick["gap"], height=0.6,
                       color=[BLUE if g > 0 else ORANGE for g in pick["gap"]])
        for b, q, g in zip(bars, pick["q_fdr"], pick["gap"]):
            b.set_alpha(1 if q < 0.05 else 0.35)
            ax.text(g + (0.1 if g > 0 else -0.1), b.get_y() + 0.3, f"{g:+.1f}", va="center",
                    ha="left" if g > 0 else "right", fontsize=9)
        ax.set_yticks(range(len(pick)), pick["trait"], fontsize=9.5)
        ax.axvline(0, color=INK2, lw=1)
        lim = pick["gap"].abs().max() * 1.35
        ax.set_xlim(-lim, lim)
        ax.set_title(f"{RUNS[k][0]} (avg {data[k]['points'].mean():.1f} points)", loc="left")
        ax.set_xlabel("Point difference, high vs low level")
        ax.grid(axis="y", visible=False)
    fig.subplots_adjust(top=0.86, wspace=0.55, left=0.15)
    fig.savefig(out / "charts/c1_successful_traits.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    # 2. Honesty-Humility across both models
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.9))
    title(fig, "Honesty-Humility in conversation games",
          "Mean per agent at each Honesty-Humility level")
    for ax, (m, lab, pct) in zip(axes, [("coop_rate", "Cooperation", True), ("points", "Points", False),
                                       ("last_round_D", "Betrayed in the final round", True)]):
        for k in RUNS:
            y = data[k].groupby("trait:Honesty-Humility")[m].mean().reindex(range(1, 11))
            ax.plot(y.index, y.values, color=RUNS[k][2], lw=2, marker="o", ms=4, label=RUNS[k][0])
        ax.set_title(lab, loc="left")
        ax.set_xticks(range(1, 11))
        ax.set_xlabel("Honesty-Humility level")
        if pct:
            ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    axes[0].legend(frameon=False)
    fig.subplots_adjust(top=0.78, wspace=0.28)
    fig.savefig(out / "charts/c2_honesty.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    # 3. Which traits drive the final-round betrayal (Terra)
    t = effs["terra"][effs["terra"]["metric"] == "last_round_D"].copy()
    t = t.reindex(t["r"].abs().sort_values(ascending=False).index).head(12).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 5.6))
    title(fig, "Who saves their betrayal for the last round? (Terra)",
          "Final-round betrayal rate at trait level 8-10 vs 1-3. Faded = not reliable (FDR q >= 0.05)")
    yy = np.arange(len(t))
    for i, (_, r) in enumerate(t.iterrows()):
        a = 1 if r["q_fdr"] < 0.05 else 0.35
        ax.plot([r["low"], r["high"]], [i, i], color=GRID, lw=3, zorder=1)
        ax.scatter(r["low"], i, color=BLUE, s=55, alpha=a, zorder=2)
        ax.scatter(r["high"], i, color=ORANGE, s=55, alpha=a, zorder=2)
    ax.scatter([], [], color=BLUE, label="Low level (1-3)")
    ax.scatter([], [], color=ORANGE, label="High level (8-10)")
    ax.set_yticks(yy, t["trait"])
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_xlabel("Betrayed in round 10")
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2)
    ax.grid(axis="y", visible=False)
    fig.subplots_adjust(top=0.82, left=0.3)
    fig.savefig(out / "charts/c3_final_round_traits.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    # 4. Private messages: who sends them and who lies in them (Luna and Terra)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.4))
    title(fig, "Private messages: who uses them, and who lies in them",
          "Correlation between trait level and behavior; top 10 traits by strength, reliable effects only")
    for ax, (k, m, lab) in zip(axes, [("terra", "dms_sent", "Private messages sent (Terra)"),
                                      ("luna", "dm_promise_broken", "Broke a private promise (Luna)")]):
        x = effs[k][(effs[k]["metric"] == m) & (effs[k]["q_fdr"] < 0.05)]
        x = x.reindex(x["r"].abs().sort_values(ascending=False).index).head(10).iloc[::-1]
        ax.barh(x["trait"], x["r"], color=[BLUE if v > 0 else ORANGE for v in x["r"]], height=0.6)
        for i, v in enumerate(x["r"]):
            ax.text(v + (0.01 if v > 0 else -0.01), i, f"{v:+.2f}", va="center",
                    ha="left" if v > 0 else "right", fontsize=9)
        ax.axvline(0, color=INK2, lw=1)
        ax.set_title(lab, loc="left")
        ax.set_xlabel("r (blue = more, orange = less)")
        lim = max(0.3, x["r"].abs().max() * 1.35) if len(x) else 0.3
        ax.set_xlim(-lim, lim)
        ax.grid(axis="y", visible=False)
    fig.subplots_adjust(top=0.84, wspace=0.6, left=0.17)
    fig.savefig(out / "charts/c4_private_messages.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    # 5. Trait groups that matter, both models
    fig, ax = plt.subplots(figsize=(9, 4.4))
    title(fig, "Which trait groups change behavior", "Share of traits in each group with at least one reliable effect")
    names = list(GROUPS)
    w = 0.38
    for i, k in enumerate(RUNS):
        sig = set(effs[k][effs[k]["q_fdr"] < 0.05]["trait"])
        vals = [sum(t in sig for t in GROUPS[g]) / len(GROUPS[g]) for g in names]
        ax.barh(np.arange(len(names)) + (i - 0.5) * (w + 0.02), vals, height=w, color=RUNS[k][2], label=RUNS[k][0])
    ax.set_yticks(range(len(names)), names)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_xlim(0, 1.05)
    ax.legend(frameon=False, loc="lower right")
    ax.grid(axis="y", visible=False)
    fig.subplots_adjust(top=0.84, left=0.25)
    fig.savefig(out / "charts/c5_trait_groups.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    # stats for the write-up
    for k in RUNS:
        d, e = data[k], effs[k]
        sig = e[e["q_fdr"] < 0.05]
        print(f"\n===== {k}: agents {len(d)}, tests {len(e)}, significant {len(sig)}, traits with effect {sig.trait.nunique()}")
        print(d[["points", "coop_rate", *EXTRA]].mean().round(3).to_string())
        g = gaps[k]
        print("TOP points:", [(r.trait, round(r.gap, 1), round(r.q_fdr, 3)) for r in g.tail(6).iloc[::-1].itertuples()])
        print("BOTTOM points:", [(r.trait, round(r.gap, 1), round(r.q_fdr, 3)) for r in g.head(6).itertuples()])
        for m in ["coop_rate", "last_round_D", "dms_sent", "dm_promise_broken", "accusations_made", "accused_by", "self_honesty"]:
            x = sig[sig.metric == m]
            x = x.reindex(x.r.abs().sort_values(ascending=False).index).head(5)
            print(f"  {m}:", [(r.trait, round(r.r, 2), round(r.high, 2), round(r.low, 2)) for r in x.itertuples()])
        print("  no effect:", sorted(set(ALL_TRAITS) - set(sig.trait)))


if __name__ == "__main__":
    main(sys.argv[1])
