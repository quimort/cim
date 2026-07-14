"""Idempotent writer for prices and FX rates (task 1f).

Read-modify-write rather than a dialect-specific ``INSERT ... ON CONFLICT``:
tests run against SQLite while production is Postgres, and the row counts here
are trivial (one instrument/pair times at most a lookback window), so a plain
select-then-write is simple and portable. The unique constraints
(``uq_price_instrument_date``, ``uq_exchange_rate_date_pair``) remain the hard
backstop against a concurrent writer; the caller commits (or rolls back) the
transaction, one instrument/step at a time, so one bad row never taints
another instrument's writes.
"""

from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.exchange_rate import ExchangeRate
from app.models.price import Price
from app.services.market_data.types import FxRate, Quote


def upsert_prices(db: Session, instrument_id: int, currency: str, quotes: Sequence[Quote]) -> int:
    """Insert or update ``price`` rows for one instrument. Returns rows written."""
    if not quotes:
        return 0
    days = [q.day for q in quotes]
    existing = {
        row.date: row
        for row in db.execute(
            select(Price).where(Price.instrument_id == instrument_id, Price.date.in_(days))
        ).scalars()
    }
    written = 0
    for quote in quotes:
        row = existing.get(quote.day)
        if row is None:
            db.add(
                Price(
                    instrument_id=instrument_id,
                    date=quote.day,
                    value=quote.value,
                    currency=currency,
                )
            )
            written += 1
        elif row.value != quote.value:
            row.value = quote.value
            written += 1
    return written


def upsert_fx(db: Session, rates: Sequence[FxRate]) -> int:
    """Insert or update ``exchange_rate`` rows. Returns rows written."""
    if not rates:
        return 0
    pairs = {(r.base, r.quote) for r in rates}
    days = [r.day for r in rates]
    existing: dict[tuple[str, str, date], ExchangeRate] = {}
    for base, quote in pairs:
        stmt = select(ExchangeRate).where(
            ExchangeRate.base_currency == base,
            ExchangeRate.quote_currency == quote,
            ExchangeRate.date.in_(days),
        )
        for existing_row in db.execute(stmt).scalars():
            key = (existing_row.base_currency, existing_row.quote_currency, existing_row.date)
            existing[key] = existing_row

    written = 0
    for rate in rates:
        row = existing.get((rate.base, rate.quote, rate.day))
        if row is None:
            db.add(
                ExchangeRate(
                    date=rate.day,
                    base_currency=rate.base,
                    quote_currency=rate.quote,
                    rate=rate.rate,
                )
            )
            written += 1
        elif row.rate != rate.rate:
            row.rate = rate.rate
            written += 1
    return written
