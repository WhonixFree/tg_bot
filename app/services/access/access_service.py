from __future__ import annotations

from aiogram import Bot
from aiogram.types import ChatJoinRequest

from app.core.config import Settings
from app.core.enums import AccessLinkStatus, JoinRequestDecision, SubscriptionStatus
from app.db.models import AccessLink, Subscription
from app.db.repositories.access_link import AccessLinkRepository
from app.db.repositories.join_request_log import JoinRequestLogRepository


class AccessService:
    def __init__(
        self,
        *,
        bot: Bot,
        settings: Settings,
        access_link_repository: AccessLinkRepository,
        join_request_log_repository: JoinRequestLogRepository,
    ) -> None:
        self._bot = bot
        self._settings = settings
        self._access_link_repository = access_link_repository
        self._join_request_log_repository = join_request_log_repository

    async def get_active_access_link_for_user(self, user_id: int) -> AccessLink | None:
        return await self._access_link_repository.get_active_by_user_id(user_id)

    async def ensure_access_link(self, *, user_id: int, subscription: Subscription) -> AccessLink:
        access_link = await self._access_link_repository.get_active_by_subscription_id(subscription.id)
        if access_link is not None:
            return access_link

        telegram_link = await self._bot.create_chat_invite_link(
            chat_id=self._settings.private_channel_id,
            creates_join_request=True,
            name=f"subscription-{subscription.id}",
        )
        return await self._access_link_repository.create(
            user_id=user_id,
            subscription_id=subscription.id,
            invite_link=telegram_link.invite_link,
            status=AccessLinkStatus.ACTIVE,
        )

    async def handle_join_request(self, request: ChatJoinRequest) -> None:
        invite_link = request.invite_link.invite_link if request.invite_link is not None else None
        access_link = (
            await self._access_link_repository.get_by_invite_link(invite_link)
            if invite_link is not None
            else None
        )
        actual_user_id = request.from_user.id

        if access_link is None:
            await self._decline_and_log(
                request=request,
                subscription_id=None,
                expected_telegram_user_id=0,
                actual_telegram_user_id=actual_user_id,
                invite_link=invite_link,
                reason="Invite link is unknown.",
            )
            return

        subscription = access_link.subscription
        expected_user_id = access_link.user.telegram_user_id

        if access_link.status != AccessLinkStatus.ACTIVE:
            await self._decline_and_log(
                request=request,
                subscription_id=subscription.id,
                expected_telegram_user_id=expected_user_id,
                actual_telegram_user_id=actual_user_id,
                invite_link=invite_link,
                reason="Access link is not active.",
            )
            return

        if subscription.status != SubscriptionStatus.ACTIVE or not subscription.is_lifetime:
            await self._decline_and_log(
                request=request,
                subscription_id=subscription.id,
                expected_telegram_user_id=expected_user_id,
                actual_telegram_user_id=actual_user_id,
                invite_link=invite_link,
                reason="Subscription is not active for this access link.",
            )
            return

        if actual_user_id != expected_user_id:
            await self._decline_and_log(
                request=request,
                subscription_id=subscription.id,
                expected_telegram_user_id=expected_user_id,
                actual_telegram_user_id=actual_user_id,
                invite_link=invite_link,
                reason="Join request Telegram user ID does not match the subscription owner.",
            )
            return

        await self._bot.approve_chat_join_request(
            chat_id=request.chat.id,
            user_id=actual_user_id,
        )
        await self._join_request_log_repository.create(
            subscription_id=subscription.id,
            expected_telegram_user_id=expected_user_id,
            actual_telegram_user_id=actual_user_id,
            invite_link=invite_link,
            decision=JoinRequestDecision.APPROVED,
            reason="Approved for matching active lifetime subscription.",
        )

    async def _decline_and_log(
        self,
        *,
        request: ChatJoinRequest,
        subscription_id: int | None,
        expected_telegram_user_id: int,
        actual_telegram_user_id: int,
        invite_link: str | None,
        reason: str,
    ) -> None:
        await self._bot.decline_chat_join_request(
            chat_id=request.chat.id,
            user_id=actual_telegram_user_id,
        )
        await self._join_request_log_repository.create(
            subscription_id=subscription_id,
            expected_telegram_user_id=expected_telegram_user_id,
            actual_telegram_user_id=actual_telegram_user_id,
            invite_link=invite_link,
            decision=JoinRequestDecision.DECLINED,
            reason=reason,
        )
