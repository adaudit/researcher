"""Authentication API — signup, login, invite, workspace switching.

POST   /v1/auth/signup                 — create user + first workspace
POST   /v1/auth/login                  — issue JWT
GET    /v1/auth/me                     — current user + workspaces
POST   /v1/auth/workspaces             — create additional workspace
POST   /v1/auth/workspaces/{id}/invite — invite user to workspace
POST   /v1/auth/invites/{token}/accept — accept invite
GET    /v1/auth/workspaces/{id}/members — list workspace members
PATCH  /v1/auth/memberships/{id}       — update member role
DELETE /v1/auth/memberships/{id}       — remove member
"""

from __future__ import annotations

import secrets
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_membership, get_current_user, require_permission
from app.core.permissions import Permission, Role, ROLE_PERMISSIONS
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.account import Account
from app.db.models.user import User, WorkspaceMembership
from app.db.session import get_db

router = APIRouter()


# ── Request/Response schemas ────────────────────────────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str | None = None
    workspace_name: str = Field(..., min_length=2)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    default_workspace_id: str | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str | None
    is_active: bool
    is_verified: bool


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    slug: str
    role: str


class MeResponse(BaseModel):
    user: UserResponse
    workspaces: list[WorkspaceResponse]


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=2)
    description: str | None = None
    industry: str | None = None


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = Field("creative", description="owner | admin | strategist | creative | analyst | viewer")


class MembershipUpdate(BaseModel):
    role: str


class MemberResponse(BaseModel):
    id: str
    user_id: str
    email: str
    full_name: str | None
    role: str
    status: str


# ── Auth endpoints ──────────────────────────────────────────────────

@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Create a new user and their first workspace."""
    # Check email doesn't exist
    stmt = select(User).where(User.email == body.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create user
    user = User(
        id=f"usr_{uuid4().hex[:12]}",
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        is_active=True,
    )
    db.add(user)

    # Create workspace (account)
    account_id = f"acct_{uuid4().hex[:12]}"
    slug_base = body.workspace_name.lower().replace(" ", "-")[:100]
    account = Account(
        id=account_id,
        name=body.workspace_name,
        slug=f"{slug_base}-{uuid4().hex[:6]}",
        is_active=True,
    )
    db.add(account)

    # Create owner membership
    membership = WorkspaceMembership(
        id=f"mem_{uuid4().hex[:12]}",
        user_id=user.id,
        account_id=account_id,
        role=Role.OWNER.value,
        status="active",
    )
    db.add(membership)

    await db.commit()

    token = create_access_token(
        subject=user.id,
        extra={"active_account": account_id, "role": Role.OWNER.value},
    )
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        default_workspace_id=account_id,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Authenticate and issue JWT."""
    stmt = select(User).where(User.email == body.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Find default workspace
    mem_stmt = select(WorkspaceMembership).where(
        WorkspaceMembership.user_id == user.id,
        WorkspaceMembership.status == "active",
    ).order_by(WorkspaceMembership.created_at).limit(1)
    mem_result = await db.execute(mem_stmt)
    default_membership = mem_result.scalar_one_or_none()

    extra: dict = {}
    if default_membership:
        extra["active_account"] = default_membership.account_id
        extra["role"] = default_membership.role

    token = create_access_token(subject=user.id, extra=extra)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        default_workspace_id=default_membership.account_id if default_membership else None,
    )


@router.get("/me", response_model=MeResponse)
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    """Get current user + all their workspaces."""
    stmt = (
        select(WorkspaceMembership, Account)
        .join(Account, WorkspaceMembership.account_id == Account.id)
        .where(
            WorkspaceMembership.user_id == user.id,
            WorkspaceMembership.status == "active",
        )
    )
    result = await db.execute(stmt)
    rows = result.all()

    return MeResponse(
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
        ),
        workspaces=[
            WorkspaceResponse(
                id=acct.id,
                name=acct.name,
                slug=acct.slug,
                role=mem.role,
            )
            for mem, acct in rows
        ],
    )


@router.post("/workspaces", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    body: WorkspaceCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    """Create an additional workspace. User becomes owner."""
    account_id = f"acct_{uuid4().hex[:12]}"
    slug = f"{body.name.lower().replace(' ', '-')[:100]}-{uuid4().hex[:6]}"

    account = Account(
        id=account_id,
        name=body.name,
        slug=slug,
        description=body.description,
        industry=body.industry,
        is_active=True,
    )
    db.add(account)

    membership = WorkspaceMembership(
        id=f"mem_{uuid4().hex[:12]}",
        user_id=user.id,
        account_id=account_id,
        role=Role.OWNER.value,
        status="active",
    )
    db.add(membership)
    await db.commit()

    return WorkspaceResponse(
        id=account.id, name=account.name, slug=account.slug, role=Role.OWNER.value,
    )


@router.post("/workspaces/{account_id}/invite", status_code=status.HTTP_201_CREATED)
async def invite_member(
    account_id: str,
    body: InviteRequest,
    db: AsyncSession = Depends(get_db),
    membership: WorkspaceMembership = Depends(require_permission(Permission.MANAGE_MEMBERS)),
) -> dict:
    """Invite a user to the workspace with a specific role."""
    if account_id != membership.account_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    # Validate role
    try:
        Role(body.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{body.role}'",
        )

    # Find or create user stub
    stmt = select(User).where(User.email == body.email)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    user_id = existing_user.id if existing_user else f"usr_{uuid4().hex[:12]}"
    if not existing_user:
        # Create stub user — will complete signup via invite token
        placeholder_user = User(
            id=user_id,
            email=body.email,
            password_hash="",  # set on accept
            is_active=False,
            is_verified=False,
        )
        db.add(placeholder_user)

    # Check for existing membership
    mem_stmt = select(WorkspaceMembership).where(
        WorkspaceMembership.user_id == user_id,
        WorkspaceMembership.account_id == account_id,
    )
    mem_result = await db.execute(mem_stmt)
    existing_mem = mem_result.scalar_one_or_none()
    if existing_mem:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already has a membership in this workspace",
        )

    invite_token = secrets.token_urlsafe(32)
    new_membership = WorkspaceMembership(
        id=f"mem_{uuid4().hex[:12]}",
        user_id=user_id,
        account_id=account_id,
        role=body.role,
        status="invited",
        invited_by=membership.user_id,
        invite_token=invite_token,
    )
    db.add(new_membership)
    await db.commit()

    # In production: send email with invite link
    return {
        "invite_token": invite_token,
        "email": body.email,
        "role": body.role,
        "status": "invited",
    }


@router.post("/invites/{invite_token}/accept", response_model=TokenResponse)
async def accept_invite(
    invite_token: str,
    password: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Accept a workspace invite. If user is new, set password."""
    stmt = select(WorkspaceMembership).where(
        WorkspaceMembership.invite_token == invite_token,
        WorkspaceMembership.status == "invited",
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found or already used",
        )

    # Get user
    user_stmt = select(User).where(User.id == membership.user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one()

    # Activate user if new
    if not user.is_active:
        if not password or len(password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password required for new user (min 8 chars)",
            )
        user.password_hash = hash_password(password)
        user.is_active = True
        user.is_verified = True

    membership.status = "active"
    membership.invite_token = None
    await db.commit()

    token = create_access_token(
        subject=user.id,
        extra={"active_account": membership.account_id, "role": membership.role},
    )
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        default_workspace_id=membership.account_id,
    )


@router.get("/workspaces/{account_id}/members", response_model=list[MemberResponse])
async def list_members(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    membership: WorkspaceMembership = Depends(get_current_membership),
) -> list[MemberResponse]:
    """List all members of a workspace."""
    if account_id != membership.account_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    stmt = (
        select(WorkspaceMembership, User)
        .join(User, WorkspaceMembership.user_id == User.id)
        .where(WorkspaceMembership.account_id == account_id)
    )
    result = await db.execute(stmt)
    return [
        MemberResponse(
            id=mem.id,
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=mem.role,
            status=mem.status,
        )
        for mem, user in result.all()
    ]


@router.patch("/memberships/{membership_id}", response_model=MemberResponse)
async def update_membership(
    membership_id: str,
    body: MembershipUpdate,
    db: AsyncSession = Depends(get_db),
    actor: WorkspaceMembership = Depends(require_permission(Permission.MANAGE_MEMBERS)),
) -> MemberResponse:
    """Update a member's role."""
    try:
        Role(body.role)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role")

    stmt = select(WorkspaceMembership, User).join(
        User, WorkspaceMembership.user_id == User.id,
    ).where(WorkspaceMembership.id == membership_id)
    result = await db.execute(stmt)
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    target_mem, user = row
    if target_mem.account_id != actor.account_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    target_mem.role = body.role
    await db.commit()

    return MemberResponse(
        id=target_mem.id, user_id=user.id, email=user.email,
        full_name=user.full_name, role=target_mem.role, status=target_mem.status,
    )


@router.delete("/memberships/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    membership_id: str,
    db: AsyncSession = Depends(get_db),
    actor: WorkspaceMembership = Depends(require_permission(Permission.MANAGE_MEMBERS)),
) -> None:
    """Remove a member from the workspace."""
    stmt = select(WorkspaceMembership).where(WorkspaceMembership.id == membership_id)
    result = await db.execute(stmt)
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if target.account_id != actor.account_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    if target.id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove yourself — transfer ownership first",
        )

    await db.delete(target)
    await db.commit()


@router.get("/roles")
async def list_roles() -> dict:
    """List all available roles and their permissions."""
    return {
        role.value: sorted([p.value for p in perms])
        for role, perms in ROLE_PERMISSIONS.items()
    }
