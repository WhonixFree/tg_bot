from __future__ import annotations

from datetime import UTC, datetime

from app.core.logging import get_logger
from app.core.enums import SubscriptionStatus
from app.db.models import Subscription
from app.db.repositories.subscription import SubscriptionRepository


logger = get_logger(__name__)


class SubscriptionService:
    def __init__(self, repository: SubscriptionRepository) -> None:
        self._repository = repository

    async def get_active_lifetime_subscription(self, user_id: int) -> Subscription | None:
        return await self._repository.get_active_lifetime_by_user_id(user_id)

    async def has_active_lifetime_access(self, user_id: int) -> bool:
        return await self.get_active_lifetime_subscription(user_id) is not None

    async def ensure_lifetime_subscription(self, *, user_id: int, plan_id: int) -> Subscription:
        subscription = await self._repository.get_active_lifetime_by_user_id(user_id)
        if subscription is not None:
            logger.info(
                "Webhook subscription already active user_id=%s plan_id=%s subscription_id=%s",
                user_id,
                plan_id,
                subscription.id,
            )
            return subscription

        subscription = await self._repository.create(
            user_id=user_id,
            plan_id=plan_id,
            status=SubscriptionStatus.ACTIVE,
            starts_at=datetime.now(UTC),
            expires_at=None,
            is_lifetime=True,
            granted_by_admin=False,
        )
        logger.info(
            "Webhook subscription activated user_id=%s plan_id=%s subscription_id=%s",
            user_id,
            plan_id,
            subscription.id,
        )
        return subscription
