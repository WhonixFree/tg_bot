from __future__ import annotations

from decimal import Decimal
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.core.enums import OrderStatus, PaymentProvider, PaymentStatus
from app.db.models import Order
from app.db.repositories.base import Repository
from app.utils.datetime import normalize_sqlite_utc, utc_now_naive


class OrderRepository(Repository):
    async def get_by_id(self, order_pk: int) -> Order | None:
        return await self.session.get(Order, order_pk)

    async def get_by_order_id(self, order_id: str) -> Order | None:
        stmt = (
            select(Order)
            .options(joinedload(Order.plan), selectinload(Order.payments))
            .where(Order.order_id == order_id)
        )
        return await self.session.scalar(stmt)

    async def get_latest_for_user(self, user_id: int) -> Order | None:
        stmt = (
            select(Order)
            .options(joinedload(Order.plan), selectinload(Order.payments))
            .where(Order.user_id == user_id)
            .order_by(Order.id.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def get_active_unpaid_for_user(self, user_id: int) -> Order | None:
        now = utc_now_naive()
        stmt = (
            select(Order)
            .options(joinedload(Order.plan), selectinload(Order.payments))
            .where(
                Order.user_id == user_id,
                Order.status == OrderStatus.AWAITING_PAYMENT,
            )
            .order_by(Order.id.desc())
        )
        result = await self.session.scalars(stmt)
        for order in result.all():
            payment = order.payments[0] if order.payments else None
            if payment is None:
                continue
            expires_at = normalize_sqlite_utc(payment.expires_at)
            if payment.provider_status == PaymentStatus.CHECK and expires_at and expires_at > now:
                return order
        return None

    async def get_active_unpaid_for_user_plan(self, user_id: int, plan_id: int) -> Order | None:
        now = utc_now_naive()
        stmt = (
            select(Order)
            .options(joinedload(Order.plan), selectinload(Order.payments))
            .where(
                Order.user_id == user_id,
                Order.plan_id == plan_id,
                Order.status == OrderStatus.AWAITING_PAYMENT,
            )
            .order_by(Order.id.desc())
        )
        result = await self.session.scalars(stmt)
        for order in result.all():
            payment = order.payments[0] if order.payments else None
            if payment is None:
                continue
            expires_at = normalize_sqlite_utc(payment.expires_at)
            if payment.provider_status == PaymentStatus.CHECK and expires_at and expires_at > now:
                return order
        return None

    async def create(
        self,
        *,
        order_id: str,
        user_id: int,
        plan_id: int,
        amount_usd: Decimal,
        payment_provider: PaymentProvider,
        status: OrderStatus,
    ) -> Order:
        order = Order(
            order_id=order_id,
            user_id=user_id,
            plan_id=plan_id,
            amount_usd=amount_usd,
            payment_provider=payment_provider,
            status=status,
        )
        self.session.add(order)
        await self.session.flush()
        return order

    async def update_status(self, order: Order, status: OrderStatus) -> Order:
        order.status = status
        await self.session.flush()
        return order
