"""LLM backend factory."""

from __future__ import annotations

from typing import Optional

from ..config import LLMConfig
from .base import LLMClient
from .mock import MockClient
from .openai_compatible import OpenAICompatibleClient
from .anthropic import AnthropicClient

__all__ = [
    "LLMClient",
    "MockClient",
    "OpenAICompatibleClient",
    "AnthropicClient",
    "build_client",
]


def build_client(config: LLMConfig) -> LLMClient:
    """Instantiate the backend described by ``config``."""
    provider = config.provider.lower()
    if provider == "mock":
        return MockClient(model=config.model)
    if provider in ("openai", "openai-compatible", "azure", "vllm", "ollama"):
        return OpenAICompatibleClient(
            model=config.model,
            temperature=config.temperature,
            top_p=config.top_p,
            max_tokens=config.max_tokens,
            seed=config.seed,
            api_key_env=config.api_key_env,
            base_url=config.base_url,
            timeout=config.timeout,
            max_retries=config.max_retries,
        )
    if provider == "anthropic":
        return AnthropicClient(
            model=config.model,
            temperature=config.temperature,
            top_p=config.top_p,
            max_tokens=config.max_tokens,
            seed=config.seed,
            api_key_env=config.api_key_env,
            base_url=config.base_url,
            timeout=config.timeout,
            max_retries=config.max_retries,
        )
    raise ValueError(
        f"Unknown LLM provider {config.provider!r}. "
        "Use 'mock', 'openai', or 'anthropic'."
    )
