"""Anthropic Messages API backend (plain ``requests``)."""

from __future__ import annotations

import os
import time
from typing import Optional

from ..usage import LLMResponse
from .base import LLMClient


class AnthropicClient(LLMClient):
    provider = "anthropic"

    def __init__(
        self,
        model: str,
        temperature: float = 0.7,
        top_p: float = 1.0,
        max_tokens: int = 300,
        seed: Optional[int] = None,
        api_key_env: str = "ANTHROPIC_API_KEY",
        base_url: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 4,
    ):
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.seed = seed
        self.api_key_env = api_key_env
        self.base_url = (base_url or "https://api.anthropic.com").rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    def _api_key(self) -> str:
        key = os.environ.get(self.api_key_env)
        if not key:
            raise RuntimeError(
                f"Environment variable {self.api_key_env!r} is not set."
            )
        return key

    def complete(self, system: str, user: str, **kwargs) -> LLMResponse:
        import requests

        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self._api_key(),
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
        }

        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.post(
                    url, headers=headers, json=payload, timeout=self.timeout
                )
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise RuntimeError(
                        f"HTTP {resp.status_code}: {resp.text[:300]}"
                    )
                resp.raise_for_status()
                data = resp.json()
                parts = data.get("content", []) or []
                text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
                usage = data.get("usage", {}) or {}
                return LLMResponse(
                    text=text,
                    input_tokens=int(usage.get("input_tokens", 0)),
                    output_tokens=int(usage.get("output_tokens", 0)),
                    model=data.get("model", self.model),
                    provider=self.provider,
                    raw=None,
                )
            except Exception as exc:  # noqa: BLE001 - retry any transient error
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(min(30.0, 2.0 ** attempt))
        raise RuntimeError(
            f"Anthropic request failed after {self.max_retries + 1} attempts: "
            f"{last_exc}"
        )
