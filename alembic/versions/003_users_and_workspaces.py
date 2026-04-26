"""Users and workspace memberships for SaaS auth/RBAC.

Adds:
  - users table
  - workspace_memberships table (user ↔ account with role)

Revision ID: 003
Revises: 002
Create Date: 2026-04-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("email", sa.String(256), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("full_name", sa.String(256)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("is_verified", sa.Boolean, server_default="false"),
        sa.Column("is_superadmin", sa.Boolean, server_default="false"),
        sa.Column("preferences", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # workspace_memberships
    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "user_id", sa.String(64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            index=True, nullable=False,
        ),
        sa.Column(
            "account_id", sa.String(64),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            index=True, nullable=False,
        ),
        sa.Column("role", sa.String(32), nullable=False, server_default="creative", index=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active", index=True),
        sa.Column("invited_by", sa.String(64)),
        sa.Column("invite_token", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index(
        "workspace_memberships_user_account_idx",
        "workspace_memberships",
        ["user_id", "account_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("workspace_memberships_user_account_idx", table_name="workspace_memberships")
    op.drop_table("workspace_memberships")
    op.drop_table("users")
