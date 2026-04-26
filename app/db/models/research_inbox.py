"""Research inbox — staging table for webhook-ingested research data.

External services push data here continuously (Taddy webhooks, RSS feeds
converted via internal poller, etc.). The weekly research_synthesis worker
processes the inbox: scores relevance, synthesizes findings into Hindsight
banks, then cleans up irrelevant or already-processed items.

This pattern is cheap because:
- Webhook ingestion: no polling cost when nothing changes
- Cheap LLM (Qwen Flash) scores each item for relevance — filters ~80% noise
- Premium LLM only synthesizes the top 20%
- Cleanup bounds storage (irrelevant deleted immediately, processed
  items older than 30 days deleted)
"""

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin


class ResearchInbox(Base, TimestampMixin, TenantMixin):
    """Raw research data received from webhooks, awaiting weekly synthesis."""

    __tablename__ = "research_inbox"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    offer_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("offers.id"), index=True,
    )

    # Source classification
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # taddy_podcast | substack | google_news | fda_alert | reddit_rising |
    # custom_zapier | brand_mention | etc.

    source_url: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[str | None] = mapped_column(String(256), index=True)

    # Content hash for deduplication (sha256 of normalized content)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)

    # Raw payload as received from the webhook
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Extracted text for relevance scoring (denormalized for fast access)
    title: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)

    # Lifecycle
    received_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    processed: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True,
    )
    processed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))

    # Relevance score (1-10) assigned during weekly synthesis
    relevance_score: Mapped[int | None] = mapped_column(Integer, index=True)
    relevance_reason: Mapped[str | None] = mapped_column(Text)

    # Where the synthesized finding ended up (RESEARCH, CULTURE, VOC, or null
    # if filtered out)
    synthesized_to_bank: Mapped[str | None] = mapped_column(String(32))
    hindsight_memory_id: Mapped[str | None] = mapped_column(String(64))

    def __repr__(self) -> str:
        return (
            f"<ResearchInbox id={self.id} source={self.source} "
            f"processed={self.processed} score={self.relevance_score}>"
        )


class WebhookRegistration(Base, TimestampMixin, TenantMixin):
    """Tracks webhooks the system has registered with external services.

    When the AI registers a webhook with Taddy/Substack/Zapier on behalf
    of an account, the registration ID + secret is stored here so we can
    validate incoming payloads and de-register later.
    """

    __tablename__ = "webhook_registrations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    offer_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("offers.id"), index=True,
    )

    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(256))
    keywords: Mapped[list | None] = mapped_column(JSONB)

    # HMAC secret for verifying incoming payloads
    secret: Mapped[str] = mapped_column(String(128), nullable=False)

    # State
    status: Mapped[str] = mapped_column(
        String(16), default="active", index=True,
    )

    last_received_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    payload_count: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return (
            f"<WebhookRegistration id={self.id} source={self.source} "
            f"status={self.status}>"
        )
