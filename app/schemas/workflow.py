from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ResearchCycleCreate(BaseModel):
    offer_id: str
    workflow_type: str = Field(
        ...,
        description=(
            "onboarding | offer_refresh | landing_page_decomposition | "
            "weekly_refresh | health_evidence_refresh | iteration_synthesis | "
            "performance_feedback"
        ),
    )
    input_payload: dict[str, Any] | None = None


class WorkflowJobResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    account_id: str
    offer_id: str | None = None
    workflow_type: str
    state: str
    previous_state: str | None = None
    celery_task_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    input_payload: dict[str, Any] | None = None
    output_payload: dict[str, Any] | None = None
    step_log: list[dict[str, Any]] | None = None
    retry_count: int
    created_at: datetime
    updated_at: datetime


class LandingPageDecomposeRequest(BaseModel):
    url: str = Field(..., max_length=2048)
    offer_id: str
    extract_video: bool = True
    depth: str = "full"  # quick | full
