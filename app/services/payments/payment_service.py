from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from app.core.enums import OrderStatus, PaymentProvider, PaymentStatus
from app.db.models import Order, Payment, Plan
from app.db.repositories.order import OrderRepository
from app.db.repositories.payment import PaymentRepository
from app.services.catalog import CatalogService
from app.services.payments.gateway import PaymentGateway
from app.services.payments.status_processor import PaymentProcessingResult, PaymentStatusProcessor
from app.services.payments.schemas import InvoiceView, PaymentCreateRequest, WebhookEvent
from app.utils.datetime import normalize_sqlite_utc, utc_now_naive


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
        catalog_service: CatalogService,
        gateway: PaymentGateway,
        status_processor: PaymentStatusProcessor,
    ) -> None:
        self._order_repository = order_repository
        self._payment_repository = payment_repository
        self._catalog_service = catalog_service
        self._gateway = gateway
        self._status_processor = status_processor

    async def get_purchase_entry(self, *, user_id: int, plan: Plan) -> PurchaseEntry:
        active_order = await self._order_repository.get_active_unpaid_for_user_plan(user_id, plan.id)
        if active_order is not None:
            payment = self._require_payment(active_order)
            return PurchaseEntry(active_invoice=self._build_invoice_view(active_order, payment))

        latest_order = await self._order_repository.get_latest_for_user(user_id)
        if latest_order is None:
            return PurchaseEntry()

        if latest_order.plan_id != plan.id:
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
        plan: Plan,
        coin_code: str,
        network_code: str,
    ) -> InvoiceView:
        active_order = await self._order_repository.get_active_unpaid_for_user_plan(user_id, plan.id)
        if active_order is not None:
            return self._build_invoice_view(active_order, self._require_payment(active_order))

        order = await self._order_repository.create(
            order_id=uuid4().hex,
            user_id=user_id,
            plan_id=plan.id,
            amount_usd=plan.price_usd,
            payment_provider=PaymentProvider.PROVIDER_2328,
            status=OrderStatus.AWAITING_PAYMENT,
        )
        gateway_result = await self._gateway.create_payment(
            PaymentCreateRequest(
                order_id=order.order_id,
                amount_usd=plan.price_usd,
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
            raw_payload_json=gateway_result.raw_payload_json,
        )
        order.plan = plan
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
        plan: Plan,
        coin_code: str,
        network_code: str,
    ) -> InvoiceView:
        return await self.create_invoice(
            user_id=user_id,
            plan=plan,
            coin_code=coin_code,
            network_code=network_code,
        )

    async def get_invoice(self, *, public_order_id: str) -> InvoiceView:
        order = await self._get_order_or_raise(public_order_id)
        return self._build_invoice_view(order, self._require_payment(order))

    async def process_webhook_event(self, event: WebhookEvent) -> PaymentProcessingResult:
        if event.provider_payment_uuid:
            payment = await self._payment_repository.get_by_provider_payment_uuid(event.provider_payment_uuid)
            if payment is not None and payment.order is not None:
                return await self._status_processor.process(
                    order=payment.order,
                    payment=payment,
                    result=event.result,
                )

        if event.order_id:
            order = await self._get_order_or_raise(event.order_id)
            payment = self._require_payment(order)
            return await self._status_processor.process(
                order=order,
                payment=payment,
                result=event.result,
            )

        raise RuntimeError("Webhook event does not contain a resolvable payment or order identifier.")

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
            plan_name=order.plan.display_name,
            amount_usd=order.amount_usd,
            payer_currency=payment.payer_currency or "",
            payer_amount=payment.payer_amount or Decimal("0"),
            network=payment.network or "",
            network_label=self._catalog_service.get_network_label(payment.network or ""),
            address=payment.address or "",
            provider_url=payment.provider_url,
            qr_data_uri=payment.qr_data_uri,
            expires_at=normalize_sqlite_utc(payment.expires_at) or utc_now_naive(),
            status=payment.provider_status,
        )

    def _is_inactive_invoice(self, *, order: Order, payment: Payment) -> bool:
        return (
            order.status in {OrderStatus.CANCELLED, OrderStatus.EXPIRED}
            or payment.provider_status == PaymentStatus.CANCEL
            or self._is_expired(payment)
        )

    def _is_expired(self, payment: Payment) -> bool:
        expires_at = normalize_sqlite_utc(payment.expires_at)
        return expires_at is not None and expires_at <= utc_now_naive()
