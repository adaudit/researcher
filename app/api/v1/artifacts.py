"""POST /v1/artifacts/import — ingest links, uploads, ad references, or exports."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_account_id
from app.core.events import DomainEvent, EventTopic, event_bus
from app.db.models.artifact import Artifact
from app.db.session import get_db
from app.schemas.artifact import ArtifactImportRequest, ArtifactImportResponse, ArtifactResponse

router = APIRouter()


@router.post("/import", response_model=ArtifactImportResponse, status_code=status.HTTP_201_CREATED)
async def import_artifacts(
    body: ArtifactImportRequest,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    artifacts: list[Artifact] = []

    for item in body.items:
        artifact = Artifact(
            id=f"art_{uuid4().hex[:12]}",
            account_id=account_id,
            offer_id=body.offer_id,
            source_type=item.source_type,
            source_url=item.source_url,
            canonical_url=item.source_url,
            content_type=item.content_type or "application/octet-stream",
            artifact_kind=item.artifact_kind,
            processing_status="pending",
            extracted_metadata=item.metadata,
        )
        db.add(artifact)
        artifacts.append(artifact)

    await db.commit()
    for a in artifacts:
        await db.refresh(a)

    # Emit events
    for a in artifacts:
        await event_bus.publish(DomainEvent(
            topic=EventTopic.ARTIFACT_INGESTED,
            payload={"artifact_id": a.id, "kind": a.artifact_kind},
            account_id=account_id,
            offer_id=body.offer_id,
        ))

    return {
        "imported_count": len(artifacts),
        "artifacts": artifacts,
        "workflow_id": None,
    }
