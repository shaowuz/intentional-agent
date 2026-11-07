"""Run the approved pilot concurrently across independent episodes.

Game execution within each episode uses the unchanged, frozen runner.
"""

import argparse
import concurrent.futures
import json
import os
import random
import shutil
import sys
import time
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=48)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    load_dotenv(root / ".env", override=False)
    output = args.output.resolve()
    if args.resume:
        if not (output / "comparison_manifest.json").exists():
            raise ValueError("Missing comparison manifest")
    else:
        output.mkdir(parents=True, exist_ok=False)
        import swarm_game
        shutil.copytree(Path(swarm_game.__file__).parent, output / "runtime/swarm_game",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copy2(root / "configs/pilot.json", output / "pilot_config.json")
        shutil.copy2(root / "uv.lock", output / "uv.lock")
        shutil.copy2(__file__, output / "launch_source.py")
        # Imports below must resolve to the frozen package, including on resume.
        del sys.modules["swarm_game"]
    sys.path.insert(0, str(output / "runtime"))
    from swarm_game.analysis import analyze_comparison
    from swarm_game.config import Config, pilot_counts
    from swarm_game.game import derived_seed
    from swarm_game.providers import OpenRouterProvider
    from swarm_game.runner import run_episode
    from swarm_game.storage import exclusive_run, provenance, read_json, scrub, write_json
    spec = read_json(output / "pilot_config.json")
    config = Config(**spec["game"])
    manifest = {"config": config.to_dict(), "seeds": spec["seeds"],
                "counts": pilot_counts(config.players, config.rounds, spec["seeds"])}
    with exclusive_run(output):
        if args.resume:
            if read_json(output / "comparison_manifest.json") != manifest:
                raise ValueError("Pilot configuration changed")
        else:
            write_json(output / "comparison_manifest.json", manifest)
            preflight = OpenRouterProvider(config)
            try:
                write_json(output / "catalog.json", preflight.catalog_entry())
                key_response = preflight.client.get(
                    "key", headers={"Authorization": f"Bearer {preflight.key}"})
                if key_response.status_code != 200:
                    raise RuntimeError(f"OpenRouter authentication HTTP {key_response.status_code}")
                key_data = key_response.json().get("data", {})
                write_json(output / "access_check.json", {
                    k: key_data.get(k) for k in ("limit", "limit_remaining", "is_free_tier", "rate_limit")})
            finally:
                preflight.close()
        write_json(output / "launch.json", {"pid": os.getpid(), "workers": args.workers,
                   "started_at": time.time(), "resume": args.resume, "provenance": provenance(),
                   "parallelism": "Independent episodes; original sequential within-episode collector"})
        tasks = []
        for seed in range(config.seed, config.seed + spec["seeds"]):
            cells = [(k, mode) for k in (0, 1) for mode in ("none", "public")]
            random.Random(derived_seed(seed, "condition_order")).shuffle(cells)
            tasks.extend(replace(config, seed=seed, selfish_count=k, communication=mode)
                         for k, mode in cells)

        def worker(cell):
            name = f"seed-{cell.seed}-selfish-{cell.selfish_count}-{cell.communication}"
            episode = output / name
            status = output / "progress" / f"{name}.json"
            checkpoint = episode / "checkpoint.json"
            if checkpoint.exists() and read_json(checkpoint)["completed"]:
                return {"episode": name, "status": "already_complete"}
            started = time.time()
            provider = OpenRouterProvider(cell)

            def progress(message):
                write_json(status, {"episode": name, "status": "running", "phase": message,
                                    "started_at": started, "updated_at": time.time()})
            try:
                summary = run_episode(cell, provider, episode,
                                      resume=episode.exists(), progress=progress)
                result = {"episode": name, "status": "complete",
                          "good_total_return": summary["good_total_return"],
                          "elapsed_seconds": time.time()-started}
            except Exception as exc:
                result = {"episode": name, "status": "failed", "error": str(exc),
                          "elapsed_seconds": time.time()-started}
            finally:
                provider.close()
            write_json(status, result)
            print(json.dumps(scrub(result)), flush=True)
            return result

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            results = list(pool.map(worker, tasks))
        summary = analyze_comparison(output)
        receipt = {"status": "complete" if all(r["status"] in ("complete", "already_complete")
                                              for r in results) else "incomplete",
                   "finished_at": time.time(), "episodes": results, "comparison": summary}
        write_json(output / "execution_receipt.json", receipt)
        print(json.dumps({"status": receipt["status"], "completed_episodes": summary["episodes"]}), flush=True)
        return 0 if receipt["status"] == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
