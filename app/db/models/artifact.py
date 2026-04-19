from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin


class Artifact(Base, TimestampMixin, TenantMixin):
    """Raw source material: page HTML, screenshots, transcripts, ad exports, uploads."""

    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    offer_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("offers.id"), index=True
    )

    # Source classification
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )  # api | upload | crawler | transcript | research | manual
    source_url: Mapped[str | None] = mapped_column(String(2048))
    canonical_url: Mapped[str | None] = mapped_column(String(2048), index=True)

    # Content
    content_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # text/html | image/png | video/mp4 | application/json | text/plain
    content_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)

    # Storage pointers
    storage_bucket: Mapped[str | None] = mapped_column(String(128))
    storage_key: Mapped[str | None] = mapped_column(String(512))

    # Classification
    artifact_kind: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )  # landing_page | ad_creative | comment_dump | transcript | screenshot | research_doc | upload

    # Processing state
    processing_status: Mapped[str] = mapped_column(
        String(32), default="pending"
    )  # pending | processing | completed | failed
    error_message: Mapped[str | None] = mapped_column(Text)

    # Extracted metadata (populated after normalization)
    extracted_metadata: Mapped[dict | None] = mapped_column(JSONB)

    # Freshness
    freshness_window_days: Mapped[int] = mapped_column(default=30)

    def __repr__(self) -> str:
        return f"<Artifact id={self.id} kind={self.artifact_kind} status={self.processing_status}>"
