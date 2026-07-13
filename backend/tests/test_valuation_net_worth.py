"""Net worth: per-class strategies dispatched by asset_class, consolidated to EUR."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.enums import AssetClass, MovementType
from app.services.errors import DomainRuleError
from app.services.valuation import VALUERS, net_worth
from tests.factories import (
    make_account,
    make_fx,
    make_instrument,
    make_movement,
    make_price,
    ts,
)

OWNER = 1


def test_dispatch_table_covers_every_asset_class() -> None:
    """The same guarantee test_asset_class_sync gives the seed: no class without a strategy."""
    assert set(VALUERS) == set(AssetClass)


def test_mixed_portfolio_consolidates_to_eur(session: Session) -> None:
    """One asset of each class, two currencies, every value hand-computed.

    EUR account: deposit 5000, lend 1000            -> cash 4000 EUR
    USD account: deposit 2000, buy 10 @ 100         -> cash 1000 USD -> 900 EUR
    tradable:    10 units @ 120 USD                 -> 1200 USD -> 1080 EUR
    loan:        1000 principal + 73 days at 5%     -> 1010 EUR
                                                  total 6990 EUR
    """
    eur_account = make_account(session, currency="EUR")
    usd_account = make_account(session, currency="USD")
    stock = make_instrument(session, currency="USD")
    loan = make_instrument(session, asset_class="loan", expected_interest="0.05")

    make_movement(
        session,
        eur_account,
        type=MovementType.DEPOSIT,
        quantity="5000",
        occurred_at=ts("2026-01-01"),
    )
    make_movement(
        session,
        eur_account,
        type=MovementType.PURCHASE,
        instrument=loan,
        quantity="1000",
        price="1",
        occurred_at=ts("2026-01-01"),
    )
    make_movement(
        session,
        usd_account,
        type=MovementType.DEPOSIT,
        quantity="2000",
        occurred_at=ts("2026-01-01"),
    )
    make_movement(
        session,
        usd_account,
        type=MovementType.PURCHASE,
        instrument=stock,
        quantity="10",
        price="100",
        occurred_at=ts("2026-01-02"),
    )
    make_price(session, stock, day="2026-03-10", value="120")
    make_fx(session, day="2026-01-01", base="USD", quote="EUR", rate="0.9")

    report = net_worth(session, OWNER, as_of=date(2026, 3, 15))

    by_key = {
        (item.asset_class, item.instrument_id, item.account_id): item for item in report.items
    }

    stock_item = by_key[(AssetClass.TRADABLE.value, stock.id, None)]
    assert stock_item.native_value == Decimal("1200")
    assert stock_item.native_currency == "USD"
    assert stock_item.value_eur == Decimal("1080.0")
    assert stock_item.unrealized_pnl == Decimal("200")
    assert stock_item.cost_basis == Decimal("1000")

    assert by_key[(AssetClass.CASH.value, None, eur_account.id)].value_eur == Decimal("4000")
    assert by_key[(AssetClass.CASH.value, None, usd_account.id)].value_eur == Decimal("900.0")

    loan_item = by_key[(AssetClass.LOAN.value, loan.id, None)]
    assert loan_item.native_value == Decimal("1010")  # 1000 + 1000*0.05*73/365
    assert loan_item.value_eur == Decimal("1010")

    assert report.total_eur == Decimal("6990.0")
    assert report.as_of == date(2026, 3, 15)


def test_net_worth_at_a_past_date_replays_the_ledger(session: Session) -> None:
    """The ledger's payoff: asking for an old date gives the state back then."""
    account = make_account(session)
    make_movement(
        session,
        account,
        type=MovementType.DEPOSIT,
        quantity="1000",
        occurred_at=ts("2026-01-01"),
    )
    make_movement(
        session,
        account,
        type=MovementType.WITHDRAWAL,
        quantity="600",
        occurred_at=ts("2026-02-01"),
    )

    assert net_worth(session, OWNER, as_of=date(2026, 1, 15)).total_eur == Decimal("1000")
    assert net_worth(session, OWNER, as_of=date(2026, 2, 15)).total_eur == Decimal("400")


def test_missing_price_fails_loudly(session: Session) -> None:
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
        net_worth(session, OWNER, as_of=date(2026, 2, 1))


def test_closed_position_needs_no_price(session: Session) -> None:
    """A fully-sold instrument holds no value, so no quote is required for it."""
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

    report = net_worth(session, OWNER, as_of=date(2026, 2, 1))

    # Only the cash from the round trip remains: -1000 + 1100.
    assert report.total_eur == Decimal("100")


def test_other_owners_assets_do_not_leak(session: Session) -> None:
    mine = make_account(session)
    theirs = make_account(session, owner_id=2)
    make_movement(
        session,
        mine,
        type=MovementType.DEPOSIT,
        quantity="100",
        occurred_at=ts("2026-01-01"),
    )
    make_movement(
        session,
        theirs,
        type=MovementType.DEPOSIT,
        quantity="9000",
        occurred_at=ts("2026-01-01"),
    )

    assert net_worth(session, OWNER).total_eur == Decimal("100")
    assert net_worth(session, 2).total_eur == Decimal("9000")
