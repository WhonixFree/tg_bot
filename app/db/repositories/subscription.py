from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.core.enums import SubscriptionStatus
from app.db.models import Subscription
from app.db.repositories.base import Repository


class SubscriptionRepository(Repository):
    async def get_by_id(self, subscription_id: int) -> Subscription | None:
        return await self.session.get(Subscription, subscription_id)

    async def get_active_by_user_id(self, user_id: int) -> Subscription | None:
        stmt = (
            select(Subscription)
            .options(joinedload(Subscription.plan), selectinload(Subscription.access_links))
            .where(
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
        )
        return await self.session.scalar(stmt)

    async def get_active_lifetime_by_user_id(self, user_id: int) -> Subscription | None:
        stmt = (
            select(Subscription)
            .options(joinedload(Subscription.plan), selectinload(Subscription.access_links))
            .where(
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.is_lifetime.is_(True),
            )
            .order_by(Subscription.id.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def create(
        self,
        *,
        user_id: int,
        plan_id: int,
        status: SubscriptionStatus,
        starts_at: datetime,
        expires_at: datetime | None = None,
        is_lifetime: bool = True,
        granted_by_admin: bool = False,
    ) -> Subscription:
        subscription = Subscription(
            user_id=user_id,
            plan_id=plan_id,
            status=status,
            starts_at=starts_at,
            expires_at=expires_at,
            is_lifetime=is_lifetime,
            granted_by_admin=granted_by_admin,
        )
        self.session.add(subscription)
        await self.session.flush()
        return subscription

    async def save(self, subscription: Subscription) -> Subscription:
        await self.session.flush()
        return subscription
