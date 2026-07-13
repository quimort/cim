"""Loan valuation: simple linear accrual, actual/365, segment-wise on principal.

Expected values are written as the exact Decimal expressions of the model, not
as rounded literals, so a test failure means the model changed — not that a
literal was rounded differently.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.enums import MovementType
from app.services.errors import DomainRuleError
from app.services.valuation import value_loan
from tests.factories import make_account, make_instrument, make_movement, ts

OWNER = 1
YEAR = Decimal(365)


def test_simple_accrual_73_days(session: Session) -> None:
    """1000 at 5% for 73 days = 1000 * 0.05 * 73/365 = 10 exactly."""
    account = make_account(session)
    loan = make_instrument(session, asset_class="loan", expected_interest="0.05")
    make_movement(
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=loan,
        quantity="1000",
        price="1",
        occurred_at=ts("2026-01-01"),
    )

    result = value_loan(session, OWNER, loan, as_of=date(2026, 3, 15))  # 73 days later

    assert result.outstanding_principal == Decimal("1000")
    assert result.accrued_interest == Decimal("10")
    assert result.value == Decimal("1010")


def test_repayment_splits_the_accrual_segments(session: Session) -> None:
    """1000 for 60 days, then 600 for another 60 days after a 400 repayment."""
    account = make_account(session)
    loan = make_instrument(session, asset_class="loan", expected_interest="0.05")
    make_movement(
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=loan,
        quantity="1000",
        price="1",
        occurred_at=ts("2026-01-01"),
    )
    make_movement(
        session,
        account,
        type=MovementType.PRINCIPAL_REPAYMENT,
        instrument=loan,
        quantity="400",
        occurred_at=ts("2026-03-02"),  # day 60
    )

    result = value_loan(session, OWNER, loan, as_of=date(2026, 5, 1))  # day 120

    rate = Decimal("0.05")
    expected = (
        Decimal("1000") * rate * Decimal(60) / YEAR + Decimal("600") * rate * Decimal(60) / YEAR
    )
    assert result.outstanding_principal == Decimal("600")
    assert result.accrued_interest == expected


def test_interest_received_reduces_accrual_and_floors_at_zero(session: Session) -> None:
    account = make_account(session)
    loan = make_instrument(session, asset_class="loan", expected_interest="0.05")
    make_movement(
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=loan,
        quantity="1000",
        price="1",
        occurred_at=ts("2026-01-01"),
    )
    make_movement(
        session,
        account,
        type=MovementType.INTEREST,
        instrument=loan,
        quantity="4",
        occurred_at=ts("2026-02-01"),
    )

    # 73 days accrue 10; 4 already received -> 6 outstanding.
    partial = value_loan(session, OWNER, loan, as_of=date(2026, 3, 15))
    assert partial.accrued_interest == Decimal("6")

    # Receiving more interest than accrued does not create negative accrual.
    make_movement(
        session,
        account,
        type=MovementType.INTEREST,
        instrument=loan,
        quantity="50",
        occurred_at=ts("2026-03-01"),
    )
    overpaid = value_loan(session, OWNER, loan, as_of=date(2026, 3, 15))
    assert overpaid.accrued_interest == Decimal("0")
    assert overpaid.value == Decimal("1000")


def test_fully_repaid_loan_stops_accruing(session: Session) -> None:
    account = make_account(session)
    loan = make_instrument(session, asset_class="loan", expected_interest="0.05")
    make_movement(
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=loan,
        quantity="1000",
        price="1",
        occurred_at=ts("2026-01-01"),
    )
    make_movement(
        session,
        account,
        type=MovementType.PRINCIPAL_REPAYMENT,
        instrument=loan,
        quantity="1000",
        occurred_at=ts("2026-03-02"),  # day 60
    )

    result = value_loan(session, OWNER, loan, as_of=date(2027, 1, 1))

    assert result.outstanding_principal == Decimal("0")
    # Only the 60 live days accrued; nothing after full repayment.
    assert result.accrued_interest == Decimal("1000") * Decimal("0.05") * Decimal(60) / YEAR


def test_non_loan_instrument_rejected(session: Session) -> None:
    tradable = make_instrument(session)

    with pytest.raises(DomainRuleError, match="not a loan"):
        value_loan(session, OWNER, tradable)


def test_loan_without_rate_rejected(session: Session) -> None:
    loan = make_instrument(session, asset_class="loan")

    with pytest.raises(DomainRuleError, match="expected_interest"):
        value_loan(session, OWNER, loan)
