from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.bot.keyboards.purchase import build_underpaid_keyboard
from app.bot.keyboards.purchase import build_success_keyboard
from app.bot.screens.purchase import build_underpaid_invoice_text
from app.bot.screens.purchase import build_payment_success_with_access_text
from app.core.config import Settings
from app.core.enums import BotMessageType, PaymentStatus
from app.core.logging import get_logger
from app.db.session import session_manager
from app.services.runtime import build_runtime_services


logger = get_logger(__name__)


def create_webhook_router(*, bot, settings: Settings) -> APIRouter:
    router = APIRouter(tags=["payments"])

    @router.post(settings.payment_webhook_path)
    async def webhook_2328(request: Request) -> dict[str, str]:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Webhook payload must be a JSON object.")

        sign_exists = isinstance(payload.get("sign"), str) and bool(payload.get("sign"))
        uuid = payload.get("uuid") if isinstance(payload.get("uuid"), str) else None
        order_id = payload.get("order_id") if isinstance(payload.get("order_id"), str) else None
        payment_status = (
            payload.get("payment_status")
            if isinstance(payload.get("payment_status"), str)
            else None
        )

        async with session_manager.session() as session:
            services = build_runtime_services(session=session, bot=bot, settings=settings)
            try:
                is_valid = services.webhook_gateway.verify_webhook_signature(payload=payload)
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc

            logger.info(
                "2328 webhook received sign_exists=%s signature_valid=%s uuid=%s order_id=%s payment_status=%s",
                sign_exists,
                is_valid,
                uuid,
                order_id,
                payment_status,
            )

            if not is_valid:
                raise HTTPException(status_code=401, detail="Invalid webhook signature.")

            event = services.webhook_gateway.parse_webhook_event(payload)
            processing = await services.payment_service.process_webhook_event(event)

            if processing is None:
                logger.info(
                    "Webhook ignored after verification uuid=%s order_id=%s payment_status=%s",
                    uuid,
                    order_id,
                    payment_status,
                )
            elif processing.payment.provider_status in {
                PaymentStatus.UNDERPAID,
                PaymentStatus.UNDERPAID_CHECK,
            }:
                try:
                    user = await services.user_service.get_by_id(processing.order.user_id)
                    if user is None:
                        logger.info(
                            "Webhook underpaid notification skipped user_missing order_id=%s local_user_id=%s",
                            processing.order.order_id,
                            processing.order.user_id,
                        )
                    else:
                        await services.message_service.show_text(
                            user_id=user.id,
                            chat_id=user.telegram_user_id,
                            text=build_underpaid_invoice_text(),
                            reply_markup=build_underpaid_keyboard(),
                            message_type=BotMessageType.INVOICE,
                        )
                        logger.info(
                            "Webhook underpaid message sent order_id=%s local_user_id=%s payment_status=%s",
                            processing.order.order_id,
                            user.id,
                            processing.payment.provider_status,
                        )
                except Exception:
                    logger.exception(
                        "Webhook underpaid message failed order_id=%s local_user_id=%s payment_status=%s",
                        processing.order.order_id,
                        processing.order.user_id,
                        processing.payment.provider_status,
                    )
            elif processing.is_success and processing.access_link is not None:
                try:
                    user = await services.user_service.get_by_id(processing.order.user_id)
                    if user is None:
                        logger.info(
                            "Webhook success notification skipped user_missing order_id=%s local_user_id=%s",
                            processing.order.order_id,
                            processing.order.user_id,
                        )
                    else:
                        invoice = await services.payment_service.get_invoice(
                            public_order_id=processing.order.order_id,
                        )
                        await services.message_service.show_text(
                            user_id=user.id,
                            chat_id=user.telegram_user_id,
                            text=build_payment_success_with_access_text(
                                invoice,
                                processing.access_link.invite_link,
                            ),
                            reply_markup=build_success_keyboard(),
                            message_type=BotMessageType.ACCESS,
                        )
                        logger.info(
                            "Webhook success message sent order_id=%s local_user_id=%s",
                            processing.order.order_id,
                            user.id,
                        )
                except Exception:
                    logger.exception(
                        "Webhook success message failed order_id=%s local_user_id=%s",
                        processing.order.order_id,
                        processing.order.user_id,
                    )

            await session.commit()

        return {"status": "ok"}

    return router
