"""Creative intelligence tables + pgvector + skill components.

Adds:
  - pgvector extension
  - creative_assets (with content_embedding, visual_embedding)
  - creative_analyses
  - swipe_entries
  - skill_components (with embedding)
  - skill_compositions

Revision ID: 002
Revises: 001
Create Date: 2026-04-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # creative_analyses (referenced by creative_assets FK)
    op.create_table(
        "creative_analyses",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("asset_id", sa.String(64), index=True, nullable=False),
        sa.Column("account_id", sa.String(64), index=True, nullable=False),
        sa.Column("analysis_type", sa.String(32), nullable=False),
        sa.Column("visual_analysis", JSONB),
        sa.Column("copy_analysis", JSONB),
        sa.Column("psychology_analysis", JSONB),
        sa.Column("synergy_analysis", JSONB),
        sa.Column("performance_correlation", JSONB),
        sa.Column("storyboard", JSONB),
        sa.Column("dr_tags", JSONB),
        sa.Column("categories", JSONB),
        sa.Column("reptile_triggers", ARRAY(sa.String(32))),
        sa.Column("scroll_stop_score", sa.Integer),
        sa.Column("native_feed_score", sa.Integer),
        sa.Column("anti_generic_score", sa.Integer),
        sa.Column("proof_density_score", sa.Integer),
        sa.Column("mechanism_present", sa.Boolean),
        sa.Column("model_provider", sa.String(32)),
        sa.Column("model_name", sa.String(64)),
        sa.Column("raw_analysis", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # creative_assets
    op.create_table(
        "creative_assets",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), index=True, nullable=False),
        sa.Column("offer_id", sa.String(64), sa.ForeignKey("offers.id"), index=True),
        sa.Column("parent_asset_id", sa.String(64), sa.ForeignKey("creative_assets.id"), index=True),
        sa.Column("asset_type", sa.String(32), nullable=False, index=True),
        sa.Column("ownership", sa.String(32), nullable=False, server_default="own", index=True),
        sa.Column("source_platform", sa.String(32), index=True),
        sa.Column("source_url", sa.String(2048)),
        sa.Column("advertiser_name", sa.String(256)),
        sa.Column("headline", sa.Text),
        sa.Column("body_copy", sa.Text),
        sa.Column("cta_text", sa.String(256)),
        sa.Column("transcript", sa.Text),
        sa.Column("storage_bucket", sa.String(128)),
        sa.Column("storage_key", sa.String(512)),
        sa.Column("thumbnail_key", sa.String(512)),
        sa.Column("content_type", sa.String(64)),
        sa.Column("content_hash", sa.String(128), index=True),
        sa.Column("size_bytes", sa.BigInteger),
        sa.Column("duration_seconds", sa.Float),
        sa.Column("clip_start", sa.String(16)),
        sa.Column("clip_end", sa.String(16)),
        sa.Column("segment_type", sa.String(32)),
        sa.Column("format_type", sa.String(64), index=True),
        sa.Column("visual_style", sa.String(64), index=True),
        sa.Column("hook_type", sa.String(64), index=True),
        sa.Column("angle", sa.String(128)),
        sa.Column("awareness_level", sa.String(32), index=True),
        sa.Column("segment_target", sa.String(128)),
        sa.Column("emotional_tone", sa.String(64)),
        sa.Column("dr_tags", ARRAY(sa.String(64))),
        sa.Column("spend", sa.Float),
        sa.Column("impressions", sa.BigInteger),
        sa.Column("clicks", sa.BigInteger),
        sa.Column("ctr", sa.Float),
        sa.Column("cpa", sa.Float),
        sa.Column("roas", sa.Float),
        sa.Column("hook_rate", sa.Float),
        sa.Column("thumb_stop_ratio", sa.Float),
        sa.Column("performance_tier", sa.String(16), index=True),
        sa.Column("running_days", sa.Integer),
        sa.Column("processing_status", sa.String(32), server_default="pending", index=True),
        sa.Column("analysis_id", sa.String(64), sa.ForeignKey("creative_analyses.id")),
        sa.Column("metadata", JSONB),
        sa.Column("content_embedding", Vector(1536)),
        sa.Column("visual_embedding", Vector(1024)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Create IVFFlat indexes for embeddings (for fast similarity search)
    op.execute(
        "CREATE INDEX creative_assets_content_embedding_idx "
        "ON creative_assets USING ivfflat (content_embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )
    op.execute(
        "CREATE INDEX creative_assets_visual_embedding_idx "
        "ON creative_assets USING ivfflat (visual_embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )

    # swipe_entries
    op.create_table(
        "swipe_entries",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), index=True, nullable=False),
        sa.Column("asset_id", sa.String(64), sa.ForeignKey("creative_assets.id"), index=True),
        sa.Column("offer_id", sa.String(64), sa.ForeignKey("offers.id"), index=True),
        sa.Column("swipe_source", sa.String(32), nullable=False, index=True),
        sa.Column("study_notes", sa.Text),
        sa.Column("why_it_works", sa.Text),
        sa.Column("what_to_steal", sa.Text),
        sa.Column("what_to_avoid", sa.Text),
        sa.Column("format_type", sa.String(64), index=True),
        sa.Column("visual_style", sa.String(64), index=True),
        sa.Column("hook_type", sa.String(64), index=True),
        sa.Column("angle", sa.String(128)),
        sa.Column("awareness_level", sa.String(32), index=True),
        sa.Column("segment_target", sa.String(128)),
        sa.Column("industry", sa.String(64), index=True),
        sa.Column("vertical", sa.String(64), index=True),
        sa.Column("tags", ARRAY(sa.String(64))),
        sa.Column("estimated_spend", sa.String(64)),
        sa.Column("running_duration", sa.String(64)),
        sa.Column("is_active", sa.Boolean),
        sa.Column("curated_by", sa.String(64)),
        sa.Column("curation_status", sa.String(16), server_default="active", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # skill_components
    op.create_table(
        "skill_components",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), index=True, nullable=False),
        sa.Column("domain", sa.String(64), nullable=False, index=True),
        sa.Column("subdomain", sa.String(64), index=True),
        sa.Column("specialty", sa.String(64), index=True),
        sa.Column("applies_to_formats", ARRAY(sa.String(32))),
        sa.Column("applies_to_awareness", ARRAY(sa.String(32))),
        sa.Column("applies_to_platforms", ARRAY(sa.String(32))),
        sa.Column("applies_to_segments", ARRAY(sa.String(64))),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("trigger_conditions", sa.Text),
        sa.Column("confidence", sa.Float, server_default="0.5"),
        sa.Column("evidence_count", sa.Integer, server_default="0"),
        sa.Column("performance_evidence", JSONB),
        sa.Column("scope", sa.String(16), server_default="account", index=True),
        sa.Column("embedding", Vector(1536)),
        sa.Column("version", sa.Integer, server_default="1"),
        sa.Column("parent_version_id", sa.String(64), sa.ForeignKey("skill_components.id")),
        sa.Column("is_active", sa.Boolean, server_default="true", index=True),
        sa.Column("tags", ARRAY(sa.String(64))),
        sa.Column("created_by", sa.String(64), server_default="system"),
        sa.Column("source_worker", sa.String(64)),
        sa.Column("promoted_from", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.execute(
        "CREATE INDEX skill_components_embedding_idx "
        "ON skill_components USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )

    # skill_compositions
    op.create_table(
        "skill_compositions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), index=True, nullable=False),
        sa.Column("task_type", sa.String(64), index=True),
        sa.Column("worker_name", sa.String(64), index=True),
        sa.Column("asset_id", sa.String(64), index=True),
        sa.Column("component_ids", ARRAY(sa.String(64)), nullable=False),
        sa.Column("context", JSONB, nullable=False),
        sa.Column("outcome", sa.String(16), index=True),
        sa.Column("outcome_metrics", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("skill_compositions")
    op.drop_index("skill_components_embedding_idx", table_name="skill_components")
    op.drop_table("skill_components")
    op.drop_table("swipe_entries")
    op.drop_index("creative_assets_visual_embedding_idx", table_name="creative_assets")
    op.drop_index("creative_assets_content_embedding_idx", table_name="creative_assets")
    op.drop_table("creative_assets")
    op.drop_table("creative_analyses")
    op.execute("DROP EXTENSION IF EXISTS vector")
