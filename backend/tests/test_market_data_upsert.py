"""Idempotency of the price/FX writer (task 1f) — the core batch guarantee."""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.exchange_rate import ExchangeRate
from app.models.price import Price
from app.services.market_data.types import FxRate, Quote
from app.services.market_data.upsert import upsert_fx, upsert_prices
from tests.factories import make_instrument


def _prices_for(session: Session, instrument_id: int) -> list[Price]:
    stmt = select(Price).where(Price.instrument_id == instrument_id)
    return list(session.execute(stmt).scalars().all())


def test_upsert_prices_running_twice_does_not_duplicate(session: Session) -> None:
    instrument = make_instrument(session)
    quotes = [Quote(day=date(2026, 1, 5), value=Decimal("10.5"))]

    written_first = upsert_prices(session, instrument.id, "EUR", quotes)
    session.commit()
    written_second = upsert_prices(session, instrument.id, "EUR", quotes)
    session.commit()

    assert written_first == 1
    assert written_second == 0
    rows = _prices_for(session, instrument.id)
    assert len(rows) == 1
    assert rows[0].value == Decimal("10.5")


def test_upsert_prices_updates_changed_value_in_place(session: Session) -> None:
    instrument = make_instrument(session)
    day = date(2026, 1, 5)

    upsert_prices(session, instrument.id, "EUR", [Quote(day=day, value=Decimal("10.5"))])
    session.commit()
    written = upsert_prices(session, instrument.id, "EUR", [Quote(day=day, value=Decimal("11.0"))])
    session.commit()

    rows = _prices_for(session, instrument.id)
    assert written == 1
    assert len(rows) == 1
    assert rows[0].value == Decimal("11.0")


def test_upsert_fx_running_twice_does_not_duplicate(session: Session) -> None:
    rates = [FxRate(day=date(2026, 1, 5), base="USD", quote="EUR", rate=Decimal("0.9"))]

    written_first = upsert_fx(session, rates)
    session.commit()
    written_second = upsert_fx(session, rates)
    session.commit()

    assert written_first == 1
    assert written_second == 0
    rows = session.execute(select(ExchangeRate)).scalars().all()
    assert len(rows) == 1


def test_upsert_empty_sequence_is_a_no_op(session: Session) -> None:
    instrument = make_instrument(session)
    assert upsert_prices(session, instrument.id, "EUR", []) == 0
    assert upsert_fx(session, []) == 0
