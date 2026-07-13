"""Cash balances: the fold of every movement's cash leg, per (account, currency)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.enums import MovementType
from app.services.valuation import cash_balances
from tests.factories import make_account, make_instrument, make_movement, ts

OWNER = 1


def _balance(session: Session, account_id: int, currency: str) -> Decimal:
    for row in cash_balances(session, OWNER):
        if row.account_id == account_id and row.currency == currency:
            return row.balance
    raise AssertionError(f"no balance for account {account_id} in {currency}")


def test_deposit_withdrawal_fee_arithmetic(session: Session) -> None:
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
        quantity="200",
        occurred_at=ts("2026-01-02"),
    )
    make_movement(
        session,
        account,
        type=MovementType.FEE,
        quantity="10",
        occurred_at=ts("2026-01-03"),
    )

    assert _balance(session, account.id, "EUR") == Decimal("790")


def test_purchase_and_sale_carry_implicit_cash_legs(session: Session) -> None:
    account = make_account(session)
    instrument = make_instrument(session)
    make_movement(
        session,
        account,
        type=MovementType.DEPOSIT,
        quantity="2000",
        occurred_at=ts("2026-01-01"),
    )
    # purchase: -(10*100 + 5) = -1005
    make_movement(
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=instrument,
        quantity="10",
        price="100",
        fee="5",
        occurred_at=ts("2026-01-02"),
    )
    # sale: +(4*120 - 2) = +478
    make_movement(
        session,
        account,
        type=MovementType.SALE,
        instrument=instrument,
        quantity="4",
        price="120",
        fee="2",
        occurred_at=ts("2026-01-03"),
    )

    assert _balance(session, account.id, "EUR") == Decimal("1473")


def test_cash_transfer_moves_money_total_unchanged(session: Session) -> None:
    origin = make_account(session)
    destination = make_account(session)
    make_movement(
        session,
        origin,
        type=MovementType.DEPOSIT,
        quantity="1000",
        occurred_at=ts("2026-01-01"),
    )
    transfer_id = uuid.uuid4()
    make_movement(
        session,
        origin,
        type=MovementType.TRANSFER_OUT,
        quantity="300",
        occurred_at=ts("2026-01-02"),
        transfer_id=transfer_id,
    )
    make_movement(
        session,
        destination,
        type=MovementType.TRANSFER_IN,
        quantity="300",
        occurred_at=ts("2026-01-02"),
        transfer_id=transfer_id,
    )

    assert _balance(session, origin.id, "EUR") == Decimal("700")
    assert _balance(session, destination.id, "EUR") == Decimal("300")
    total = sum(row.balance for row in cash_balances(session, OWNER))
    assert total == Decimal("1000")


def test_instrument_transfer_leaves_cash_untouched(session: Session) -> None:
    origin = make_account(session)
    destination = make_account(session)
    instrument = make_instrument(session)
    make_movement(
        session,
        origin,
        type=MovementType.DEPOSIT,
        quantity="500",
        occurred_at=ts("2026-01-01"),
    )
    transfer_id = uuid.uuid4()
    make_movement(
        session,
        origin,
        type=MovementType.TRANSFER_OUT,
        instrument=instrument,
        quantity="10",
        occurred_at=ts("2026-01-02"),
        transfer_id=transfer_id,
    )
    make_movement(
        session,
        destination,
        type=MovementType.TRANSFER_IN,
        instrument=instrument,
        quantity="10",
        occurred_at=ts("2026-01-02"),
        transfer_id=transfer_id,
    )

    assert _balance(session, origin.id, "EUR") == Decimal("500")
    assert _balance(session, destination.id, "EUR") == Decimal("0")


def test_two_currencies_in_one_account_are_separate_balances(session: Session) -> None:
    account = make_account(session, currency="EUR")
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
        type=MovementType.DEPOSIT,
        quantity="500",
        currency="USD",
        occurred_at=ts("2026-01-02"),
    )

    assert _balance(session, account.id, "EUR") == Decimal("1000")
    assert _balance(session, account.id, "USD") == Decimal("500")


def test_income_types_increase_cash(session: Session) -> None:
    account = make_account(session)
    tradable = make_instrument(session)
    loan = make_instrument(session, asset_class="loan", expected_interest="0.05")
    make_movement(
        session,
        account,
        type=MovementType.DIVIDEND,
        instrument=tradable,
        quantity="50",
        fee="1",
        occurred_at=ts("2026-01-01"),
    )
    make_movement(
        session,
        account,
        type=MovementType.INTEREST,
        instrument=loan,
        quantity="20",
        occurred_at=ts("2026-01-02"),
    )
    make_movement(
        session,
        account,
        type=MovementType.PRINCIPAL_REPAYMENT,
        instrument=loan,
        quantity="100",
        occurred_at=ts("2026-01-03"),
    )

    # 49 + 20 + 100
    assert _balance(session, account.id, "EUR") == Decimal("169")


def test_as_of_and_scoping(session: Session) -> None:
    account = make_account(session)
    foreign = make_account(session, owner_id=2)
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
    make_movement(  # voided: never counts
        session,
        account,
        type=MovementType.DEPOSIT,
        quantity="9999",
        occurred_at=ts("2026-01-05"),
        voided=True,
    )
    make_movement(  # another owner's money: never visible here
        session,
        foreign,
        type=MovementType.DEPOSIT,
        quantity="7777",
        occurred_at=ts("2026-01-05"),
    )

    past = cash_balances(session, OWNER, as_of=date(2026, 1, 15))
    assert [(row.account_id, row.balance) for row in past] == [(account.id, Decimal("1000"))]

    now = cash_balances(session, OWNER)
    assert [(row.account_id, row.balance) for row in now] == [(account.id, Decimal("400"))]
