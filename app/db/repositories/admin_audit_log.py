from __future__ import annotations

from typing import Any

from app.db.models import AdminAuditLog
from app.db.repositories.base import Repository


class AdminAuditLogRepository(Repository):
    async def create(
        self,
        *,
        admin_telegram_user_id: int,
        action: str,
        target_user_id: int | None = None,
        details_json: dict[str, Any] | None = None,
    ) -> AdminAuditLog:
        entry = AdminAuditLog(
            admin_telegram_user_id=admin_telegram_user_id,
            target_user_id=target_user_id,
            action=action,
            details_json=details_json,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry
