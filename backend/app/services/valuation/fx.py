"""Currency conversion to EUR, the reporting base currency.

Amounts are stored in their native currency; the EUR figure is always derived
here at valuation time, never frozen. A row ``(date, base, quote, rate)`` in
``exchange_rate`` means "1 base = rate quote" — the convention the batch
script (task 1f) must follow.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.exchange_rate import ExchangeRate
from app.services.errors import DomainRuleError

BASE_CURRENCY = "EUR"

_ONE = Decimal(1)


def rate_to_eur(db: Session, currency: str, as_of: date) -> Decimal:
    """EUR per one unit of ``currency``, using the latest rate on or before ``as_of``.

    Tries the direct pair (``currency``→EUR) first, then the inverse pair
    (EUR→``currency``) inverted, so the lookup works whichever direction the
    batch script wrote. Missing both ways is an error, not a silent skip:
    dropping an asset from net worth would misreport it, and the fix (load
    rates) is actionable.
    """
    if currency == BASE_CURRENCY:
        return _ONE

    direct = _latest_rate(db, currency, BASE_CURRENCY, as_of)
    if direct is not None:
        return direct
    inverse = _latest_rate(db, BASE_CURRENCY, currency, as_of)
    if inverse is not None:
        return _ONE / inverse
    raise DomainRuleError(f"no exchange rate for {currency}->{BASE_CURRENCY} on or before {as_of}")


def convert_to_eur(db: Session, amount: Decimal, currency: str, as_of: date) -> Decimal:
    return amount * rate_to_eur(db, currency, as_of)


def _latest_rate(db: Session, base: str, quote: str, as_of: date) -> Decimal | None:
    stmt = (
        select(ExchangeRate.rate)
        .where(
            ExchangeRate.base_currency == base,
            ExchangeRate.quote_currency == quote,
            ExchangeRate.date <= as_of,
        )
        .order_by(ExchangeRate.date.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()
