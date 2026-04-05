from __future__ import annotations

import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.bot.handlers.purchase import _handle_invoice_status_action
from app.bot.screens.purchase import build_underpaid_invoice_text
from app.core.enums import PaymentStatus


class FakeState:
    def __init__(self) -> None:
        self.set_state = AsyncMock()
        self.set_data = AsyncMock()


class FakeSession:
    def __init__(self) -> None:
        self.commit = AsyncMock()


class PurchaseUnderpaidFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.session = FakeSession()

        @asynccontextmanager
        async def fake_session_context():
            yield self.session

        self.fake_session_context = fake_session_context

    async def test_underpaid_shows_dedicated_message(self) -> None:
        callback = SimpleNamespace(
            from_user=SimpleNamespace(id=100, username="user", first_name="Test", last_name=None),
            message=SimpleNamespace(chat=SimpleNamespace(id=555)),
            data="invoice:refresh:ORDER-123",
            bot=object(),
            answer=AsyncMock(),
        )
        state = FakeState()
        invoice = SimpleNamespace(status=PaymentStatus.UNDERPAID)
        services = SimpleNamespace(
            user_service=SimpleNamespace(
                upsert_from_telegram=AsyncMock(return_value=SimpleNamespace(id=7))
            ),
            payment_service=SimpleNamespace(
                refresh_invoice=AsyncMock(
                    return_value=SimpleNamespace(is_success=False, access_link=None)
                ),
                get_invoice=AsyncMock(return_value=invoice),
            ),
            message_service=SimpleNamespace(show_text=AsyncMock()),
        )

        with (
            patch("app.bot.handlers.purchase.session_manager.session", new=self.fake_session_context),
            patch("app.bot.handlers.purchase.build_runtime_services", return_value=services),
        ):
            await _handle_invoice_status_action(
                callback=callback,
                state=state,
                user_confirmed_payment=False,
            )

        services.message_service.show_text.assert_awaited_once()
        kwargs = services.message_service.show_text.await_args.kwargs
        self.assertEqual(kwargs["text"], build_underpaid_invoice_text())
        self.assertEqual(
            kwargs["reply_markup"].inline_keyboard[0][0].text,
            "Main Menu",
        )
        self.assertEqual(len(kwargs["reply_markup"].inline_keyboard), 1)
        self.session.commit.assert_awaited_once()

    async def test_underpaid_check_shows_dedicated_message(self) -> None:
        callback = SimpleNamespace(
            from_user=SimpleNamespace(id=100, username="user", first_name="Test", last_name=None),
            message=SimpleNamespace(chat=SimpleNamespace(id=555)),
            data="invoice:refresh:ORDER-123",
            bot=object(),
            answer=AsyncMock(),
        )
        state = FakeState()
        invoice = SimpleNamespace(status=PaymentStatus.UNDERPAID_CHECK)
        services = SimpleNamespace(
            user_service=SimpleNamespace(
                upsert_from_telegram=AsyncMock(return_value=SimpleNamespace(id=7))
            ),
            payment_service=SimpleNamespace(
                refresh_invoice=AsyncMock(
                    return_value=SimpleNamespace(is_success=False, access_link=None)
                ),
                get_invoice=AsyncMock(return_value=invoice),
            ),
            message_service=SimpleNamespace(show_text=AsyncMock()),
        )

        with (
            patch("app.bot.handlers.purchase.session_manager.session", new=self.fake_session_context),
            patch("app.bot.handlers.purchase.build_runtime_services", return_value=services),
        ):
            await _handle_invoice_status_action(
                callback=callback,
                state=state,
                user_confirmed_payment=False,
            )

        services.message_service.show_text.assert_awaited_once()
        kwargs = services.message_service.show_text.await_args.kwargs
        self.assertEqual(kwargs["text"], build_underpaid_invoice_text())
        self.assertEqual(
            kwargs["reply_markup"].inline_keyboard[0][0].text,
            "Main Menu",
        )
        self.assertEqual(len(kwargs["reply_markup"].inline_keyboard), 1)
        self.session.commit.assert_awaited_once()
