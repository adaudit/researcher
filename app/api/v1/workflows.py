"""Workflow status API — list active workflows + per-workflow detail."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_account_id
from app.db.models.workflow import WorkflowJob
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


class WorkflowSummary(BaseModel):
    id: str
    workflow_type: str
    state: str
    offer_id: str | None
    started_at: datetime | None
    completed_at: datetime | None
    step_log: list[dict[str, Any]] | None
    error_message: str | None
    retry_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[WorkflowSummary])
async def list_workflows(
    state: str | None = None,
    workflow_type: str | None = None,
    offer_id: str | None = None,
    limit: int = 50,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> list[WorkflowJob]:
    """List workflows for an account, optionally filtered by state/type."""
    stmt = select(WorkflowJob).where(
        WorkflowJob.account_id == account_id,
    ).order_by(WorkflowJob.created_at.desc()).limit(limit)

    if state:
        stmt = stmt.where(WorkflowJob.state == state)
    if workflow_type:
        stmt = stmt.where(WorkflowJob.workflow_type == workflow_type)
    if offer_id:
        stmt = stmt.where(WorkflowJob.offer_id == offer_id)

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/active", response_model=list[WorkflowSummary])
async def list_active_workflows(
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> list[WorkflowJob]:
    """List currently-running workflows (not yet published or failed)."""
    active_states = [
        "queued", "acquiring", "normalizing",
        "retaining", "reasoning", "reflecting",
        "awaiting_approval",
    ]
    stmt = select(WorkflowJob).where(
        WorkflowJob.account_id == account_id,
        WorkflowJob.state.in_(active_states),
    ).order_by(WorkflowJob.created_at.desc())

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{workflow_id}", response_model=WorkflowSummary)
async def get_workflow(
    workflow_id: str,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> WorkflowJob:
    result = await db.execute(
        select(WorkflowJob).where(
            WorkflowJob.id == workflow_id,
            WorkflowJob.account_id == account_id,
        )
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow
