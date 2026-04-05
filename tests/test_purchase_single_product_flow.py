from __future__ import annotations

import unittest
from contextlib import asynccontextmanager
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.bot.handlers.purchase import handle_buy_access
from app.services.payments.payment_service import PurchaseEntry
from app.services.product import FixedProduct


class FakeState:
    def __init__(self) -> None:
        self.set_state = AsyncMock()
        self.set_data = AsyncMock()


class FakeSession:
    def __init__(self) -> None:
        self.commit = AsyncMock()


class PurchaseSingleProductFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.session = FakeSession()

        @asynccontextmanager
        async def fake_session_context():
            yield self.session

        self.fake_session_context = fake_session_context

    async def test_buy_flow_uses_single_fixed_product_without_plan_selection(self) -> None:
        callback = SimpleNamespace(
            from_user=SimpleNamespace(id=100, username="user", first_name="Test", last_name=None),
            message=SimpleNamespace(chat=SimpleNamespace(id=555)),
            bot=object(),
            answer=AsyncMock(),
        )
        state = FakeState()
        services = SimpleNamespace(
            user_service=SimpleNamespace(
                upsert_from_telegram=AsyncMock(return_value=SimpleNamespace(id=7))
            ),
            subscription_service=SimpleNamespace(
                has_active_lifetime_access=AsyncMock(return_value=False)
            ),
            payment_service=SimpleNamespace(
                get_purchase_entry=AsyncMock(return_value=PurchaseEntry())
            ),
            product_service=SimpleNamespace(
                get_product=AsyncMock(
                    return_value=FixedProduct(
                        id=1,
                        code="GUIDE_ACCESS_LIFETIME",
                        display_name="Lifetime access",
                        description="One-time lifetime access to the private guide channel.",
                        price_usd=Decimal("25.00"),
                    )
                )
            ),
            message_service=SimpleNamespace(show_text=AsyncMock()),
        )

        with (
            patch("app.bot.handlers.purchase.session_manager.session", new=self.fake_session_context),
            patch("app.bot.handlers.purchase.build_runtime_services", return_value=services),
        ):
            await handle_buy_access(callback, state)

        services.payment_service.get_purchase_entry.assert_awaited_once_with(user_id=7)
        services.message_service.show_text.assert_awaited_once()
        kwargs = services.message_service.show_text.await_args.kwargs
        self.assertIn("Choose your payment coin.", kwargs["text"])
        self.assertEqual(callback.answer.await_count, 1)
        self.session.commit.assert_awaited_once()
