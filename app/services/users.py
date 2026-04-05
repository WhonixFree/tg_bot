from __future__ import annotations

from aiogram.types import User as TelegramUser

from app.core.config import Settings
from app.db.models import User
from app.db.repositories.user import UserRepository


class UserService:
    def __init__(self, repository: UserRepository, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._repository.get_by_id(user_id)

    async def upsert_from_telegram(self, telegram_user: TelegramUser) -> User:
        return await self._repository.upsert_telegram_user(
            telegram_user_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
            is_admin=telegram_user.id == self._settings.admin_tg_id,
        )
