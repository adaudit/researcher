"""Seed bank API — manual seed submission and retrieval.

POST   /v1/seeds/{offer_id}        — submit a seed (human gambit or manual input)
GET    /v1/seeds/{offer_id}        — list seeds for an offer
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_account_id
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker, retain_observation

router = APIRouter()


class SeedSubmission(BaseModel):
    content: str = Field(..., min_length=5, description="The seed idea")
    source_type: str = Field(
        "gambit",
        description="Source: gambit | swipe | organic | research | template | internal | new_style",
    )
    segment: str | None = Field(None, description="Target segment if known")
    awareness_level: str | None = Field(None, description="Target awareness level if known")
    notes: str | None = Field(None, description="Additional context")


class SeedResponse(BaseModel):
    content: str
    source_type: str
    memory_id: str | None = None


@router.post("/{offer_id}", response_model=SeedResponse, status_code=status.HTTP_201_CREATED)
async def submit_seed(
    offer_id: str,
    body: SeedSubmission,
    account_id: str = Depends(get_current_account_id),
) -> SeedResponse:
    """Submit a seed to the seed bank.

    Use this for human gambits (your own ideas), manual seeds from
    research, or any idea you want to feed into the ideation process.
    """
    seed_content = f"Seed ({body.source_type}): {body.content}"
    if body.segment:
        seed_content += f". Segment: {body.segment}"
    if body.awareness_level:
        seed_content += f". Awareness: {body.awareness_level}"
    if body.notes:
        seed_content += f". Notes: {body.notes}"

    result = await retain_observation(
        account_id=account_id,
        bank_type=BankType.SEEDS,
        content=seed_content,
        offer_id=offer_id,
        source_type=body.source_type,
        evidence_type="ideation_seed",
        confidence_score=0.7,
        extra_metadata={
            "seed_source": body.source_type,
            "segment": body.segment,
            "awareness_level": body.awareness_level,
            "submitted_by": "human",
        },
    )

    return SeedResponse(
        content=body.content,
        source_type=body.source_type,
        memory_id=result.get("id") if result else None,
    )


@router.get("/{offer_id}", response_model=list[SeedResponse])
async def list_seeds(
    offer_id: str,
    account_id: str = Depends(get_current_account_id),
    source_type: str | None = None,
    limit: int = 50,
) -> list[SeedResponse]:
    """List seeds for an offer, optionally filtered by source type."""
    metadata_filter = None
    if source_type:
        metadata_filter = {"seed_source": source_type}

    memories = await recall_for_worker(
        "coverage_matrix",
        account_id,
        "seed ideation hook angle format concept idea",
        offer_id=offer_id,
        bank_types=[BankType.SEEDS],
        top_k=limit,
        metadata_filter=metadata_filter,
    )

    return [
        SeedResponse(
            content=m.get("content", ""),
            source_type=m.get("metadata", {}).get("seed_source", "unknown"),
            memory_id=m.get("id"),
        )
        for m in memories
    ]
