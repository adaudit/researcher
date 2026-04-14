"""Shared FastAPI dependencies: database sessions, auth, tenant context."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.models.account import Account
from app.db.session import get_db


async def get_current_account_id(
    x_account_id: str = Header(..., description="Tenant account ID"),
) -> str:
    """Resolve the active account from the request header.

    In production this would be extracted from the JWT claims after
    auth middleware validation. For now, uses a simple header.
    """
    if not x_account_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Account-Id header",
        )
    return x_account_id


async def require_active_account(
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> Account:
    """Load and verify the account exists and is active."""
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found",
        )
    if not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )
    return account
