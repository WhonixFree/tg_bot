from __future__ import annotations

from aiogram import Dispatcher

from app.bot.handlers.purchase import router as purchase_router

def register_handlers(dispatcher: Dispatcher) -> None:
    dispatcher.include_router(purchase_router)
