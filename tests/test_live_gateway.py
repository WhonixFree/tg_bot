from __future__ import annotations

import re
import unittest
from decimal import Decimal

from pydantic import SecretStr

from app.core.config import get_settings
from app.services.payments.live_gateway import Live2328Gateway


class LiveGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        base = get_settings()
        self.settings = base.model_copy(
            update={
                "merchant_project_uuid": "project-uuid",
                "merchant_api_key": SecretStr("secret-key"),
            }
        )
        self.gateway = Live2328Gateway(self.settings)

    def test_signature_helper_returns_hex_sha256_shape(self) -> None:
        body = self.gateway._encode_json({"amount": "25.00", "currency": "USD"})
        signature = self.gateway._build_signature(body=body, secret="secret-key")
        self.assertRegex(signature, re.compile(r"^[0-9a-f]{64}$"))

    def test_webhook_signature_verification(self) -> None:
        payload = {
            "uuid": "test-uuid",
            "order_id": "ORDER-123",
            "payment_status": "paid",
        }
        signature = self.gateway._build_signature(
            body=self.gateway._encode_webhook_payload(payload),
            secret="secret-key",
        )

        self.assertTrue(self.gateway.verify_webhook_signature(payload={**payload, "sign": signature}))
        self.assertFalse(self.gateway.verify_webhook_signature(payload={**payload, "sign": "bad-signature"}))
        self.assertFalse(self.gateway.verify_webhook_signature(payload=payload))

    def test_nested_result_response_normalization(self) -> None:
        payload = {
            "state": 0,
            "result": {
                "uuid": "abc123",
                "order_id": "ORDER-123",
                "payer_currency": "USDT",
                "payer_amount": "25.50",
                "network": "TRX-TRC20",
                "address": "TXYZabc123",
                "payment_status": "paid",
                "url": "https://2328.io/pay/abc123",
                "expires_at": "2026-01-11T21:00:00Z",
                "qr": "data:image/png;base64,AAA",
            },
        }

        result = self.gateway._normalize_payload(payload)
        self.assertEqual(result.provider_payment_uuid, "abc123")
        self.assertEqual(result.provider_status.value, "paid")
        self.assertEqual(result.payer_currency, "USDT")
        self.assertEqual(result.payer_amount, Decimal("25.50"))
        self.assertEqual(result.provider_url, "https://2328.io/pay/abc123")

    def test_flat_webhook_payload_parsing(self) -> None:
        payload = {
            "uuid": "abc123",
            "order_id": "ORDER-123",
            "payer_currency": "USDT",
            "payer_amount": "25.50",
            "network": "TRX-TRC20",
            "address": "TXYZabc123",
            "payment_status": "paid",
            "url": "https://2328.io/pay/abc123",
            "expires_at": "2026-01-11T21:00:00Z",
            "qr": "data:image/png;base64,AAA",
            "sign": "ignored-for-parsing",
        }

        event = self.gateway.parse_webhook_event(payload)

        self.assertEqual(event.provider_payment_uuid, "abc123")
        self.assertEqual(event.order_id, "ORDER-123")
        self.assertEqual(event.result.provider_status.value, "paid")
