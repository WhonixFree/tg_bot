from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.core.enums import OrderStatus, PaymentStatus
from app.services.payments.schemas import PaymentGatewayResult
from app.services.payments.status_processor import PaymentStatusProcessor


@dataclass
class FakeOrder:
    id: int
    order_id: str
    user_id: int
    plan_id: int
    status: OrderStatus


@dataclass
class FakePayment:
    id: int
    order_id: int
    provider_status: PaymentStatus
    provider_payment_uuid: str | None = None
    payer_currency: str | None = None
    payer_amount: Decimal | None = None
    network: str | None = None
    address: str | None = None
    qr_data_uri: str | None = None
    provider_url: str | None = None
    expires_at: datetime | None = None
    txid: str | None = None
    raw_payload_json: dict | None = None
    paid_at: datetime | None = None


class FakeOrderRepository:
    def __init__(self) -> None:
        self.updated_statuses: list[OrderStatus] = []

    async def update_status(self, order: FakeOrder, status: OrderStatus) -> FakeOrder:
        order.status = status
        self.updated_statuses.append(status)
        return order


class FakePaymentRepository:
    def __init__(self) -> None:
        self.saved = 0

    async def save(self, payment: FakePayment) -> FakePayment:
        self.saved += 1
        return payment


class FakeSubscriptionService:
    def __init__(self, subscription) -> None:
        self.subscription = subscription
        self.calls = 0

    async def ensure_lifetime_subscription(self, *, user_id: int, plan_id: int):
        self.calls += 1
        return self.subscription


class FakeAccessService:
    def __init__(self, access_link) -> None:
        self.access_link = access_link
        self.calls = 0

    async def ensure_access_link(self, *, user_id: int, subscription):
        self.calls += 1
        return self.access_link


class PaymentStatusProcessorTests(unittest.IsolatedAsyncioTestCase):
    async def test_overpaid_behaves_like_successful_payment(self) -> None:
        order = FakeOrder(
            id=1,
            order_id="ORDER-OVERPAID",
            user_id=10,
            plan_id=20,
            status=OrderStatus.AWAITING_PAYMENT,
        )
        payment = FakePayment(id=2, order_id=1, provider_status=PaymentStatus.CHECK)
        order_repository = FakeOrderRepository()
        payment_repository = FakePaymentRepository()
        subscription = SimpleNamespace(id=100)
        access_link = SimpleNamespace(id=200, invite_link="https://t.me/join/example")
        subscription_service = FakeSubscriptionService(subscription)
        access_service = FakeAccessService(access_link)
        processor = PaymentStatusProcessor(
            order_repository=order_repository,
            payment_repository=payment_repository,
            subscription_service=subscription_service,
            access_service=access_service,
        )

        result = await processor.process(
            order=order,
            payment=payment,
            result=PaymentGatewayResult(
                provider_payment_uuid="provider-uuid",
                provider_status=PaymentStatus.OVERPAID,
                payer_currency="USDT",
                payer_amount=Decimal("30"),
                network="TRX-TRC20",
                address="wallet",
                qr_data_uri=None,
                provider_url="https://2328.io/pay/provider-uuid",
                expires_at=datetime.now(UTC),
                txid="txid",
                raw_payload_json={"payment_status": "overpaid"},
            ),
        )

        self.assertEqual(order.status, OrderStatus.PAID)
        self.assertEqual(payment.provider_status, PaymentStatus.OVERPAID)
        self.assertIsNotNone(payment.paid_at)
        self.assertEqual(order_repository.updated_statuses, [OrderStatus.PAID])
        self.assertEqual(subscription_service.calls, 1)
        self.assertEqual(access_service.calls, 1)
        self.assertTrue(result.is_success)
        self.assertIs(result.subscription, subscription)
        self.assertIs(result.access_link, access_link)

    async def test_paid_webhook_updates_payment_and_order_and_activates_access(self) -> None:
        order = FakeOrder(
            id=1,
            order_id="ORDER-123",
            user_id=10,
            plan_id=20,
            status=OrderStatus.AWAITING_PAYMENT,
        )
        payment = FakePayment(id=2, order_id=1, provider_status=PaymentStatus.CHECK)
        subscription = SimpleNamespace(id=100)
        access_link = SimpleNamespace(id=200, invite_link="https://t.me/join/example")
        processor = PaymentStatusProcessor(
            order_repository=FakeOrderRepository(),
            payment_repository=FakePaymentRepository(),
            subscription_service=FakeSubscriptionService(subscription),
            access_service=FakeAccessService(access_link),
        )
        result = await processor.process(
            order=order,
            payment=payment,
            result=PaymentGatewayResult(
                provider_payment_uuid="provider-uuid",
                provider_status=PaymentStatus.PAID,
                payer_currency="USDT",
                payer_amount=Decimal("25"),
                network="TRX-TRC20",
                address="wallet",
                qr_data_uri=None,
                provider_url="https://2328.io/pay/provider-uuid",
                expires_at=datetime.now(UTC),
                txid="txid",
                raw_payload_json={"payment_status": "paid"},
            ),
        )

        self.assertEqual(order.status, OrderStatus.PAID)
        self.assertEqual(payment.provider_status, PaymentStatus.PAID)
        self.assertEqual(payment.provider_payment_uuid, "provider-uuid")
        self.assertIsNotNone(payment.paid_at)
        self.assertIs(result.subscription, subscription)
        self.assertIs(result.access_link, access_link)

    async def test_paid_webhook_can_reuse_existing_access_link(self) -> None:
        order = FakeOrder(
            id=1,
            order_id="ORDER-123",
            user_id=10,
            plan_id=20,
            status=OrderStatus.AWAITING_PAYMENT,
        )
        payment = FakePayment(id=2, order_id=1, provider_status=PaymentStatus.CHECK)
        existing_subscription = SimpleNamespace(id=101)
        existing_access_link = SimpleNamespace(id=201, invite_link="https://t.me/join/existing")
        subscription_service = FakeSubscriptionService(existing_subscription)
        access_service = FakeAccessService(existing_access_link)
        processor = PaymentStatusProcessor(
            order_repository=FakeOrderRepository(),
            payment_repository=FakePaymentRepository(),
            subscription_service=subscription_service,
            access_service=access_service,
        )

        result = await processor.process(
            order=order,
            payment=payment,
            result=PaymentGatewayResult(
                provider_payment_uuid="provider-uuid",
                provider_status=PaymentStatus.PAID,
                payer_currency="USDT",
                payer_amount=Decimal("25"),
                network="TRX-TRC20",
                address="wallet",
                qr_data_uri=None,
                provider_url="https://2328.io/pay/provider-uuid",
                expires_at=datetime.now(UTC),
                txid="txid",
                raw_payload_json={"payment_status": "paid"},
            ),
        )

        self.assertIs(result.subscription, existing_subscription)
        self.assertIs(result.access_link, existing_access_link)
        self.assertEqual(subscription_service.calls, 1)
        self.assertEqual(access_service.calls, 1)

    async def test_underpaid_check_does_not_activate_access(self) -> None:
        order = FakeOrder(
            id=1,
            order_id="ORDER-UNDERPAID-CHECK",
            user_id=10,
            plan_id=20,
            status=OrderStatus.AWAITING_PAYMENT,
        )
        payment = FakePayment(id=2, order_id=1, provider_status=PaymentStatus.CHECK)
        order_repository = FakeOrderRepository()
        payment_repository = FakePaymentRepository()
        subscription_service = FakeSubscriptionService(SimpleNamespace(id=100))
        access_service = FakeAccessService(SimpleNamespace(id=200, invite_link="https://t.me/join/example"))
        processor = PaymentStatusProcessor(
            order_repository=order_repository,
            payment_repository=payment_repository,
            subscription_service=subscription_service,
            access_service=access_service,
        )

        result = await processor.process(
            order=order,
            payment=payment,
            result=PaymentGatewayResult(
                provider_payment_uuid="provider-uuid",
                provider_status=PaymentStatus.UNDERPAID_CHECK,
                payer_currency="USDT",
                payer_amount=Decimal("20"),
                network="TRX-TRC20",
                address="wallet",
                qr_data_uri=None,
                provider_url="https://2328.io/pay/provider-uuid",
                expires_at=datetime.now(UTC),
                txid="txid",
                raw_payload_json={"payment_status": "underpaid_check"},
            ),
        )

        self.assertEqual(order.status, OrderStatus.AWAITING_PAYMENT)
        self.assertEqual(payment.provider_status, PaymentStatus.UNDERPAID_CHECK)
        self.assertIsNone(payment.paid_at)
        self.assertEqual(order_repository.updated_statuses, [OrderStatus.AWAITING_PAYMENT])
        self.assertEqual(payment_repository.saved, 1)
        self.assertEqual(subscription_service.calls, 0)
        self.assertEqual(access_service.calls, 0)
        self.assertFalse(result.is_success)
        self.assertIsNone(result.subscription)
        self.assertIsNone(result.access_link)

    async def test_underpaid_does_not_activate_access(self) -> None:
        order = FakeOrder(
            id=1,
            order_id="ORDER-UNDERPAID",
            user_id=10,
            plan_id=20,
            status=OrderStatus.AWAITING_PAYMENT,
        )
        payment = FakePayment(id=2, order_id=1, provider_status=PaymentStatus.CHECK)
        order_repository = FakeOrderRepository()
        payment_repository = FakePaymentRepository()
        subscription_service = FakeSubscriptionService(SimpleNamespace(id=100))
        access_service = FakeAccessService(SimpleNamespace(id=200, invite_link="https://t.me/join/example"))
        processor = PaymentStatusProcessor(
            order_repository=order_repository,
            payment_repository=payment_repository,
            subscription_service=subscription_service,
            access_service=access_service,
        )

        result = await processor.process(
            order=order,
            payment=payment,
            result=PaymentGatewayResult(
                provider_payment_uuid="provider-uuid",
                provider_status=PaymentStatus.UNDERPAID,
                payer_currency="USDT",
                payer_amount=Decimal("20"),
                network="TRX-TRC20",
                address="wallet",
                qr_data_uri=None,
                provider_url="https://2328.io/pay/provider-uuid",
                expires_at=datetime.now(UTC),
                txid="txid",
                raw_payload_json={"payment_status": "underpaid"},
            ),
        )

        self.assertEqual(order.status, OrderStatus.AWAITING_PAYMENT)
        self.assertEqual(payment.provider_status, PaymentStatus.UNDERPAID)
        self.assertIsNone(payment.paid_at)
        self.assertEqual(order_repository.updated_statuses, [OrderStatus.AWAITING_PAYMENT])
        self.assertEqual(payment_repository.saved, 1)
        self.assertEqual(subscription_service.calls, 0)
        self.assertEqual(access_service.calls, 0)
        self.assertFalse(result.is_success)
        self.assertIsNone(result.subscription)
        self.assertIsNone(result.access_link)
