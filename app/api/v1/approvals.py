"""Approval queue — human gate between ideation and writing/creative."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_account_id
from app.db.models.approval import Approval
from app.db.session import get_db
from app.schemas.approval import ApprovalDecision, ApprovalResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[ApprovalResponse])
async def list_approvals(
    status_filter: str = "pending",
    approval_type: str | None = None,
    offer_id: str | None = None,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> list[Approval]:
    stmt = select(Approval).where(
        Approval.account_id == account_id,
        Approval.status == status_filter,
    ).order_by(Approval.created_at.desc())

    if approval_type:
        stmt = stmt.where(Approval.approval_type == approval_type)
    if offer_id:
        stmt = stmt.where(Approval.offer_id == offer_id)

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: str,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> Approval:
    result = await db.execute(
        select(Approval).where(
            Approval.id == approval_id,
            Approval.account_id == account_id,
        )
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    return approval


@router.post("/{approval_id}/decide", response_model=ApprovalResponse)
async def decide_approval(
    approval_id: str,
    body: ApprovalDecision,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> Approval:
    result = await db.execute(
        select(Approval).where(
            Approval.id == approval_id,
            Approval.account_id == account_id,
        )
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    if approval.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Approval already {approval.status}",
        )

    now = datetime.now(timezone.utc)
    approval.status = "approved" if body.action == "approve" else "rejected"
    approval.reviewed_at = now
    approval.rejection_reason = body.rejection_reason

    await db.commit()
    await db.refresh(approval)

    logger.info(
        "approval.decided id=%s type=%s action=%s account=%s",
        approval_id, approval.approval_type, body.action, account_id,
    )

    if body.action == "approve" and approval.workflow_job_id:
        try:
            from app.orchestrator.workflows.full_cycle import dispatch_writing_phase
            dispatch_writing_phase.delay(
                account_id=account_id,
                offer_id=approval.offer_id,
                workflow_job_id=approval.workflow_job_id,
                approved_payload=approval.payload,
            )
            logger.info(
                "approval.writing_phase_dispatched workflow=%s",
                approval.workflow_job_id,
            )
        except Exception as exc:
            logger.warning(
                "approval.dispatch_failed workflow=%s error=%s",
                approval.workflow_job_id, exc,
            )

    if body.action == "reject" and approval.workflow_job_id:
        logger.info(
            "approval.rejected workflow=%s reason=%s",
            approval.workflow_job_id,
            (body.rejection_reason or "")[:200],
        )

    return approval


@router.get("/stats/summary")
async def approval_stats(
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    pending = await db.execute(
        select(Approval).where(
            Approval.account_id == account_id,
            Approval.status == "pending",
        )
    )
    return {
        "pending_count": len(list(pending.scalars().all())),
    }
