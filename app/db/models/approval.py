"""Approval queue — human gate between ideation and writing/creative."""

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin


class Approval(Base, TimestampMixin, TenantMixin):
    """Tracks items requiring human review before the next pipeline phase runs.

    Approval types:
      - angle_approval: hook territories / angle ideas from ideation
      - brief_approval: brief packs from brief_composer
      - concept_approval: image concepts from image_concept_generator
      - reflection_approval: durable lessons from memory_reflection

    States:
      pending → approved | rejected

    On approve: the linked workflow_job_id resumes (writing phase dispatched).
    On reject: rejection_reason is fed back as refinement context and the
    ideation phase can re-run with that feedback.
    """

    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    offer_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("offers.id"), index=True,
    )

    approval_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True,
    )

    status: Mapped[str] = mapped_column(
        String(16), default="pending", index=True,
    )

    workflow_job_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("workflow_jobs.id"), index=True,
    )

    payload: Mapped[dict | None] = mapped_column(JSONB)

    grade_trajectory: Mapped[list | None] = mapped_column(JSONB)

    rejection_reason: Mapped[str | None] = mapped_column(Text)

    reviewed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return (
            f"<Approval id={self.id} type={self.approval_type} "
            f"status={self.status}>"
        )
