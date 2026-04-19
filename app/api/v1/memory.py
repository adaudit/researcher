"""POST /v1/memory/reflect — trigger account or offer reflection."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_account_id
from app.schemas.strategy import ReflectRequest
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import trigger_reflection

router = APIRouter()


@router.post("/reflect", status_code=status.HTTP_202_ACCEPTED)
async def trigger_memory_reflection(
    body: ReflectRequest,
    account_id: str = Depends(get_current_account_id),
) -> dict:
    """Trigger a reflection cycle for the account or offer.

    This creates higher-order lessons and mental models from
    accumulated evidence in the specified banks.
    """
    source_bank_types = [BankType.OFFER, BankType.CREATIVE, BankType.VOC,
                         BankType.LANDING_PAGE, BankType.RESEARCH]

    result = await trigger_reflection(
        account_id=account_id,
        source_bank_types=source_bank_types,
        offer_id=body.offer_id,
        prompt=(
            "Reflect on accumulated evidence. Identify recurring patterns, "
            "emerging rules, and durable lessons that should inform future "
            "strategy and creative decisions."
        ),
    )

    return {
        "status": "reflection_triggered",
        "reflection_id": result.get("id"),
        "account_id": account_id,
        "offer_id": body.offer_id,
    }
