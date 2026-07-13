"""The ``asset_class`` reference table.

An asset class is not a label: it is the key the valuation services dispatch on
(FIFO for ``tradable``, movement-sum balance for ``cash``, principal plus accrued
interest for ``loan``). Each code therefore corresponds to a piece of Python, and
the set of codes stays a **closed, code-level decision** — the table exists so the
database can enforce referential integrity and the UI can read display metadata,
not so new classes can be invented at runtime.

The open, user-managed axis is :mod:`app.models.category`, which never touches
valuation.

``ASSET_CLASS_SEED`` is the single source of truth for the seeded rows. The
migration necessarily repeats these literals (a migration must not import live
model code, which drifts), and ``tests/test_asset_class_sync.py`` asserts that the
enum, this constant, and the migration's copy all agree — so drift fails CI
rather than production.
"""

from typing import TypedDict

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import AssetClass


class AssetClassSeed(TypedDict):
    code: str
    label: str
    description: str
    sort_order: int


class AssetClassRef(Base):
    """Named ``...Ref`` because ``AssetClass`` is the enum, which stays the dispatch key."""

    __tablename__ = "asset_class"

    # The natural key. Instruments already store the string, so a surrogate id
    # would force a needless rewrite of every existing row.
    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    label: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(Integer)


ASSET_CLASS_SEED: tuple[AssetClassSeed, ...] = (
    {
        "code": AssetClass.TRADABLE.value,
        "label": "Tradable",
        "description": "Quoted assets valued at market price, with FIFO cost basis.",
        "sort_order": 1,
    },
    {
        "code": AssetClass.CASH.value,
        "label": "Cash",
        "description": "Balances valued at face value, derived from the ledger.",
        "sort_order": 2,
    },
    {
        "code": AssetClass.LOAN.value,
        "label": "Loan",
        "description": "Money lent out, valued at outstanding principal plus accrued interest.",
        "sort_order": 3,
    },
)
