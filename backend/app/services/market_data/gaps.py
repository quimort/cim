"""Gap-fill window computation for the price/FX batch (task 1f).

Each run fetches from the last stored day (inclusive) through today, so a
missed cron run heals itself on the next one; a bounded lookback covers
instruments/pairs with no history yet. The last stored day is re-fetched on
purpose — an intraday run may have stored a provisional "today" quote that the
next run should refresh — which is why the writer (``upsert.py``) updates on
conflict rather than skipping.
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.exchange_rate import ExchangeRate
from app.models.instrument import Instrument
from app.models.price import Price

DEFAULT_LOOKBACK_DAYS = 30


def fetch_window(
    last: date | None, today: date, lookback_days: int = DEFAULT_LOOKBACK_DAYS
) -> tuple[date, date]:
    """Inclusive ``(start, end)`` to fetch, given the last stored day (if any)."""
    start = last if last is not None else today - timedelta(days=lookback_days)
    return start, today


def last_price_date(db: Session, instrument_id: int) -> date | None:
    stmt = (
        select(Price.date)
        .where(Price.instrument_id == instrument_id)
        .order_by(Price.date.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def last_fx_date(db: Session, base: str, quote: str) -> date | None:
    stmt = (
        select(ExchangeRate.date)
        .where(ExchangeRate.base_currency == base, ExchangeRate.quote_currency == quote)
        .order_by(ExchangeRate.date.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def currencies_in_use(db: Session) -> set[str]:
    """Non-EUR currencies that need an FX rate to be converted for net worth.

    Reads ``instrument.currency`` (tradables/loans) and ``account.currency``
    (cash) unscoped by owner: this is system-level reference data the batch
    must cover, not a user-facing read of anyone's balances or positions — no
    amount is read or exposed here, only which currencies exist.
    """
    instrument_currencies = db.execute(
        select(Instrument.currency).where(Instrument.is_active).distinct()
    ).scalars()
    account_currencies = db.execute(
        select(Account.currency).where(Account.is_active).distinct()
    ).scalars()
    return {c for c in (*instrument_currencies, *account_currencies) if c != "EUR"}
