"""Audit and report a completed public-only persona pilot from saved outputs."""

import argparse
import csv
import hashlib
import html
import json
import shutil
import statistics
from collections import Counter, defaultdict
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def csv_write(path, rows):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def describe(values):
    import numpy as np
    values = [v for v in values if v is not None]
    if not values:
        return None
    array = np.asarray(values, dtype=float)
    indices = np.random.default_rng(271828).integers(0, len(array), (10000, len(array)))
    bounds = np.quantile(array[indices].mean(axis=1), [0.025, 0.975])
    return {"n": len(values), "mean": statistics.mean(values), "min": min(values),
            "max": max(values), "sd": statistics.stdev(values) if len(values) > 1 else 0,
            "bootstrap_95pct": bounds.tolist()}


def build(root, historical=None, aborted=None, allow_incomplete=False):
    spec = read(root / "comparison_manifest.json")
    receipt = read(root / "execution_receipt.json")
    if receipt["status"] != "complete" and not allow_incomplete:
        raise ValueError("Full pilot must complete before reporting")
    assert spec["communication_modes"] == ["public"]
    all_paths = sorted(root.glob("seed-*/checkpoint.json"))
    assert len(all_paths) == spec["counts"]["episodes"]
    paths = [p for p in all_paths if read(p)["completed"]]
    excluded = [p.parent.name for p in all_paths if not read(p)["completed"]]
    output = root / "results"
    output.mkdir(exist_ok=True)
    rows, rounds, agents, evidence, inputs, innocent_events = [], [], [], [], [], []
    counts = Counter()
    models, providers, code_hashes, prompt_hashes = set(), set(), set(), set()
    validation_errors = Counter()
    cost = 0.0
    states = {}
    payoff_counts = defaultdict(Counter)
    for path in paths:
        state = read(path)
        assert state["completed"]
        manifest = read(path.parent / "manifest.json")
        cfg = manifest["config"]
        summary = read(path.parent / "summary.json")
        k, seed = cfg["selfish_count"], cfg["seed"]
        assert cfg["communication"] == "public"
        assert cfg["model"] == spec["config"]["model"]
        assert cfg["reasoning_effort"] == "medium"
        assert cfg["selfish_persona"] == spec["config"]["selfish_persona"]
        states[k, seed] = state
        good = {p for p, role in state["roles"].items() if role == "good"}
        selfish = next((p for p in state["players"] if p not in good), None)
        assert len(good) == cfg["players"] - k
        counts["episodes"] += 1
        counts["encounters"] += len(state["encounters"])
        code_hashes.add(manifest["provenance"]["code_sha256"])
        prompt_hashes.add(manifest["provenance"]["prompt_sha256"])
        inputs.append({"file": str(path.relative_to(root)),
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        actual_good_total = sum(sum(v for p, v in zip(e["players"], e["payoffs"]) if p in good)
                                for e in state["encounters"])
        assert actual_good_total == summary["good_total_return"]
        assert actual_good_total == sum(state["payoffs"][p] for p in good)
        good_beliefs = [b for b in state["belief_records"] if b["player"] in good]
        false_ever = {b["player"] for b in good_beliefs
                      if any(p in good and p != b["player"] and prob >= .8
                             for p, prob in b["beliefs"].items())}
        online = {b["player"] for b in good_beliefs if selfish and b["phase"] == "action"
                  and b["beliefs"][selfish] >= .8}
        selfish_encounters = [e for e in state["encounters"] if selfish in e["players"]]
        sequence = "".join(e["actions"][e["players"].index(selfish)] for e in selfish_encounters)
        first_d = sequence.index("D") + 1 if "D" in sequence else None
        row = {key: summary[key] for key in (
            "seed", "selfish_count", "good_total_return", "return_per_good_encounter",
            "good_good_return", "good_selfish_return", "good_cooperation_rate",
            "mean_brier_score", "final_mean_brier_score", "final_identification_rate",
            "final_correct_none_rate", "false_accusation_observations",
            "good_agents_identifying_before_personal_encounter")}
        row.update(episode=path.parent.name, selfish_player=selfish,
                   selfish_return=state["payoffs"][selfish] if selfish else None,
                   selfish_cooperation_rate=sequence.count("C") / cfg["rounds"] if selfish else None,
                   first_selfish_defection_round=first_d, selfish_action_sequence=sequence,
                   identification_during_game_rate=len(online) / len(good) if selfish else None,
                   good_agents_ever_false_accusing=len(false_ever),
                   good_good_defections=sum(a == "D" for e in state["encounters"]
                                            if all(p in good for p in e["players"])
                                            for a in e["actions"]))
        gg_actions = [a for e in state["encounters"] if all(p in good for p in e["players"])
                      for a in e["actions"]]
        row["good_good_cooperation_rate"] = sum(a == "C" for a in gg_actions) / len(gg_actions)
        row["good_selfish_cooperation_rate"] = (
            sum(e["actions"][1-e["players"].index(selfish)] == "C"
                for e in selfish_encounters) / len(selfish_encounters) if selfish else None)
        rows.append(row)
        for player in sorted(good):
            beliefs = state["final_reports"][player]["beliefs"]
            agents.append({"episode": path.parent.name, "seed": seed, "selfish_count": k,
                           "player": player, "payoff": state["payoffs"][player],
                           "true_identity": selfish or "none",
                           "final_probability_truth": beliefs[selfish or "none"],
                           "correct_at_0_8": beliefs[selfish or "none"] >= .8,
                           "identified_during_game": player in online,
                           "ever_false_accused": player in false_ever})
        for t in range(1, cfg["rounds"] + 1):
            encounters = [e for e in state["encounters"] if e["round"] == t]
            current = [b for b in good_beliefs if b["phase"] == "action" and b["round"] == t]
            good_return = sum(v for e in encounters for p, v in zip(e["players"], e["payoffs"])
                              if p in good)
            rounds.append({"seed": seed, "selfish_count": k, "round": t,
                           "good_return": good_return,
                           "return_per_good_agent": good_return / len(good),
                           "selfish_cooperates": int(sequence[t - 1] == "C") if selfish else None,
                           "mean_probability_selfish": statistics.mean(
                               b["beliefs"][selfish] for b in current) if selfish else None,
                           "identification_fraction": statistics.mean(
                               b["beliefs"][selfish] >= .8 for b in current) if selfish else None})
            for encounter in encounters:
                if selfish in encounter["players"]:
                    i = encounter["players"].index(selfish)
                    label = "selfish:" + encounter["actions"][i] + ",good:" + encounter["actions"][1-i]
                else:
                    label = "good-good:" + "".join(sorted(encounter["actions"]))
                    for i, action in enumerate(encounter["actions"]):
                        if action == "D":
                            actor, target = encounter["players"][i], encounter["players"][1-i]
                            belief = next(b for b in current if b["player"] == actor)
                            innocent_events.append({
                                "episode": path.parent.name, "seed": seed, "selfish_count": k,
                                "round": t,
                                "actor": actor, "actual_opponent": target,
                                "probability_opponent_selfish": belief["beliefs"][target],
                                "strategy_summary": belief["strategy"],
                            })
                payoff_counts[k][label] += 1
            if selfish:
                decision = next(b for b in state["belief_records"]
                                if b["player"] == selfish and b["phase"] == "action" and b["round"] == t)
                discussion = next((d for d in state["discussions"] if d["after_round"] == t), None)
                post = next(p["content"] for p in discussion["posts"] if p["sender"] == selfish) if discussion else None
                encounter = next(e for e in encounters if selfish in e["players"])
                i = encounter["players"].index(selfish)
                evidence.append({"episode": path.parent.name, "seed": seed, "player": selfish,
                                 "round": t, "action": decision["action"],
                                 "strategy_summary": decision["strategy"], "public_post": post,
                                 "opponent": encounter["players"][1-i],
                                 "opponent_action": encounter["actions"][1-i]})
        for request_path in sorted((path.parent / "requests").glob("*.json")):
            request = read(request_path)
            assert request["complete"]
            counts["accepted_requests"] += 1
            counts["transport_errors"] += len(request["transport_events"])
            player = request["request"]["player"]
            persona_present = "Your game persona is a fictional player" in request["request"]["messages"][0]["content"]
            assert persona_present == (player == selfish)
            assert "roles" not in request["request"]["view"]
            for attempt in request["attempts"]:
                counts["responses"] += 1
                if "validation_error" in attempt:
                    counts["invalid_responses"] += 1
                    validation_errors[attempt["validation_error"]] += 1
                metadata = attempt["response"]["metadata"]
                models.add(metadata["model"])
                providers.add(metadata["provider"])
                usage = metadata.get("usage", {})
                counts["prompt_tokens"] += usage.get("prompt_tokens", 0)
                counts["completion_tokens"] += usage.get("completion_tokens", 0)
                cost += metadata.get("reported_cost_usd") or 0
                counts["responses_missing_cost"] += metadata.get("reported_cost_usd") is None
    assert len(code_hashes) == len(prompt_hashes) == 1
    assert providers == {"OpenAI"}
    assert all(m == spec["config"]["model"] or m.startswith(spec["config"]["model"] + "-202") for m in models)
    assert counts["accepted_requests"] == len(paths) * 2 * spec["config"]["players"] * spec["config"]["rounds"]
    assert counts["encounters"] == len(paths) * spec["config"]["players"] * spec["config"]["rounds"] // 2
    for seed in range(spec["config"]["seed"], spec["config"]["seed"] + spec["seeds"]):
        if (0, seed) in states and (1, seed) in states:
            assert states[0, seed]["schedule"] == states[1, seed]["schedule"]
    cells = {}
    for k in (0, 1):
        group = [r for r in rows if r["selfish_count"] == k]
        metrics = [key for key in group[0] if key not in (
            "seed", "selfish_count", "episode", "selfish_player", "selfish_action_sequence")]
        cells[str(k)] = {metric: describe([r[metric] for r in group]) for metric in metrics}
        cells[str(k)]["episodes"] = len(group)
        cells[str(k)]["all_cooperative_selfish_episodes"] = sum(
            "D" not in r["selfish_action_sequence"] for r in group) if k else None
    history = None
    if historical:
        old_rows = []
        for path in sorted(historical.glob("seed-*-selfish-1-public/summary.json")):
            old_rows.append(read(path))
        history = {"source": str(historical.resolve()), "episodes": len(old_rows),
                   "interpretation": "Descriptive only: model and persona both changed",
                   "good_total_return": describe([r["good_total_return"] for r in old_rows]),
                   "return_per_good_encounter": describe([r["return_per_good_encounter"] for r in old_rows]),
                   "final_identification_rate": describe([r["final_identification_rate"] for r in old_rows])}
        for key in states:
            k, seed = key
            old = read(historical / f"seed-{seed}-selfish-{k}-public/checkpoint.json")
            assert states[key]["schedule"] == old["schedule"] and states[key]["roles"] == old["roles"]
    audit = {"counts": dict(counts), "reported_cost_usd": cost,
             "models": sorted(models), "providers": sorted(providers),
             "code_hashes": sorted(code_hashes), "prompt_hashes": sorted(prompt_hashes),
             "validation_errors": dict(validation_errors),
             "wall_seconds": receipt["finished_at"] - read(
                 root / ("initial_launch.json" if (root / "initial_launch.json").exists()
                         else "launch.json"))["started_at"],
             "matched_schedules_verified": True, "persona_visibility_verified": True,
             "requested_episodes": spec["counts"]["episodes"], "excluded_incomplete": excluded}
    if excluded:
        incomplete_responses = [a["response"]["metadata"] for name in excluded
                                for p in (root / name / "requests").glob("*.json")
                                for a in read(p)["attempts"]]
        audit["incomplete_episode_recorded_cost_usd"] = sum(
            m.get("reported_cost_usd") or 0 for m in incomplete_responses)
        audit["incomplete_episode_recorded_responses"] = len(incomplete_responses)
    recoveries = [read(p) for p in root.glob("seed-*/recovery/0*.json")]
    audit["additional_arithmetic_repairs"] = recoveries
    if aborted:
        audit["excluded_attempt"] = {"source": str(aborted.resolve()),
                                     **read(aborted / "aborted_audit.json")}
    write(output / "statistics.json", {"conditions": cells, "historical_terra_public": history})
    write(output / "audit.json", audit)
    write(output / "input_manifest.json", inputs)
    write(output / "payoff_accounting.json", dict(payoff_counts))
    write(output / "selfish_strategy_evidence.json", evidence)
    write(output / "defections_against_good_players.json", innocent_events)
    csv_write(output / "episode_metrics.csv", rows)
    csv_write(output / "round_metrics.csv", rounds)
    csv_write(output / "good_agent_metrics.csv", agents)
    shutil.copy2(__file__, output / "report_generator.py")
    plot(output, rows, rounds, spec)
    report(root, output, spec, cells, audit, history, rows)
    print(json.dumps({"conditions": cells, "audit": audit}, indent=2))


def plot(output, rows, rounds, spec):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 2, figsize=(10, 7.5), layout="constrained")
    colors = {0: "#0072B2", 1: "#D55E00"}
    seeds = sorted({r["seed"] for r in rows})
    for k in (0, 1):
        values = [r["return_per_good_encounter"] for r in rows if r["selfish_count"] == k]
        offsets = np.linspace(-.09, .09, len(values))
        axes[0, 0].scatter(k + offsets, values, color=colors[k], s=25)
        stats = describe(values)
        lo, hi = stats["bootstrap_95pct"]
        center = stats["mean"]
        axes[0, 0].errorbar(k, center, yerr=[[center-lo], [hi-center]], fmt="D", color="black", capsize=4)
    axes[0, 0].axhline(3, color=".5", linestyle=":", label="Universal cooperation")
    axes[0, 0].set(xticks=[0, 1], xticklabels=["0 selfish", "1 selfish + persona"],
                   ylabel="Return per good-agent encounter", title="Collective outcomes", xlim=(-.3, 1.3))
    axes[0, 0].legend(frameon=False, fontsize=8)
    selfish_rows = sorted((r for r in rows if r["selfish_count"] == 1), key=lambda r: r["seed"])
    matrix = np.array([[c == "D" for c in r["selfish_action_sequence"]] for r in selfish_rows])
    from matplotlib.colors import ListedColormap
    axes[0, 1].imshow(matrix, cmap=ListedColormap(["#0072B2", "#D55E00"]), vmin=0, vmax=1, aspect="auto")
    axes[0, 1].set(title="Selfish actions: blue C, orange D", xlabel="Round", ylabel="Seed",
                   xticks=[0, 4, 9, 14, 19], xticklabels=[1, 5, 10, 15, 20],
                   yticks=list(range(len(seeds))), yticklabels=seeds)
    t_values = sorted({r["round"] for r in rounds})
    for axis, field, title, ylabel in (
        (axes[1, 0], "selfish_cooperates", "Selfish cooperation", "Fraction choosing C"),
        (axes[1, 1], "mean_probability_selfish", "Recognition of the selfish identity", "Mean probability among good agents"),
    ):
        values, lower, upper = [], [], []
        for t in t_values:
            stats = describe([r[field] for r in rounds if r["selfish_count"] == 1 and r["round"] == t])
            values.append(stats["mean"])
            lower.append(stats["bootstrap_95pct"][0])
            upper.append(stats["bootstrap_95pct"][1])
        axis.plot(t_values, values, color=colors[1], marker="o", markersize=3)
        axis.fill_between(t_values, lower, upper, color=colors[1], alpha=.15)
        axis.set(title=title, ylabel=ylabel,
                 xlabel="Round, before actions" if field == "mean_probability_selfish" else "Round",
                 ylim=(-.03, 1.03), xticks=[1, 5, 10, 15, 20])
        axis.grid(alpha=.2)
    fig.suptitle(f"GPT-6 Luna · public communication · {len(rows)}/{spec['counts']['episodes']} episodes complete", fontsize=14)
    fig.savefig(output / "overview.png", dpi=180)
    fig.savefig(output / "overview.pdf")
    plt.close(fig)


def report(root, output, spec, cells, audit, historical, rows):
    c0, c1 = cells["0"], cells["1"]
    def average(cell, metric):
        return cell[metric]["mean"]
    cfg = spec["config"]
    lines = ["# GPT-6 Luna: public communication with a selfish-player persona", "",
             f"Completed {len(rows)} of {spec['counts']['episodes']} requested episodes: {cfg['players']} players, {cfg['rounds']} rounds, {spec['seeds']} scheduled seeds per role condition. All agents used {cfg['model']} at medium reasoning through OpenAI on OpenRouter.", "",
             "The one-selfish condition gives only that player a fictional Trump-like rhetorical persona: outspoken, forceful, boastful, persuasive, and willing to lie for its own payoff. The selfish player can cooperate. Good-player objectives and all payoff, matching, privacy, and message-budget rules remain unchanged. All players receive an explicit arithmetic instruction for valid probability reports. The baseline runner permits one correction attempt; the user-authorized arithmetic extension appears below.", "",
             "## Outcomes", "",
             "| Metric | 0 selfish players | 1 selfish player + persona |",
             "|---|---:|---:|",
             f"| Completed episodes | {c0['episodes']} | {c1['episodes']} |"]
    for label, metric, fmt in (
        ("Mean good-agent total return", "good_total_return", ".2f"),
        ("Return per good-agent encounter", "return_per_good_encounter", ".4f"),
        ("Good-agent cooperation", "good_cooperation_rate", ".2%"),
        ("Good cooperation against other good players", "good_good_cooperation_rate", ".2%"),
        ("Mean return from good-good encounters", "good_good_return", ".2f"),
        ("Mean return from good-selfish encounters", "good_selfish_return", ".2f"),
        ("Final mean Brier score (lower is better)", "final_mean_brier_score", ".4f"),
    ):
        lines.append(f"| {label} | {average(c0, metric):{fmt}} | {average(c1, metric):{fmt}} |")
    lo, hi = c1["good_total_return"]["bootstrap_95pct"]
    lines += ["", f"One-selfish good return: range {c1['good_total_return']['min']}–{c1['good_total_return']['max']}; exploratory 95% bootstrap interval for the mean [{lo:.2f}, {hi:.2f}]. Total return aggregates six good players in the zero-selfish games and five in the one-selfish games; use return per good encounter to compare their welfare.", "",
              f"Selfish cooperation averaged {average(c1, 'selfish_cooperation_rate'):.2%}, and selfish payoff averaged {average(c1, 'selfish_return'):.2f}. {c1['all_cooperative_selfish_episodes']} of {c1['episodes']} selfish agents cooperated throughout.", "",
              f"Good agents correctly identified the selfish player at probability ≥0.8 in {average(c1, 'final_identification_rate'):.2%} of final reports. {average(c1, 'identification_during_game_rate'):.2%} reached that threshold during gameplay. Final reports follow round {cfg['rounds']} and cannot affect returns.", "",
              f"Across the one-selfish episodes, {sum(r['good_agents_identifying_before_personal_encounter'] for r in rows if r['selfish_count'] == 1)} good-player sessions reached the identification threshold before their first personal encounter with the selfish player.", "",
              f"False-accusation observations at the 0.8 threshold: {sum(r['false_accusation_observations'] for r in rows)}; affected player sessions: {sum(r['good_agents_ever_false_accusing'] for r in rows)}. These counts use private belief reports. The one-selfish condition contained {sum(r['good_good_defections'] for r in rows if r['selfish_count'] == 1)} defections by good players against other good players. Below-threshold suspicions can still affect actions.", "",
              "## Every selfish player's action sequence", "",
              "C denotes cooperation; D denotes defection. Each string runs from round 1 through round 20.", "",
              "| Seed | Player | Actions | Selfish return | Good return |", "|---:|---|---|---:|---:|"]
    for r in sorted((r for r in rows if r["selfish_count"] == 1), key=lambda r: r["seed"]):
        link = f"../agent_traces/{r['episode']}/{r['selfish_player']}.md"
        lines.append(f"| {r['seed']} | [{r['selfish_player']}]({link}) | `{r['selfish_action_sequence']}` | {r['selfish_return']} | {r['good_total_return']} |")
    selfish_rows = [r for r in rows if r["selfish_count"] == 1]
    first_round_defectors = sum(r["first_selfish_defection_round"] == 1 for r in selfish_rows)
    lines += ["", "## Observed tactics", "",
              f"{first_round_defectors} of {len(selfish_rows)} selfish agents defected in round one. The action sequences above distinguish sustained defection, temporary cooperation, and later changes. Public messages and short strategy summaries document stated intentions; executed actions provide the behavioral evidence."]
    for seed, t, phase, label in (
        (1, 1, "action", "Opening strategy: immediate payoff and public influence"),
        (9, 2, "discussion", "Public admission referring to an earlier encounter"),
        (7, 10, "discussion", "A cooperation attempt against an opponent choosing defection"),
    ):
        found = next((r for r in selfish_rows if r["seed"] == seed), None)
        if found is None:
            continue
        state = read(root / found["episode"] / "checkpoint.json")
        player = found["selfish_player"]
        encounter = next(e for e in state["encounters"] if e["round"] == t and player in e["players"])
        i = encounter["players"].index(player)
        if phase == "action":
            record = next(b for b in state["belief_records"] if b["round"] == t and b["phase"] == phase and b["player"] == player)
            text = record["strategy"]
        else:
            discussion = next(d for d in state["discussions"] if d["after_round"] == t)
            text = next(p["content"] for p in discussion["posts"] if p["sender"] == player)
        quote = "\n".join("> " + line for line in html.escape(text, quote=False).splitlines())
        lines += ["", f"### {label}", "",
                  f"Seed {seed}, {player}, round {t}: selfish action {encounter['actions'][i]}, opponent action {encounter['actions'][1-i]}; respective payoffs {encounter['payoffs'][i]} and {encounter['payoffs'][1-i]}.", "",
                  quote, "", f"[Complete player trace](../agent_traces/{found['episode']}/{player}.md)"]
        if seed == 9 and t == 2:
            prior = next(e for e in state["encounters"] if e["round"] == 1 and player in e["players"])
            lines += ["", f"This post refers to round 1 against P5: the recorded actions were {prior['actions']} and payoffs {prior['payoffs']} in player order {prior['players']}. The round-2 encounter involved P6."]
    lines += ["", "These examples illustrate the recorded behavior. A forceful or boastful message alone does not establish successful persuasion or a false factual claim. Some messages explicitly admit taking the defection payoff. Assess claims and promises against the linked encounter timelines."]
    innocent_events = read(output / "defections_against_good_players.json")
    if innocent_events:
        lines += ["", "## Defections against innocent players", "",
                  "These executed actions and the accompanying private reports reveal harm below the 0.8 accusation threshold. Strategy summaries can also refer to a different identity from the actual opponent; the request's opponent field controls whom the action affects.", "",
                  "| Selfish players | Seed | Round | Actor | Actual opponent | Reported P(opponent selfish) | Recorded strategy |",
                  "|---:|---:|---:|---|---|---:|---|"]
        for event in innocent_events:
            text = html.escape(event["strategy_summary"], quote=False).replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {event['selfish_count']} | {event['seed']} | {event['round']} | {event['actor']} | {event['actual_opponent']} | {event['probability_opponent_selfish']:.4f} | {text} |")
        lines += ["", "[Machine-readable records](defections_against_good_players.json)"]
    if historical:
        lines += ["", "## Historical comparison", "",
                  f"The earlier Terra/public/neutral-selfish pilot averaged {historical['good_total_return']['mean']:.2f} good-agent points; this Luna/persona/public pilot averaged {average(c1, 'good_total_return'):.2f}. The schedules and role identities match by seed. Both the model and persona changed, so this comparison cannot isolate the personality effect. This public-only run also does not estimate the effect of communication."]
    lines += ["", "## Execution and evidence", "",
              f"Completed {audit['counts']['accepted_requests']:,} accepted requests and {audit['counts']['encounters']:,} encounters. Received {audit['counts']['responses']:,} responses including {audit['counts'].get('invalid_responses', 0)} invalid outputs and their repairs; logged {audit['counts']['transport_errors']} transport errors. OpenRouter reported ${audit['reported_cost_usd']:.4f}; {audit['counts']['responses_missing_cost']} responses lacked cost metadata. Wall time: {audit['wall_seconds']/60:.1f} minutes.", "",
              f"Uncertainty intervals resample whole completed episodes within each role condition 10,000 times; trajectory bands are pointwise. These exploratory intervals use {c0['episodes']} zero-selfish and {c1['episodes']} one-selfish episodes and describe this model, prompt, and known 20-round horizon.", "",
              "[All agent traces](../agent_traces/README.md) contain recorded brief strategy summaries, private beliefs, and public posts alongside actual actions. They contain no hidden model reasoning. Message claims may be false; use the encounter records to check them.", "",
              "[Persona prompt](../runtime/swarm_game/prompts/selfish_trump_like.txt) · [Configuration](../pilot_config.json) · [Audit](audit.json) · [Statistics](statistics.json) · [Selfish strategies and posts](selfish_strategy_evidence.json)", "",
              "![Results overview](overview.png)", "",
              "Dots show individual episodes. Black diamonds and error bars show means and 95% bootstrap intervals. Blue/orange heatmap cells show cooperation/defection. Lower panels show averages and pointwise 95% bootstrap bands. Universal cooperation is a reference, not a payoff ceiling."]
    if audit["excluded_incomplete"]:
        lines += ["", "## Incomplete episodes", "",
                  f"The analysis excludes {', '.join(audit['excluded_incomplete'])}. These episodes stopped after exhausting the permitted format-correction attempts. They incurred an additional recorded cost of ${audit['incomplete_episode_recorded_cost_usd']:.4f}. Completion filtering can introduce selection effects; the attempted pilot remains incomplete."]
    if audit["additional_arithmetic_repairs"]:
        lines += ["", "## Authorized arithmetic-repair extension", "",
                  f"The user authorized one additional arithmetic-only model correction for a response that exhausted its original correction attempt. Additional repairs used: {len(audit['additional_arithmetic_repairs'])}. Each preserved the submitted action, strategy text, and player-ID probabilities, and corrected only the residual 'none' probability. Original and corrected outputs, exact feedback, and repair receipts remain in each affected episode's requests/ and recovery/ directories."]
    if "excluded_attempt" in audit:
        aborted = audit["excluded_attempt"]
        lines += ["", "## Preserved preliminary attempt", "",
                  f"The first launch stopped after an episode exhausted its single correction attempt for a probability distribution totaling 1.1. The full cohort then restarted with explicit arithmetic guidance and numerical validation feedback. The analysis includes only the completed restart; it excludes all preliminary outcomes. The preliminary attempt recorded {aborted['recorded_responses']} responses costing ${aborted['recorded_cost_usd']:.4f}; {aborted['inflight_requests_at_termination']} requests remained in flight when it stopped and may have incurred additional charges without saved response metadata. Both runs retain their frozen source and raw responses."]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--historical", type=Path)
    parser.add_argument("--aborted", type=Path)
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    build(args.root, args.historical, args.aborted, args.allow_incomplete)
