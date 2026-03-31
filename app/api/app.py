from __future__ import annotations

from aiogram import Bot
from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.webhook_2328 import create_webhook_router
from app.core.config import Settings


def create_fastapi_app(settings: Settings, bot: Bot) -> FastAPI:
    app = FastAPI(title="Telegram Subscription Bot", version="0.1.0")
    app.state.settings = settings
    app.state.bot = bot
    app.include_router(health_router)
    app.include_router(create_webhook_router(bot=bot, settings=settings))
    return app
