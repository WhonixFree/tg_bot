from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.core.enums import PaymentStatus


@dataclass(frozen=True)
class PaymentCreateRequest:
    order_id: str
    amount_usd: Decimal
    payer_currency: str
    network: str


@dataclass(frozen=True)
class PaymentGatewayResult:
    provider_payment_uuid: str | None
    provider_status: PaymentStatus
    payer_currency: str
    payer_amount: Decimal
    network: str
    address: str
    qr_data_uri: str | None
    provider_url: str | None
    expires_at: datetime
    txid: str | None
    raw_payload_json: dict[str, Any]


@dataclass(frozen=True)
class WebhookEvent:
    provider_payment_uuid: str | None
    order_id: str | None
    result: PaymentGatewayResult


@dataclass(frozen=True)
class InvoiceView:
    public_order_id: str
    amount_usd: Decimal
    payer_currency: str
    payer_amount: Decimal
    network: str
    network_label: str
    address: str
    provider_url: str | None
    qr_data_uri: str | None
    expires_at: datetime
    status: PaymentStatus
