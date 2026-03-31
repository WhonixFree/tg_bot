from __future__ import annotations

import contextlib
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InputFile, Message

from app.core.config import Settings
from app.core.enums import BotMessageType
from app.db.repositories.bot_message import BotMessageRepository


class MessageService:
    def __init__(
        self,
        *,
        bot: Bot,
        settings: Settings,
        bot_message_repository: BotMessageRepository,
    ) -> None:
        self._bot = bot
        self._settings = settings
        self._bot_message_repository = bot_message_repository

    async def show_main_menu(
        self,
        *,
        user_id: int,
        chat_id: int,
        caption: str,
        reply_markup: InlineKeyboardMarkup,
    ) -> Message:
        photo = self._resolve_photo(self._settings.main_menu_image_path)
        return await self._send_screen(
            user_id=user_id,
            chat_id=chat_id,
            text=caption,
            reply_markup=reply_markup,
            message_type=BotMessageType.SCREEN,
            photo=photo,
        )

    async def show_text(
        self,
        *,
        user_id: int,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup,
        message_type: BotMessageType = BotMessageType.SCREEN,
    ) -> Message:
        return await self._send_screen(
            user_id=user_id,
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            message_type=message_type,
            photo=None,
        )

    async def _send_screen(
        self,
        *,
        user_id: int,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup,
        message_type: BotMessageType,
        photo: InputFile | str | None,
    ) -> Message:
        await self._delete_previous_message(user_id=user_id)

        if photo is not None:
            message = await self._bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=text,
                reply_markup=reply_markup,
            )
        else:
            message = await self._bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
            )

        await self._bot_message_repository.upsert(
            user_id=user_id,
            chat_id=chat_id,
            message_id=message.message_id,
            message_type=message_type,
        )
        return message

    async def _delete_previous_message(self, *, user_id: int) -> None:
        bot_message = await self._bot_message_repository.get_by_user_id(user_id)
        if bot_message is None:
            return

        with contextlib.suppress(TelegramBadRequest):
            await self._bot.delete_message(
                chat_id=bot_message.chat_id,
                message_id=bot_message.message_id,
            )

    def _resolve_photo(self, image_ref: str) -> InputFile | str | None:
        if image_ref.startswith(("http://", "https://")):
            return image_ref

        path = Path(image_ref)
        if path.exists() and path.is_file():
            return FSInputFile(path)

        return None
