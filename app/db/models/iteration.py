from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin


class IterationHeader(Base, TimestampMixin, TenantMixin):
    """Concise strategic directive that bridges research and revision.

    Not a rewrite — a compact instruction that forces the next draft to
    improve for a specific evidence-backed reason.
    """

    __tablename__ = "iteration_headers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    offer_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("offers.id"), nullable=False, index=True
    )

    # What asset and section this targets
    asset_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # landing_page | advertorial | ad_creative | email | vsl
    asset_section: Mapped[str | None] = mapped_column(String(128))

    # The directive
    target: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    constraint: Mapped[str | None] = mapped_column(Text)

    # Evidence backing
    evidence_refs: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    evidence_detail: Mapped[dict | None] = mapped_column(JSONB)

    # Priority
    priority: Mapped[str] = mapped_column(
        String(16), default="medium"
    )  # critical | high | medium | low
    expected_effect: Mapped[str | None] = mapped_column(Text)

    # Lifecycle
    status: Mapped[str] = mapped_column(
        String(16), default="active", index=True
    )  # active | applied | superseded | rejected

    # Provenance
    source_workflow_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("workflow_jobs.id")
    )

    def __repr__(self) -> str:
        return f"<IterationHeader id={self.id} asset={self.asset_type} priority={self.priority}>"
