from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin


class ObservationRecord(Base, TimestampMixin, TenantMixin):
    """Extracted fact linked to evidence — the bridge between raw artifacts
    and strategic memory in Hindsight."""

    __tablename__ = "observations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    offer_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("offers.id"), index=True
    )
    artifact_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("artifacts.id"), index=True
    )

    # Bank targeting
    bank_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # Observation content
    category: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # audience_desire | audience_objection | proof_claim | hook_pattern | mechanism_insight | ...
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    # Quality signals
    confidence_score: Mapped[float] = mapped_column(Float, default=0.5)
    freshness_window_days: Mapped[int] = mapped_column(default=30)

    # Review gate
    review_status: Mapped[str] = mapped_column(
        String(16), default="pending", index=True
    )  # pending | approved | flagged | rejected
    domain_risk_level: Mapped[str] = mapped_column(String(16), default="standard")

    # Hindsight linkage
    hindsight_memory_ref: Mapped[str | None] = mapped_column(String(128))

    # Extra structured data
    metadata: Mapped[dict | None] = mapped_column(JSONB)

    def __repr__(self) -> str:
        return f"<Observation id={self.id} category={self.category} status={self.review_status}>"
