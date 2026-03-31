from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.enums import AccessLinkStatus
from app.db.models import AccessLink
from app.db.repositories.base import Repository


class AccessLinkRepository(Repository):
    async def get_by_id(self, access_link_id: int) -> AccessLink | None:
        return await self.session.get(AccessLink, access_link_id)

    async def get_active_by_user_id(self, user_id: int) -> AccessLink | None:
        stmt = (
            select(AccessLink)
            .options(joinedload(AccessLink.subscription), joinedload(AccessLink.user))
            .where(
                AccessLink.user_id == user_id,
                AccessLink.status == AccessLinkStatus.ACTIVE,
            )
            .order_by(AccessLink.id.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def get_active_by_subscription_id(self, subscription_id: int) -> AccessLink | None:
        stmt = (
            select(AccessLink)
            .options(joinedload(AccessLink.subscription), joinedload(AccessLink.user))
            .where(
                AccessLink.subscription_id == subscription_id,
                AccessLink.status == AccessLinkStatus.ACTIVE,
            )
            .order_by(AccessLink.id.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def get_by_invite_link(self, invite_link: str) -> AccessLink | None:
        stmt = (
            select(AccessLink)
            .options(joinedload(AccessLink.subscription), joinedload(AccessLink.user))
            .where(AccessLink.invite_link == invite_link)
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def create(
        self,
        *,
        user_id: int,
        subscription_id: int,
        invite_link: str,
        status: AccessLinkStatus = AccessLinkStatus.ACTIVE,
        revoked_at: datetime | None = None,
    ) -> AccessLink:
        access_link = AccessLink(
            user_id=user_id,
            subscription_id=subscription_id,
            invite_link=invite_link,
            status=status,
            revoked_at=revoked_at,
        )
        self.session.add(access_link)
        await self.session.flush()
        return access_link

    async def save(self, access_link: AccessLink) -> AccessLink:
        await self.session.flush()
        return access_link
