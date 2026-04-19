from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin


class StrategyOutput(Base, TimestampMixin, TenantMixin):
    """Published strategic control object — desire maps, proof inventories,
    hook territories, mechanism maps, brief packs, seed banks, etc."""

    __tablename__ = "strategy_outputs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    offer_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("offers.id"), nullable=False, index=True
    )

    # Classification
    output_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # desire_map | proof_inventory | differentiation_map | hook_territory_map
    #   | mechanism_map | seed_bank | brief_pack | strategy_map

    # Versioning — each publish creates a new version
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(
        String(16), default="draft"
    )  # draft | approved | published | superseded

    # Content
    title: Mapped[str | None] = mapped_column(String(512))
    summary: Mapped[str | None] = mapped_column(Text)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Provenance
    source_workflow_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("workflow_jobs.id")
    )
    evidence_refs: Mapped[list | None] = mapped_column(JSONB)

    # Optional Hindsight mirror
    hindsight_memory_ref: Mapped[str | None] = mapped_column(String(128))

    def __repr__(self) -> str:
        return f"<StrategyOutput id={self.id} type={self.output_type} v{self.version}>"
