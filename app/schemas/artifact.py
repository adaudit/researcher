from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ArtifactImportItem(BaseModel):
    """Single item in an artifact import batch."""

    source_type: str = Field(
        ..., description="api | upload | crawler | transcript | research | manual"
    )
    source_url: str | None = None
    artifact_kind: str = Field(
        ...,
        description=(
            "landing_page | ad_creative | comment_dump | transcript | "
            "screenshot | research_doc | upload"
        ),
    )
    content_type: str | None = None  # auto-detected if not provided
    metadata: dict[str, Any] | None = None


class ArtifactImportRequest(BaseModel):
    offer_id: str | None = None
    items: list[ArtifactImportItem] = Field(..., min_length=1, max_length=50)


class ArtifactResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    account_id: str
    offer_id: str | None = None
    source_type: str
    source_url: str | None = None
    canonical_url: str | None = None
    content_type: str
    content_hash: str | None = None
    size_bytes: int | None = None
    artifact_kind: str
    processing_status: str
    freshness_window_days: int
    extracted_metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class ArtifactImportResponse(BaseModel):
    imported_count: int
    artifacts: list[ArtifactResponse]
    workflow_id: str | None = None
