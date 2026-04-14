from datetime import datetime
from typing import Any

from pydantic import BaseModel


class StrategyOutputResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    account_id: str
    offer_id: str
    output_type: str
    version: int
    status: str
    title: str | None = None
    summary: str | None = None
    content: dict[str, Any]
    source_workflow_id: str | None = None
    evidence_refs: list[Any] | None = None
    hindsight_memory_ref: str | None = None
    created_at: datetime
    updated_at: datetime


class StrategyMapResponse(BaseModel):
    """Composite view of all approved strategy outputs for an offer."""

    offer_id: str
    desire_map: StrategyOutputResponse | None = None
    proof_inventory: StrategyOutputResponse | None = None
    differentiation_map: StrategyOutputResponse | None = None
    hook_territory_map: StrategyOutputResponse | None = None
    mechanism_map: StrategyOutputResponse | None = None
    seed_bank: StrategyOutputResponse | None = None
    brief_pack: StrategyOutputResponse | None = None


class ReflectRequest(BaseModel):
    offer_id: str | None = None
    bank_ids: list[str] | None = None
    scope: str = "offer"  # offer | account
