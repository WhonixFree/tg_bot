from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import PaymentStatus
from app.db.base import Base, TimestampMixin


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    provider_payment_uuid: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    provider_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, native_enum=False, validate_strings=True, name="payment_status"),
        nullable=False,
    )
    payer_currency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payer_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    network: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    qr_data_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    txid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="payments")
