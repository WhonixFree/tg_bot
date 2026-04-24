from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from decimal import Decimal, ROUND_UP
from uuid import uuid4

from app.core.enums import PaymentStatus
from app.db.models import Payment
from app.services.payments.schemas import PaymentCreateRequest, PaymentGatewayResult, WebhookEvent
from app.utils.datetime import normalize_utc, utc_now


class Mock2328Gateway:
    _RATES = {
        "USDT": Decimal("1"),
        "USDC": Decimal("1"),
        "BTC": Decimal("65000"),
        "ETH": Decimal("3200"),
    }

    async def create_payment(self, request: PaymentCreateRequest) -> PaymentGatewayResult:
        provider_payment_uuid = str(uuid4())
        payer_amount = self._calculate_amount(
            amount_usd=request.amount_usd,
            payer_currency=request.payer_currency,
        )
        expires_at = utc_now() + timedelta(minutes=30)
        raw_payload = {
            "mock_status": PaymentStatus.CHECK.value,
            "claim_paid_attempts": 0,
            "auto_mark_paid_after_claims": 2,
        }
        return PaymentGatewayResult(
            provider_payment_uuid=provider_payment_uuid,
            provider_status=PaymentStatus.CHECK,
            payer_currency=request.payer_currency,
            payer_amount=payer_amount,
            network=request.network,
            address=f"mock_{request.payer_currency.lower()}_{provider_payment_uuid[:12]}",
            qr_data_uri=f"mock://qr/{provider_payment_uuid}",
            provider_url=f"https://mock-payments.local/{provider_payment_uuid}",
            expires_at=expires_at,
            txid=None,
            raw_payload_json=raw_payload,
        )

    async def get_payment_info(
        self,
        payment: Payment,
        *,
        user_confirmed_payment: bool = False,
    ) -> PaymentGatewayResult:
        payload = dict(payment.raw_payload_json or {})
        expires_at = normalize_utc(payment.expires_at) or utc_now()
        forced_status = payload.get("force_status")
        if forced_status:
            status = PaymentStatus(forced_status)
        elif expires_at <= utc_now():
            status = PaymentStatus.CANCEL
            payload["mock_status"] = status.value
        else:
            attempts = int(payload.get("claim_paid_attempts", 0))
            if user_confirmed_payment:
                attempts += 1
                payload["claim_paid_attempts"] = attempts

            auto_mark_paid_after_claims = int(payload.get("auto_mark_paid_after_claims", 2))
            status = (
                PaymentStatus.PAID
                if user_confirmed_payment and attempts >= auto_mark_paid_after_claims
                else PaymentStatus.CHECK
            )
            payload["mock_status"] = status.value

        return PaymentGatewayResult(
            provider_payment_uuid=payment.provider_payment_uuid,
            provider_status=status,
            payer_currency=payment.payer_currency or "",
            payer_amount=payment.payer_amount or Decimal("0"),
            network=payment.network or "",
            address=payment.address or "",
            qr_data_uri=payment.qr_data_uri,
            provider_url=payment.provider_url,
            expires_at=expires_at,
            txid=payment.txid,
            raw_payload_json=payload,
        )

    def _calculate_amount(self, *, amount_usd: Decimal, payer_currency: str) -> Decimal:
        rate = self._RATES[payer_currency]
        amount = amount_usd / rate
        return amount.quantize(Decimal("0.00000001"), rounding=ROUND_UP)

    def verify_webhook_signature(self, *, payload: Mapping[str, object]) -> bool:
        del payload
        return False

    def parse_webhook_event(self, payload: Mapping[str, object]) -> WebhookEvent:
        raise NotImplementedError("Mock webhook parsing is not implemented.")
