"""add instrument price_source and provider_ref

Revision ID: c2d5e8f41a7b
Revises: b1c4d7e29f30
Create Date: 2026-07-13

Nullable so existing instruments are untouched: a NULL ``price_source`` means
the price batch script (task 1f) skips that instrument. Both columns are
independent of ``asset_class``/``category`` (the two existing axes) — this is
routing information for market-data ingestion, not a valuation or grouping key.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2d5e8f41a7b"
down_revision: str | Sequence[str] | None = "b1c4d7e29f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("instrument", sa.Column("price_source", sa.String(length=20), nullable=True))
    op.add_column("instrument", sa.Column("provider_ref", sa.String(length=100), nullable=True))
    op.create_check_constraint(
        "ck_instrument_price_source",
        "instrument",
        "price_source IS NULL OR price_source IN ('yfinance','coingecko')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_instrument_price_source", "instrument", type_="check")
    op.drop_column("instrument", "provider_ref")
    op.drop_column("instrument", "price_source")
