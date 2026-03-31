from __future__ import annotations

from enum import StrEnum


class PaymentProviderMode(StrEnum):
    MOCK = "mock"
    LIVE = "live"


class PaymentProvider(StrEnum):
    PROVIDER_2328 = "2328"


class OrderStatus(StrEnum):
    CREATED = "created"
    INVOICE_CREATED = "invoice_created"
    AWAITING_PAYMENT = "awaiting_payment"
    PAID = "paid"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    FAILED = "failed"


class PaymentStatus(StrEnum):
    CHECK = "check"
    PAID = "paid"
    CANCEL = "cancel"
    OVERPAID = "overpaid"
    UNDERPAID_CHECK = "underpaid_check"
    UNDERPAID = "underpaid"
    AML_LOCK = "aml_lock"
    UNKNOWN = "unknown"


class SubscriptionStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class PlanAccessType(StrEnum):
    LIFETIME_GUIDE_ACCESS = "lifetime_guide_access"


class AccessLinkStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class JoinRequestDecision(StrEnum):
    APPROVED = "approved"
    DECLINED = "declined"
    IGNORED = "ignored"


class BotMessageType(StrEnum):
    SCREEN = "screen"
    INVOICE = "invoice"
    ACCESS = "access"
    SYSTEM = "system"
