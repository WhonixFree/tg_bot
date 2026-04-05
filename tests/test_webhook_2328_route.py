from __future__ import annotations

import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from app.api.app import create_fastapi_app
from app.core.config import get_settings
from app.core.enums import PaymentStatus


class DummyBot:
    pass


class FakeSession:
    def __init__(self) -> None:
        self.commit = AsyncMock()


class WebhookRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        base = get_settings()
        self.settings = base.model_copy(update={"payment_webhook_path": "/webhooks/2328"})
        self.bot = DummyBot()
        self.session = FakeSession()

        @asynccontextmanager
        async def fake_session_context():
            yield self.session

        self.fake_session_context = fake_session_context

    async def test_valid_signed_webhook_with_known_order_is_processed_normally(self) -> None:
        payload = {
            "uuid": "abc123",
            "order_id": "ORDER-123",
            "payment_status": "paid",
            "sign": "valid-signature",
        }
        services = SimpleNamespace(
            webhook_gateway=SimpleNamespace(
                verify_webhook_signature=lambda *, payload: True,
                parse_webhook_event=lambda parsed_payload: SimpleNamespace(
                    provider_payment_uuid=parsed_payload["uuid"],
                    order_id=parsed_payload["order_id"],
                    result=SimpleNamespace(provider_status=SimpleNamespace(value=parsed_payload["payment_status"])),
                ),
            ),
            payment_service=SimpleNamespace(
                process_webhook_event=AsyncMock(
                    return_value=SimpleNamespace(
                        is_success=False,
                        access_link=None,
                        order=SimpleNamespace(order_id="ORDER-123", user_id=7),
                        payment=SimpleNamespace(provider_status=PaymentStatus.CHECK),
                    )
                ),
            ),
        )

        with (
            patch("app.api.routes.webhook_2328.session_manager.session", new=self.fake_session_context),
            patch("app.api.routes.webhook_2328.build_runtime_services", return_value=services),
        ):
            transport = httpx.ASGITransport(app=create_fastapi_app(self.settings, self.bot))
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post("/webhooks/2328", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        services.payment_service.process_webhook_event.assert_awaited_once()
        self.session.commit.assert_awaited_once()

    async def test_valid_signed_webhook_with_unknown_order_is_ignored_safely(self) -> None:
        payload = {
            "uuid": "abc123",
            "order_id": "debug-order-1",
            "payment_status": "paid",
            "sign": "valid-signature",
        }
        services = SimpleNamespace(
            webhook_gateway=SimpleNamespace(
                verify_webhook_signature=lambda *, payload: True,
                parse_webhook_event=lambda parsed_payload: SimpleNamespace(
                    provider_payment_uuid=parsed_payload["uuid"],
                    order_id=parsed_payload["order_id"],
                    result=SimpleNamespace(provider_status=SimpleNamespace(value=parsed_payload["payment_status"])),
                ),
            ),
            payment_service=SimpleNamespace(process_webhook_event=AsyncMock(return_value=None)),
        )

        with (
            patch("app.api.routes.webhook_2328.session_manager.session", new=self.fake_session_context),
            patch("app.api.routes.webhook_2328.build_runtime_services", return_value=services),
        ):
            transport = httpx.ASGITransport(app=create_fastapi_app(self.settings, self.bot))
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post("/webhooks/2328", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        services.payment_service.process_webhook_event.assert_awaited_once()
        self.session.commit.assert_awaited_once()

    async def test_invalid_signature_returns_401(self) -> None:
        payload = {
            "uuid": "abc123",
            "order_id": "ORDER-123",
            "payment_status": "paid",
            "sign": "invalid-signature",
        }
        services = SimpleNamespace(
            webhook_gateway=SimpleNamespace(
                verify_webhook_signature=lambda *, payload: False,
                parse_webhook_event=AsyncMock(),
            ),
            payment_service=SimpleNamespace(process_webhook_event=AsyncMock()),
        )

        with (
            patch("app.api.routes.webhook_2328.session_manager.session", new=self.fake_session_context),
            patch("app.api.routes.webhook_2328.build_runtime_services", return_value=services),
        ):
            transport = httpx.ASGITransport(app=create_fastapi_app(self.settings, self.bot))
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post("/webhooks/2328", json=payload)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid webhook signature.")
        services.payment_service.process_webhook_event.assert_not_awaited()
        self.session.commit.assert_not_awaited()

    async def test_paid_webhook_triggers_success_notification_path(self) -> None:
        payload = {
            "uuid": "abc123",
            "order_id": "ORDER-123",
            "payment_status": "paid",
            "sign": "valid-signature",
        }
        processing = SimpleNamespace(
            is_success=True,
            access_link=SimpleNamespace(invite_link="https://t.me/join/example"),
            order=SimpleNamespace(order_id="ORDER-123", user_id=7),
            payment=SimpleNamespace(provider_status=PaymentStatus.PAID),
        )
        services = SimpleNamespace(
            webhook_gateway=SimpleNamespace(
                verify_webhook_signature=lambda *, payload: True,
                parse_webhook_event=lambda parsed_payload: SimpleNamespace(
                    provider_payment_uuid=parsed_payload["uuid"],
                    order_id=parsed_payload["order_id"],
                    result=SimpleNamespace(provider_status=SimpleNamespace(value=parsed_payload["payment_status"])),
                ),
            ),
            payment_service=SimpleNamespace(
                process_webhook_event=AsyncMock(return_value=processing),
                get_invoice=AsyncMock(
                    return_value=SimpleNamespace(
                        payer_amount="25.0",
                        payer_currency="USDT",
                        network_label="TRX-TRC20",
                    )
                ),
            ),
            user_service=SimpleNamespace(
                get_by_id=AsyncMock(return_value=SimpleNamespace(id=7, telegram_user_id=777000))
            ),
            message_service=SimpleNamespace(show_text=AsyncMock()),
        )

        with (
            patch("app.api.routes.webhook_2328.session_manager.session", new=self.fake_session_context),
            patch("app.api.routes.webhook_2328.build_runtime_services", return_value=services),
        ):
            transport = httpx.ASGITransport(app=create_fastapi_app(self.settings, self.bot))
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post("/webhooks/2328", json=payload)

        self.assertEqual(response.status_code, 200)
        services.message_service.show_text.assert_awaited_once()
        self.session.commit.assert_awaited_once()

    async def test_underpaid_webhook_sends_dedicated_message(self) -> None:
        payload = {
            "uuid": "abc123",
            "order_id": "ORDER-123",
            "payment_status": "underpaid",
            "sign": "valid-signature",
        }
        processing = SimpleNamespace(
            is_success=False,
            access_link=None,
            order=SimpleNamespace(order_id="ORDER-123", user_id=7),
            payment=SimpleNamespace(provider_status=PaymentStatus.UNDERPAID),
        )
        services = SimpleNamespace(
            webhook_gateway=SimpleNamespace(
                verify_webhook_signature=lambda *, payload: True,
                parse_webhook_event=lambda parsed_payload: SimpleNamespace(
                    provider_payment_uuid=parsed_payload["uuid"],
                    order_id=parsed_payload["order_id"],
                    result=SimpleNamespace(provider_status=SimpleNamespace(value=parsed_payload["payment_status"])),
                ),
            ),
            payment_service=SimpleNamespace(
                process_webhook_event=AsyncMock(return_value=processing),
                get_invoice=AsyncMock(),
            ),
            user_service=SimpleNamespace(
                get_by_id=AsyncMock(return_value=SimpleNamespace(id=7, telegram_user_id=777000))
            ),
            message_service=SimpleNamespace(show_text=AsyncMock()),
        )

        with (
            patch("app.api.routes.webhook_2328.session_manager.session", new=self.fake_session_context),
            patch("app.api.routes.webhook_2328.build_runtime_services", return_value=services),
        ):
            transport = httpx.ASGITransport(app=create_fastapi_app(self.settings, self.bot))
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post("/webhooks/2328", json=payload)

        self.assertEqual(response.status_code, 200)
        services.message_service.show_text.assert_awaited_once()
        kwargs = services.message_service.show_text.await_args.kwargs
        self.assertEqual(
            kwargs["text"],
            "You have underpaid for this invoice.\n\nIf you want to request a refund, please contact support.",
        )
        self.assertEqual(kwargs["reply_markup"].inline_keyboard[0][0].text, "Main Menu")
        self.assertEqual(len(kwargs["reply_markup"].inline_keyboard), 1)
        services.payment_service.get_invoice.assert_not_awaited()
        self.session.commit.assert_awaited_once()

    async def test_underpaid_check_webhook_sends_dedicated_message(self) -> None:
        payload = {
            "uuid": "abc123",
            "order_id": "ORDER-123",
            "payment_status": "underpaid_check",
            "sign": "valid-signature",
        }
        processing = SimpleNamespace(
            is_success=False,
            access_link=None,
            order=SimpleNamespace(order_id="ORDER-123", user_id=7),
            payment=SimpleNamespace(provider_status=PaymentStatus.UNDERPAID_CHECK),
        )
        services = SimpleNamespace(
            webhook_gateway=SimpleNamespace(
                verify_webhook_signature=lambda *, payload: True,
                parse_webhook_event=lambda parsed_payload: SimpleNamespace(
                    provider_payment_uuid=parsed_payload["uuid"],
                    order_id=parsed_payload["order_id"],
                    result=SimpleNamespace(provider_status=SimpleNamespace(value=parsed_payload["payment_status"])),
                ),
            ),
            payment_service=SimpleNamespace(
                process_webhook_event=AsyncMock(return_value=processing),
                get_invoice=AsyncMock(),
            ),
            user_service=SimpleNamespace(
                get_by_id=AsyncMock(return_value=SimpleNamespace(id=7, telegram_user_id=777000))
            ),
            message_service=SimpleNamespace(show_text=AsyncMock()),
        )

        with (
            patch("app.api.routes.webhook_2328.session_manager.session", new=self.fake_session_context),
            patch("app.api.routes.webhook_2328.build_runtime_services", return_value=services),
        ):
            transport = httpx.ASGITransport(app=create_fastapi_app(self.settings, self.bot))
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post("/webhooks/2328", json=payload)

        self.assertEqual(response.status_code, 200)
        services.message_service.show_text.assert_awaited_once()
        kwargs = services.message_service.show_text.await_args.kwargs
        self.assertEqual(
            kwargs["text"],
            "You have underpaid for this invoice.\n\nIf you want to request a refund, please contact support.",
        )
        self.assertEqual(kwargs["reply_markup"].inline_keyboard[0][0].text, "Main Menu")
        self.assertEqual(len(kwargs["reply_markup"].inline_keyboard), 1)
        services.payment_service.get_invoice.assert_not_awaited()
        self.session.commit.assert_awaited_once()
