from __future__ import annotations

from sqlalchemy import select

from app.db.models import User
from app.db.repositories.base import Repository


class UserRepository(Repository):
    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> User | None:
        stmt = select(User).where(User.telegram_user_id == telegram_user_id)
        return await self.session.scalar(stmt)

    async def create(
        self,
        *,
        telegram_user_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        is_admin: bool = False,
    ) -> User:
        user = User(
            telegram_user_id=telegram_user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            is_admin=is_admin,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def upsert_telegram_user(
        self,
        *,
        telegram_user_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        is_admin: bool = False,
    ) -> User:
        user = await self.get_by_telegram_user_id(telegram_user_id)
        if user is None:
            return await self.create(
                telegram_user_id=telegram_user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                is_admin=is_admin,
            )

        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.is_admin = is_admin
        await self.session.flush()
        return user
