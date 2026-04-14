from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(String(128))
    website_url: Mapped[str | None] = mapped_column(String(2048))

    # Plan and access control
    plan_tier: Mapped[str] = mapped_column(String(32), default="starter")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Auto-approve reflections or require manual review
    auto_approve_reflections: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    offers: Mapped[list["Offer"]] = relationship(  # noqa: F821
        back_populates="account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Account id={self.id} slug={self.slug}>"
