from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.enums import OrderStatus, PaymentStatus
from app.core.logging import get_logger
from app.db.models import AccessLink, Order, Payment, Subscription
from app.db.repositories.order import OrderRepository
from app.db.repositories.payment import PaymentRepository
from app.services.access.access_service import AccessService
from app.services.payments.schemas import PaymentGatewayResult
from app.services.subscriptions.subscription_service import SubscriptionService


logger = get_logger(__name__)


@dataclass(frozen=True)
class PaymentProcessingResult:
    order: Order
    payment: Payment
    subscription: Subscription | None = None
    access_link: AccessLink | None = None

    @property
    def is_success(self) -> bool:
        return self.payment.provider_status in {PaymentStatus.PAID, PaymentStatus.OVERPAID}


class PaymentStatusProcessor:
    def __init__(
        self,
        *,
        order_repository: OrderRepository,
        payment_repository: PaymentRepository,
        subscription_service: SubscriptionService,
        access_service: AccessService,
    ) -> None:
        self._order_repository = order_repository
        self._payment_repository = payment_repository
        self._subscription_service = subscription_service
        self._access_service = access_service

    async def process(
        self,
        *,
        order: Order,
        payment: Payment,
        result: PaymentGatewayResult,
    ) -> PaymentProcessingResult:
        previous_order_status = order.status
        previous_payment_status = payment.provider_status
        current_success = order.status == OrderStatus.PAID or payment.provider_status in {
            PaymentStatus.PAID,
            PaymentStatus.OVERPAID,
        }

        if current_success and result.provider_status not in {PaymentStatus.PAID, PaymentStatus.OVERPAID}:
            logger.info(
                "Webhook status transition skipped order_id=%s provider_uuid=%s previous_order_status=%s previous_payment_status=%s incoming_status=%s",
                order.order_id,
                payment.provider_payment_uuid,
                previous_order_status,
                previous_payment_status,
                result.provider_status,
            )
            subscription = await self._subscription_service.ensure_lifetime_subscription(
                user_id=order.user_id,
                plan_id=order.plan_id,
            )
            access_link = await self._access_service.ensure_access_link(
                user_id=order.user_id,
                subscription=subscription,
            )
            return PaymentProcessingResult(
                order=order,
                payment=payment,
                subscription=subscription,
                access_link=access_link,
            )

        payment.provider_status = result.provider_status
        payment.provider_payment_uuid = result.provider_payment_uuid
        payment.payer_currency = result.payer_currency
        payment.payer_amount = result.payer_amount
        payment.network = result.network
        payment.address = result.address
        payment.qr_data_uri = result.qr_data_uri
        payment.provider_url = result.provider_url
        payment.expires_at = result.expires_at
        payment.txid = result.txid
        payment.raw_payload_json = result.raw_payload_json

        subscription: Subscription | None = None
        access_link: AccessLink | None = None

        if result.provider_status in {PaymentStatus.PAID, PaymentStatus.OVERPAID}:
            if payment.paid_at is None:
                payment.paid_at = datetime.now(UTC)
            await self._order_repository.update_status(order, OrderStatus.PAID)
            subscription = await self._subscription_service.ensure_lifetime_subscription(
                user_id=order.user_id,
                plan_id=order.plan_id,
            )
            access_link = await self._access_service.ensure_access_link(
                user_id=order.user_id,
                subscription=subscription,
            )
        elif result.provider_status == PaymentStatus.CANCEL:
            if order.status != OrderStatus.CANCELLED:
                await self._order_repository.update_status(order, OrderStatus.EXPIRED)
        else:
            await self._order_repository.update_status(order, OrderStatus.AWAITING_PAYMENT)

        await self._payment_repository.save(payment)
        status_changed = previous_order_status != order.status or previous_payment_status != payment.provider_status
        logger.info(
            "Webhook status transition %s order_id=%s provider_uuid=%s previous_order_status=%s new_order_status=%s previous_payment_status=%s new_payment_status=%s",
            "applied" if status_changed else "skipped",
            order.order_id,
            payment.provider_payment_uuid,
            previous_order_status,
            order.status,
            previous_payment_status,
            payment.provider_status,
        )
        return PaymentProcessingResult(
            order=order,
            payment=payment,
            subscription=subscription,
            access_link=access_link,
        )
