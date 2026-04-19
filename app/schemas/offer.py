from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OfferCreate(BaseModel):
    name: str = Field(..., max_length=256)
    mechanism: str | None = None
    cta: str | None = None
    price_point: float | None = None
    price_model: str | None = None  # one_time | subscription | trial
    product_url: str | None = None
    claim_constraints: dict[str, Any] | None = None
    regulated_category: str | None = None  # health | finance | none
    domain_risk_level: str = "standard"
    target_audience: str | None = None
    awareness_level: str | None = None  # unaware | problem_aware | solution_aware | product_aware | most_aware
    proof_basis: dict[str, Any] | None = None
    refresh_enabled: bool = True
    refresh_interval_days: int = 7


class OfferUpdate(BaseModel):
    name: str | None = None
    mechanism: str | None = None
    cta: str | None = None
    price_point: float | None = None
    price_model: str | None = None
    product_url: str | None = None
    claim_constraints: dict[str, Any] | None = None
    regulated_category: str | None = None
    domain_risk_level: str | None = None
    target_audience: str | None = None
    awareness_level: str | None = None
    proof_basis: dict[str, Any] | None = None
    refresh_enabled: bool | None = None
    refresh_interval_days: int | None = None


class OfferResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    account_id: str
    name: str
    status: str
    mechanism: str | None = None
    cta: str | None = None
    price_point: float | None = None
    price_model: str | None = None
    product_url: str | None = None
    claim_constraints: dict[str, Any] | None = None
    regulated_category: str | None = None
    domain_risk_level: str
    target_audience: str | None = None
    awareness_level: str | None = None
    proof_basis: dict[str, Any] | None = None
    hindsight_core_bank_id: str | None = None
    hindsight_offer_bank_id: str | None = None
    refresh_enabled: bool
    refresh_interval_days: int
    created_at: datetime
    updated_at: datetime
