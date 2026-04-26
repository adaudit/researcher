from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ApprovalResponse(BaseModel):
    id: str
    account_id: str
    offer_id: str | None
    approval_type: str
    status: str
    workflow_job_id: str | None
    payload: dict[str, Any] | None
    grade_trajectory: list[dict[str, Any]] | None
    rejection_reason: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApprovalDecision(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")
    rejection_reason: str | None = None
