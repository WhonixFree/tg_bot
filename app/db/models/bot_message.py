from __future__ import annotations

from sqlalchemy import BigInteger, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import BotMessageType
from app.db.base import Base, TimestampMixin


class BotMessage(TimestampMixin, Base):
    __tablename__ = "bot_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(nullable=False)
    message_type: Mapped[BotMessageType] = mapped_column(
        Enum(BotMessageType, native_enum=False, validate_strings=True, name="bot_message_type"),
        nullable=False,
    )

    user = relationship("User", back_populates="bot_message")
