"""Primer API — upload, list, and update living primer documents.

POST   /v1/primers/{offer_id}          — upload a primer
GET    /v1/primers/{offer_id}          — list all primers for an offer
PUT    /v1/primers/{offer_id}/{type}   — update a specific primer
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_account_id
from app.knowledge.primers import PrimerType, primer_store

router = APIRouter()


class PrimerUpload(BaseModel):
    primer_type: str = Field(..., description="One of: ad_primer, hook_primer, headline_primer")
    content: str = Field(..., min_length=10, description="Primer document content")


class PrimerResponse(BaseModel):
    primer_type: str
    offer_id: str
    content: str
    memory_id: str | None = None


class PrimerUpdateRequest(BaseModel):
    content: str = Field(..., min_length=10, description="Updated primer content")


def _parse_primer_type(raw: str) -> PrimerType:
    try:
        return PrimerType(raw)
    except ValueError:
        valid = [pt.value for pt in PrimerType]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid primer type '{raw}'. Must be one of: {valid}",
        )


@router.post("/{offer_id}", response_model=PrimerResponse, status_code=status.HTTP_201_CREATED)
async def upload_primer(
    offer_id: str,
    body: PrimerUpload,
    account_id: str = Depends(get_current_account_id),
) -> PrimerResponse:
    """Upload a new primer document for an offer."""
    pt = _parse_primer_type(body.primer_type)
    result = await primer_store.save(
        account_id=account_id,
        offer_id=offer_id,
        primer_type=pt,
        content=body.content,
    )
    return PrimerResponse(
        primer_type=pt.value,
        offer_id=offer_id,
        content=body.content,
        memory_id=result.get("id"),
    )


@router.get("/{offer_id}", response_model=list[PrimerResponse])
async def list_primers(
    offer_id: str,
    account_id: str = Depends(get_current_account_id),
) -> list[PrimerResponse]:
    """List all primers for an offer."""
    primers = await primer_store.list_for_offer(account_id, offer_id)
    return [
        PrimerResponse(
            primer_type=p["primer_type"],
            offer_id=offer_id,
            content=p.get("content", ""),
            memory_id=p.get("memory_id"),
        )
        for p in primers
    ]


@router.put("/{offer_id}/{primer_type}", response_model=PrimerResponse)
async def update_primer(
    offer_id: str,
    primer_type: str,
    body: PrimerUpdateRequest,
    account_id: str = Depends(get_current_account_id),
) -> PrimerResponse:
    """Update a specific primer for an offer."""
    pt = _parse_primer_type(primer_type)
    result = await primer_store.save(
        account_id=account_id,
        offer_id=offer_id,
        primer_type=pt,
        content=body.content,
    )
    return PrimerResponse(
        primer_type=pt.value,
        offer_id=offer_id,
        content=body.content,
        memory_id=result.get("id"),
    )
