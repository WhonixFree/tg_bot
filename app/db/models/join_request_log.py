from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import JoinRequestDecision
from app.db.base import Base


class JoinRequestLog(Base):
    __tablename__ = "join_request_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
    )
    expected_telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actual_telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    invite_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[JoinRequestDecision] = mapped_column(
        Enum(JoinRequestDecision, native_enum=False, validate_strings=True, name="join_request_decision"),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    subscription = relationship("Subscription", back_populates="join_request_logs")
