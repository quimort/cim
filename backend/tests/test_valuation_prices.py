"""Price lookup: latest quote on or before the as-of date, error when absent."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.services.errors import DomainRuleError
from app.services.valuation import latest_price
from tests.factories import make_instrument, make_price


def test_latest_price_on_or_before_as_of(session: Session) -> None:
    instrument = make_instrument(session)
    make_price(session, instrument, day="2026-01-05", value="100")
    make_price(session, instrument, day="2026-01-10", value="110")
    make_price(session, instrument, day="2026-01-20", value="130")

    quote = latest_price(session, instrument.id, date(2026, 1, 15))
    assert quote.value == Decimal("110")
    assert quote.date == date(2026, 1, 10)


def test_missing_price_raises(session: Session) -> None:
    instrument = make_instrument(session)
    make_price(session, instrument, day="2026-02-01", value="100")  # only in the future

    with pytest.raises(DomainRuleError, match=f"instrument {instrument.id}"):
        latest_price(session, instrument.id, date(2026, 1, 15))
