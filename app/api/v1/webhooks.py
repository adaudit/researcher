"""POST /v1/webhooks/performance — ingest ad, email, or page performance feedback."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_account_id
from app.core.events import DomainEvent, EventTopic, event_bus
from app.db.models.workflow import WorkflowJob
from app.db.session import get_db
from app.schemas.iteration import PerformanceFeedbackPayload

router = APIRouter()


@router.post("/performance", status_code=status.HTTP_202_ACCEPTED)
async def receive_performance_feedback(
    body: PerformanceFeedbackPayload,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Ingest external performance data (ad metrics, email stats, page analytics).

    This triggers the performance feedback workflow which retains outcome
    data and can trigger iteration synthesis when patterns emerge.
    """
    job_id = f"wf_{uuid4().hex[:12]}"

    job = WorkflowJob(
        id=job_id,
        account_id=account_id,
        offer_id=body.offer_id,
        workflow_type="performance_feedback",
        state="queued",
        input_payload=body.model_dump(),
        step_log=[],
    )
    db.add(job)
    await db.commit()

    await event_bus.publish(DomainEvent(
        topic=EventTopic.PERFORMANCE_FEEDBACK_RECEIVED,
        payload={
            "workflow_id": job_id,
            "asset_type": body.asset_type,
            "platform": body.platform,
        },
        account_id=account_id,
        offer_id=body.offer_id,
    ))

    return {
        "status": "accepted",
        "workflow_id": job_id,
        "message": "Performance feedback queued for processing",
    }
