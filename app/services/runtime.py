from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.repositories.access_link import AccessLinkRepository
from app.db.repositories.bot_message import BotMessageRepository
from app.db.repositories.join_request_log import JoinRequestLogRepository
from app.db.repositories.order import OrderRepository
from app.db.repositories.payment import PaymentRepository
from app.db.repositories.plan import PlanRepository
from app.db.repositories.subscription import SubscriptionRepository
from app.db.repositories.user import UserRepository
from app.services.access.access_service import AccessService
from app.services.messaging.message_service import MessageService
from app.services.payments.factory import get_payment_gateway, get_webhook_gateway
from app.services.payments.payment_service import PaymentService
from app.services.product import ProductService
from app.services.payments.status_processor import PaymentStatusProcessor
from app.services.rates.service import RateService
from app.services.subscriptions.subscription_service import SubscriptionService
from app.services.users import UserService


@dataclass
class RuntimeServices:
    settings: Settings
    user_service: UserService
    product_service: ProductService
    subscription_service: SubscriptionService
    access_service: AccessService
    payment_status_processor: PaymentStatusProcessor
    payment_service: PaymentService
    message_service: MessageService
    payment_gateway: object
    webhook_gateway: object


def build_runtime_services(*, session: AsyncSession, bot: Bot, settings: Settings | None = None) -> RuntimeServices:
    resolved_settings = settings or get_settings()

    user_repository = UserRepository(session)
    plan_repository = PlanRepository(session)
    subscription_repository = SubscriptionRepository(session)
    access_link_repository = AccessLinkRepository(session)
    join_request_log_repository = JoinRequestLogRepository(session)
    order_repository = OrderRepository(session)
    payment_repository = PaymentRepository(session)
    bot_message_repository = BotMessageRepository(session)

    product_service = ProductService(plan_repository)
    user_service = UserService(user_repository, resolved_settings)
    subscription_service = SubscriptionService(subscription_repository)
    access_service = AccessService(
        bot=bot,
        settings=resolved_settings,
        access_link_repository=access_link_repository,
        join_request_log_repository=join_request_log_repository,
    )
    payment_status_processor = PaymentStatusProcessor(
        order_repository=order_repository,
        payment_repository=payment_repository,
        subscription_service=subscription_service,
        access_service=access_service,
    )
    payment_gateway = get_payment_gateway(resolved_settings)
    rate_service = RateService(resolved_settings)

    return RuntimeServices(
        settings=resolved_settings,
        user_service=user_service,
        product_service=product_service,
        subscription_service=subscription_service,
        access_service=access_service,
        payment_status_processor=payment_status_processor,
        payment_service=PaymentService(
            order_repository=order_repository,
            payment_repository=payment_repository,
            product_service=product_service,
            gateway=payment_gateway,
            status_processor=payment_status_processor,
            rate_service=rate_service,
            use_external_rates=resolved_settings.payment_provider_mode == "live",
        ),
        message_service=MessageService(
            bot=bot,
            settings=resolved_settings,
            bot_message_repository=bot_message_repository,
        ),
        payment_gateway=payment_gateway,
        webhook_gateway=get_webhook_gateway(resolved_settings),
    )
