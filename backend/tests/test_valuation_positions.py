"""Valued positions: FIFO state enriched with instrument name and market price."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.enums import MovementType
from app.services.errors import DomainRuleError
from app.services.valuation import valued_positions
from tests.factories import make_account, make_fx, make_instrument, make_movement, make_price, ts

OWNER = 1


def test_open_position_is_valued_at_market_price(session: Session) -> None:
    account = make_account(session)
    stock = make_instrument(session)
    make_movement(
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=stock,
        quantity="10",
        price="100",
        occurred_at=ts("2026-01-01"),
    )
    make_price(session, stock, day="2026-01-01", value="120")

    [position] = valued_positions(session, OWNER, as_of=date(2026, 2, 1))

    assert position.instrument_id == stock.id
    assert position.instrument_name == stock.name
    assert position.quantity == Decimal("10")
    assert position.cost_basis == Decimal("1000")
    assert position.market_value == Decimal("1200")
    assert position.unrealized_pnl == Decimal("200")
    assert position.value_eur == Decimal("1200")


def test_foreign_currency_position_converts_to_eur(session: Session) -> None:
    account = make_account(session, currency="USD")
    stock = make_instrument(session, currency="USD")
    make_movement(
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=stock,
        quantity="10",
        price="100",
        occurred_at=ts("2026-01-01"),
    )
    make_price(session, stock, day="2026-01-01", value="120")
    make_fx(session, day="2026-01-01", base="USD", quote="EUR", rate="0.9")

    [position] = valued_positions(session, OWNER, as_of=date(2026, 2, 1))

    assert position.market_value == Decimal("1200")
    assert position.value_eur == Decimal("1080.0")


def test_closed_position_excluded_by_default(session: Session) -> None:
    account = make_account(session)
    stock = make_instrument(session)
    make_movement(
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=stock,
        quantity="10",
        price="100",
        occurred_at=ts("2026-01-01"),
    )
    make_movement(
        session,
        account,
        type=MovementType.SALE,
        instrument=stock,
        quantity="10",
        price="110",
        occurred_at=ts("2026-01-05"),
    )

    assert valued_positions(session, OWNER, as_of=date(2026, 2, 1)) == []

    [position] = valued_positions(session, OWNER, as_of=date(2026, 2, 1), include_closed=True)
    assert position.quantity == Decimal("0")
    assert position.realized_pnl == Decimal("100")
    assert position.market_value is None
    assert position.unrealized_pnl is None
    assert position.value_eur is None


def test_missing_price_fails_loudly_for_an_open_position(session: Session) -> None:
    account = make_account(session)
    stock = make_instrument(session)
    make_movement(
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=stock,
        quantity="10",
        price="100",
        occurred_at=ts("2026-01-01"),
    )

    with pytest.raises(DomainRuleError, match="no price"):
        valued_positions(session, OWNER, as_of=date(2026, 2, 1))
