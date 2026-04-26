"""Performance data models — first-party + third-party metrics with full breakdowns.

This is the real performance intelligence layer. Not just spend/CTR —
full demographic, geographic, placement, device, and audience targeting
breakdowns that let the system understand WHO is responding to WHAT.

Data sources:
  - First-party: Meta Ads Manager, GA4, pixel events, CRM/revenue
  - Third-party: Ad Audit, Bulk Launcher

Tables:
  - performance_snapshots: daily roll-ups per ad creative
  - demographic_breakdowns: age × gender × state × DMA per creative
  - audience_targeting: the targeting combo that received spend
  - winning_definitions: per-account + industry benchmark configs
  - ingest_questions: clarifying questions the system asks about data
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin


class PerformanceSnapshot(Base, TimestampMixin, TenantMixin):
    """Daily performance metrics per creative asset.

    One row per asset per day per source. This is the core performance
    data that drives the learning loop.
    """

    __tablename__ = "performance_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    asset_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("creative_assets.id"), index=True,
    )
    offer_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("offers.id"), index=True,
    )

    # Identity
    external_ad_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    external_adset_id: Mapped[str | None] = mapped_column(String(128), index=True)
    external_campaign_id: Mapped[str | None] = mapped_column(String(128), index=True)
    ad_name: Mapped[str | None] = mapped_column(String(512))
    adset_name: Mapped[str | None] = mapped_column(String(512))
    campaign_name: Mapped[str | None] = mapped_column(String(512))

    # Time
    date: Mapped[str] = mapped_column(Date, nullable=False, index=True)
    date_start: Mapped[str | None] = mapped_column(Date)
    date_end: Mapped[str | None] = mapped_column(Date)

    # Source
    data_source: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True,
    )  # meta_first_party | ga4 | pixel | crm | ad_audit | bulk_launcher

    platform: Mapped[str] = mapped_column(
        String(32), nullable=False, default="meta",
    )  # meta | tiktok | google | youtube | linkedin | snapchat

    # ── First-party metrics (platform-reported) ─────────────────────
    spend: Mapped[float | None] = mapped_column(Float)
    impressions: Mapped[int | None] = mapped_column(BigInteger)
    reach: Mapped[int | None] = mapped_column(BigInteger)
    frequency: Mapped[float | None] = mapped_column(Float)
    clicks: Mapped[int | None] = mapped_column(BigInteger)
    link_clicks: Mapped[int | None] = mapped_column(BigInteger)
    outbound_clicks: Mapped[int | None] = mapped_column(BigInteger)

    # Engagement
    likes: Mapped[int | None] = mapped_column(BigInteger)
    comments: Mapped[int | None] = mapped_column(BigInteger)
    shares: Mapped[int | None] = mapped_column(BigInteger)
    saves: Mapped[int | None] = mapped_column(BigInteger)

    # Video metrics
    video_plays: Mapped[int | None] = mapped_column(BigInteger)
    video_plays_25: Mapped[int | None] = mapped_column(BigInteger)
    video_plays_50: Mapped[int | None] = mapped_column(BigInteger)
    video_plays_75: Mapped[int | None] = mapped_column(BigInteger)
    video_plays_95: Mapped[int | None] = mapped_column(BigInteger)
    video_plays_100: Mapped[int | None] = mapped_column(BigInteger)
    avg_watch_time_seconds: Mapped[float | None] = mapped_column(Float)
    thumb_stop_ratio: Mapped[float | None] = mapped_column(Float)
    hook_rate: Mapped[float | None] = mapped_column(Float)  # % past 3s

    # Conversions (first-party attribution)
    purchases: Mapped[int | None] = mapped_column(BigInteger)
    purchase_value: Mapped[float | None] = mapped_column(Float)
    add_to_carts: Mapped[int | None] = mapped_column(BigInteger)
    initiates_checkout: Mapped[int | None] = mapped_column(BigInteger)
    leads: Mapped[int | None] = mapped_column(BigInteger)
    registrations: Mapped[int | None] = mapped_column(BigInteger)
    custom_conversions: Mapped[dict | None] = mapped_column(JSONB)

    # Calculated first-party metrics
    ctr: Mapped[float | None] = mapped_column(Float)
    cpc: Mapped[float | None] = mapped_column(Float)
    cpm: Mapped[float | None] = mapped_column(Float)
    cpa: Mapped[float | None] = mapped_column(Float)
    roas: Mapped[float | None] = mapped_column(Float)
    aov: Mapped[float | None] = mapped_column(Float)

    # ── Third-party metrics (Ad Audit / Bulk Launcher) ──────────────
    tp_purchases: Mapped[int | None] = mapped_column(BigInteger)
    tp_revenue: Mapped[float | None] = mapped_column(Float)
    tp_roas: Mapped[float | None] = mapped_column(Float)
    tp_cpa: Mapped[float | None] = mapped_column(Float)
    tp_new_customer_purchases: Mapped[int | None] = mapped_column(BigInteger)
    tp_new_customer_revenue: Mapped[float | None] = mapped_column(Float)
    tp_new_customer_roas: Mapped[float | None] = mapped_column(Float)
    tp_attribution_model: Mapped[str | None] = mapped_column(String(64))

    # ── Landing page / post-click ───────────────────────────────────
    landing_page_views: Mapped[int | None] = mapped_column(BigInteger)
    bounce_rate: Mapped[float | None] = mapped_column(Float)
    avg_session_duration: Mapped[float | None] = mapped_column(Float)
    pages_per_session: Mapped[float | None] = mapped_column(Float)

    # Status
    delivery_status: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool | None] = mapped_column(Boolean)

    # Performance classification
    performance_tier: Mapped[str | None] = mapped_column(String(16), index=True)

    # Raw data preservation
    raw_data: Mapped[dict | None] = mapped_column(JSONB)


class DemographicBreakdown(Base, TimestampMixin, TenantMixin):
    """Demographic performance breakdown per creative.

    Age × gender × geography breakdowns so the system can learn
    WHICH demographics respond to WHICH creative approaches.
    """

    __tablename__ = "demographic_breakdowns"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("performance_snapshots.id"), index=True, nullable=False,
    )
    external_ad_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)

    # Demographic dimensions
    age_range: Mapped[str | None] = mapped_column(String(16), index=True)
    # 18-24 | 25-34 | 35-44 | 45-54 | 55-64 | 65+
    gender: Mapped[str | None] = mapped_column(String(16), index=True)
    # male | female | unknown
    state: Mapped[str | None] = mapped_column(String(64), index=True)
    dma: Mapped[str | None] = mapped_column(String(128), index=True)
    country: Mapped[str | None] = mapped_column(String(4), index=True)
    device: Mapped[str | None] = mapped_column(String(32), index=True)
    # mobile | desktop | tablet
    placement: Mapped[str | None] = mapped_column(String(64), index=True)
    # feed | stories | reels | right_column | audience_network | search

    # Metrics for this demographic slice
    spend: Mapped[float | None] = mapped_column(Float)
    impressions: Mapped[int | None] = mapped_column(BigInteger)
    clicks: Mapped[int | None] = mapped_column(BigInteger)
    conversions: Mapped[int | None] = mapped_column(BigInteger)
    revenue: Mapped[float | None] = mapped_column(Float)
    ctr: Mapped[float | None] = mapped_column(Float)
    cpa: Mapped[float | None] = mapped_column(Float)
    roas: Mapped[float | None] = mapped_column(Float)


class AudienceTargeting(Base, TimestampMixin, TenantMixin):
    """The actual audience targeting configuration that received spend.

    Captures the targeting combo so the system can learn which
    targeting × creative combinations work.
    """

    __tablename__ = "audience_targeting"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    external_adset_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    offer_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("offers.id"), index=True,
    )

    # Targeting config
    targeting_type: Mapped[str | None] = mapped_column(String(32), index=True)
    # broad | interest | lookalike | custom_audience | retargeting | asc

    # Interest targeting
    interests: Mapped[list | None] = mapped_column(ARRAY(String(128)))
    excluded_interests: Mapped[list | None] = mapped_column(ARRAY(String(128)))

    # Lookalike config
    lookalike_source: Mapped[str | None] = mapped_column(String(128))
    lookalike_percentage: Mapped[float | None] = mapped_column(Float)
    lookalike_country: Mapped[str | None] = mapped_column(String(4))

    # Custom audience
    custom_audience_name: Mapped[str | None] = mapped_column(String(256))
    custom_audience_type: Mapped[str | None] = mapped_column(String(64))
    # website | customer_list | engagement | video_viewers | ig_followers

    # Demographics targeting
    age_min: Mapped[int | None] = mapped_column(Integer)
    age_max: Mapped[int | None] = mapped_column(Integer)
    genders: Mapped[list | None] = mapped_column(ARRAY(String(16)))
    locations: Mapped[list | None] = mapped_column(ARRAY(String(128)))
    excluded_locations: Mapped[list | None] = mapped_column(ARRAY(String(128)))
    languages: Mapped[list | None] = mapped_column(ARRAY(String(16)))

    # Placement config
    placements: Mapped[list | None] = mapped_column(ARRAY(String(64)))
    # feed | stories | reels | search | audience_network | messenger

    # Optimization
    optimization_goal: Mapped[str | None] = mapped_column(String(64))
    # conversions | value | link_clicks | impressions | reach
    bid_strategy: Mapped[str | None] = mapped_column(String(64))
    # lowest_cost | cost_cap | bid_cap | target_roas
    bid_amount: Mapped[float | None] = mapped_column(Float)
    daily_budget: Mapped[float | None] = mapped_column(Float)
    lifetime_budget: Mapped[float | None] = mapped_column(Float)

    # Performance summary for this targeting
    total_spend: Mapped[float | None] = mapped_column(Float)
    total_conversions: Mapped[int | None] = mapped_column(BigInteger)
    avg_cpa: Mapped[float | None] = mapped_column(Float)
    avg_roas: Mapped[float | None] = mapped_column(Float)

    # Raw targeting spec
    raw_targeting: Mapped[dict | None] = mapped_column(JSONB)


class WinningDefinition(Base, TimestampMixin, TenantMixin):
    """Per-account winning criteria with industry benchmark baselines.

    What counts as "winning" is different for every business and
    evolves as the account matures. This table stores the thresholds.
    """

    __tablename__ = "winning_definitions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    offer_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("offers.id"), index=True,
    )

    # Which metric to use as the primary performance signal
    primary_metric: Mapped[str] = mapped_column(
        String(32), nullable=False, default="roas",
    )  # roas | cpa | ctr | hook_rate | tp_roas | tp_cpa

    # Tier thresholds (values depend on primary_metric)
    winner_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    strong_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)
    average_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    weak_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    # Secondary metrics that must also pass
    min_spend_for_evaluation: Mapped[float] = mapped_column(Float, default=50.0)
    min_impressions_for_evaluation: Mapped[int] = mapped_column(Integer, default=1000)
    min_days_running: Mapped[int] = mapped_column(Integer, default=3)

    # Use third-party or first-party as source of truth?
    attribution_source: Mapped[str] = mapped_column(
        String(32), default="first_party",
    )  # first_party | third_party | blended

    # Industry benchmarks (starting baselines)
    industry: Mapped[str | None] = mapped_column(String(64), index=True)
    industry_avg_cpa: Mapped[float | None] = mapped_column(Float)
    industry_avg_roas: Mapped[float | None] = mapped_column(Float)
    industry_avg_ctr: Mapped[float | None] = mapped_column(Float)
    industry_avg_hook_rate: Mapped[float | None] = mapped_column(Float)

    # Auto-calibration: thresholds adjust as account data accumulates
    auto_calibrate: Mapped[bool] = mapped_column(Boolean, default=True)
    calibration_window_days: Mapped[int] = mapped_column(Integer, default=30)

    # Notes
    notes: Mapped[str | None] = mapped_column(Text)


class IngestQuestion(Base, TimestampMixin, TenantMixin):
    """Questions the system asks when ingested data is ambiguous.

    When performance data arrives that the system doesn't fully
    understand, it logs a question here. The user answers via the UI,
    and the system learns from the answer.
    """

    __tablename__ = "ingest_questions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # Context
    data_source: Mapped[str] = mapped_column(String(32), nullable=False)
    related_field: Mapped[str] = mapped_column(String(64), nullable=False)
    related_value: Mapped[str | None] = mapped_column(Text)

    # The question
    question: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # question_type: metric_definition | data_mapping | anomaly | threshold | missing_data

    # Possible answers (if applicable)
    options: Mapped[list | None] = mapped_column(JSONB)

    # Resolution
    status: Mapped[str] = mapped_column(
        String(16), default="pending", index=True,
    )  # pending | answered | dismissed
    answer: Mapped[str | None] = mapped_column(Text)
    answered_by: Mapped[str | None] = mapped_column(String(64))

    # Learning: once answered, this becomes a rule for future ingests
    creates_rule: Mapped[bool] = mapped_column(Boolean, default=False)
    rule_description: Mapped[str | None] = mapped_column(Text)
