from __future__ import annotations

from sqlalchemy import inspect

from app.core.constants import (
    FIXED_PRODUCT_CODE,
    FIXED_PRODUCT_DESCRIPTION,
    FIXED_PRODUCT_DISPLAY_NAME,
    FIXED_PRODUCT_PRICE_USD,
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
        plan = await repository.get_by_code(FIXED_PRODUCT_CODE)
        if plan is not None:
            return

        await repository.create(
            code=FIXED_PRODUCT_CODE,
            display_name=FIXED_PRODUCT_DISPLAY_NAME,
            description=FIXED_PRODUCT_DESCRIPTION,
            price_usd=FIXED_PRODUCT_PRICE_USD,
            is_active=True,
            access_type=PlanAccessType.LIFETIME_GUIDE_ACCESS,
        )
        await session.commit()
        logger.info("Seeded fixed product compatibility row", extra={"product_code": FIXED_PRODUCT_CODE})


async def _plans_table_exists() -> bool:
    async with session_manager.engine.connect() as connection:
        return await connection.run_sync(lambda sync_conn: inspect(sync_conn).has_table("plans"))
