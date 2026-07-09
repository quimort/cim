"""Read contract for the ``price`` time series.

Market data is written by the batch script directly to Postgres, never via HTTP
(market data is a read-only API family), so there is no Create/Update schema in phase 1 — only
a read shape the valuation endpoints expose.
"""

from datetime import date

from app.schemas.common import MoneyStr, ResponseSchema


class PriceRead(ResponseSchema):
    id: int
    instrument_id: int
    date: date
    value: MoneyStr
    currency: str
