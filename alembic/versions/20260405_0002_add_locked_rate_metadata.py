"""Add locked rate metadata to payments

Revision ID: 20260405_0002
Revises: 20260331_0001
Create Date: 2026-04-05 08:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260405_0002"
down_revision = "20260331_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("rate_source", sa.String(length=50), nullable=True))
    op.add_column("payments", sa.Column("rate_base_currency", sa.String(length=10), nullable=True))
    op.add_column("payments", sa.Column("rate_quote_currency", sa.String(length=10), nullable=True))
    op.add_column("payments", sa.Column("rate_value_usd", sa.Numeric(20, 8), nullable=True))
    op.add_column("payments", sa.Column("rate_fetched_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payments", sa.Column("amount_before_rounding", sa.Numeric(20, 8), nullable=True))
    op.add_column("payments", sa.Column("raw_rate_payload_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "raw_rate_payload_json")
    op.drop_column("payments", "amount_before_rounding")
    op.drop_column("payments", "rate_fetched_at")
    op.drop_column("payments", "rate_value_usd")
    op.drop_column("payments", "rate_quote_currency")
    op.drop_column("payments", "rate_base_currency")
    op.drop_column("payments", "rate_source")
