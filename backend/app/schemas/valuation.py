"""API contracts for the derived (read-only) valuation endpoints.

These wrap the frozen dataclasses in ``app/services/valuation/types.py`` —
``ResponseSchema``'s ``from_attributes=True`` reads them directly, dataclass
or ORM row alike. Nothing here is ever written: there is no create/update
shape, because nothing behind these endpoints is ever POSTed.
"""

from datetime import date

from pydantic import Field

from app.schemas.common import MoneyStr, ResponseSchema


class PositionRead(ResponseSchema):
    instrument_id: int
    instrument_name: str
    quantity: MoneyStr
    cost_basis: MoneyStr
    realized_pnl: MoneyStr
    currency: str
    market_value: MoneyStr | None = Field(
        default=None, description="Null for a closed (zero-quantity) position."
    )
    unrealized_pnl: MoneyStr | None = Field(default=None, description="Null when closed.")
    value_eur: MoneyStr | None = Field(default=None, description="Null when closed.")


class NetWorthItemRead(ResponseSchema):
    asset_class: str
    instrument_id: int | None
    account_id: int | None
    native_value: MoneyStr
    native_currency: str
    value_eur: MoneyStr
    quantity: MoneyStr | None = None
    cost_basis: MoneyStr | None = None
    unrealized_pnl: MoneyStr | None = None


class NetWorthRead(ResponseSchema):
    as_of: date
    total_eur: MoneyStr
    items: list[NetWorthItemRead]


class NetWorthPointRead(ResponseSchema):
    as_of: date
    total_eur: MoneyStr


class NetWorthSeriesRead(ResponseSchema):
    interval: str
    points: list[NetWorthPointRead]


class AllocationBucketRead(ResponseSchema):
    key: str | None = Field(description="Null means 'uncategorized' (category dimension only).")
    label: str
    value_eur: MoneyStr
    weight: MoneyStr | None = Field(
        default=None, description="Share of the total, 0-1. Null when the total is zero."
    )


class AllocationRead(ResponseSchema):
    as_of: date
    dimension: str
    total_eur: MoneyStr
    buckets: list[AllocationBucketRead]
