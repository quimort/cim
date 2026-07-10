"""Market-price lookup for tradable valuation.

The ``price`` table is a time series written by the batch script (task 1f);
valuation reads the latest quote on or before the as-of date.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.price import Price
from app.services.errors import DomainRuleError


def latest_price(db: Session, instrument_id: int, as_of: date) -> Price:
    """The most recent quote on or before ``as_of``.

    A missing quote raises rather than guessing: valuing at cost would silently
    misstate net worth, and the fix (run the price batch) is actionable.
    """
    stmt = (
        select(Price)
        .where(Price.instrument_id == instrument_id, Price.date <= as_of)
        .order_by(Price.date.desc())
        .limit(1)
    )
    price = db.execute(stmt).scalar_one_or_none()
    if price is None:
        raise DomainRuleError(f"no price for instrument {instrument_id} on or before {as_of}")
    return price
