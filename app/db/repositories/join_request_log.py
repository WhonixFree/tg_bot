from __future__ import annotations

from sqlalchemy import select

from app.core.enums import JoinRequestDecision
from app.db.models import JoinRequestLog
from app.db.repositories.base import Repository


class JoinRequestLogRepository(Repository):
    async def create(
        self,
        *,
        expected_telegram_user_id: int,
        actual_telegram_user_id: int,
        decision: JoinRequestDecision,
        subscription_id: int | None = None,
        invite_link: str | None = None,
        reason: str | None = None,
    ) -> JoinRequestLog:
        entry = JoinRequestLog(
            subscription_id=subscription_id,
            expected_telegram_user_id=expected_telegram_user_id,
            actual_telegram_user_id=actual_telegram_user_id,
            invite_link=invite_link,
            decision=decision,
            reason=reason,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def list_recent(self, limit: int = 50) -> list[JoinRequestLog]:
        stmt = select(JoinRequestLog).order_by(JoinRequestLog.id.desc()).limit(limit)
        result = await self.session.scalars(stmt)
        return list(result.all())
