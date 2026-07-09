"""Read contract for the ``exchange_rate`` time series.

Like prices, FX rates are written by the batch script directly to Postgres, so
phase 1 exposes only a read shape.
"""

from datetime import date

from app.schemas.common import MoneyStr, ResponseSchema


class ExchangeRateRead(ResponseSchema):
    id: int
    date: date
    base_currency: str
    quote_currency: str
    rate: MoneyStr
