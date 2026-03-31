from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.core.config import Settings
from app.db.session import session_manager
from app.services.runtime import build_runtime_services


def create_webhook_router(*, bot, settings: Settings) -> APIRouter:
    router = APIRouter(tags=["payments"])

    @router.post(settings.payment_webhook_path)
    async def webhook_2328(request: Request) -> dict[str, str]:
        body = await request.body()
        signature = request.headers.get("sign")

        async with session_manager.session() as session:
            services = build_runtime_services(session=session, bot=bot, settings=settings)
            try:
                is_valid = services.webhook_gateway.verify_webhook_signature(
                    body=body,
                    signature=signature,
                )
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc

            if not is_valid:
                raise HTTPException(status_code=401, detail="Invalid webhook signature.")

            payload = await request.json()
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Webhook payload must be a JSON object.")

            event = services.webhook_gateway.parse_webhook_event(payload)
            await services.payment_service.process_webhook_event(event)
            await session.commit()

        return {"status": "ok"}

    return router
