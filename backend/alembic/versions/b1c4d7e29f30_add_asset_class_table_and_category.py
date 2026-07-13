"""add asset_class reference table and user-managed category

Revision ID: b1c4d7e29f30
Revises: f6a988738adc
Create Date: 2026-07-09

Ordering matters. Existing `instrument` rows already carry asset_class values, so
the reference table must exist *and be seeded* before the foreign key is created,
or the constraint fails against live data.

`_SEED` is duplicated from `app.models.asset_class.ASSET_CLASS_SEED` on purpose: a
migration must be self-contained, because model code drifts while a migration is
a fixed historical record. `tests/test_asset_class_sync.py` asserts the two agree.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c4d7e29f30"
down_revision: str | Sequence[str] | None = "f6a988738adc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SEED: tuple[dict[str, str | int], ...] = (
    {
        "code": "tradable",
        "label": "Tradable",
        "description": "Quoted assets valued at market price, with FIFO cost basis.",
        "sort_order": 1,
    },
    {
        "code": "cash",
        "label": "Cash",
        "description": "Balances valued at face value, derived from the ledger.",
        "sort_order": 2,
    },
    {
        "code": "loan",
        "label": "Loan",
        "description": "Money lent out, valued at outstanding principal plus accrued interest.",
        "sort_order": 3,
    },
)

# The CHECK the foreign key replaces. Restored verbatim on downgrade.
_OLD_ASSET_CLASS_CHECK = "asset_class IN ('tradable','cash','loan')"


def upgrade() -> None:
    """Upgrade schema."""
    asset_class = op.create_table(
        "asset_class",
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("label", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    # Seed before the FK below can reference it.
    op.bulk_insert(asset_class, [dict(row) for row in _SEED])

    op.create_table(
        "category",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_category_name"),
    )

    # The FK now does what the CHECK did, and does it by referential integrity.
    op.drop_constraint("ck_instrument_asset_class", "instrument", type_="check")
    op.create_foreign_key(
        "fk_instrument_asset_class",
        "instrument",
        "asset_class",
        ["asset_class"],
        ["code"],
    )

    op.add_column("instrument", sa.Column("category_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_instrument_category_id", "instrument", "category", ["category_id"], ["id"]
    )
    op.create_index(op.f("ix_instrument_category_id"), "instrument", ["category_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_instrument_category_id"), table_name="instrument")
    op.drop_constraint("fk_instrument_category_id", "instrument", type_="foreignkey")
    op.drop_column("instrument", "category_id")

    op.drop_constraint("fk_instrument_asset_class", "instrument", type_="foreignkey")
    op.create_check_constraint("ck_instrument_asset_class", "instrument", _OLD_ASSET_CLASS_CHECK)

    op.drop_table("category")
    op.drop_table("asset_class")
