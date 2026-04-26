"""Approval queue table.

Adds:
  - approvals (human gate between ideation and writing/creative phases)

Revision ID: 005
Revises: 004
Create Date: 2026-04-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "approvals",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False, index=True),
        sa.Column("offer_id", sa.String(64), sa.ForeignKey("offers.id"), index=True),
        sa.Column("approval_type", sa.String(32), nullable=False, index=True),
        sa.Column("status", sa.String(16), server_default="pending", index=True),
        sa.Column(
            "workflow_job_id", sa.String(64),
            sa.ForeignKey("workflow_jobs.id"), index=True,
        ),
        sa.Column("payload", JSONB),
        sa.Column("grade_trajectory", JSONB),
        sa.Column("rejection_reason", sa.Text),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("approvals")
