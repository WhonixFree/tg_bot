from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.core.enums import PlanAccessType
from app.db.models import Plan
from app.db.repositories.base import Repository


class PlanRepository(Repository):
    async def get_by_id(self, plan_id: int) -> Plan | None:
        return await self.session.get(Plan, plan_id)

    async def get_by_code(self, code: str) -> Plan | None:
        stmt = select(Plan).where(Plan.code == code)
        return await self.session.scalar(stmt)

    async def list_active(self) -> list[Plan]:
        stmt = select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.id.asc())
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def create(
        self,
        *,
        code: str,
        display_name: str,
        description: str | None,
        price_usd: Decimal,
        is_active: bool,
        access_type: PlanAccessType,
    ) -> Plan:
        plan = Plan(
            code=code,
            display_name=display_name,
            description=description,
            price_usd=price_usd,
            is_active=is_active,
            access_type=access_type,
        )
        self.session.add(plan)
        await self.session.flush()
        return plan
