from __future__ import annotations

from sqlalchemy import select

from app.core.enums import BotMessageType
from app.db.models import BotMessage
from app.db.repositories.base import Repository


class BotMessageRepository(Repository):
    async def get_by_user_id(self, user_id: int) -> BotMessage | None:
        stmt = select(BotMessage).where(BotMessage.user_id == user_id)
        return await self.session.scalar(stmt)

    async def upsert(
        self,
        *,
        user_id: int,
        chat_id: int,
        message_id: int,
        message_type: BotMessageType,
    ) -> BotMessage:
        bot_message = await self.get_by_user_id(user_id)
        if bot_message is None:
            bot_message = BotMessage(
                user_id=user_id,
                chat_id=chat_id,
                message_id=message_id,
                message_type=message_type,
            )
            self.session.add(bot_message)
        else:
            bot_message.chat_id = chat_id
            bot_message.message_id = message_id
            bot_message.message_type = message_type

        await self.session.flush()
        return bot_message

    async def clear_for_user(self, user_id: int) -> None:
        bot_message = await self.get_by_user_id(user_id)
        if bot_message is not None:
            await self.session.delete(bot_message)
            await self.session.flush()
