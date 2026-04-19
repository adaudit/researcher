"""User and workspace membership models.

The SaaS model:
  - Users are global (one user can belong to many workspaces)
  - An Account IS a workspace (tenant boundary)
  - WorkspaceMembership connects users to accounts with a role
  - Roles: owner | admin | strategist | creative | analyst | viewer

Roles map to permissions:
  - owner: everything including billing, delete workspace
  - admin: manage members, all operations
  - strategist: create/edit briefs, primers, approve outputs
  - creative: generate creative, edit drafts
  - analyst: read all, write performance data, trigger analysis
  - viewer: read-only
"""

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """A platform user — can belong to multiple workspaces."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)
    preferences: Mapped[dict | None] = mapped_column(JSONB)


class WorkspaceMembership(Base, TimestampMixin):
    """Connects a user to a workspace (account) with a specific role."""

    __tablename__ = "workspace_memberships"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("accounts.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, default="creative", index=True,
    )
    # role: owner | admin | strategist | creative | analyst | viewer

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", index=True,
    )  # active | invited | suspended

    invited_by: Mapped[str | None] = mapped_column(String(64))
    invite_token: Mapped[str | None] = mapped_column(String(128))
