from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin


class Offer(Base, TimestampMixin, TenantMixin):
    __tablename__ = "offers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active")  # active | paused | archived

    # Offer fundamentals
    mechanism: Mapped[str | None] = mapped_column(Text)
    cta: Mapped[str | None] = mapped_column(String(512))
    price_point: Mapped[float | None] = mapped_column(Numeric(12, 2))
    price_model: Mapped[str | None] = mapped_column(String(64))  # one_time | subscription | trial
    product_url: Mapped[str | None] = mapped_column(String(2048))

    # Constraints and compliance
    claim_constraints: Mapped[dict | None] = mapped_column(JSONB)
    regulated_category: Mapped[str | None] = mapped_column(String(64))  # health | finance | none
    domain_risk_level: Mapped[str] = mapped_column(String(16), default="standard")

    # Buyer context
    target_audience: Mapped[str | None] = mapped_column(Text)
    awareness_level: Mapped[str | None] = mapped_column(String(32))  # unaware..most_aware

    # Proof basis
    proof_basis: Mapped[dict | None] = mapped_column(JSONB)

    # Hindsight bank references
    hindsight_core_bank_id: Mapped[str | None] = mapped_column(String(128))
    hindsight_offer_bank_id: Mapped[str | None] = mapped_column(String(128))

    # Auto-refresh settings
    refresh_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    refresh_interval_days: Mapped[int] = mapped_column(default=7)

    # Relationships
    account: Mapped["Account"] = relationship(back_populates="offers")  # noqa: F821

    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("accounts.id"), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<Offer id={self.id} name={self.name}>"
