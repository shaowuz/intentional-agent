"""Export recorded strategy summaries and messages; never reconstruct reasoning."""

import argparse
import csv
import hashlib
import html
import json
import re
from pathlib import Path


def quote(text):
    # Model-authored strings remain literal quoted data in Markdown reports.
    safe = html.escape(text, quote=False)
    safe = re.sub(r"([\\`*_{}\[\]()#+!|])", r"\\\1", safe)
    return "\n".join("> " + line for line in safe.splitlines()) if safe else "> (empty message)"


def beliefs_text(beliefs):
    return "; ".join(f"{name}: {value:.6g}" for name, value in beliefs.items())


def row_for(state, root, episode, mode, player, report):
    round_number = report["round"]
    final = report["phase"] == "final"
    encounter = None if final else next(
        e for e in state["encounters"] if e["round"] == round_number and player in e["players"]
    )
    discussion = None if final else next(
        (d for d in state["discussions"] if d["after_round"] == round_number), None
    )
    post = next((m["content"] for m in discussion["posts"] if m["sender"] == player), None) if discussion else None
    i = encounter["players"].index(player) if encounter else None
    return {
        "episode": episode, "communication": mode, "player": player,
        "objective": state["roles"][player], "round": round_number, "phase": report["phase"],
        "opponent": encounter["players"][1-i] if encounter else None,
        "action": report.get("action"),
        "opponent_action": encounter["actions"][1-i] if encounter else None,
        "payoff": encounter["payoffs"][i] if encounter else None,
        "strategy_summary": report["strategy"], "beliefs": report["beliefs"],
        "outgoing_message": post,
        "message_visibility": ("private note" if mode == "none" else "public post") if discussion else None,
        "request_file": str(root.resolve() / episode / "requests" / f"{round_number:04d}-{report['phase']}-{player}.json"),
        "message_request_file": str(root.resolve() / episode / "requests" / f"{round_number:04d}-discussion-{player}.json") if discussion else None,
    }


def decision_lines(row, heading):
    lines = [heading, ""]
    if row["phase"] == "action":
        lines += [f"Opponent: **{row['opponent']}**. Executed actions: **{row['action']} / {row['opponent_action']}** (you / opponent). Your payoff: **{row['payoff']}**.",
                  "", "Strategy summary submitted with the decision:", "", quote(row["strategy_summary"]),
                  "", "Private identity beliefs before the outcome:", "", beliefs_text(row["beliefs"]), ""]
    else:
        lines += ["Final strategy summary:", "", quote(row["strategy_summary"]), "",
                  "Final private identity beliefs:", "", beliefs_text(row["beliefs"]), ""]
    lines += [f"[Original request and response](<{row['request_file']}>)", ""]
    return lines


def export(root):
    receipt = json.loads((root / "execution_receipt.json").read_text())
    if receipt["status"] != "complete":
        raise ValueError("Export requires the complete pilot")
    output = root / "agent_traces"
    output.mkdir(exist_ok=True)
    paths = sorted(root.glob("seed-*/checkpoint.json"))
    flat, index, inputs = [], [], []
    for path in paths:
        state = json.loads(path.read_text())
        config = json.loads((path.parent / "manifest.json").read_text())["config"]
        name = path.parent.name
        episode_dir = output / name
        episode_dir.mkdir(exist_ok=True)
        mode = config["communication"]
        rows = [row_for(state, root, name, mode, b["player"], b) for b in state["belief_records"]]
        flat.extend(rows)
        inputs.append({"file": str(path.relative_to(root)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        for player in state["players"]:
            own = [r for r in rows if r["player"] == player]
            lines = [f"# {name} — {player} ({state['roles'][player]})", "",
                     "[All agents in this episode](all_agents.md) · [Pilot trace index](../README.md)", "",
                     f"Final individual payoff: **{state['payoffs'][player]}**.", "",
                     "These are recorded strategy summaries, messages, and beliefs. The API excluded hidden model reasoning. Decision summaries precede the encounter outcome; notes and public posts follow it.", ""]
            for row in own:
                label = "Final report" if row["phase"] == "final" else f"Round {row['round']}"
                lines += decision_lines(row, f"## {label}")
                if row["outgoing_message"] is not None:
                    lines += [f"After the outcome — **{row['message_visibility']}**:", "",
                              quote(row["outgoing_message"]), "",
                              f"[Original note/post request and response](<{row['message_request_file']}>)", ""]
                    if mode == "public":
                        lines += [f"[Read everyone's posts after this round](all_agents.md#discussion-after-round-{row['round']})", ""]
            (episode_dir / f"{player}.md").write_text("\n".join(lines) + "\n")
        lines = [f"# {name} — all agents", "", "[Pilot trace index](../README.md)", "",
                 "Observer view: the true objectives below were hidden from other players. Strategy summaries are explicit game outputs; hidden model reasoning was excluded.", "",
                 "| Player | Objective | Final payoff | Individual trace |", "|---|---|---:|---|"]
        for player in state["players"]:
            lines.append(f"| {player} | {state['roles'][player]} | {state['payoffs'][player]} | [{player}.md]({player}.md) |")
        for r in range(1, config["rounds"] + 1):
            lines += ["", f"## Round {r}", "", "Agents submitted these decisions before receiving any outcome from this round.", ""]
            for row in rows:
                if row["round"] == r and row["phase"] == "action":
                    lines += decision_lines(row, f"### {row['player']} — {row['objective']}")
            discussion = next((d for d in state["discussions"] if d["after_round"] == r), None)
            if discussion:
                visibility = "Public posts, delivered together to everyone" if mode == "public" else "Private notes, each visible only to its author"
                lines += [f"### Discussion after round {r}", "", visibility + ":", ""]
                for post in discussion["posts"]:
                    lines += [f"**{post['sender']}**", "", quote(post["content"]), ""]
        lines += ["## Final reports", ""]
        for row in rows:
            if row["phase"] == "final":
                lines += decision_lines(row, f"### {row['player']} — {row['objective']}")
        (episode_dir / "all_agents.md").write_text("\n".join(lines) + "\n")
        selfish = next((p for p, role in state["roles"].items() if role == "selfish"), None)
        index.append({"seed": config["seed"], "selfish_count": config["selfish_count"],
                      "communication": mode, "episode": name, "selfish_player": selfish,
                      "players": config["players"]})

    intro = ["# Agent strategy and message traces", "",
             f"This export contains every accepted strategy summary, private identity-belief report, private note, and public post from the completed {len(index)}-episode pilot. It covers **{sum(r['players'] for r in index)} player sessions**, including **{sum(r['selfish_player'] is not None for r in index)} selfish-player sessions**.", "",
             "The API used `reasoning.exclude=true`; hidden model reasoning is absent. Strategy summaries were capped at 300 characters and notes/posts at 96 tokens. These explicit self-reports describe stated strategies and may be incomplete; inspect executed actions alongside them.", "",
             "Decision summaries and beliefs accompany an action, before its outcome. Private notes or public posts follow the outcome. Public-mode players have private strategy summaries but send public messages instead of private notes. A separate final report follows round 20.", "",
             "## Start with the selfish agents", "",
             "| Seed | No communication | Public communication |", "|---:|---|---|"]
    for seed in sorted({r["seed"] for r in index}):
        cells=[]
        for mode in ("none", "public"):
            row=next((r for r in index if r["seed"]==seed and r["selfish_count"]==1 and r["communication"]==mode), None)
            if row is None:
                cells.append("Not run")
                continue
            cells.append(f"[{row['selfish_player']} — complete trace]({row['episode']}/{row['selfish_player']}.md)")
        intro.append(f"| {seed} | {' | '.join(cells)} |")
    intro += ["", "## Everyone, grouped by episode", "",
              "Each episode links to six individual player traces and a chronological transcript of all decisions and messages.", "",
              "| Seed | 0 selfish, none | 0 selfish, public | 1 selfish, none | 1 selfish, public |",
              "|---:|---|---|---|---|"]
    for seed in sorted({r["seed"] for r in index}):
        cells=[]
        for k,mode in [(0,"none"),(0,"public"),(1,"none"),(1,"public")]:
            row=next((r for r in index if r["seed"]==seed and r["selfish_count"]==k and r["communication"]==mode), None)
            if row is None:
                cells.append("Not run")
                continue
            cells.append(f"[All six agents]({row['episode']}/all_agents.md)")
        intro.append(f"| {seed} | {' | '.join(cells)} |")
    intro += ["", "## Machine-readable export", "",
              "- [All accepted decision/final reports with outgoing notes/posts: JSONL](all_agents.jsonl)",
              "- [The same records as CSV](all_agents.csv)",
              "- [Export provenance](manifest.json)", "",
              "The original request files retain correction attempts. This view displays accepted responses that the game used. Public-board transcripts include authentic sender IDs and unverified message claims."]
    (output / "README.md").write_text("\n".join(intro)+"\n")
    (output / "all_agents.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in flat))
    with (output / "all_agents.csv").open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(flat[0]));writer.writeheader()
        for row in flat: writer.writerow({**row,"beliefs":json.dumps(row['beliefs'])})
    manifest={"episodes":len(index),"player_sessions":sum(r["players"] for r in index),
              "selfish_player_sessions":sum(r['selfish_player'] is not None for r in index),
              "decision_and_final_reports":len(flat),
              "notes_and_posts":sum(r['outgoing_message'] is not None for r in flat),
              "hidden_reasoning_present":False,"inputs":inputs,
              "generator_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (output / "manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps({k:v for k,v in manifest.items() if k!='inputs'},indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('root',type=Path)
    export(parser.parse_args().root)
