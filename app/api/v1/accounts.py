"""POST /v1/accounts — create account or workspace."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.account import Account
from app.db.session import get_db
from app.schemas.account import AccountCreate, AccountResponse, AccountUpdate
from app.services.hindsight.banks import provision_account_banks

router = APIRouter()


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    body: AccountCreate,
    db: AsyncSession = Depends(get_db),
) -> Account:
    # Check slug uniqueness
    existing = await db.execute(select(Account).where(Account.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Account slug '{body.slug}' already exists",
        )

    account = Account(
        id=f"acct_{uuid4().hex[:12]}",
        **body.model_dump(),
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)

    # Provision Hindsight banks
    try:
        await provision_account_banks(account.id)
    except Exception:
        pass  # Non-blocking — banks can be provisioned later

    return account


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
) -> Account:
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: str,
    body: AccountUpdate,
    db: AsyncSession = Depends(get_db),
) -> Account:
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(account, field, value)

    await db.commit()
    await db.refresh(account)
    return account
