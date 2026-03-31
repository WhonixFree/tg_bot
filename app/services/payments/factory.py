from __future__ import annotations

from app.core.config import Settings
from app.core.enums import PaymentProviderMode
from app.services.payments.gateway import PaymentGateway
from app.services.payments.live_gateway import Live2328Gateway
from app.services.payments.mock_gateway import Mock2328Gateway


def get_payment_gateway(settings: Settings) -> PaymentGateway:
    if settings.payment_provider_mode == PaymentProviderMode.MOCK:
        return Mock2328Gateway()
    return Live2328Gateway(settings)


def get_webhook_gateway(settings: Settings) -> Live2328Gateway:
    return Live2328Gateway(settings)
