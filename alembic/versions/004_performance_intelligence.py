"""Performance intelligence tables.

Adds:
  - performance_snapshots (daily metrics per creative)
  - demographic_breakdowns (age × gender × state × DMA)
  - audience_targeting (targeting combos that got spend)
  - winning_definitions (per-account thresholds + industry benchmarks)
  - ingest_questions (clarifying questions about ambiguous data)

Revision ID: 004
Revises: 003
Create Date: 2026-04-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "performance_snapshots",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), index=True, nullable=False),
        sa.Column("asset_id", sa.String(64), sa.ForeignKey("creative_assets.id"), index=True),
        sa.Column("offer_id", sa.String(64), sa.ForeignKey("offers.id"), index=True),
        sa.Column("external_ad_id", sa.String(128), index=True, nullable=False),
        sa.Column("external_adset_id", sa.String(128), index=True),
        sa.Column("external_campaign_id", sa.String(128), index=True),
        sa.Column("ad_name", sa.String(512)),
        sa.Column("adset_name", sa.String(512)),
        sa.Column("campaign_name", sa.String(512)),
        sa.Column("date", sa.Date, nullable=False, index=True),
        sa.Column("date_start", sa.Date),
        sa.Column("date_end", sa.Date),
        sa.Column("data_source", sa.String(32), nullable=False, index=True),
        sa.Column("platform", sa.String(32), nullable=False, server_default="meta"),
        # First-party
        sa.Column("spend", sa.Float),
        sa.Column("impressions", sa.BigInteger),
        sa.Column("reach", sa.BigInteger),
        sa.Column("frequency", sa.Float),
        sa.Column("clicks", sa.BigInteger),
        sa.Column("link_clicks", sa.BigInteger),
        sa.Column("outbound_clicks", sa.BigInteger),
        sa.Column("likes", sa.BigInteger),
        sa.Column("comments", sa.BigInteger),
        sa.Column("shares", sa.BigInteger),
        sa.Column("saves", sa.BigInteger),
        # Video
        sa.Column("video_plays", sa.BigInteger),
        sa.Column("video_plays_25", sa.BigInteger),
        sa.Column("video_plays_50", sa.BigInteger),
        sa.Column("video_plays_75", sa.BigInteger),
        sa.Column("video_plays_95", sa.BigInteger),
        sa.Column("video_plays_100", sa.BigInteger),
        sa.Column("avg_watch_time_seconds", sa.Float),
        sa.Column("thumb_stop_ratio", sa.Float),
        sa.Column("hook_rate", sa.Float),
        # Conversions
        sa.Column("purchases", sa.BigInteger),
        sa.Column("purchase_value", sa.Float),
        sa.Column("add_to_carts", sa.BigInteger),
        sa.Column("initiates_checkout", sa.BigInteger),
        sa.Column("leads", sa.BigInteger),
        sa.Column("registrations", sa.BigInteger),
        sa.Column("custom_conversions", JSONB),
        # Calculated
        sa.Column("ctr", sa.Float),
        sa.Column("cpc", sa.Float),
        sa.Column("cpm", sa.Float),
        sa.Column("cpa", sa.Float),
        sa.Column("roas", sa.Float),
        sa.Column("aov", sa.Float),
        # Third-party
        sa.Column("tp_purchases", sa.BigInteger),
        sa.Column("tp_revenue", sa.Float),
        sa.Column("tp_roas", sa.Float),
        sa.Column("tp_cpa", sa.Float),
        sa.Column("tp_new_customer_purchases", sa.BigInteger),
        sa.Column("tp_new_customer_revenue", sa.Float),
        sa.Column("tp_new_customer_roas", sa.Float),
        sa.Column("tp_attribution_model", sa.String(64)),
        # Landing page
        sa.Column("landing_page_views", sa.BigInteger),
        sa.Column("bounce_rate", sa.Float),
        sa.Column("avg_session_duration", sa.Float),
        sa.Column("pages_per_session", sa.Float),
        # Status
        sa.Column("delivery_status", sa.String(32)),
        sa.Column("is_active", sa.Boolean),
        sa.Column("performance_tier", sa.String(16), index=True),
        sa.Column("raw_data", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "demographic_breakdowns",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), index=True, nullable=False),
        sa.Column("snapshot_id", sa.String(64), sa.ForeignKey("performance_snapshots.id"), index=True, nullable=False),
        sa.Column("external_ad_id", sa.String(128), index=True, nullable=False),
        sa.Column("age_range", sa.String(16), index=True),
        sa.Column("gender", sa.String(16), index=True),
        sa.Column("state", sa.String(64), index=True),
        sa.Column("dma", sa.String(128), index=True),
        sa.Column("country", sa.String(4), index=True),
        sa.Column("device", sa.String(32), index=True),
        sa.Column("placement", sa.String(64), index=True),
        sa.Column("spend", sa.Float),
        sa.Column("impressions", sa.BigInteger),
        sa.Column("clicks", sa.BigInteger),
        sa.Column("conversions", sa.BigInteger),
        sa.Column("revenue", sa.Float),
        sa.Column("ctr", sa.Float),
        sa.Column("cpa", sa.Float),
        sa.Column("roas", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "audience_targeting",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), index=True, nullable=False),
        sa.Column("external_adset_id", sa.String(128), index=True, nullable=False),
        sa.Column("offer_id", sa.String(64), sa.ForeignKey("offers.id"), index=True),
        sa.Column("targeting_type", sa.String(32), index=True),
        sa.Column("interests", ARRAY(sa.String(128))),
        sa.Column("excluded_interests", ARRAY(sa.String(128))),
        sa.Column("lookalike_source", sa.String(128)),
        sa.Column("lookalike_percentage", sa.Float),
        sa.Column("lookalike_country", sa.String(4)),
        sa.Column("custom_audience_name", sa.String(256)),
        sa.Column("custom_audience_type", sa.String(64)),
        sa.Column("age_min", sa.Integer),
        sa.Column("age_max", sa.Integer),
        sa.Column("genders", ARRAY(sa.String(16))),
        sa.Column("locations", ARRAY(sa.String(128))),
        sa.Column("excluded_locations", ARRAY(sa.String(128))),
        sa.Column("languages", ARRAY(sa.String(16))),
        sa.Column("placements", ARRAY(sa.String(64))),
        sa.Column("optimization_goal", sa.String(64)),
        sa.Column("bid_strategy", sa.String(64)),
        sa.Column("bid_amount", sa.Float),
        sa.Column("daily_budget", sa.Float),
        sa.Column("lifetime_budget", sa.Float),
        sa.Column("total_spend", sa.Float),
        sa.Column("total_conversions", sa.BigInteger),
        sa.Column("avg_cpa", sa.Float),
        sa.Column("avg_roas", sa.Float),
        sa.Column("raw_targeting", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "winning_definitions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), index=True, nullable=False),
        sa.Column("offer_id", sa.String(64), sa.ForeignKey("offers.id"), index=True),
        sa.Column("primary_metric", sa.String(32), nullable=False, server_default="roas"),
        sa.Column("winner_threshold", sa.Float, nullable=False, server_default="3.0"),
        sa.Column("strong_threshold", sa.Float, nullable=False, server_default="2.0"),
        sa.Column("average_threshold", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("weak_threshold", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("min_spend_for_evaluation", sa.Float, server_default="50.0"),
        sa.Column("min_impressions_for_evaluation", sa.Integer, server_default="1000"),
        sa.Column("min_days_running", sa.Integer, server_default="3"),
        sa.Column("attribution_source", sa.String(32), server_default="first_party"),
        sa.Column("industry", sa.String(64), index=True),
        sa.Column("industry_avg_cpa", sa.Float),
        sa.Column("industry_avg_roas", sa.Float),
        sa.Column("industry_avg_ctr", sa.Float),
        sa.Column("industry_avg_hook_rate", sa.Float),
        sa.Column("auto_calibrate", sa.Boolean, server_default="true"),
        sa.Column("calibration_window_days", sa.Integer, server_default="30"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "ingest_questions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), index=True, nullable=False),
        sa.Column("data_source", sa.String(32), nullable=False),
        sa.Column("related_field", sa.String(64), nullable=False),
        sa.Column("related_value", sa.Text),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("question_type", sa.String(32), nullable=False),
        sa.Column("options", JSONB),
        sa.Column("status", sa.String(16), server_default="pending", index=True),
        sa.Column("answer", sa.Text),
        sa.Column("answered_by", sa.String(64)),
        sa.Column("creates_rule", sa.Boolean, server_default="false"),
        sa.Column("rule_description", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ingest_questions")
    op.drop_table("winning_definitions")
    op.drop_table("audience_targeting")
    op.drop_table("demographic_breakdowns")
    op.drop_table("performance_snapshots")
