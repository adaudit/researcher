from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin


class WorkflowJob(Base, TimestampMixin, TenantMixin):
    """Tracks durable workflow execution — onboarding, refresh, synthesis,
    reflection, and decomposition jobs."""

    __tablename__ = "workflow_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    offer_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("offers.id"), index=True
    )

    # Workflow classification
    workflow_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # onboarding | offer_refresh | landing_page_decomposition | weekly_refresh
    #   | health_evidence_refresh | iteration_synthesis | performance_feedback

    # State machine
    # queued -> acquiring -> normalizing -> retaining -> reasoning -> reflecting -> approved -> published
    state: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    previous_state: Mapped[str | None] = mapped_column(String(32))

    # Execution
    celery_task_id: Mapped[str | None] = mapped_column(String(128))
    started_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    # Inputs and outputs
    input_payload: Mapped[dict | None] = mapped_column(JSONB)
    output_payload: Mapped[dict | None] = mapped_column(JSONB)

    # Audit
    step_log: Mapped[list | None] = mapped_column(JSONB)  # list of {step, status, ts, detail}
    retry_count: Mapped[int] = mapped_column(default=0)

    def __repr__(self) -> str:
        return f"<WorkflowJob id={self.id} type={self.workflow_type} state={self.state}>"
