"""FIFO cost basis: known inputs -> known outputs, exact Decimals throughout."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.enums import MovementType
from app.services.errors import DomainRuleError
from app.services.valuation import position, positions
from tests.factories import make_account, make_instrument, make_movement, ts

OWNER = 1


def test_multi_lot_partial_sale_across_lots_with_fees(session: Session) -> None:
    """The canonical case: two lots, one sale eating the first lot and part of the second.

    buy 10 @ 100, fee 5    -> lot cost 1005
    buy  5 @ 110, fee 2.5  -> lot cost 552.5
    sell 12 @ 120, fee 3   -> proceeds 1437
                              consumed = 1005 + 552.5 * 2/5 = 1226
                              realized = 1437 - 1226 = 211
    left: 3 units of lot 2, cost 552.5 * 3/5 = 331.5
    """
    account = make_account(session)
    instrument = make_instrument(session)
    make_movement(
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=instrument,
        quantity="10",
        price="100",
        fee="5",
        occurred_at=ts("2026-01-01"),
    )
    make_movement(
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=instrument,
        quantity="5",
        price="110",
        fee="2.5",
        occurred_at=ts("2026-02-01"),
    )
    make_movement(
        session,
        account,
        type=MovementType.SALE,
        instrument=instrument,
        quantity="12",
        price="120",
        fee="3",
        occurred_at=ts("2026-03-01"),
    )

    result = position(session, OWNER, instrument.id)

    assert result.realized_pnl == Decimal("211")
    assert result.quantity == Decimal("3")
    assert result.cost_basis == Decimal("331.5")
    assert len(result.lots) == 1
    assert result.lots[0].quantity == Decimal("3")
    assert result.lots[0].cost == Decimal("331.5")


def test_single_purchase_capitalizes_fee(session: Session) -> None:
    account = make_account(session)
    instrument = make_instrument(session)
    make_movement(
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=instrument,
        quantity="10",
        price="100",
        fee="5",
        occurred_at=ts("2026-01-01"),
    )

    result = position(session, OWNER, instrument.id)

    assert result.quantity == Decimal("10")
    assert result.cost_basis == Decimal("1005")
    assert result.realized_pnl == Decimal("0")


def test_missing_fee_means_zero(session: Session) -> None:
    account = make_account(session)
    instrument = make_instrument(session)
    make_movement(
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=instrument,
        quantity="4",
        price="25",
        occurred_at=ts("2026-01-01"),
    )

    assert position(session, OWNER, instrument.id).cost_basis == Decimal("100")


def test_oversell_raises(session: Session) -> None:
    account = make_account(session)
    instrument = make_instrument(session)
    make_movement(
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=instrument,
        quantity="5",
        price="100",
        occurred_at=ts("2026-01-01"),
    )
    make_movement(
        session,
        account,
        type=MovementType.SALE,
        instrument=instrument,
        quantity="6",
        price="100",
        occurred_at=ts("2026-02-01"),
    )

    with pytest.raises(DomainRuleError, match="exceeds held quantity"):
        position(session, OWNER, instrument.id)


def test_exact_sellout_leaves_zero_position_with_realized_pnl(session: Session) -> None:
    account = make_account(session)
    instrument = make_instrument(session)
    make_movement(
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=instrument,
        quantity="5",
        price="100",
        fee="1",
        occurred_at=ts("2026-01-01"),
    )
    make_movement(
        session,
        account,
        type=MovementType.SALE,
        instrument=instrument,
        quantity="5",
        price="120",
        fee="1",
        occurred_at=ts("2026-02-01"),
    )

    result = position(session, OWNER, instrument.id)

    assert result.quantity == Decimal("0")
    assert result.cost_basis == Decimal("0")
    assert result.lots == ()
    # proceeds 599 - cost 501
    assert result.realized_pnl == Decimal("98")
    # Closed positions stay in the listing: they carry realized P&L.
    assert [p.instrument_id for p in positions(session, OWNER)] == [instrument.id]


def test_same_timestamp_ordered_by_id(session: Session) -> None:
    """A buy and a sell at the same instant: the row created first wins the tie."""
    account = make_account(session)
    instrument = make_instrument(session)
    when = ts("2026-01-01")
    make_movement(
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=instrument,
        quantity="5",
        price="100",
        occurred_at=when,
    )
    make_movement(
        session,
        account,
        type=MovementType.SALE,
        instrument=instrument,
        quantity="5",
        price="110",
        occurred_at=when,
    )

    result = position(session, OWNER, instrument.id)

    assert result.quantity == Decimal("0")
    assert result.realized_pnl == Decimal("50")


def test_as_of_excludes_later_movements(session: Session) -> None:
    account = make_account(session)
    instrument = make_instrument(session)
    make_movement(
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=instrument,
        quantity="10",
        price="100",
        occurred_at=ts("2026-01-01"),
    )
    make_movement(
        session,
        account,
        type=MovementType.SALE,
        instrument=instrument,
        quantity="10",
        price="120",
        occurred_at=ts("2026-03-01"),
    )

    before_sale = position(session, OWNER, instrument.id, as_of=date(2026, 2, 1))
    assert before_sale.quantity == Decimal("10")
    assert before_sale.realized_pnl == Decimal("0")

    # A movement on the as-of day itself still counts (end-of-day cutoff).
    on_sale_day = position(session, OWNER, instrument.id, as_of=date(2026, 3, 1))
    assert on_sale_day.quantity == Decimal("0")


def test_voided_and_foreign_movements_excluded(session: Session) -> None:
    account = make_account(session)
    other_owner_account = make_account(session, owner_id=2)
    instrument = make_instrument(session)
    make_movement(
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=instrument,
        quantity="10",
        price="100",
        occurred_at=ts("2026-01-01"),
    )
    make_movement(  # annulled: must not count
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=instrument,
        quantity="99",
        price="1",
        occurred_at=ts("2026-01-02"),
        voided=True,
    )
    make_movement(  # another owner's trade in the same instrument: must not count
        session,
        other_owner_account,
        type=MovementType.PURCHASE,
        instrument=instrument,
        quantity="7",
        price="100",
        occurred_at=ts("2026-01-03"),
    )

    assert position(session, OWNER, instrument.id).quantity == Decimal("10")
    assert position(session, 2, instrument.id).quantity == Decimal("7")


def test_positions_aggregate_across_accounts(session: Session) -> None:
    """One position per instrument, whichever account the trades sit in."""
    account_a = make_account(session)
    account_b = make_account(session)
    instrument = make_instrument(session)
    make_movement(
        session,
        account_a,
        type=MovementType.PURCHASE,
        instrument=instrument,
        quantity="10",
        price="100",
        occurred_at=ts("2026-01-01"),
    )
    make_movement(
        session,
        account_b,
        type=MovementType.PURCHASE,
        instrument=instrument,
        quantity="5",
        price="110",
        occurred_at=ts("2026-02-01"),
    )

    result = positions(session, OWNER)

    assert len(result) == 1
    assert result[0].quantity == Decimal("15")
    assert result[0].cost_basis == Decimal("1550")


def test_position_rejects_non_tradable(session: Session) -> None:
    loan = make_instrument(session, asset_class="loan", expected_interest="0.05")

    with pytest.raises(DomainRuleError, match="not tradable"):
        position(session, OWNER, loan.id)
