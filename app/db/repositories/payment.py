from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.enums import PaymentStatus
from app.db.models import Payment
from app.db.repositories.base import Repository


class PaymentRepository(Repository):
    async def get_by_id(self, payment_id: int) -> Payment | None:
        return await self.session.get(Payment, payment_id)

    async def get_by_provider_payment_uuid(self, provider_payment_uuid: str) -> Payment | None:
        stmt = (
            select(Payment)
            .options(joinedload(Payment.order))
            .where(Payment.provider_payment_uuid == provider_payment_uuid)
        )
        return await self.session.scalar(stmt)

    async def get_latest_by_order_id(self, order_id: int) -> Payment | None:
        stmt = (
            select(Payment)
            .options(joinedload(Payment.order))
            .where(Payment.order_id == order_id)
            .order_by(Payment.id.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def list_by_order_id(self, order_id: int) -> list[Payment]:
        stmt = select(Payment).where(Payment.order_id == order_id).order_by(Payment.id.asc())
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def create(
        self,
        *,
        order_id: int,
        provider_status: PaymentStatus,
        provider_payment_uuid: str | None = None,
        payer_currency: str | None = None,
        payer_amount: Decimal | None = None,
        network: str | None = None,
        address: str | None = None,
        qr_data_uri: str | None = None,
        provider_url: str | None = None,
        expires_at: datetime | None = None,
        txid: str | None = None,
        rate_source: str | None = None,
        rate_base_currency: str | None = None,
        rate_quote_currency: str | None = None,
        rate_value_usd: Decimal | None = None,
        rate_fetched_at: datetime | None = None,
        amount_before_rounding: Decimal | None = None,
        raw_rate_payload_json: dict[str, Any] | None = None,
        raw_payload_json: dict[str, Any] | None = None,
        paid_at: datetime | None = None,
    ) -> Payment:
        payment = Payment(
            order_id=order_id,
            provider_status=provider_status,
            provider_payment_uuid=provider_payment_uuid,
            payer_currency=payer_currency,
            payer_amount=payer_amount,
            network=network,
            address=address,
            qr_data_uri=qr_data_uri,
            provider_url=provider_url,
            expires_at=expires_at,
            txid=txid,
            rate_source=rate_source,
            rate_base_currency=rate_base_currency,
            rate_quote_currency=rate_quote_currency,
            rate_value_usd=rate_value_usd,
            rate_fetched_at=rate_fetched_at,
            amount_before_rounding=amount_before_rounding,
            raw_rate_payload_json=raw_rate_payload_json,
            raw_payload_json=raw_payload_json,
            paid_at=paid_at,
        )
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def save(self, payment: Payment) -> Payment:
        await self.session.flush()
        return payment
