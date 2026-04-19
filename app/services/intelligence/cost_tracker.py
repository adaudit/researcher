"""LLM cost tracking per account.

Tracks every LLM call's token usage and estimated cost. Stored in-memory
with periodic flush to database. Provides:
  - Per-account cost tracking
  - Per-provider cost breakdown
  - Per-worker cost attribution
  - Budget alerts when approaching limits
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Cost per million tokens (input / output) by provider + model
COST_TABLE: dict[str, dict[str, tuple[float, float]]] = {
    "anthropic": {
        "claude-opus-4-6": (15.0, 75.0),
        "claude-sonnet-4-6": (3.0, 15.0),
        "claude-haiku-4-5-20251001": (0.80, 4.0),
    },
    "google": {
        "gemini-2.5-flash": (0.15, 0.60),
        "gemini-2.5-pro": (1.25, 10.0),
        "gemini-embedding-001": (0.0, 0.0),
    },
    "openai": {
        "gpt-4.1": (2.0, 8.0),
        "gpt-4.1-mini": (0.40, 1.60),
        "o3": (10.0, 40.0),
        "text-embedding-3-small": (0.02, 0.0),
    },
    "zai": {
        "glm-5.1": (0.95, 3.15),
    },
    "local": {
        "": (0.0, 0.0),
    },
    "twelvelabs": {
        "Marengo-retrieval-2.7": (0.0, 0.0),  # per-minute pricing handled separately
    },
}


@dataclass
class UsageRecord:
    """One LLM call's usage."""

    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    worker_name: str
    account_id: str
    timestamp: str = ""


@dataclass
class AccountCostSummary:
    """Cost summary for one account."""

    account_id: str
    total_cost_usd: float = 0.0
    calls: int = 0
    by_provider: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    by_worker: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    by_model: dict[str, float] = field(default_factory=lambda: defaultdict(float))


class CostTracker:
    """Tracks LLM costs per account."""

    def __init__(self) -> None:
        self._records: list[UsageRecord] = []
        self._account_totals: dict[str, AccountCostSummary] = {}

    def record(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        account_id: str = "",
        worker_name: str = "",
    ) -> float:
        """Record a usage event and return estimated cost in USD."""
        cost = self._estimate_cost(provider, model, input_tokens, output_tokens)

        record = UsageRecord(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            worker_name=worker_name,
            account_id=account_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._records.append(record)

        # Update account summary
        if account_id:
            summary = self._account_totals.setdefault(
                account_id, AccountCostSummary(account_id=account_id)
            )
            summary.total_cost_usd += cost
            summary.calls += 1
            summary.by_provider[provider] += cost
            summary.by_worker[worker_name] += cost
            summary.by_model[model] += cost

        return cost

    def get_account_summary(self, account_id: str) -> AccountCostSummary:
        """Get cost summary for an account."""
        return self._account_totals.get(
            account_id, AccountCostSummary(account_id=account_id)
        )

    def get_all_summaries(self) -> dict[str, AccountCostSummary]:
        """Get cost summaries for all accounts."""
        return dict(self._account_totals)

    def get_total_cost(self) -> float:
        """Get total cost across all accounts."""
        return sum(s.total_cost_usd for s in self._account_totals.values())

    def _estimate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost in USD based on provider/model pricing."""
        provider_costs = COST_TABLE.get(provider, {})
        cost_per_m = provider_costs.get(model)

        if cost_per_m is None:
            # Try partial match
            for model_key, costs in provider_costs.items():
                if model_key in model or model in model_key:
                    cost_per_m = costs
                    break

        if cost_per_m is None:
            cost_per_m = (1.0, 5.0)  # conservative default

        input_cost, output_cost = cost_per_m
        return (input_tokens * input_cost / 1_000_000) + (output_tokens * output_cost / 1_000_000)

    def flush(self) -> list[UsageRecord]:
        """Flush buffered records (for persistence to DB)."""
        records = self._records.copy()
        self._records.clear()
        return records


# Module-level singleton
cost_tracker = CostTracker()
