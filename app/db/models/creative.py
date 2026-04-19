"""Creative asset models — the creative intelligence database.

Every creative asset (own ads, competitor swipes, reference images,
video clips) gets stored, analyzed, and categorized across multiple
dimensions. This is not just a file store — it's a structured,
searchable library that the system studies and learns from.

Tables:
  creative_assets  — individual creative pieces (video, image, clip, carousel card)
  creative_analyses — deep structured analysis per asset
  swipe_entries    — competitor/reference creatives with categorization
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin


class CreativeAsset(Base, TimestampMixin, TenantMixin):
    """A single creative piece — video, image, clip, or carousel card.

    This is the atomic unit of the creative library. Everything gets
    stored here: your own ads, competitor swipes, reference images,
    video clips cut from longer videos, individual carousel cards.
    """

    __tablename__ = "creative_assets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    offer_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("offers.id"), index=True,
    )
    parent_asset_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("creative_assets.id"), index=True,
    )

    # What type of asset
    asset_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True,
    )  # video | image | clip | carousel_card | ugc | vsl | email_creative

    # Ownership — is this ours or a swipe?
    ownership: Mapped[str] = mapped_column(
        String(32), nullable=False, default="own", index=True,
    )  # own | competitor | swipe | reference | template

    # Source tracking
    source_platform: Mapped[str | None] = mapped_column(String(32), index=True)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    advertiser_name: Mapped[str | None] = mapped_column(String(256))

    # Content
    headline: Mapped[str | None] = mapped_column(Text)
    body_copy: Mapped[str | None] = mapped_column(Text)
    cta_text: Mapped[str | None] = mapped_column(String(256))
    transcript: Mapped[str | None] = mapped_column(Text)

    # Storage pointers
    storage_bucket: Mapped[str | None] = mapped_column(String(128))
    storage_key: Mapped[str | None] = mapped_column(String(512))
    thumbnail_key: Mapped[str | None] = mapped_column(String(512))
    content_type: Mapped[str | None] = mapped_column(String(64))
    content_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    duration_seconds: Mapped[float | None] = mapped_column(Float)

    # For clips: timestamp within parent video
    clip_start: Mapped[str | None] = mapped_column(String(16))   # HH:MM:SS.mmm
    clip_end: Mapped[str | None] = mapped_column(String(16))
    segment_type: Mapped[str | None] = mapped_column(String(32))  # HOOK | PROBLEM_AGITATE | SOLUTION | DEMO | SOCIAL_PROOF | CTA

    # Multi-dimensional categorization
    format_type: Mapped[str | None] = mapped_column(String(64), index=True)
    visual_style: Mapped[str | None] = mapped_column(String(64), index=True)
    hook_type: Mapped[str | None] = mapped_column(String(64), index=True)
    angle: Mapped[str | None] = mapped_column(String(128))
    awareness_level: Mapped[str | None] = mapped_column(String(32), index=True)
    segment_target: Mapped[str | None] = mapped_column(String(128))
    emotional_tone: Mapped[str | None] = mapped_column(String(64))

    # DR tags
    dr_tags: Mapped[list | None] = mapped_column(ARRAY(String(64)))

    # Performance data (when available)
    spend: Mapped[float | None] = mapped_column(Float)
    impressions: Mapped[int | None] = mapped_column(BigInteger)
    clicks: Mapped[int | None] = mapped_column(BigInteger)
    ctr: Mapped[float | None] = mapped_column(Float)
    cpa: Mapped[float | None] = mapped_column(Float)
    roas: Mapped[float | None] = mapped_column(Float)
    hook_rate: Mapped[float | None] = mapped_column(Float)
    thumb_stop_ratio: Mapped[float | None] = mapped_column(Float)
    performance_tier: Mapped[str | None] = mapped_column(String(16), index=True)
    running_days: Mapped[int | None] = mapped_column(Integer)

    # Processing
    processing_status: Mapped[str] = mapped_column(
        String(32), default="pending", index=True,
    )  # pending | analyzing | analyzed | failed
    analysis_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("creative_analyses.id"),
    )

    # Flexible metadata
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB)

    # Vector embeddings for similarity search
    # content_embedding: text-based (transcript + copy + visual description)
    # visual_embedding: image/video-based (TwelveLabs or equivalent)
    content_embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    visual_embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))

    # Relationships
    analysis: Mapped["CreativeAnalysis | None"] = relationship(
        "CreativeAnalysis", foreign_keys=[analysis_id], lazy="selectin",
    )
    clips: Mapped[list["CreativeAsset"]] = relationship(
        "CreativeAsset", foreign_keys=[parent_asset_id], lazy="selectin",
    )


class CreativeAnalysis(Base, TimestampMixin):
    """Deep structured analysis of a creative asset.

    This is the output of the ad analyzer pipeline — visual analysis,
    copy analysis, psychology mapping, and performance correlation
    stored as structured JSONB for querying and learning.
    """

    __tablename__ = "creative_analyses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    asset_id: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False,
    )
    account_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    # Analysis type
    analysis_type: Mapped[str] = mapped_column(
        String(32), nullable=False,
    )  # full | visual_only | copy_only | video_storyboard

    # Structured analysis sections (JSONB for flexible querying)
    visual_analysis: Mapped[dict | None] = mapped_column(JSONB)
    copy_analysis: Mapped[dict | None] = mapped_column(JSONB)
    psychology_analysis: Mapped[dict | None] = mapped_column(JSONB)
    synergy_analysis: Mapped[dict | None] = mapped_column(JSONB)
    performance_correlation: Mapped[dict | None] = mapped_column(JSONB)

    # Video-specific: full storyboard with timestamps
    storyboard: Mapped[list | None] = mapped_column(JSONB)  # list of scene segments

    # DR tags extracted
    dr_tags: Mapped[dict | None] = mapped_column(JSONB)

    # Categories assigned by analysis
    categories: Mapped[dict | None] = mapped_column(JSONB)

    # Reptile triggers identified
    reptile_triggers: Mapped[list | None] = mapped_column(ARRAY(String(32)))

    # Quality scores
    scroll_stop_score: Mapped[int | None] = mapped_column(Integer)
    native_feed_score: Mapped[int | None] = mapped_column(Integer)
    anti_generic_score: Mapped[int | None] = mapped_column(Integer)
    proof_density_score: Mapped[int | None] = mapped_column(Integer)
    mechanism_present: Mapped[bool | None] = mapped_column(Boolean)

    # Model that performed the analysis
    model_provider: Mapped[str | None] = mapped_column(String(32))
    model_name: Mapped[str | None] = mapped_column(String(64))

    # Full raw analysis (for reprocessing)
    raw_analysis: Mapped[dict | None] = mapped_column(JSONB)


class SwipeEntry(Base, TimestampMixin, TenantMixin):
    """A curated swipe file entry — competitor or reference creative
    with categorization for study and learning.

    Swipe entries are the STUDIED version of creative assets. They
    include human curation notes, categorization, and the reasons
    WHY this swipe is worth studying.
    """

    __tablename__ = "swipe_entries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    asset_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("creative_assets.id"), index=True,
    )
    offer_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("offers.id"), index=True,
    )

    # Swipe source
    swipe_source: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True,
    )  # competitor | adjacent_market | organic_viral | template | reference | archive

    # What to study about this swipe
    study_notes: Mapped[str | None] = mapped_column(Text)
    why_it_works: Mapped[str | None] = mapped_column(Text)
    what_to_steal: Mapped[str | None] = mapped_column(Text)  # specific learnable elements
    what_to_avoid: Mapped[str | None] = mapped_column(Text)

    # Multi-dimensional categorization (same dimensions as creative_assets)
    format_type: Mapped[str | None] = mapped_column(String(64), index=True)
    visual_style: Mapped[str | None] = mapped_column(String(64), index=True)
    hook_type: Mapped[str | None] = mapped_column(String(64), index=True)
    angle: Mapped[str | None] = mapped_column(String(128))
    awareness_level: Mapped[str | None] = mapped_column(String(32), index=True)
    segment_target: Mapped[str | None] = mapped_column(String(128))

    # Industry/vertical tags for cross-business learning
    industry: Mapped[str | None] = mapped_column(String(64), index=True)
    vertical: Mapped[str | None] = mapped_column(String(64), index=True)
    tags: Mapped[list | None] = mapped_column(ARRAY(String(64)))

    # Performance signals (from ad library if available)
    estimated_spend: Mapped[str | None] = mapped_column(String(64))
    running_duration: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool | None] = mapped_column(Boolean)

    # Curation
    curated_by: Mapped[str | None] = mapped_column(String(64))  # user_id or "system"
    curation_status: Mapped[str] = mapped_column(
        String(16), default="active", index=True,
    )  # active | archived | starred

    # Relationship to the underlying asset
    asset: Mapped["CreativeAsset | None"] = relationship(
        "CreativeAsset", foreign_keys=[asset_id], lazy="selectin",
    )
