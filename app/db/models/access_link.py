from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import AccessLinkStatus
from app.db.base import Base, TimestampMixin


class AccessLink(TimestampMixin, Base):
    __tablename__ = "access_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    invite_link: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    status: Mapped[AccessLinkStatus] = mapped_column(
        Enum(AccessLinkStatus, native_enum=False, validate_strings=True, name="access_link_status"),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="access_links")
    subscription = relationship("Subscription", back_populates="access_links")
