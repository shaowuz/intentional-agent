"""Typed configuration for the ranked 4-agent tournament."""

from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ipd.config import LLMConfig, PricingConfig
from ipd.utils import stable_hash


@dataclass
class TournamentConfig:
    """Top-level configuration for one ranked tournament run."""

    name: str = "ranked_tournament"
    seed: int = 20240501
    output_dir: str = "results/ranked_tournament"
    n_rounds: int = 15
    agents: List[str] = field(default_factory=lambda: ["A", "B", "C", "D"])
    continue_prob: float = 0.95
    max_stages: int = 500
    ranking_points: List[float] = field(
        default_factory=lambda: [3.0, 2.0, 1.0, 0.0]
    )
    max_decision_retries: int = 3
    max_reflection_retries: int = 3
    llm: LLMConfig = field(default_factory=LLMConfig)

    # ------------------------------------------------------------------ #
    def validate(self) -> None:
        if not self.agents:
            raise ValueError("At least two agents are required.")
        if len(self.agents) % 2 != 0:
            raise ValueError("The number of agents must be even for pair-games.")
        if len(set(self.agents)) != len(self.agents):
            raise ValueError("Agent labels must be unique.")
        if len(self.agents) < 4:
            raise ValueError("The tournament requires at least four agents.")
        if self.n_rounds < 1:
            raise ValueError("n_rounds must be >= 1.")
        if not (0.0 < self.continue_prob < 1.0):
            raise ValueError("continue_prob must be in (0, 1).")
        if self.max_stages < 1:
            raise ValueError("max_stages must be >= 1.")
        if len(self.ranking_points) != len(self.agents):
            raise ValueError(
                "ranking_points must contain exactly one value per occupied "
                "ranking position (one per agent)."
            )
        if self.max_decision_retries < 0:
            raise ValueError("max_decision_retries must be >= 0.")
        if self.max_reflection_retries < 0:
            raise ValueError("max_reflection_retries must be >= 0.")
        if self.llm.temperature < 0:
            raise ValueError("temperature must be >= 0.")
        if self.llm.max_tokens < 1:
            raise ValueError("max_tokens must be >= 1.")

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def fingerprint(self) -> str:
        return stable_hash(self.to_dict())


_TOP_LEVEL_KEYS = {
    "name",
    "seed",
    "output_dir",
    "n_rounds",
    "agents",
    "continue_prob",
    "max_stages",
    "ranking_points",
    "max_decision_retries",
    "max_reflection_retries",
    "llm",
}

_LLM_KEYS = {
    "provider",
    "model",
    "temperature",
    "top_p",
    "max_tokens",
    "seed",
    "api_key_env",
    "base_url",
    "timeout",
    "max_retries",
    "pricing",
}

_PRICING_KEYS = {"input_per_1k_tokens", "output_per_1k_tokens"}


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


def _build_llm(raw: Optional[dict]) -> LLMConfig:
    if raw is None:
        return LLMConfig()
    unknown = set(raw) - _LLM_KEYS
    if unknown:
        raise ValueError(
            "Unknown llm config key(s): " + ", ".join(sorted(unknown))
        )
    pricing_raw = raw.get("pricing", {}) or {}
    unknown_pricing = set(pricing_raw) - _PRICING_KEYS
    if unknown_pricing:
        raise ValueError(
            "Unknown pricing config key(s): "
            + ", ".join(sorted(unknown_pricing))
        )
    pricing = PricingConfig(**pricing_raw)
    kwargs = {k: v for k, v in raw.items() if k != "pricing"}
    return LLMConfig(pricing=pricing, **kwargs)


def config_from_dict(raw: dict) -> TournamentConfig:
    """Build and validate a config from a plain dictionary."""
    if raw is None:
        raw = {}
    unknown = set(raw) - _TOP_LEVEL_KEYS
    if unknown:
        raise ValueError(
            "Unknown config key(s): " + ", ".join(sorted(unknown))
        )
    data = dict(raw)
    llm = _build_llm(data.pop("llm", None))
    config = TournamentConfig(llm=llm, **data)
    config.validate()
    return config


def load_config(path: str, overrides: Optional[dict] = None) -> TournamentConfig:
    """Load a YAML configuration file with optional nested overrides."""
    import yaml

    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if overrides:
        raw = _deep_merge(raw, overrides)
    return config_from_dict(raw)


def save_config_snapshot(config: TournamentConfig, path: str) -> None:
    """Persist the resolved configuration next to the results."""
    import yaml

    from ipd.utils import ensure_dir

    ensure_dir(os.path.dirname(os.path.abspath(path)))
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(config.to_dict(), fh, sort_keys=False)
