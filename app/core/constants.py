from __future__ import annotations

from decimal import Decimal

DEFAULT_SQLITE_PATH = "data/app.db"
DEFAULT_PAYMENT_WEBHOOK_PATH = "/webhooks/2328"
DEFAULT_API_HOST = "0.0.0.0"
DEFAULT_API_PORT = 8000

FIXED_PRODUCT_CODE = "GUIDE_ACCESS_LIFETIME"
FIXED_PRODUCT_DISPLAY_NAME = "Lifetime access"
FIXED_PRODUCT_DESCRIPTION = "One-time lifetime access to the private guide channel."
FIXED_PRODUCT_PRICE_USD = Decimal("1.00")
