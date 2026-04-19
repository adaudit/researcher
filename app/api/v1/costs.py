"""Cost tracking API — view LLM spend per account."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_account_id
from app.services.intelligence.cost_tracker import cost_tracker

router = APIRouter()


@router.get("/summary")
async def get_cost_summary(
    account_id: str = Depends(get_current_account_id),
) -> dict:
    """Get LLM cost summary for this account."""
    summary = cost_tracker.get_account_summary(account_id)
    return {
        "account_id": account_id,
        "total_cost_usd": round(summary.total_cost_usd, 4),
        "total_calls": summary.calls,
        "by_provider": dict(summary.by_provider),
        "by_worker": dict(summary.by_worker),
        "by_model": dict(summary.by_model),
    }


@router.get("/platform-total")
async def get_platform_total() -> dict:
    """Get total LLM cost across all accounts (admin)."""
    total = cost_tracker.get_total_cost()
    summaries = cost_tracker.get_all_summaries()
    return {
        "total_cost_usd": round(total, 4),
        "accounts": len(summaries),
        "per_account": {
            aid: round(s.total_cost_usd, 4)
            for aid, s in summaries.items()
        },
    }
