"""API usage tracking and cost estimation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class LLMResponse:
    """Normalised response returned by every backend."""

    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    provider: str = ""
    raw: Optional[dict] = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class UsageTracker:
    """Accumulates per-call usage records and estimates cost."""

    input_per_1k: float = 0.0
    output_per_1k: float = 0.0
    records: List[dict] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    n_calls: int = 0

    def log(
        self,
        agent_id: str,
        task: str,
        response: LLMResponse,
        meta: Optional[dict] = None,
    ) -> dict:
        cost = (
            response.input_tokens / 1000.0 * self.input_per_1k
            + response.output_tokens / 1000.0 * self.output_per_1k
        )
        record = {
            "agent_id": agent_id,
            "task": task,
            "provider": response.provider,
            "model": response.model,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
            "cost_usd": round(cost, 8),
        }
        if meta:
            record.update(meta)
        self.records.append(record)
        self.total_input_tokens += response.input_tokens
        self.total_output_tokens += response.output_tokens
        self.total_cost += cost
        self.n_calls += 1
        return record

    def drain(self) -> List[dict]:
        """Return and clear buffered records (for writing to disk)."""
        out = self.records
        self.records = []
        return out

    @property
    def pricing_configured(self) -> bool:
        """True if any per-token price was supplied (otherwise cost is unknown)."""
        return self.input_per_1k > 0.0 or self.output_per_1k > 0.0

    def summary(self) -> Dict[str, float]:
        summary = {
            "n_calls": self.n_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "estimated_cost_usd": round(self.total_cost, 6),
            "pricing_configured": self.pricing_configured,
        }
        if not self.pricing_configured and (
            self.total_input_tokens + self.total_output_tokens
        ) > 0:
            summary["cost_note"] = (
                "pricing not configured: estimated_cost_usd=0 is NOT a true cost. "
                "Set llm.pricing.* or pass --price-in/--price-out, or compute "
                "afterwards with scripts/report_usage.py."
            )
        return summary
