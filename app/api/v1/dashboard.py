"""Dashboard stats — aggregate counts for the home page."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_account_id
from app.db.models.approval import Approval
from app.db.models.creative import CreativeAsset
from app.db.models.performance import IngestQuestion, PerformanceSnapshot
from app.db.models.workflow import WorkflowJob
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/summary")
async def dashboard_summary(
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Aggregate stats for the dashboard home page."""

    # Active creative assets
    active_ads_q = select(func.count(CreativeAsset.id)).where(
        CreativeAsset.account_id == account_id,
    )
    active_ads = (await db.execute(active_ads_q)).scalar_one() or 0

    # Winners — performance snapshots tagged as winner tier
    winners_q = select(
        func.count(func.distinct(PerformanceSnapshot.external_ad_id))
    ).where(
        PerformanceSnapshot.account_id == account_id,
        PerformanceSnapshot.performance_tier == "winner",
    )
    winners = (await db.execute(winners_q)).scalar_one() or 0

    # Pending approvals
    pending_approvals_q = select(func.count(Approval.id)).where(
        Approval.account_id == account_id,
        Approval.status == "pending",
    )
    pending_approvals = (await db.execute(pending_approvals_q)).scalar_one() or 0

    # Pending ingest questions
    pending_questions_q = select(func.count(IngestQuestion.id)).where(
        IngestQuestion.account_id == account_id,
        IngestQuestion.status == "pending",
    )
    pending_questions = (await db.execute(pending_questions_q)).scalar_one() or 0

    # Active workflows
    active_workflows_q = select(func.count(WorkflowJob.id)).where(
        WorkflowJob.account_id == account_id,
        WorkflowJob.state.in_(
            ["queued", "acquiring", "normalizing", "retaining", "reasoning", "reflecting"],
        ),
    )
    active_workflows = (await db.execute(active_workflows_q)).scalar_one() or 0

    # Recent reflection count (last 30 days)
    recent_workflows_q = select(func.count(WorkflowJob.id)).where(
        WorkflowJob.account_id == account_id,
        WorkflowJob.state == "published",
    )
    completed_workflows = (await db.execute(recent_workflows_q)).scalar_one() or 0

    return {
        "active_ads": active_ads,
        "winners": winners,
        "pending_approvals": pending_approvals,
        "pending_questions": pending_questions,
        "active_workflows": active_workflows,
        "completed_workflows": completed_workflows,
    }
