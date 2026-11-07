"""One matched model × communication design and one auditable output contract."""

import random
import shutil
from dataclasses import replace
from pathlib import Path

from .config import COMMUNICATION_MODES, LEGACY_COMMUNICATION_MODES, MODELS, SELFISH_COUNTS, Config
from .game import derived_seed
from .providers import OpenRouterProvider, ScriptedProvider
from .runner import run_episode
from .storage import exclusive_run, provenance, read_json, write_json

SCHEMA_VERSION = "intentional-experiments/1"


def normalize_spec(raw):
    if not isinstance(raw, dict) or set(raw) - {
        "models",
        "communication_modes",
        "selfish_counts",
        "seeds",
        "game",
    }:
        raise ValueError("Unknown matrix fields")
    game = raw.get("game", {})
    if not isinstance(game, dict):
        raise ValueError("game must be an object")
    legacy = game.get("protocol_version") == "rotating-v2"
    protocol = game.get("protocol_version", "rotating-v4")
    modes = COMMUNICATION_MODES if protocol == "rotating-v4" else LEGACY_COMMUNICATION_MODES
    counts = (0, 1) if legacy else SELFISH_COUNTS
    spec = {
        "models": raw.get("models", ["openai/gpt-6-luna", "anthropic/claude-haiku-5.5"]),
        "communication_modes": raw.get("communication_modes", list(modes)),
        "selfish_counts": raw.get("selfish_counts", list(counts)),
        "seeds": raw.get("seeds", list(range(12))),
        "game": game,
    }
    for field, allowed in (
        ("models", MODELS),
        ("communication_modes", modes),
        ("selfish_counts", counts),
    ):
        values = spec[field]
        if not isinstance(values, list) or not values or any(v not in allowed for v in values):
            raise ValueError(f"Invalid {field}")
        if len(set(values)) != len(values):
            raise ValueError(f"Duplicate {field}")
    if any(type(k) is not int for k in spec["selfish_counts"]):
        raise ValueError("selfish_counts must contain integers")
    seeds = spec["seeds"]
    if not isinstance(seeds, list) or not seeds or any(type(s) is not int or s < 0 for s in seeds):
        raise ValueError("seeds must be a nonempty list of nonnegative integers")
    if len(set(seeds)) != len(seeds):
        raise ValueError("Duplicate seeds")
    if not isinstance(spec["game"], dict) or set(spec["game"]) & {
        "model",
        "communication",
        "selfish_count",
        "seed",
    }:
        raise ValueError("Set model, communication, roles and seeds through the matrix axes")
    try:
        defaults = (
            {"protocol_version": "rotating-v2"} if legacy else
            {"protocol_version": "rotating-v4", "players": 10, "rounds": 10}
        )
        config = Config(**{
            **defaults, **spec["game"], "selfish_count": spec["selfish_counts"][0]
        })
    except TypeError as exc:
        raise ValueError(f"Invalid game settings: {exc}") from None
    if config.protocol_version not in ("rotating-v2", "rotating-v3", "rotating-v4") or config.selfish_persona != "neutral":
        raise ValueError("This matrix requires rotating-v2/v3/v4 and neutral personalities")
    spec["game"] = {
        k: v
        for k, v in config.to_dict().items()
        if k not in {"model", "communication", "selfish_count", "seed"}
    }
    return spec


def episode_plan(spec):
    spec = normalize_spec(spec)
    base = Config(**spec["game"], selfish_count=spec["selfish_counts"][0])
    plan = []
    for seed in spec["seeds"]:
        cells = [
            (model, k, mode)
            for model in spec["models"]
            for k in spec["selfish_counts"]
            for mode in spec["communication_modes"]
        ]
        random.Random(derived_seed(seed, "matrix_order")).shuffle(cells)
        for model, k, mode in cells:
            config = replace(base, model=model, selfish_count=k, communication=mode, seed=seed)
            name = f"seed-{seed}__{model.replace('/', '__')}__selfish-{k}__{mode}"
            plan.append({"episode_id": name, "config": config.to_dict()})
    return plan


def preview(raw):
    spec = normalize_spec(raw)
    plan = episode_plan(spec)
    config = Config(**spec["game"], selfish_count=spec["selfish_counts"][0])
    return {
        "status": "preview",
        "schema_version": SCHEMA_VERSION,
        "spec": spec,
        "episodes": len(plan),
        "encounters": len(plan) * config.rounds * config.players // 2,
        "requests_before_retries": sum(
            Config(**entry["config"]).expected_requests for entry in plan
        ),
        "midpoint_after_round": config.midpoint_round if config.has_midpoint else None,
        "requests_per_episode": {
            mode: replace(config, communication=mode).expected_requests
            for mode in spec["communication_modes"]
        },
        "launch": "Add --execute to run this matrix; --backend scripted uses no hosted model.",
    }


def make_provider(config):
    return ScriptedProvider(config) if config.backend == "scripted" else OpenRouterProvider(config)


def run_matrix(raw, output, *, resume=False, provider_factory=make_provider, progress=print):
    from .matrix_analysis import analyze_matrix

    spec = normalize_spec(raw)
    output = Path(output)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "spec": spec,
        "plan": episode_plan(spec),
        "provenance": provenance(),
        "counts": preview(spec),
    }
    if not resume:
        output.mkdir(parents=True, exist_ok=False)
    elif not (output / "matrix_manifest.json").is_file():
        raise ValueError("Resume requires an existing matrix manifest")
    with exclusive_run(output):
        if resume:
            if read_json(output / "matrix_manifest.json") != manifest:
                raise ValueError(
                    "Matrix configuration or source changed; resume with the saved runtime"
                )
        else:
            write_json(output / "matrix_manifest.json", manifest)
            write_json(output / "spec.json", spec)
            shutil.copytree(
                Path(__file__).parent,
                output / "runtime/swarm_game",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            write_json(output / "runtime/provenance.json", manifest["provenance"])
            lock = Path.cwd() / "uv.lock"
            if lock.exists():
                shutil.copy2(lock, output / "runtime/uv.lock")
        try:
            # One capability check per model before any paid generations.
            if spec["game"]["backend"] == "openrouter":
                catalog = []
                for model in spec["models"]:
                    provider = provider_factory(Config(
                        **spec["game"], model=model, selfish_count=spec["selfish_counts"][0]
                    ))
                    try:
                        catalog.append(provider.catalog_entry())
                    finally:
                        provider.close()
                write_json(output / "catalog.json", catalog)
            for entry in manifest["plan"]:
                name, config = entry["episode_id"], Config(**entry["config"])
                episode = output / "episodes" / name
                progress(name)
                provider = provider_factory(config)
                try:
                    # Completed episodes also pass manifest/source checks; no calls replay.
                    run_episode(
                        config,
                        provider,
                        episode,
                        resume=resume and episode.exists(),
                        progress=progress,
                    )
                finally:
                    if hasattr(provider, "close"):
                        provider.close()
        except BaseException:
            analyze_matrix(output)
            raise
        return analyze_matrix(output)
