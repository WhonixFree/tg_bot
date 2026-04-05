from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_UP
from typing import Any

import httpx

from app.core.config import Settings

_RATE_CACHE: dict[str, tuple[datetime, "ConversionQuote"]] = {}
_ROUNDING_STEP = Decimal("0.00000001")


@dataclass(frozen=True)
class ConversionQuote:
    coin_code: str
    rate_source: str
    rate_base_currency: str
    rate_quote_currency: str
    rate_value_usd: Decimal
    rate_fetched_at: datetime
    amount_before_rounding: Decimal
    payer_amount: Decimal
    raw_rate_payload_json: dict[str, Any]


class RateService:
    _COINGECKO_IDS = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
    }
    _BINANCE_SYMBOLS = {
        "BTC": "BTCUSDT",
        "ETH": "ETHUSDT",
    }

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def get_locked_quote(self, *, amount_usd: Decimal, coin_code: str) -> ConversionQuote:
        coin_code = coin_code.upper()
        if coin_code not in self._COINGECKO_IDS:
            raise ValueError(f"Unsupported rate lookup coin: {coin_code}")

        cached = self._get_cached(coin_code)
        if cached is not None:
            return self._build_conversion(amount_usd=amount_usd, cached=cached)

        errors: list[str] = []

        try:
            quote = await self._fetch_from_coingecko(coin_code)
            self._set_cached(coin_code, quote)
            return self._build_conversion(amount_usd=amount_usd, cached=quote)
        except Exception as exc:
            errors.append(f"CoinGecko: {exc}")

        try:
            quote = await self._fetch_from_binance(coin_code)
            self._set_cached(coin_code, quote)
            return self._build_conversion(amount_usd=amount_usd, cached=quote)
        except Exception as exc:
            errors.append(f"Binance: {exc}")

        raise RuntimeError(
            f"Failed to fetch {coin_code}/USD market rate from free APIs. "
            + " | ".join(errors)
        )

    def _get_cached(self, coin_code: str) -> ConversionQuote | None:
        cached = _RATE_CACHE.get(coin_code)
        if cached is None:
            return None

        cached_at, quote = cached
        ttl = timedelta(seconds=self._settings.rate_cache_ttl_seconds)
        if datetime.now(UTC) - cached_at > ttl:
            _RATE_CACHE.pop(coin_code, None)
            return None

        return quote

    def _set_cached(self, coin_code: str, quote: ConversionQuote) -> None:
        _RATE_CACHE[coin_code] = (datetime.now(UTC), quote)

    def _build_conversion(self, *, amount_usd: Decimal, cached: ConversionQuote) -> ConversionQuote:
        amount_before_rounding = amount_usd / cached.rate_value_usd
        payer_amount = amount_before_rounding.quantize(_ROUNDING_STEP, rounding=ROUND_UP)
        return ConversionQuote(
            coin_code=cached.coin_code,
            rate_source=cached.rate_source,
            rate_base_currency="USD",
            rate_quote_currency=cached.coin_code,
            rate_value_usd=cached.rate_value_usd,
            rate_fetched_at=cached.rate_fetched_at,
            amount_before_rounding=amount_before_rounding,
            payer_amount=payer_amount,
            raw_rate_payload_json=cached.raw_rate_payload_json,
        )

    async def _fetch_from_coingecko(self, coin_code: str) -> ConversionQuote:
        coin_id = self._COINGECKO_IDS[coin_code]
        payload = {"ids": coin_id, "vs_currencies": "usd"}
        timeout = httpx.Timeout(self._settings.rate_api_timeout_seconds)
        async with httpx.AsyncClient(base_url=self._settings.coingecko_base_url, timeout=timeout) as client:
            response = await client.get("/simple/price", params=payload)
            response.raise_for_status()
            data = response.json()

        try:
            rate_value = Decimal(str(data[coin_id]["usd"]))
        except Exception as exc:
            raise RuntimeError(f"Unexpected CoinGecko payload: {data}") from exc

        return ConversionQuote(
            coin_code=coin_code,
            rate_source="coingecko",
            rate_base_currency="USD",
            rate_quote_currency=coin_code,
            rate_value_usd=rate_value,
            rate_fetched_at=datetime.now(UTC),
            amount_before_rounding=Decimal("0"),
            payer_amount=Decimal("0"),
            raw_rate_payload_json=data,
        )

    async def _fetch_from_binance(self, coin_code: str) -> ConversionQuote:
        symbol = self._BINANCE_SYMBOLS[coin_code]
        timeout = httpx.Timeout(self._settings.rate_api_timeout_seconds)
        async with httpx.AsyncClient(base_url=self._settings.binance_base_url, timeout=timeout) as client:
            response = await client.get("/api/v3/ticker/price", params={"symbol": symbol})
            response.raise_for_status()
            data = response.json()

        try:
            rate_value = Decimal(str(data["price"]))
        except Exception as exc:
            raise RuntimeError(f"Unexpected Binance payload: {data}") from exc

        return ConversionQuote(
            coin_code=coin_code,
            rate_source="binance",
            rate_base_currency="USD",
            rate_quote_currency=coin_code,
            rate_value_usd=rate_value,
            rate_fetched_at=datetime.now(UTC),
            amount_before_rounding=Decimal("0"),
            payer_amount=Decimal("0"),
            raw_rate_payload_json=data,
        )
