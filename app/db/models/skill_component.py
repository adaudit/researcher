"""Skill components — granular, composable skill pieces.

The hybrid skill model: instead of one monolithic skill file per domain,
skills are broken into small, tagged, embeddable COMPONENTS. Each ad
generation task composes its own skill context by pulling the specific
components it needs.

Example for a video UGC ad targeting problem-aware audience:
  - hook.ugc.pattern_interrupt (specific hook pattern for UGC)
  - visual.authentic.phone_quality (visual style for UGC)
  - copy.conversational.problem_aware (copy tone for this awareness)
  - structure.hook_first.15s (15-second structure)
  - dr_tag.pain_point (how to use pain_point tag effectively)

The ad pulls 5 specific components, not 5 full skill files. Each
component is vector-searchable so the system can find relevant skills
semantically, not just by tag lookup.

Skills are:
  - Learnable (auto-update from performance data)
  - Searchable (vector embedding + tag filters)
  - Composable (multiple components per task)
  - Shareable (can be promoted from per-account to global)
  - Versioned (can track skill evolution over time)
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin


class SkillComponent(Base, TimestampMixin, TenantMixin):
    """One granular skill component that can be composed with others."""

    __tablename__ = "skill_components"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # Taxonomy — multi-level for precise targeting
    domain: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # domain: hook | copy | visual | structure | dr_tag | psychology | format |
    #         awareness | mechanism | proof | objection | audience | platform

    subdomain: Mapped[str | None] = mapped_column(String(64), index=True)
    # subdomain: ugc | authority | curiosity | pain_point | native | polished etc.

    specialty: Mapped[str | None] = mapped_column(String(64), index=True)
    # specialty: pattern_interrupt | scientific | testimonial | before_after etc.

    # Context dimensions this skill applies to
    applies_to_formats: Mapped[list | None] = mapped_column(ARRAY(String(32)))
    applies_to_awareness: Mapped[list | None] = mapped_column(ARRAY(String(32)))
    applies_to_platforms: Mapped[list | None] = mapped_column(ARRAY(String(32)))
    applies_to_segments: Mapped[list | None] = mapped_column(ARRAY(String(64)))

    # The actual skill content
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # `content` is the markdown skill definition — rules, examples, anti-patterns

    # When to use this skill
    trigger_conditions: Mapped[str | None] = mapped_column(Text)
    # Natural language description of when to pull this skill

    # Confidence and evidence
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    performance_evidence: Mapped[dict | None] = mapped_column(JSONB)

    # Scope
    scope: Mapped[str] = mapped_column(String(16), default="account", index=True)
    # scope: account (per-business) | vertical (shared across a vertical) | global

    # Vector embedding for semantic search
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))

    # Version tracking
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_version_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("skill_components.id"),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Tags for filtering
    tags: Mapped[list | None] = mapped_column(ARRAY(String(64)))

    # Metadata
    created_by: Mapped[str] = mapped_column(String(64), default="system")
    source_worker: Mapped[str | None] = mapped_column(String(64))
    promoted_from: Mapped[str | None] = mapped_column(String(64))
    # If this was promoted from account→vertical or vertical→global


class SkillComposition(Base, TimestampMixin, TenantMixin):
    """Records which skill components were used for a specific task.

    This is the learning signal — when an ad performs well/poorly,
    we can trace back to exactly which skill components were active.
    Used for:
    - Performance attribution (which skills drive results)
    - Skill evolution (winners strengthen components, losers weaken)
    - Composition pattern learning (which combos work)
    """

    __tablename__ = "skill_compositions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # What task used these skills
    task_type: Mapped[str] = mapped_column(String(64), index=True)
    # task_type: hook_generation | copy_generation | image_concept | video_script etc.

    worker_name: Mapped[str] = mapped_column(String(64), index=True)
    asset_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # The creative_asset this composition produced (links back for performance)

    # Which components were composed
    component_ids: Mapped[list] = mapped_column(ARRAY(String(64)), nullable=False)

    # Context of the composition
    context: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # {format, awareness_level, segment, platform, ...}

    # Outcome tracking (populated when performance data arrives)
    outcome: Mapped[str | None] = mapped_column(String(16), index=True)
    # outcome: winner | strong | average | weak | loser | pending
    outcome_metrics: Mapped[dict | None] = mapped_column(JSONB)
