"""Research inbox + webhook registration tables.

Adds:
  - research_inbox (raw research data awaiting weekly synthesis)
  - webhook_registrations (webhooks registered with external services)

Revision ID: 006
Revises: 005
Create Date: 2026-04-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_inbox",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False, index=True),
        sa.Column("offer_id", sa.String(64), sa.ForeignKey("offers.id"), index=True),
        sa.Column("source", sa.String(64), nullable=False, index=True),
        sa.Column("source_url", sa.Text),
        sa.Column("source_id", sa.String(256), index=True),
        sa.Column("content_hash", sa.String(64), nullable=False, index=True),
        sa.Column("raw_payload", JSONB, nullable=False),
        sa.Column("title", sa.Text),
        sa.Column("summary", sa.Text),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("processed", sa.Boolean, server_default=sa.false(), index=True),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("relevance_score", sa.Integer, index=True),
        sa.Column("relevance_reason", sa.Text),
        sa.Column("synthesized_to_bank", sa.String(32)),
        sa.Column("hindsight_memory_id", sa.String(64)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index(
        "ix_research_inbox_account_processed",
        "research_inbox",
        ["account_id", "processed", "received_at"],
    )
    op.create_index(
        "ix_research_inbox_dedup",
        "research_inbox",
        ["account_id", "content_hash"],
        unique=True,
    )

    op.create_table(
        "webhook_registrations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False, index=True),
        sa.Column("offer_id", sa.String(64), sa.ForeignKey("offers.id"), index=True),
        sa.Column("source", sa.String(64), nullable=False, index=True),
        sa.Column("external_id", sa.String(256)),
        sa.Column("keywords", JSONB),
        sa.Column("secret", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), server_default="active", index=True),
        sa.Column("last_received_at", sa.DateTime(timezone=True)),
        sa.Column("payload_count", sa.Integer, server_default="0"),
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
    op.drop_table("webhook_registrations")
    op.drop_index("ix_research_inbox_dedup", "research_inbox")
    op.drop_index("ix_research_inbox_account_processed", "research_inbox")
    op.drop_table("research_inbox")
