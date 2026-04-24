from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import contextlib
from uuid import uuid4

from app.core.enums import OrderStatus, PaymentProvider, PaymentStatus
from app.core.logging import get_logger
from app.db.models import Order, Payment
from app.db.repositories.order import OrderRepository
from app.db.repositories.payment import PaymentRepository
from app.services.payments.gateway import PaymentGateway
from app.services.payments.status_processor import PaymentProcessingResult, PaymentStatusProcessor
from app.services.product import ProductService
from app.services.payments.schemas import InvoiceView, PaymentCreateRequest, WebhookEvent
from app.services.rates.service import RateService
from app.utils.datetime import normalize_utc, utc_now


logger = get_logger(__name__)


@dataclass(frozen=True)
class PurchaseEntry:
    active_invoice: InvoiceView | None = None
    expired_invoice: InvoiceView | None = None


class PaymentService:
    def __init__(
        self,
        *,
        order_repository: OrderRepository,
        payment_repository: PaymentRepository,
        product_service: ProductService,
        gateway: PaymentGateway,
        status_processor: PaymentStatusProcessor,
        rate_service: RateService,
        use_external_rates: bool,
    ) -> None:
        self._order_repository = order_repository
        self._payment_repository = payment_repository
        self._product_service = product_service
        self._gateway = gateway
        self._status_processor = status_processor
        self._rate_service = rate_service
        self._use_external_rates = use_external_rates

    async def get_purchase_entry(self, *, user_id: int) -> PurchaseEntry:
        active_order = await self._order_repository.get_active_unpaid_for_user(user_id)
        if active_order is not None:
            payment = self._require_payment(active_order)
            return PurchaseEntry(active_invoice=self._build_invoice_view(active_order, payment))

        latest_order = await self._order_repository.get_latest_for_user(user_id)
        if latest_order is None:
            return PurchaseEntry()

        payment = self._require_payment(latest_order)
        if self._is_inactive_invoice(order=latest_order, payment=payment):
            if latest_order.status == OrderStatus.AWAITING_PAYMENT and self._is_expired(payment):
                payment.provider_status = PaymentStatus.CANCEL
                payment.raw_payload_json = {
                    **(payment.raw_payload_json or {}),
                    "mock_status": PaymentStatus.CANCEL.value,
                    "expired_locally": True,
                }
                await self._payment_repository.save(payment)
                await self._order_repository.update_status(latest_order, OrderStatus.EXPIRED)
            return PurchaseEntry(expired_invoice=self._build_invoice_view(latest_order, payment))

        return PurchaseEntry()

    async def create_invoice(
        self,
        *,
        user_id: int,
        coin_code: str,
        network_code: str,
    ) -> InvoiceView:
        product = await self._product_service.get_product()
        active_order = await self._order_repository.get_active_unpaid_for_user(user_id)
        if active_order is not None:
            return self._build_invoice_view(active_order, self._require_payment(active_order))

        conversion_quote = None
        if self._use_external_rates and coin_code in {"BTC", "ETH"}:
            # USD remains the canonical invoice input for 2328.
            # External BTC/ETH rates are stored only as auxiliary audit metadata.
            with contextlib.suppress(Exception):
                conversion_quote = await self._rate_service.get_locked_quote(
                    amount_usd=product.price_usd,
                    coin_code=coin_code,
                )

        order = await self._order_repository.create(
            order_id=uuid4().hex,
            user_id=user_id,
            plan_id=product.id,
            amount_usd=product.price_usd,
            payment_provider=PaymentProvider.PROVIDER_2328,
            status=OrderStatus.AWAITING_PAYMENT,
        )
        gateway_result = await self._gateway.create_payment(
            PaymentCreateRequest(
                order_id=order.order_id,
                amount_usd=product.price_usd,
                payer_currency=coin_code,
                network=network_code,
            )
        )
        payment = await self._payment_repository.create(
            order_id=order.id,
            provider_status=gateway_result.provider_status,
            provider_payment_uuid=gateway_result.provider_payment_uuid,
            payer_currency=gateway_result.payer_currency,
            payer_amount=gateway_result.payer_amount,
            network=gateway_result.network,
            address=gateway_result.address,
            qr_data_uri=gateway_result.qr_data_uri,
            provider_url=gateway_result.provider_url,
            expires_at=gateway_result.expires_at,
            txid=gateway_result.txid,
            rate_source=conversion_quote.rate_source if conversion_quote is not None else None,
            rate_base_currency=conversion_quote.rate_base_currency if conversion_quote is not None else None,
            rate_quote_currency=conversion_quote.rate_quote_currency if conversion_quote is not None else None,
            rate_value_usd=conversion_quote.rate_value_usd if conversion_quote is not None else None,
            rate_fetched_at=conversion_quote.rate_fetched_at if conversion_quote is not None else None,
            amount_before_rounding=conversion_quote.amount_before_rounding if conversion_quote is not None else None,
            raw_rate_payload_json=conversion_quote.raw_rate_payload_json if conversion_quote is not None else None,
            raw_payload_json=gateway_result.raw_payload_json,
        )
        return self._build_invoice_view(order, payment)

    async def refresh_invoice(
        self,
        *,
        public_order_id: str,
        user_confirmed_payment: bool,
    ) -> PaymentProcessingResult:
        order = await self._get_order_or_raise(public_order_id)
        payment = self._require_payment(order)
        gateway_result = await self._gateway.get_payment_info(
            payment,
            user_confirmed_payment=user_confirmed_payment,
        )
        return await self._status_processor.process(order=order, payment=payment, result=gateway_result)

    async def cancel_invoice(self, *, public_order_id: str) -> InvoiceView:
        order = await self._get_order_or_raise(public_order_id)
        payment = self._require_payment(order)
        payment.provider_status = PaymentStatus.CANCEL
        payment.raw_payload_json = {
            **(payment.raw_payload_json or {}),
            "mock_status": PaymentStatus.CANCEL.value,
            "cancelled_by_user": True,
        }
        await self._payment_repository.save(payment)
        await self._order_repository.update_status(order, OrderStatus.CANCELLED)
        return self._build_invoice_view(order, payment)

    async def create_fresh_invoice_from_previous(
        self,
        *,
        user_id: int,
        coin_code: str,
        network_code: str,
    ) -> InvoiceView:
        return await self.create_invoice(
            user_id=user_id,
            coin_code=coin_code,
            network_code=network_code,
        )

    async def get_invoice(self, *, public_order_id: str) -> InvoiceView:
        order = await self._get_order_or_raise(public_order_id)
        return self._build_invoice_view(order, self._require_payment(order))

    async def process_webhook_event(self, event: WebhookEvent) -> PaymentProcessingResult | None:
        logger.info(
            "Webhook accepted for processing provider_uuid=%s order_id=%s provider_status=%s",
            event.provider_payment_uuid,
            event.order_id,
            event.result.provider_status,
        )
        if event.provider_payment_uuid:
            payment = await self._payment_repository.get_by_provider_payment_uuid(event.provider_payment_uuid)
            if payment is not None and payment.order is not None:
                logger.info(
                    "Webhook local payment found provider_uuid=%s local_payment_id=%s local_order_id=%s",
                    event.provider_payment_uuid,
                    payment.id,
                    payment.order.order_id,
                )
                return await self._status_processor.process(
                    order=payment.order,
                    payment=payment,
                    result=event.result,
                )
            logger.info(
                "Webhook local payment not found provider_uuid=%s",
                event.provider_payment_uuid,
            )

        if event.order_id:
            order = await self._order_repository.get_by_order_id(event.order_id)
            if order is None:
                logger.info("Webhook ignored local order not found order_id=%s", event.order_id)
                return None
            logger.info(
                "Webhook local order found order_id=%s local_order_pk=%s",
                order.order_id,
                order.id,
            )
            payment = self._require_payment(order)
            return await self._status_processor.process(
                order=order,
                payment=payment,
                result=event.result,
            )

        logger.info(
            "Webhook ignored no resolvable local identifiers provider_uuid=%s order_id=%s",
            event.provider_payment_uuid,
            event.order_id,
        )
        return None

    async def _get_order_or_raise(self, public_order_id: str) -> Order:
        order = await self._order_repository.get_by_order_id(public_order_id)
        if order is None:
            raise RuntimeError(f"Order {public_order_id} not found.")
        return order

    def _require_payment(self, order: Order) -> Payment:
        payment = order.payments[0] if order.payments else None
        if payment is None:
            raise RuntimeError(f"Order {order.order_id} has no payment.")
        return payment

    def _build_invoice_view(self, order: Order, payment: Payment) -> InvoiceView:
        return InvoiceView(
            public_order_id=order.order_id,
            amount_usd=order.amount_usd,
            payer_currency=payment.payer_currency or "",
            payer_amount=payment.payer_amount or Decimal("0"),
            network=payment.network or "",
            network_label=self._product_service.get_network_label(payment.network or ""),
            address=payment.address or "",
            provider_url=payment.provider_url,
            qr_data_uri=payment.qr_data_uri,
            expires_at=normalize_utc(payment.expires_at) or utc_now(),
            status=payment.provider_status,
        )

    def _is_inactive_invoice(self, *, order: Order, payment: Payment) -> bool:
        return (
            order.status in {OrderStatus.CANCELLED, OrderStatus.EXPIRED}
            or payment.provider_status == PaymentStatus.CANCEL
            or self._is_expired(payment)
        )

    def _is_expired(self, payment: Payment) -> bool:
        expires_at = normalize_utc(payment.expires_at)
        return expires_at is not None and expires_at <= utc_now()
