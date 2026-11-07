"""Abstract LLM client interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..usage import LLMResponse


class LLMClient(ABC):
    """Common interface implemented by every backend.

    ``complete`` receives a system prompt and a user prompt and returns an
    :class:`~ipd.usage.LLMResponse`.
    """

    provider: str = "base"
    model: str = ""

    @abstractmethod
    def complete(self, system: str, user: str, **kwargs) -> LLMResponse:
        raise NotImplementedError

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"{self.__class__.__name__}(provider={self.provider!r}, model={self.model!r})"
