import argparse
import json
import random
import sys
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv

from .analysis import analyze_comparison, analyze_episode
from .config import Config, pilot_counts
from .game import derived_seed
from .providers import OpenRouterProvider, ScriptedProvider
from .runner import load_config, run_episode
from .smoke import run_smoke
from .storage import read_json, scrub, write_json


def make_provider(config, *, attempts=3):
    return (
        ScriptedProvider(config)
        if config.backend == "scripted"
        else OpenRouterProvider(config, attempts=attempts)
    )


def close_provider(provider):
    if hasattr(provider, "close"):
        provider.close()


def progress(text):
    print(text, file=sys.stderr, flush=True)


def common_options(parser):
    parser.add_argument(
        "--model", choices=["openai/gpt-6.1-terra", "openai/gpt-6-astra"], default=Config().model
    )
    parser.add_argument("--players", type=int, default=6)
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--backend", choices=["openrouter", "scripted"], default="openrouter")
    parser.add_argument(
        "--policy", choices=["cooperate", "defect", "tit_for_tat"], default="cooperate"
    )
    parser.add_argument(
        "--selfish-policy", choices=["cooperate", "defect", "tit_for_tat"], default="cooperate"
    )


def config_from_args(args):
    return Config(**{k: v for k, v in vars(args).items() if k in Config.__dataclass_fields__})


def compare(config, seeds, output, resume=False):
    output = Path(output)
    if seeds < 1:
        raise ValueError("seeds must be positive")
    spec = {
        "config": config.to_dict(),
        "seeds": seeds,
        "counts": pilot_counts(config.players, config.rounds, seeds),
    }
    if resume:
        if read_json(output / "comparison_manifest.json") != spec:
            raise ValueError("Resume comparison parameters differ from saved values")
    else:
        output.mkdir(parents=True, exist_ok=False)
        write_json(output / "comparison_manifest.json", spec)
    for seed in range(config.seed, config.seed + seeds):
        cells = [(k, mode) for k in (0, 1) for mode in ("none", "public")]
        random.Random(derived_seed(seed, "condition_order")).shuffle(cells)
        for k, mode in cells:
            cell = replace(config, seed=seed, selfish_count=k, communication=mode)
            episode = output / f"seed-{seed}-selfish-{k}-{mode}"
            if (
                resume
                and (episode / "checkpoint.json").exists()
                and read_json(episode / "checkpoint.json")["completed"]
            ):
                continue
            progress(f"{episode.name}")
            provider = make_provider(cell)
            try:
                run_episode(
                    cell, provider, episode, resume=resume and episode.exists(), progress=progress
                )
            finally:
                close_provider(provider)
    return analyze_comparison(output)


def main(argv=None):
    parser = argparse.ArgumentParser(description="GPT-6 communication experiment via OpenRouter")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run one episode")
    common_options(run)
    run.add_argument("--communication", choices=["none", "public"], default="none")
    run.add_argument("--selfish-count", type=int, choices=[0, 1], default=0)
    run.add_argument("--output", type=Path, required=True)
    paired = commands.add_parser(
        "compare", help="Run matched none/public episodes for both role counts"
    )
    common_options(paired)
    paired.add_argument("--seeds", type=int, default=1)
    paired.add_argument("--output", type=Path, required=True)
    paired.add_argument("--resume", action="store_true")
    pilot = commands.add_parser(
        "pilot", help="Preview or explicitly execute a saved pilot configuration"
    )
    pilot.add_argument("--config", type=Path, default=Path("configs/pilot.json"))
    pilot.add_argument("--output", type=Path, default=Path("runs/pilot"))
    pilot.add_argument("--execute", action="store_true")
    pilot.add_argument("--resume", action="store_true")
    resume = commands.add_parser("resume", help="Resume an episode with its original configuration")
    resume.add_argument("output", type=Path)
    analyze = commands.add_parser("analyze", help="Rebuild episode or comparison analysis")
    analyze.add_argument("output", type=Path)
    smoke = commands.add_parser("smoke", help="At most four GPT-6 generation requests; no retries")
    smoke.add_argument("--output", type=Path, default=Path("runs/smoke"))
    smoke.add_argument(
        "--model", choices=["openai/gpt-6.1-terra", "openai/gpt-6-astra"], default=Config().model
    )
    args = parser.parse_args(argv)
    load_dotenv(args.env_file, override=False)
    provider = None
    try:
        if args.command == "analyze":
            result = (
                analyze_episode(args.output)
                if (args.output / "manifest.json").exists()
                else analyze_comparison(args.output)
            )
        elif args.command == "smoke":
            provider = make_provider(Config(model=args.model), attempts=1)
            result = run_smoke(provider, args.output)
        elif args.command == "pilot":
            spec = read_json(args.config)
            config = Config(**spec["game"])
            if args.execute:
                result = compare(config, spec["seeds"], args.output, args.resume)
            else:
                result = {
                    "status": "preview",
                    **pilot_counts(config.players, config.rounds, spec["seeds"]),
                    "model": config.model,
                    "output": str(args.output),
                    "launch": "Add --execute to start the full pilot.",
                }
        elif args.command == "compare":
            result = compare(config_from_args(args), args.seeds, args.output, args.resume)
        else:
            config = (
                load_config(args.output) if args.command == "resume" else config_from_args(args)
            )
            provider = make_provider(config)
            result = run_episode(
                config, provider, args.output, resume=args.command == "resume", progress=progress
            )
        print(json.dumps(scrub(result), indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, KeyboardInterrupt) as exc:
        print(f"{type(exc).__name__}: {scrub(str(exc))}", file=sys.stderr)
        return 1
    finally:
        if provider:
            close_provider(provider)


if __name__ == "__main__":
    sys.exit(main())
