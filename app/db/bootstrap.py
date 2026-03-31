from __future__ import annotations

from sqlalchemy import inspect

from app.core.constants import (
    MVP_PLAN_CODE,
    MVP_PLAN_DESCRIPTION,
    MVP_PLAN_DISPLAY_NAME,
    MVP_PLAN_PRICE_USD,
)
from app.core.enums import PlanAccessType
from app.core.logging import get_logger
from app.db.repositories.plan import PlanRepository
from app.db.session import session_manager

logger = get_logger(__name__)


async def bootstrap_reference_data() -> None:
    if not await _plans_table_exists():
        logger.info("Skipping reference data bootstrap because database tables are not migrated yet")
        return

    async with session_manager.session() as session:
        repository = PlanRepository(session)
        plan = await repository.get_by_code(MVP_PLAN_CODE)
        if plan is not None:
            return

        await repository.create(
            code=MVP_PLAN_CODE,
            display_name=MVP_PLAN_DISPLAY_NAME,
            description=MVP_PLAN_DESCRIPTION,
            price_usd=MVP_PLAN_PRICE_USD,
            is_active=True,
            access_type=PlanAccessType.LIFETIME_GUIDE_ACCESS,
        )
        await session.commit()
        logger.info("Seeded default MVP plan", extra={"plan_code": MVP_PLAN_CODE})


async def _plans_table_exists() -> bool:
    async with session_manager.engine.connect() as connection:
        return await connection.run_sync(lambda sync_conn: inspect(sync_conn).has_table("plans"))
