"""Run the personality swarm study.

Preview (free):  python -m personality.run --seeds 0-119 --output results/personality-main
Launch:          add --execute
Offline check:   add --backend scripted --execute
Control group:   add --neutral (same seeds, no personalities)
Finished games are skipped on rerun, so rerunning the same command resumes.
Clean stop while running: create an empty file named STOP in the output folder.
Running games finish and save; no new games start.
"""

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .game import Settings, make_provider, new_episode, play

COST_PER_REQUEST_ESTIMATE = 0.0013  # USD, Luna medium reasoning, from the team's pilot plus longer prompts


def load_key():
    if os.environ.get("OPENROUTER_API_KEY"):
        return
    env = Path(".env")
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                os.environ["OPENROUTER_API_KEY"] = line.split("=", 1)[1].strip()
                return
    if sys.platform == "win32":  # value saved with setx is not visible until a new terminal
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                os.environ["OPENROUTER_API_KEY"] = winreg.QueryValueEx(k, "OPENROUTER_API_KEY")[0]
        except OSError:
            pass


def parse_seeds(text):
    seeds = []
    for part in text.split(","):
        if "-" in part:
            a, b = part.split("-")
            seeds.extend(range(int(a), int(b) + 1))
        else:
            seeds.append(int(part))
    return seeds


def write_json(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", default="0-1")
    ap.add_argument("--output", required=True)
    ap.add_argument("--players", type=int, default=10)
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument("--model", default="openai/gpt-6-luna")
    ap.add_argument("--provider", default="openai", help="OpenRouter provider to pin")
    ap.add_argument("--reasoning", default="medium")
    ap.add_argument("--backend", choices=["openrouter", "scripted"], default="openrouter")
    ap.add_argument("--neutral", action="store_true", help="control group: no personalities")
    ap.add_argument("--workers", type=int, default=3, help="games run at the same time")
    ap.add_argument("--max-cost", type=float, default=60.0, help="stop launching new games past this USD")
    ap.add_argument("--max-games", type=int, default=0,
                    help="stop starting new games once this many are complete or running (0 = no limit)")
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args(argv)

    settings = Settings(players=args.players, rounds=args.rounds, model=args.model,
                        provider=args.provider, reasoning_effort=args.reasoning,
                        neutral=args.neutral, backend=args.backend)
    seeds = parse_seeds(args.seeds)
    out = Path(args.output)
    eps_dir = out / "episodes"
    done = {int(p.stem.split("-")[1]) for p in eps_dir.glob("seed-*.json")
            if json.loads(p.read_text(encoding="utf-8")).get("status") == "complete"} if eps_dir.exists() else set()
    todo = [s for s in seeds if s not in done]
    per_game = args.players * args.rounds * 2 + args.players
    print(json.dumps({
        "games_requested": len(seeds), "already_complete": len(done & set(seeds)), "to_run": len(todo),
        "agents": len(todo) * args.players, "requests_before_retries": len(todo) * per_game,
        "estimated_cost_usd": round(len(todo) * per_game * COST_PER_REQUEST_ESTIMATE, 2)
        if args.backend == "openrouter" else 0,
        "settings": settings.__dict__ | {"extra": None},
    }, indent=1))
    if not args.execute:
        print("Preview only. Add --execute to run.")
        return 0

    load_key()
    eps_dir.mkdir(parents=True, exist_ok=True)
    spec = out / "spec.json"
    if not spec.exists():
        write_json(spec, {"settings": settings.__dict__ | {"extra": None}, "seeds": seeds})
    provider = make_provider(settings)
    lock = threading.Lock()
    spent = {"usd": 0.0}
    launched = {"n": len(done & set(seeds))}
    for p in eps_dir.glob("seed-*.json"):
        ep = json.loads(p.read_text(encoding="utf-8"))
        spent["usd"] += sum((r.get("cost") or 0) for r in ep.get("requests", []))

    def one(seed):
        with lock:
            if spent["usd"] >= args.max_cost:
                return seed, "skipped (cost cap)"
            if (out / "STOP").exists():  # graceful stop: finish running games, start no new ones
                return seed, "skipped (STOP file)"
            if args.max_games and launched["n"] >= args.max_games:
                return seed, "skipped (max games)"
            launched["n"] += 1
        ep = new_episode(seed, settings)
        t0 = time.time()
        try:
            play(ep, provider)
        except Exception as exc:  # keep other games running; rerun resumes
            ep["status"] = "failed"
            ep["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        cost = sum((r.get("cost") or 0) for r in ep["requests"])
        ep["cost_usd"], ep["seconds"] = cost, round(time.time() - t0, 1)
        write_json(eps_dir / f"seed-{seed:04d}.json", ep)
        with lock:
            spent["usd"] += cost
            return seed, f"{ep['status']} ${cost:.3f} {ep['seconds']}s total ${spent['usd']:.2f}"

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for fut in as_completed([pool.submit(one, s) for s in todo]):
            seed, msg = fut.result()
            print(f"seed {seed}: {msg}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
