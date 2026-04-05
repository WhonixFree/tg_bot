from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import Settings
from app.core.enums import PaymentStatus
from app.db.models import Payment
from app.services.payments.schemas import (
    PaymentCreateRequest,
    PaymentGatewayResult,
    WebhookEvent,
)


class Live2328Gateway:
    _BASE_URL = "https://api.2328.io/api"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def create_payment(self, request: PaymentCreateRequest) -> PaymentGatewayResult:
        self._require_credentials()
        # 2328 invoice creation uses the canonical USD amount from our order.
        # The provider returns the payable crypto amount as payer_amount.
        payload = {
            "amount": str(request.amount_usd),
            "currency": "USD",
            "order_id": request.order_id,
            "to_currency": request.payer_currency,
            "network": request.network,
            "url_callback": f"{self._settings.app_base_url.rstrip('/')}{self._settings.payment_webhook_path}",
        }
        response_payload = await self._post("/v1/payment", payload)
        return self._normalize_payload(response_payload)

    async def get_payment_info(
        self,
        payment: Payment,
        *,
        user_confirmed_payment: bool = False,
    ) -> PaymentGatewayResult:
        del user_confirmed_payment
        self._require_credentials()
        payload = {
            "uuid": payment.provider_payment_uuid,
            "order_id": payment.order.order_id if payment.order is not None else None,
        }
        response_payload = await self._post("/v1/payment/info", payload)
        return self._normalize_payload(response_payload)

    def verify_webhook_signature(self, *, payload: Mapping[str, object]) -> bool:
        signature = payload.get("sign")
        if not isinstance(signature, str) or not signature:
            return False
        api_key = self._settings.merchant_api_key
        if api_key is None or not api_key.get_secret_value():
            raise RuntimeError("MERCHANT_API_KEY is required for webhook signature verification.")
        body = self._encode_webhook_payload(payload)
        expected = self._build_signature(body=body, secret=api_key.get_secret_value())
        return hmac.compare_digest(expected, signature)

    def parse_webhook_event(self, payload: Mapping[str, object]) -> WebhookEvent:
        result = self._normalize_payload(payload)
        event_payload = self._unwrap_result(payload)
        order_id = self._extract_first_string(event_payload, "order_id", "provider_order_id")
        return WebhookEvent(
            provider_payment_uuid=result.provider_payment_uuid,
            order_id=order_id,
            result=result,
        )

    async def _post(self, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        body = self._encode_json(payload)
        headers = {
            "Content-Type": "application/json",
            "project": self._settings.merchant_project_uuid or "",
            "sign": self._build_signature(
                body=body,
                secret=self._settings.merchant_api_key.get_secret_value() if self._settings.merchant_api_key else "",
            ),
        }
        timeout = httpx.Timeout(15.0, connect=5.0)
        async with httpx.AsyncClient(base_url=self._BASE_URL, timeout=timeout) as client:
            response = await client.post(path, content=body, headers=headers)
            response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("2328 response payload must be a JSON object.")
        return data

    def _require_credentials(self) -> None:
        if not self._settings.merchant_project_uuid or self._settings.merchant_api_key is None:
            raise RuntimeError("Live 2328 gateway requires merchant credentials.")

    def _normalize_payload(self, payload: Mapping[str, object]) -> PaymentGatewayResult:
        event_payload = self._unwrap_result(payload)
        payer_currency = self._extract_first_string(
            event_payload,
            "payer_currency",
            "to_currency",
            "currency",
            "coin",
        ) or ""
        payer_amount = self._extract_decimal(event_payload, "payer_amount", "payment_amount", "amount")
        network = self._extract_first_string(event_payload, "network", "network_code") or ""
        address = self._extract_first_string(event_payload, "address", "wallet") or ""
        provider_status = self._map_status(
            self._extract_first_string(event_payload, "payment_status", "status", "provider_status")
            or "unknown"
        )
        return PaymentGatewayResult(
            provider_payment_uuid=self._extract_first_string(
                event_payload,
                "uuid",
                "provider_payment_uuid",
                "id",
            ),
            provider_status=provider_status,
            payer_currency=payer_currency,
            payer_amount=payer_amount,
            network=network,
            address=address,
            qr_data_uri=self._extract_first_string(event_payload, "qr_data_uri", "qr"),
            provider_url=self._extract_first_string(event_payload, "payment_url", "provider_url", "url"),
            expires_at=self._extract_datetime(event_payload, "expires_at", "expired_at"),
            txid=self._extract_first_string(event_payload, "txid", "hash"),
            raw_payload_json=dict(payload),
        )

    def _map_status(self, status: str) -> PaymentStatus:
        mapping = {
            "check": PaymentStatus.CHECK,
            "pending": PaymentStatus.CHECK,
            "paid": PaymentStatus.PAID,
            "overpaid": PaymentStatus.OVERPAID,
            "cancel": PaymentStatus.CANCEL,
            "underpaid_check": PaymentStatus.UNDERPAID_CHECK,
            "underpaid": PaymentStatus.UNDERPAID,
            "aml_lock": PaymentStatus.AML_LOCK,
        }
        return mapping.get(status.lower(), PaymentStatus.UNKNOWN)

    def _encode_json(self, payload: Mapping[str, Any]) -> bytes:
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def _encode_webhook_payload(self, payload: Mapping[str, object]) -> bytes:
        sanitized_payload = dict(payload)
        sanitized_payload.pop("sign", None)
        return json.dumps(
            sanitized_payload,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    def _build_signature(self, *, body: bytes, secret: str) -> str:
        base64_body = base64.b64encode(body)
        return hmac.new(secret.encode("utf-8"), base64_body, hashlib.sha256).hexdigest()

    def _unwrap_result(self, payload: Mapping[str, object]) -> Mapping[str, object]:
        result = payload.get("result")
        if isinstance(result, Mapping):
            return result
        return payload

    def _extract_first_string(self, payload: Mapping[str, object], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    def _extract_decimal(self, payload: Mapping[str, object], *keys: str) -> Decimal:
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            try:
                return Decimal(str(value))
            except Exception:
                continue
        return Decimal("0")

    def _extract_datetime(self, payload: Mapping[str, object], *keys: str) -> datetime:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str):
                normalized = value.replace("Z", "+00:00")
                try:
                    return datetime.fromisoformat(normalized)
                except ValueError:
                    continue
        return datetime.now(UTC)
