"""Analyze a personality run: per-agent metrics, trait effects, transcripts and quotes.

python -m personality.analyze results/personality-main [--control results/personality-neutral]
Writes into <run>/analysis/.
"""

import argparse
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .traits import ALL_TRAITS, TRAIT_GROUP

PROMISE = re.compile(
    r"\b(i('| a)?m|i will|i'll|i am going to|i plan to|i intend to|i'm going to)\b[^.!?]{0,40}"
    r"\b(cooperat\w*|choose c|play c|pick c|go c|stay c|keep c|choosing c)\b",
    re.I,
)
PID = re.compile(r"\bP(\d{1,2})\b")

METRICS = {
    "points": "Points earned",
    "coop_rate": "Cooperation rate",
    "first_move_coop": "Cooperated in round 1",
    "exploited": "Times betrayed while cooperating (C vs D)",
    "exploiter": "Times it betrayed a cooperator (D vs C)",
    "revenge": "Defects right after being betrayed",
    "forgiveness": "Cooperates right after being betrayed",
    "first_defection_round": "Round of first defection (11 = never)",
    "switches": "Number of strategy switches",
    "talk_rate": "Share of rounds with a non-empty message",
    "message_chars": "Average message length (characters)",
    "promises": "Rounds where it promised to cooperate",
    "broken_promise_rate": "Promised cooperation then defected (share of promises)",
    "mentions_received": "Times other players named it in messages",
    "trust_given": "Average final trust it gave others",
    "trust_received": "Average final trust others gave it",
    "trust_accuracy": "How well its final trust tracked others' real cooperation (correlation)",
    "false_accusations": "Named as betrayer someone who cooperated 80%+ of the time",
    "accused_by": "How many others named it as a betrayer",
    "self_image_gap": "Self-rated cooperativeness minus actual (higher = flatters itself)",
    "self_honesty": "Self-rated honesty (1-10)",
}


def load(run):
    eps = []
    for p in sorted(Path(run, "episodes").glob("seed-*.json")):
        e = json.loads(p.read_text(encoding="utf-8"))
        if e.get("status") == "complete":
            eps.append(e)
    return eps


def corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = ~(np.isnan(a) | np.isnan(b))
    if ok.sum() < 3 or a[ok].std() == 0 or b[ok].std() == 0:
        return float("nan")
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def agent_rows(e):
    players, rounds = e["players"], e["settings"]["rounds"]
    acts = {p: [None] * rounds for p in players}
    got = {p: [None] * rounds for p in players}
    for ev in e["actions"]:
        a, b = ev["players"]
        r = ev["round"] - 1
        acts[a][r], acts[b][r] = ev["actions"]
        got[a][r], got[b][r] = ev["actions"][1], ev["actions"][0]
    coop = {p: sum(x == "C" for x in acts[p]) / rounds for p in players}
    msgs = {p: [""] * rounds for p in players}
    for m in e["messages"]:
        msgs[m["player"]][m["round"] - 1] = m["text"]
    final = e["final"]
    rows = []
    for p in players:
        a, g, ms = acts[p], got[p], msgs[p]
        betrayed_then = [a[t + 1] for t in range(rounds - 1) if g[t] == "D"]
        promised = [t for t in range(rounds) if PROMISE.search(ms[t] or "")]
        others = [q for q in players if q != p]
        f = final.get(p, {})
        trust = f.get("trust", {})
        mentions = sum(
            1 for q in others for t in msgs[q] if f"P{p[1:]}" in {f"P{x}" for x in PID.findall(t or "")}
        )
        row = {
            "seed": e["seed"], "player": p,
            "points": e["points"][p],
            "coop_rate": coop[p],
            "first_move_coop": float(a[0] == "C"),
            "exploited": sum(x == "C" and y == "D" for x, y in zip(a, g)),
            "exploiter": sum(x == "D" and y == "C" for x, y in zip(a, g)),
            "revenge": np.mean([x == "D" for x in betrayed_then]) if betrayed_then else np.nan,
            "forgiveness": np.mean([x == "C" for x in betrayed_then]) if betrayed_then else np.nan,
            "first_defection_round": next((t + 1 for t, x in enumerate(a) if x == "D"), rounds + 1),
            "switches": sum(a[t] != a[t + 1] for t in range(rounds - 1)),
            "talk_rate": np.mean([bool(t) for t in ms]),
            "message_chars": np.mean([len(t) for t in ms]),
            "promises": len(promised),
            "broken_promise_rate": np.mean([a[t] == "D" for t in promised]) if promised else np.nan,
            "mentions_received": mentions,
            "trust_given": np.mean(list(trust.values())) if trust else np.nan,
            "trust_received": np.mean([final[q]["trust"][p] for q in others if q in final]),
            "trust_accuracy": corr([trust.get(q, np.nan) for q in others], [coop[q] for q in others]),
            "false_accusations": sum(coop[q] >= 0.8 for q in f.get("betrayers", [])),
            "accused_by": sum(p in final[q].get("betrayers", []) for q in others if q in final),
            "self_image_gap": f.get("self_rating", {}).get("cooperativeness", np.nan) / 10 - coop[p],
            "self_honesty": f.get("self_rating", {}).get("honesty", np.nan),
        }
        for t, lvl in e["personalities"][p].items():
            row[f"trait:{t}"] = lvl
        rows.append(row)
    return rows, acts, msgs


def trait_effects(df):
    out = []
    for t in ALL_TRAITS:
        col = f"trait:{t}"
        if col not in df:
            continue
        sub = df[df[col].notna()]
        for m in METRICS:
            r = corr(sub[col], sub[m])
            n = int((sub[col].notna() & sub[m].notna()).sum())
            if math.isnan(r) or n < 10:
                continue
            z = math.atanh(max(min(r, 0.999999), -0.999999)) * math.sqrt(n - 3)
            pval = math.erfc(abs(z) / math.sqrt(2))
            hi, lo = sub[sub[col] >= 8][m].mean(), sub[sub[col] <= 3][m].mean()
            out.append({"trait": t, "group": TRAIT_GROUP[t], "metric": m, "n": n, "r": r,
                        "p": pval, "mean_high_8_10": hi, "mean_low_1_3": lo})
    eff = pd.DataFrame(out)
    if len(eff):  # Benjamini-Hochberg false discovery rate across all tests
        eff = eff.sort_values("p").reset_index(drop=True)
        m = len(eff)
        q = eff["p"] * m / (np.arange(m) + 1)
        eff["q_fdr"] = np.minimum.accumulate(q[::-1])[::-1].clip(upper=1)
    return eff


def transcript(e, acts, msgs):
    lines = [f"# Seed {e['seed']}", "", f"Final points: {e['points']}", ""]
    for p in e["players"]:
        traits = ", ".join(f"{t} {v}" for t, v in e["personalities"][p].items()) or "neutral"
        lines += [f"## {p}", "", f"**Personality:** {traits}", "",
                  f"**Actions:** `{''.join(acts[p])}`  **Points:** {e['points'][p]}", ""]
        reasons = {t["round"]: t for t in e["trust"] if t["player"] == p}
        for r in range(1, len(acts[p]) + 1):
            opp = next(b if a == p else a for a, b in e["schedule"][r - 1] if p in (a, b))
            lines.append(f"- R{r} vs {opp}: says \"{msgs[p][r - 1]}\" -> **{acts[p][r - 1]}**; "
                         f"private reason: {reasons.get(r, {}).get('reason', '')}")
        f = e["final"].get(p, {})
        lines += ["", f"**Final report:** strategy: {f.get('strategy', '')}",
                  f"self-rating: {f.get('self_rating')}; suspects: {f.get('betrayers')}", ""]
    return "\n".join(lines)


def quotes(eps, df):
    out = ["# Notable quotes", "",
           "Heuristic picks; read the full transcripts before quoting in the write-up.", ""]
    out += ["## Promised cooperation, then defected the same round", ""]
    n = 0
    for e in eps:
        acts = {}
        for ev in e["actions"]:
            for i, p in enumerate(ev["players"]):
                acts[(p, ev["round"])] = ev["actions"][i]
        for m in e["messages"]:
            if PROMISE.search(m["text"]) and acts.get((m["player"], m["round"])) == "D" and n < 25:
                tr = e["personalities"][m["player"]]
                top = ", ".join(f"{k} {v}" for k, v in sorted(tr.items(), key=lambda x: -x[1])[:5])
                out.append(f"- seed {e['seed']} {m['player']} R{m['round']} ({top}): \"{m['text']}\"")
                n += 1
    for trait, label in [("Machiavellianism", "Most Machiavellian"), ("Narcissism", "Most narcissistic"),
                         ("Hostility", "Most hostile"), ("Sycophancy", "Most sycophantic"),
                         ("Psychopathy", "Most psychopathic"), ("Altruism", "Most altruistic")]:
        col = f"trait:{trait}"
        if col not in df:
            continue
        top = df[df[col] >= 9].sort_values("message_chars", ascending=False).head(3)
        out += ["", f"## {label} agents (level 9-10)", ""]
        for _, row in top.iterrows():
            e = next(x for x in eps if x["seed"] == row["seed"])
            sample = [m["text"] for m in e["messages"] if m["player"] == row["player"] and m["text"]][:3]
            out.append(f"- seed {row['seed']} {row['player']} (coop {row['coop_rate']:.0%}, "
                       f"points {row['points']}):")
            out += [f"  - \"{s}\"" for s in sample]
    return "\n".join(out)


def report(df, eff, control, eps):
    L = ["# Personality study results", "",
         f"Completed games: {len(eps)}; agents: {len(df)}. Cost: "
         f"${sum(e.get('cost_usd', 0) for e in eps):.2f}.", "",
         "Correlations use only agents that were assigned the trait (level 1-10).",
         "q_fdr corrects for the many trait x metric tests (Benjamini-Hochberg). "
         "Treat q < 0.05 as a finding and everything else as exploratory.", ""]
    L += ["## Overall", "", "| Metric | Personality agents | Neutral control |", "|---|---:|---:|"]
    for m, label in METRICS.items():
        c = f"{control[m].mean():.3f}" if control is not None and m in control else "-"
        L.append(f"| {label} | {df[m].mean():.3f} | {c} |")
    L += ["", "## Strongest trait effects (q < 0.05)", ""]
    sig = eff[eff["q_fdr"] < 0.05] if len(eff) else eff
    for m, label in METRICS.items():
        rows = sig[sig["metric"] == m].sort_values("r", key=abs, ascending=False).head(8)
        if not len(rows):
            continue
        L += [f"### {label}", "", "| Trait | Group | r | high (8-10) | low (1-3) | n |",
              "|---|---|---:|---:|---:|---:|"]
        for _, x in rows.iterrows():
            L.append(f"| {x['trait']} | {x['group']} | {x['r']:+.2f} | {x['mean_high_8_10']:.2f} | "
                     f"{x['mean_low_1_3']:.2f} | {x['n']} |")
        L.append("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--control")
    args = ap.parse_args(argv)
    out = Path(args.run, "analysis")
    (out / "transcripts").mkdir(parents=True, exist_ok=True)
    eps = load(args.run)
    rows = []
    for e in eps:
        r, acts, msgs = agent_rows(e)
        rows += r
        (out / "transcripts" / f"seed-{e['seed']:04d}.md").write_text(transcript(e, acts, msgs), encoding="utf-8")
    df = pd.DataFrame(rows)
    df.to_csv(out / "agents.csv", index=False)
    eff = trait_effects(df)
    eff.to_csv(out / "trait_effects.csv", index=False)
    control = None
    if args.control:
        control = pd.DataFrame([r for e in load(args.control) for r in agent_rows(e)[0]])
        control.to_csv(out / "control_agents.csv", index=False)
    (out / "quotes.md").write_text(quotes(eps, df), encoding="utf-8")
    (out / "report.md").write_text(report(df, eff, control, eps), encoding="utf-8")
    print(f"{len(eps)} games, {len(df)} agents -> {out}")


if __name__ == "__main__":
    main()
