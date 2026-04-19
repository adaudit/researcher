"""Initial schema — all core tables.

Revision ID: 001
Revises:
Create Date: 2026-04-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # accounts
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("slug", sa.String(128), unique=True, nullable=False, index=True),
        sa.Column("description", sa.Text),
        sa.Column("industry", sa.String(128)),
        sa.Column("website_url", sa.String(2048)),
        sa.Column("plan_tier", sa.String(32), server_default="starter"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("auto_approve_reflections", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # offers
    op.create_table(
        "offers",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), sa.ForeignKey("accounts.id"), nullable=False, index=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("status", sa.String(32), server_default="active"),
        sa.Column("mechanism", sa.Text),
        sa.Column("cta", sa.String(512)),
        sa.Column("price_point", sa.Numeric(12, 2)),
        sa.Column("price_model", sa.String(64)),
        sa.Column("product_url", sa.String(2048)),
        sa.Column("claim_constraints", JSONB),
        sa.Column("regulated_category", sa.String(64)),
        sa.Column("domain_risk_level", sa.String(16), server_default="standard"),
        sa.Column("target_audience", sa.Text),
        sa.Column("awareness_level", sa.String(32)),
        sa.Column("proof_basis", JSONB),
        sa.Column("hindsight_core_bank_id", sa.String(128)),
        sa.Column("hindsight_offer_bank_id", sa.String(128)),
        sa.Column("refresh_enabled", sa.Boolean, server_default=sa.text("true")),
        sa.Column("refresh_interval_days", sa.Integer, server_default="7"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # artifacts
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False, index=True),
        sa.Column("offer_id", sa.String(64), sa.ForeignKey("offers.id"), index=True),
        sa.Column("source_type", sa.String(32), nullable=False, index=True),
        sa.Column("source_url", sa.String(2048)),
        sa.Column("canonical_url", sa.String(2048), index=True),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(128), index=True),
        sa.Column("size_bytes", sa.BigInteger),
        sa.Column("storage_bucket", sa.String(128)),
        sa.Column("storage_key", sa.String(512)),
        sa.Column("artifact_kind", sa.String(32), nullable=False, index=True),
        sa.Column("processing_status", sa.String(32), server_default="pending"),
        sa.Column("error_message", sa.Text),
        sa.Column("extracted_metadata", JSONB),
        sa.Column("freshness_window_days", sa.Integer, server_default="30"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # observations
    op.create_table(
        "observations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False, index=True),
        sa.Column("offer_id", sa.String(64), sa.ForeignKey("offers.id"), index=True),
        sa.Column("artifact_id", sa.String(64), sa.ForeignKey("artifacts.id"), index=True),
        sa.Column("bank_id", sa.String(128), nullable=False, index=True),
        sa.Column("category", sa.String(64), nullable=False, index=True),
        sa.Column("statement", sa.Text, nullable=False),
        sa.Column("evidence_refs", ARRAY(sa.String)),
        sa.Column("confidence_score", sa.Float, server_default="0.5"),
        sa.Column("freshness_window_days", sa.Integer, server_default="30"),
        sa.Column("review_status", sa.String(16), server_default="pending", index=True),
        sa.Column("domain_risk_level", sa.String(16), server_default="standard"),
        sa.Column("hindsight_memory_ref", sa.String(128)),
        sa.Column("metadata", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # workflow_jobs
    op.create_table(
        "workflow_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False, index=True),
        sa.Column("offer_id", sa.String(64), sa.ForeignKey("offers.id"), index=True),
        sa.Column("workflow_type", sa.String(64), nullable=False, index=True),
        sa.Column("state", sa.String(32), server_default="queued", index=True),
        sa.Column("previous_state", sa.String(32)),
        sa.Column("celery_task_id", sa.String(128)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text),
        sa.Column("input_payload", JSONB),
        sa.Column("output_payload", JSONB),
        sa.Column("step_log", JSONB),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # strategy_outputs
    op.create_table(
        "strategy_outputs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False, index=True),
        sa.Column("offer_id", sa.String(64), sa.ForeignKey("offers.id"), nullable=False, index=True),
        sa.Column("output_type", sa.String(64), nullable=False, index=True),
        sa.Column("version", sa.Integer, server_default="1"),
        sa.Column("status", sa.String(16), server_default="draft"),
        sa.Column("title", sa.String(512)),
        sa.Column("summary", sa.Text),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("source_workflow_id", sa.String(64), sa.ForeignKey("workflow_jobs.id")),
        sa.Column("evidence_refs", JSONB),
        sa.Column("hindsight_memory_ref", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # iteration_headers
    op.create_table(
        "iteration_headers",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False, index=True),
        sa.Column("offer_id", sa.String(64), sa.ForeignKey("offers.id"), nullable=False, index=True),
        sa.Column("asset_type", sa.String(64), nullable=False),
        sa.Column("asset_section", sa.String(128)),
        sa.Column("target", sa.Text, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("constraint", sa.Text),
        sa.Column("evidence_refs", ARRAY(sa.String)),
        sa.Column("evidence_detail", JSONB),
        sa.Column("priority", sa.String(16), server_default="medium"),
        sa.Column("expected_effect", sa.Text),
        sa.Column("status", sa.String(16), server_default="active", index=True),
        sa.Column("source_workflow_id", sa.String(64), sa.ForeignKey("workflow_jobs.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("iteration_headers")
    op.drop_table("strategy_outputs")
    op.drop_table("workflow_jobs")
    op.drop_table("observations")
    op.drop_table("artifacts")
    op.drop_table("offers")
    op.drop_table("accounts")
