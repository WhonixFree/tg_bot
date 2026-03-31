from __future__ import annotations

from dataclasses import dataclass

from app.core.constants import MVP_PLAN_CODE
from app.db.models import Plan
from app.db.repositories.plan import PlanRepository


@dataclass(frozen=True)
class NetworkOption:
    code: str
    label: str


class CatalogService:
    _NETWORKS: dict[str, list[NetworkOption]] = {
        "USDT": [
            NetworkOption(code="TRX-TRC20", label="TRC20"),
            NetworkOption(code="BSC-BEP20", label="BEP20"),
            NetworkOption(code="ETH-ERC20", label="ERC20"),
            NetworkOption(code="AVAX-C", label="AVAX"),
            NetworkOption(code="POL-MATIC", label="MATIC"),
            NetworkOption(code="TON", label="TON"),
        ],
        "USDC": [
            NetworkOption(code="BSC-BEP20", label="BEP20"),
            NetworkOption(code="ETH-ERC20", label="ERC20"),
            NetworkOption(code="AVAX-C", label="AVAX"),
            NetworkOption(code="POL-MATIC", label="MATIC"),
        ],
        "BTC": [NetworkOption(code="BTC", label="BTC")],
        "ETH": [NetworkOption(code="ETH-ERC20", label="ERC20")],
    }

    _COINS: tuple[str, ...] = ("USDT", "USDC", "BTC", "ETH")

    def __init__(self, plan_repository: PlanRepository) -> None:
        self._plan_repository = plan_repository

    async def get_mvp_plan(self) -> Plan:
        plan = await self._plan_repository.get_by_code(MVP_PLAN_CODE)
        if plan is None or not plan.is_active:
            raise RuntimeError(f"Active plan {MVP_PLAN_CODE} is not available.")
        return plan

    def list_coins(self) -> tuple[str, ...]:
        return self._COINS

    def needs_network_selection(self, coin_code: str) -> bool:
        return coin_code in {"USDT", "USDC"}

    def get_default_network(self, coin_code: str) -> str:
        return self.get_networks_for_coin(coin_code)[0].code

    def get_networks_for_coin(self, coin_code: str) -> list[NetworkOption]:
        try:
            return self._NETWORKS[coin_code]
        except KeyError as exc:
            raise ValueError(f"Unsupported coin: {coin_code}") from exc

    def get_network_label(self, network_code: str) -> str:
        for options in self._NETWORKS.values():
            for option in options:
                if option.code == network_code:
                    return option.label
        return network_code
