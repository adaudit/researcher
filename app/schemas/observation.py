from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ObservationCreate(BaseModel):
    offer_id: str | None = None
    artifact_id: str | None = None
    bank_id: str
    category: str = Field(
        ...,
        description=(
            "audience_desire | audience_objection | proof_claim | hook_pattern | "
            "mechanism_insight | competitive_signal | research_finding | "
            "landing_page_claim | transcript_highlight | performance_signal"
        ),
    )
    statement: str
    evidence_refs: list[str] | None = None
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    freshness_window_days: int = 30
    domain_risk_level: str = "standard"
    metadata: dict[str, Any] | None = None


class ObservationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    account_id: str
    offer_id: str | None = None
    artifact_id: str | None = None
    bank_id: str
    category: str
    statement: str
    evidence_refs: list[str] | None = None
    confidence_score: float
    freshness_window_days: int
    review_status: str
    domain_risk_level: str
    hindsight_memory_ref: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
