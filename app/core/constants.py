from __future__ import annotations

from decimal import Decimal

DEFAULT_SQLITE_PATH = "data/app.db"
DEFAULT_PAYMENT_WEBHOOK_PATH = "/webhooks/payments/2328"
DEFAULT_API_HOST = "0.0.0.0"
DEFAULT_API_PORT = 8000

MVP_PLAN_CODE = "TIER_1_LIFETIME"
MVP_PLAN_DISPLAY_NAME = "Tier 1 Lifetime Access"
MVP_PLAN_DESCRIPTION = "One-time lifetime access to the private guide channel."
MVP_PLAN_PRICE_USD = Decimal("99.00")
