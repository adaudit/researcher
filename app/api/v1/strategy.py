"""GET /v1/strategy-map/{offer_id} — fetch approved strategy map."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_account_id
from app.db.models.strategy_output import StrategyOutput
from app.db.session import get_db
from app.schemas.strategy import StrategyMapResponse, StrategyOutputResponse

router = APIRouter()

# Map of output_type -> field name in StrategyMapResponse
OUTPUT_TYPE_FIELD_MAP = {
    "desire_map": "desire_map",
    "proof_inventory": "proof_inventory",
    "differentiation_map": "differentiation_map",
    "hook_territory_map": "hook_territory_map",
    "mechanism_map": "mechanism_map",
    "seed_bank": "seed_bank",
    "brief_pack": "brief_pack",
}


@router.get("/{offer_id}", response_model=StrategyMapResponse)
async def get_strategy_map(
    offer_id: str,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Fetch the composite strategy map for an offer.

    Returns the latest approved version of each strategy output type.
    """
    result = await db.execute(
        select(StrategyOutput)
        .where(
            StrategyOutput.offer_id == offer_id,
            StrategyOutput.account_id == account_id,
            StrategyOutput.status.in_(["approved", "published"]),
        )
        .order_by(StrategyOutput.output_type, StrategyOutput.version.desc())
    )
    outputs = result.scalars().all()

    # Take latest version of each type
    latest: dict[str, StrategyOutput] = {}
    for output in outputs:
        if output.output_type not in latest:
            latest[output.output_type] = output

    response = {"offer_id": offer_id}
    for output_type, field_name in OUTPUT_TYPE_FIELD_MAP.items():
        if output_type in latest:
            response[field_name] = latest[output_type]
        else:
            response[field_name] = None

    return response
