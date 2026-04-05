from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core.enums import OrderStatus, PaymentProvider, PaymentStatus
from app.db.models import Payment
from app.services.payments.payment_service import PaymentService
from app.services.payments.schemas import PaymentCreateRequest, PaymentGatewayResult, WebhookEvent
from app.services.product import FixedProduct
from app.services.rates.service import ConversionQuote


@dataclass
class FakeOrder:
    id: int
    order_id: str
    user_id: int
    plan_id: int
    amount_usd: Decimal
    payment_provider: PaymentProvider
    status: OrderStatus
    payments: list[Payment]


@dataclass
class FakeWebhookPayment:
    id: int
    order_id: int
    provider_status: PaymentStatus
    provider_payment_uuid: str | None = None
    order: FakeOrder | None = None


class FakeOrderRepository:
    def __init__(self) -> None:
        self.created_orders: list[FakeOrder] = []

    async def get_active_unpaid_for_user(self, user_id: int) -> FakeOrder | None:
        for order in reversed(self.created_orders):
            if order.user_id == user_id and order.status == OrderStatus.AWAITING_PAYMENT:
                return order
        return None

    async def get_latest_for_user(self, user_id: int) -> FakeOrder | None:
        for order in reversed(self.created_orders):
            if order.user_id == user_id:
                return order
        return None

    async def get_by_order_id(self, order_id: str) -> FakeOrder | None:
        for order in self.created_orders:
            if order.order_id == order_id:
                return order
        return None

    async def create(
        self,
        *,
        order_id: str,
        user_id: int,
        plan_id: int,
        amount_usd: Decimal,
        payment_provider: PaymentProvider,
        status: OrderStatus,
    ) -> FakeOrder:
        order = FakeOrder(
            id=len(self.created_orders) + 1,
            order_id=order_id,
            user_id=user_id,
            plan_id=plan_id,
            amount_usd=amount_usd,
            payment_provider=payment_provider,
            status=status,
            payments=[],
        )
        self.created_orders.append(order)
        return order


class FakePaymentRepository:
    def __init__(self, order_repository: FakeOrderRepository) -> None:
        self.order_repository = order_repository
        self.created_kwargs: dict[str, object] | None = None
        self.payment_by_provider_uuid: Payment | None = None

    async def create(self, **kwargs) -> Payment:
        self.created_kwargs = kwargs
        payment = Payment(
            order_id=kwargs["order_id"],
            provider_status=kwargs["provider_status"],
            provider_payment_uuid=kwargs.get("provider_payment_uuid"),
            payer_currency=kwargs.get("payer_currency"),
            payer_amount=kwargs.get("payer_amount"),
            network=kwargs.get("network"),
            address=kwargs.get("address"),
            qr_data_uri=kwargs.get("qr_data_uri"),
            provider_url=kwargs.get("provider_url"),
            expires_at=kwargs.get("expires_at"),
            txid=kwargs.get("txid"),
            rate_source=kwargs.get("rate_source"),
            rate_base_currency=kwargs.get("rate_base_currency"),
            rate_quote_currency=kwargs.get("rate_quote_currency"),
            rate_value_usd=kwargs.get("rate_value_usd"),
            rate_fetched_at=kwargs.get("rate_fetched_at"),
            amount_before_rounding=kwargs.get("amount_before_rounding"),
            raw_rate_payload_json=kwargs.get("raw_rate_payload_json"),
            raw_payload_json=kwargs.get("raw_payload_json"),
            paid_at=kwargs.get("paid_at"),
        )
        payment.id = 1
        order = self.order_repository.created_orders[-1]
        order.payments.append(payment)
        return payment

    async def get_by_provider_payment_uuid(self, provider_payment_uuid: str) -> Payment | None:
        if self.payment_by_provider_uuid and self.payment_by_provider_uuid.provider_payment_uuid == provider_payment_uuid:
            return self.payment_by_provider_uuid
        return None


class FakeProductService:
    def __init__(self, price_usd: Decimal = Decimal("25.00")) -> None:
        self.product = FixedProduct(
            id=1,
            code="GUIDE_ACCESS_LIFETIME",
            display_name="Lifetime access",
            description="One-time lifetime access to the private guide channel.",
            price_usd=price_usd,
        )

    async def get_product(self) -> FixedProduct:
        return self.product

    def get_network_label(self, network_code: str) -> str:
        return network_code


class FakeStatusProcessor:
    def __init__(self) -> None:
        self.calls: list[tuple[FakeOrder, Payment, PaymentGatewayResult]] = []

    async def process(self, *, order: FakeOrder, payment: Payment, result: PaymentGatewayResult):
        self.calls.append((order, payment, result))
        return "processed"


class RecordingGateway:
    def __init__(self) -> None:
        self.requests: list[PaymentCreateRequest] = []

    async def create_payment(self, request: PaymentCreateRequest) -> PaymentGatewayResult:
        self.requests.append(request)
        return PaymentGatewayResult(
            provider_payment_uuid="provider-uuid",
            provider_status=PaymentStatus.CHECK,
            payer_currency=request.payer_currency,
            payer_amount=Decimal("0.00123456"),
            network=request.network,
            address="provider-address",
            qr_data_uri="data:image/png;base64,AAA",
            provider_url="https://2328.io/pay/provider-uuid",
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
            txid=None,
            raw_payload_json={"result": {"payer_amount": "0.00123456"}},
        )


class FailingRateService:
    async def get_locked_quote(self, *, amount_usd: Decimal, coin_code: str) -> ConversionQuote:
        raise RuntimeError("rate lookup failed")


class SuccessfulRateService:
    async def get_locked_quote(self, *, amount_usd: Decimal, coin_code: str) -> ConversionQuote:
        return ConversionQuote(
            coin_code=coin_code,
            rate_source="coingecko",
            rate_base_currency="USD",
            rate_quote_currency=coin_code,
            rate_value_usd=Decimal("65000"),
            rate_fetched_at=datetime.now(UTC),
            amount_before_rounding=Decimal("0.00038461"),
            payer_amount=Decimal("0.00038462"),
            raw_rate_payload_json={"coin": coin_code},
        )


class PaymentServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_invoice_uses_order_amount_usd_as_canonical_input(self) -> None:
        order_repo = FakeOrderRepository()
        payment_repo = FakePaymentRepository(order_repo)
        gateway = RecordingGateway()
        service = PaymentService(
            order_repository=order_repo,
            payment_repository=payment_repo,
            product_service=FakeProductService(),
            gateway=gateway,
            status_processor=FakeStatusProcessor(),
            rate_service=FailingRateService(),
            use_external_rates=True,
        )

        await service.create_invoice(user_id=1, coin_code="USDT", network_code="TRX-TRC20")

        self.assertEqual(gateway.requests[0].amount_usd, Decimal("25.00"))

    async def test_btc_rate_failure_does_not_block_invoice_creation(self) -> None:
        order_repo = FakeOrderRepository()
        payment_repo = FakePaymentRepository(order_repo)
        gateway = RecordingGateway()
        service = PaymentService(
            order_repository=order_repo,
            payment_repository=payment_repo,
            product_service=FakeProductService(),
            gateway=gateway,
            status_processor=FakeStatusProcessor(),
            rate_service=FailingRateService(),
            use_external_rates=True,
        )

        invoice = await service.create_invoice(user_id=1, coin_code="BTC", network_code="BTC")

        self.assertEqual(invoice.payer_amount, Decimal("0.00123456"))
        self.assertIsNone(payment_repo.created_kwargs["rate_source"])

    async def test_auxiliary_rate_metadata_is_persisted_when_lookup_succeeds(self) -> None:
        order_repo = FakeOrderRepository()
        payment_repo = FakePaymentRepository(order_repo)
        gateway = RecordingGateway()
        service = PaymentService(
            order_repository=order_repo,
            payment_repository=payment_repo,
            product_service=FakeProductService(),
            gateway=gateway,
            status_processor=FakeStatusProcessor(),
            rate_service=SuccessfulRateService(),
            use_external_rates=True,
        )

        await service.create_invoice(user_id=1, coin_code="ETH", network_code="ETH-ERC20")

        self.assertEqual(payment_repo.created_kwargs["rate_source"], "coingecko")
        self.assertEqual(payment_repo.created_kwargs["rate_quote_currency"], "ETH")
        self.assertEqual(payment_repo.created_kwargs["rate_value_usd"], Decimal("65000"))

    async def test_webhook_processing_uses_provider_uuid_lookup(self) -> None:
        order_repo = FakeOrderRepository()
        payment_repo = FakePaymentRepository(order_repo)
        status_processor = FakeStatusProcessor()
        gateway = RecordingGateway()
        service = PaymentService(
            order_repository=order_repo,
            payment_repository=payment_repo,
            product_service=FakeProductService(),
            gateway=gateway,
            status_processor=status_processor,
            rate_service=FailingRateService(),
            use_external_rates=False,
        )
        order = await order_repo.create(
            order_id="ORDER-123",
            user_id=1,
            plan_id=1,
            amount_usd=Decimal("25.00"),
            payment_provider=PaymentProvider.PROVIDER_2328,
            status=OrderStatus.AWAITING_PAYMENT,
        )
        payment = FakeWebhookPayment(
            id=10,
            order_id=order.id,
            provider_status=PaymentStatus.CHECK,
            provider_payment_uuid="provider-uuid",
            order=order,
        )
        order.payments.append(payment)
        payment_repo.payment_by_provider_uuid = payment
        event = WebhookEvent(
            provider_payment_uuid="provider-uuid",
            order_id="ORDER-123",
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

        result = await service.process_webhook_event(event)

        self.assertEqual(result, "processed")
        self.assertEqual(len(status_processor.calls), 1)
        self.assertIs(status_processor.calls[0][0], order)
        self.assertIs(status_processor.calls[0][1], payment)

    async def test_webhook_processing_falls_back_to_order_id_lookup(self) -> None:
        order_repo = FakeOrderRepository()
        payment_repo = FakePaymentRepository(order_repo)
        status_processor = FakeStatusProcessor()
        gateway = RecordingGateway()
        service = PaymentService(
            order_repository=order_repo,
            payment_repository=payment_repo,
            product_service=FakeProductService(),
            gateway=gateway,
            status_processor=status_processor,
            rate_service=FailingRateService(),
            use_external_rates=False,
        )
        order = await order_repo.create(
            order_id="ORDER-456",
            user_id=1,
            plan_id=1,
            amount_usd=Decimal("25.00"),
            payment_provider=PaymentProvider.PROVIDER_2328,
            status=OrderStatus.AWAITING_PAYMENT,
        )
        payment = FakeWebhookPayment(
            id=11,
            order_id=order.id,
            provider_status=PaymentStatus.CHECK,
            provider_payment_uuid="provider-uuid",
            order=order,
        )
        order.payments.append(payment)
        event = WebhookEvent(
            provider_payment_uuid="missing-provider-uuid",
            order_id="ORDER-456",
            result=PaymentGatewayResult(
                provider_payment_uuid="missing-provider-uuid",
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

        result = await service.process_webhook_event(event)

        self.assertEqual(result, "processed")
        self.assertEqual(len(status_processor.calls), 1)
        self.assertIs(status_processor.calls[0][0], order)
        self.assertIs(status_processor.calls[0][1], payment)

    async def test_webhook_processing_unknown_order_is_ignored(self) -> None:
        order_repo = FakeOrderRepository()
        payment_repo = FakePaymentRepository(order_repo)
        status_processor = FakeStatusProcessor()
        gateway = RecordingGateway()
        service = PaymentService(
            order_repository=order_repo,
            payment_repository=payment_repo,
            product_service=FakeProductService(),
            gateway=gateway,
            status_processor=status_processor,
            rate_service=FailingRateService(),
            use_external_rates=False,
        )
        event = WebhookEvent(
            provider_payment_uuid="missing-provider-uuid",
            order_id="UNKNOWN-ORDER",
            result=PaymentGatewayResult(
                provider_payment_uuid="missing-provider-uuid",
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

        result = await service.process_webhook_event(event)

        self.assertIsNone(result)
        self.assertEqual(status_processor.calls, [])
