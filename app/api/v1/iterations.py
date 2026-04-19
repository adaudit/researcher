"""GET /v1/iteration-headers/{offer_id} — fetch current next-draft targets."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_account_id
from app.db.models.iteration import IterationHeader
from app.db.session import get_db
from app.schemas.iteration import IterationHeaderResponse

router = APIRouter()


@router.get("/{offer_id}", response_model=list[IterationHeaderResponse])
async def get_iteration_headers(
    offer_id: str,
    status_filter: str = "active",
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> list[IterationHeader]:
    """Fetch active iteration headers for an offer.

    Iteration headers are compact strategic directives that bridge
    research and revision. They are not rewrites — they are evidence-
    backed instructions for the next draft.
    """
    query = (
        select(IterationHeader)
        .where(
            IterationHeader.offer_id == offer_id,
            IterationHeader.account_id == account_id,
        )
        .order_by(
            # Priority ordering: critical > high > medium > low
            IterationHeader.priority,
            IterationHeader.created_at.desc(),
        )
    )

    if status_filter:
        query = query.where(IterationHeader.status == status_filter)

    result = await db.execute(query)
    return list(result.scalars().all())
