from datetime import datetime

from pydantic import BaseModel, Field


class AccountCreate(BaseModel):
    name: str = Field(..., max_length=256)
    slug: str = Field(..., max_length=128, pattern=r"^[a-z0-9\-]+$")
    description: str | None = None
    industry: str | None = None
    website_url: str | None = None
    plan_tier: str = "starter"
    auto_approve_reflections: bool = False


class AccountUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    industry: str | None = None
    website_url: str | None = None
    plan_tier: str | None = None
    auto_approve_reflections: bool | None = None


class AccountResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    name: str
    slug: str
    description: str | None = None
    industry: str | None = None
    website_url: str | None = None
    plan_tier: str
    is_active: bool
    auto_approve_reflections: bool
    created_at: datetime
    updated_at: datetime
