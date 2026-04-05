from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.core.constants import (
    FIXED_PRODUCT_CODE,
    FIXED_PRODUCT_DESCRIPTION,
    FIXED_PRODUCT_DISPLAY_NAME,
    FIXED_PRODUCT_PRICE_USD,
)
from app.db.repositories.plan import PlanRepository


@dataclass(frozen=True)
class NetworkOption:
    code: str
    label: str


@dataclass(frozen=True)
class FixedProduct:
    id: int
    code: str
    display_name: str
    description: str
    price_usd: Decimal


class ProductService:
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

    async def get_product(self) -> FixedProduct:
        # Keep one seeded row in the plans table as a DB compatibility layer for existing FKs.
        plan = await self._plan_repository.get_by_code(FIXED_PRODUCT_CODE)
        if plan is None or not plan.is_active:
            raise RuntimeError(f"Active product compatibility row {FIXED_PRODUCT_CODE} is not available.")
        return FixedProduct(
            id=plan.id,
            code=FIXED_PRODUCT_CODE,
            display_name=FIXED_PRODUCT_DISPLAY_NAME,
            description=FIXED_PRODUCT_DESCRIPTION,
            price_usd=plan.price_usd or FIXED_PRODUCT_PRICE_USD,
        )

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
