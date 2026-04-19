"""POST /v1/research-cycles — start onboarding or weekly research workflow.
GET  /v1/research-cycles/{id} — fetch status and outputs.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_account_id
from app.db.models.workflow import WorkflowJob
from app.db.session import get_db
from app.schemas.workflow import ResearchCycleCreate, WorkflowJobResponse

router = APIRouter()

# Lazy import map to avoid circular imports at module level
WORKFLOW_TASK_MAP = {
    "onboarding": "app.orchestrator.workflows.onboarding.run_onboarding",
    "offer_refresh": "app.orchestrator.workflows.offer_refresh.run_offer_refresh",
    "landing_page_decomposition": "app.orchestrator.workflows.landing_page_decomposition.run_decomposition",
    "weekly_refresh": "app.orchestrator.workflows.weekly_refresh.run_top_ad_refresh",
    "health_evidence_refresh": "app.orchestrator.workflows.health_evidence_refresh.run_health_refresh",
    "iteration_synthesis": "app.orchestrator.workflows.iteration_synthesis.run_iteration_synthesis",
}


@router.post("", response_model=WorkflowJobResponse, status_code=status.HTTP_201_CREATED)
async def start_research_cycle(
    body: ResearchCycleCreate,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> WorkflowJob:
    task_name = WORKFLOW_TASK_MAP.get(body.workflow_type)
    if not task_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown workflow type: {body.workflow_type}",
        )

    job_id = f"wf_{uuid4().hex[:12]}"

    job = WorkflowJob(
        id=job_id,
        account_id=account_id,
        offer_id=body.offer_id,
        workflow_type=body.workflow_type,
        state="queued",
        input_payload=body.input_payload,
        step_log=[],
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Dispatch to Celery
    from app.orchestrator.engine import celery_app

    task_args = [account_id, body.offer_id]
    if body.workflow_type == "landing_page_decomposition":
        url = (body.input_payload or {}).get("url", "")
        if not url:
            raise HTTPException(status_code=400, detail="URL required for page decomposition")
        task_args.append(url)
    elif body.workflow_type == "health_evidence_refresh":
        queries = (body.input_payload or {}).get("queries", [])
        task_args.append(queries)
    else:
        task_args.append(body.input_payload or {})

    result = celery_app.send_task(task_name, args=task_args, task_id=job_id)

    job.celery_task_id = result.id
    job.state = "acquiring"
    await db.commit()

    return job


@router.get("/{cycle_id}", response_model=WorkflowJobResponse)
async def get_research_cycle(
    cycle_id: str,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> WorkflowJob:
    result = await db.execute(
        select(WorkflowJob).where(
            WorkflowJob.id == cycle_id,
            WorkflowJob.account_id == account_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Research cycle not found")

    # Check Celery task status if still running
    if job.state not in ("completed", "published", "failed"):
        from app.orchestrator.engine import celery_app

        if job.celery_task_id:
            task_result = celery_app.AsyncResult(job.celery_task_id)
            if task_result.ready():
                if task_result.successful():
                    job.state = "approved"
                    job.output_payload = task_result.result
                else:
                    job.state = "failed"
                    job.error_message = str(task_result.result)
                await db.commit()

    return job
