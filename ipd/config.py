"""Typed configuration objects and YAML loading."""

from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass, field
from typing import Any, List, Optional

from .utils import stable_hash


@dataclass
class PopulationConfig:
    """Definition of the agent population."""

    priors: List[float] = field(default_factory=lambda: [0.1, 0.3, 0.5, 0.7, 0.9])
    agents_per_prior: int = 10

    def n_agents(self) -> int:
        return len(self.priors) * self.agents_per_prior


@dataclass
class PricingConfig:
    """Per-1k-token prices used to estimate cost.  Defaults to zero (free/mock)."""

    input_per_1k_tokens: float = 0.0
    output_per_1k_tokens: float = 0.0


@dataclass
class LLMConfig:
    """Configuration for the language-model backend."""

    provider: str = "mock"  # mock | openai | anthropic
    model: str = "mock-strategic"
    temperature: float = 0.7
    top_p: float = 1.0
    max_tokens: int = 300
    seed: Optional[int] = None
    api_key_env: str = "OPENAI_API_KEY"
    base_url: Optional[str] = None
    timeout: float = 60.0
    max_retries: int = 4
    pricing: PricingConfig = field(default_factory=PricingConfig)


@dataclass
class MemoryConfig:
    """How much history to expose to the model in each prompt.

    ``0`` means "unlimited" (render everything).  The default of 0 keeps the
    prompt view lossless: completed games contribute their full action strings
    (which reconstruct all payoffs) and the current game shows every round.
    """

    recent_rounds_in_prompt: int = 0
    max_completed_game_lines: int = 0


@dataclass
class ExperimentConfig:
    """Top-level experiment configuration."""

    name: str = "experiment"
    seed: int = 12345
    output_dir: str = "results/experiment"
    conditions: List[str] = field(default_factory=lambda: ["fixed", "random"])
    games_per_agent: int = 50
    fixed_rounds: int = 20
    continue_prob: float = 0.95
    max_rounds_random: int = 200
    pairing_strategy: str = "round_robin"  # round_robin | random
    population: PopulationConfig = field(default_factory=PopulationConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)

    # ------------------------------------------------------------------ #
    def validate(self) -> None:
        if not self.conditions:
            raise ValueError("At least one condition is required.")
        for cond in self.conditions:
            if cond not in ("fixed", "random"):
                raise ValueError(f"Unknown condition '{cond}'. Use 'fixed' or 'random'.")
        if self.games_per_agent < 1:
            raise ValueError("games_per_agent must be >= 1.")
        if self.fixed_rounds < 1:
            raise ValueError("fixed_rounds must be >= 1.")
        if not (0.0 < self.continue_prob < 1.0):
            raise ValueError("continue_prob must be in (0, 1).")
        if self.population.agents_per_prior < 1:
            raise ValueError("agents_per_prior must be >= 1.")
        if self.population.n_agents() % 2 != 0:
            raise ValueError("Total number of agents must be even to allow pairing.")
        for p in self.population.priors:
            if not (0.0 <= p <= 1.0):
                raise ValueError(f"Prior {p} must be in [0, 1].")
        if self.pairing_strategy not in ("round_robin", "random"):
            raise ValueError("pairing_strategy must be 'round_robin' or 'random'.")

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def fingerprint(self) -> str:
        """Stable fingerprint of the configuration (for provenance)."""
        return stable_hash(self.to_dict())


def _resolve_type(annotation):
    """Resolve string annotations used by ``from __future__ import annotations``."""
    if not isinstance(annotation, str):
        return annotation
    mapping = {
        "PopulationConfig": PopulationConfig,
        "PricingConfig": PricingConfig,
        "LLMConfig": LLMConfig,
        "MemoryConfig": MemoryConfig,
        "List[float]": list,
        "Optional[int]": (int, type(None)),
        "Optional[str]": (str, type(None)),
        "List[str]": list,
        "str": str,
        "int": int,
        "float": float,
        "dict": dict,
    }
    return mapping.get(annotation, annotation)


def _build(dataclass_type, data: Any):
    """Recursively construct nested dataclasses from plain dicts."""
    if data is None:
        return dataclass_type()
    if dataclasses.is_dataclass(dataclass_type):
        kwargs = {}
        field_names = {f.name: f for f in dataclasses.fields(dataclass_type)}
        for key, value in data.items():
            if key not in field_names:
                raise ValueError(
                    f"Unknown config key '{key}' for {dataclass_type.__name__}."
                )
            resolved = _resolve_type(field_names[key].type)
            if dataclasses.is_dataclass(resolved):
                kwargs[key] = _build(resolved, value)
            else:
                kwargs[key] = value
        return dataclass_type(**kwargs)
    return data


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str, overrides: Optional[dict] = None) -> ExperimentConfig:
    """Load a YAML config file into an :class:`ExperimentConfig`.

    ``overrides`` is an optional nested dict merged on top of the file contents;
    it is convenient for CLI flags such as ``--mock`` or ``--output-dir``.
    """
    import yaml

    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    if overrides:
        raw = _deep_merge(raw, overrides)

    config = _build(ExperimentConfig, raw)
    config.validate()
    return config


def save_config_snapshot(config: ExperimentConfig, path: str) -> None:
    """Persist the resolved configuration next to the results."""
    import yaml

    from .utils import ensure_dir

    ensure_dir(os.path.dirname(os.path.abspath(path)))
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(config.to_dict(), fh, sort_keys=False)
