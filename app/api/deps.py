"""Shared FastAPI dependencies: database sessions, auth, tenant context."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission, has_permission
from app.core.security import decode_access_token
from app.db.models.account import Account
from app.db.models.user import User, WorkspaceMembership
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the current user from the JWT bearer token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


async def get_current_account_id(
    x_account_id: str | None = Header(None, description="Workspace account ID"),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> str:
    """Resolve the active workspace account from JWT + X-Account-Id header.

    The user must have an active membership in the requested workspace.
    Falls back to X-Account-Id header for service-to-service calls
    (only works if no bearer token is provided).
    """
    # Service-to-service fallback — no auth, just header
    if not credentials and x_account_id:
        return x_account_id

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token or X-Account-Id",
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
        )

    # If no X-Account-Id, use the active_account from token
    account_id = x_account_id or payload.get("active_account")
    if not account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active workspace — provide X-Account-Id header",
        )

    # Verify membership
    stmt = select(WorkspaceMembership).where(
        WorkspaceMembership.user_id == user_id,
        WorkspaceMembership.account_id == account_id,
        WorkspaceMembership.status == "active",
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No active membership in workspace {account_id}",
        )

    return account_id


async def get_current_membership(
    x_account_id: str | None = Header(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceMembership:
    """Get the current user's membership in the active workspace (with role)."""
    if not x_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Account-Id header",
        )

    stmt = select(WorkspaceMembership).where(
        WorkspaceMembership.user_id == user.id,
        WorkspaceMembership.account_id == x_account_id,
        WorkspaceMembership.status == "active",
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No active membership in workspace {x_account_id}",
        )
    return membership


def require_permission(permission: Permission):
    """Dependency factory — require a specific permission."""

    async def _require(
        membership: WorkspaceMembership = Depends(get_current_membership),
    ) -> WorkspaceMembership:
        if not has_permission(membership.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{membership.role}' lacks permission '{permission.value}'",
            )
        return membership

    return _require


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
