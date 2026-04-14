from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IterationHeaderCreate(BaseModel):
    offer_id: str
    asset_type: str = Field(
        ...,
        description="landing_page | advertorial | ad_creative | email | vsl",
    )
    asset_section: str | None = None
    target: str
    reason: str
    constraint: str | None = None
    evidence_refs: list[str] | None = None
    evidence_detail: dict[str, Any] | None = None
    priority: str = "medium"  # critical | high | medium | low
    expected_effect: str | None = None


class IterationHeaderResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    account_id: str
    offer_id: str
    asset_type: str
    asset_section: str | None = None
    target: str
    reason: str
    constraint: str | None = None
    evidence_refs: list[str] | None = None
    evidence_detail: dict[str, Any] | None = None
    priority: str
    expected_effect: str | None = None
    status: str
    source_workflow_id: str | None = None
    created_at: datetime
    updated_at: datetime


class PerformanceFeedbackPayload(BaseModel):
    offer_id: str
    asset_type: str
    asset_id: str | None = None
    metrics: dict[str, Any]
    period_start: str | None = None
    period_end: str | None = None
    platform: str | None = None  # meta | google | tiktok | email | page
    notes: str | None = None
