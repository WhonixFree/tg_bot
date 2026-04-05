from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from app.db.models import Payment
from app.services.payments.schemas import PaymentCreateRequest, PaymentGatewayResult, WebhookEvent


class PaymentGateway(Protocol):
    async def create_payment(self, request: PaymentCreateRequest) -> PaymentGatewayResult:
        ...

    async def get_payment_info(
        self,
        payment: Payment,
        *,
        user_confirmed_payment: bool = False,
    ) -> PaymentGatewayResult:
        ...

    def verify_webhook_signature(self, *, payload: Mapping[str, object]) -> bool:
        ...

    def parse_webhook_event(self, payload: Mapping[str, object]) -> WebhookEvent:
        ...
