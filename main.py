from __future__ import annotations

import asyncio
import contextlib

import uvicorn

from app.api.app import create_fastapi_app
from app.bot.app import create_bot, create_dispatcher
from app.bot.handlers import register_handlers
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.bootstrap import bootstrap_reference_data
from app.db.session import session_manager


async def run_bot_polling(bot) -> None:
    dispatcher = create_dispatcher()
    register_handlers(dispatcher)

    logger = get_logger(__name__)
    logger.info("Starting Telegram bot polling")
    await dispatcher.start_polling(bot)


async def run_api_server(bot) -> None:
    settings = get_settings()
    app = create_fastapi_app(settings, bot)
    config = uvicorn.Config(
        app=app,
        host=settings.api_host,
        port=settings.api_port,
        log_config=None,
        reload=False,
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    session_manager.init(settings.database_url)
    await bootstrap_reference_data()
    bot = create_bot(settings)

    logger = get_logger(__name__)
    logger.info(
        "Application bootstrap complete",
        extra={
            "payment_provider_mode": settings.payment_provider_mode.value,
            "database_url": settings.database_url,
        },
    )

    try:
        bot_task = asyncio.create_task(run_bot_polling(bot), name="telegram-polling")
        api_task = asyncio.create_task(run_api_server(bot), name="fastapi-server")

        done, pending = await asyncio.wait(
            {bot_task, api_task},
            return_when=asyncio.FIRST_EXCEPTION,
        )

        for task in done:
            exc = task.exception()
            if exc:
                for pending_task in pending:
                    pending_task.cancel()
                for pending_task in pending:
                    with contextlib.suppress(asyncio.CancelledError):
                        await pending_task
                raise exc

        for pending_task in pending:
            await pending_task
    finally:
        await session_manager.dispose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
