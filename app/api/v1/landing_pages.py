"""POST /v1/landing-page/decompose — analyze a page and embedded media."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_account_id
from app.db.models.workflow import WorkflowJob
from app.db.session import get_db
from app.schemas.workflow import LandingPageDecomposeRequest, WorkflowJobResponse

router = APIRouter()


@router.post("/decompose", response_model=WorkflowJobResponse, status_code=status.HTTP_201_CREATED)
async def decompose_landing_page(
    body: LandingPageDecomposeRequest,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> WorkflowJob:
    job_id = f"wf_{uuid4().hex[:12]}"

    job = WorkflowJob(
        id=job_id,
        account_id=account_id,
        offer_id=body.offer_id,
        workflow_type="landing_page_decomposition",
        state="queued",
        input_payload={
            "url": body.url,
            "extract_video": body.extract_video,
            "depth": body.depth,
        },
        step_log=[],
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Dispatch to Celery
    from app.orchestrator.engine import celery_app

    result = celery_app.send_task(
        "app.orchestrator.workflows.landing_page_decomposition.run_decomposition",
        args=[account_id, body.offer_id, body.url, body.extract_video],
        task_id=job_id,
    )

    job.celery_task_id = result.id
    job.state = "acquiring"
    await db.commit()

    return job
