"""Allocation: net worth regrouped by one dimension.

Every dimension's buckets must sum to exactly the same total as ``net_worth()``
— that invariant, not any particular bucketing mechanics, is what's asserted
most heavily here.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.enums import MovementType
from app.services.valuation import Dimension, allocation, net_worth
from app.services.valuation.loans import value_loan
from tests.factories import (
    make_account,
    make_category,
    make_fx,
    make_instrument,
    make_movement,
    make_price,
    ts,
)

OWNER = 1


def _bucket(report, key: str | None):
    for bucket in report.buckets:
        if bucket.key == key:
            return bucket
    raise AssertionError(f"no bucket with key {key!r} in {[b.key for b in report.buckets]}")


def _build_mixed_portfolio(session: Session) -> None:
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


def test_asset_class_dimension_sums_to_net_worth_total(session: Session) -> None:
    _build_mixed_portfolio(session)
    as_of = date(2026, 3, 15)

    report = allocation(session, OWNER, dimension=Dimension.ASSET_CLASS, as_of=as_of)
    expected_total = net_worth(session, OWNER, as_of=as_of).total_eur

    assert report.total_eur == expected_total
    assert sum(bucket.value_eur for bucket in report.buckets) == expected_total
    assert _bucket(report, "loan").label == "Loan"


def test_currency_dimension_sums_to_net_worth_total(session: Session) -> None:
    _build_mixed_portfolio(session)
    as_of = date(2026, 3, 15)

    report = allocation(session, OWNER, dimension=Dimension.CURRENCY, as_of=as_of)
    expected_total = net_worth(session, OWNER, as_of=as_of).total_eur

    assert report.total_eur == expected_total
    assert sum(bucket.value_eur for bucket in report.buckets) == expected_total
    assert {bucket.key for bucket in report.buckets} == {"EUR", "USD"}


def test_category_dimension_groups_instruments_and_flags_uncategorized(session: Session) -> None:
    crypto = make_category(session, name="Crypto")
    account = make_account(session)
    categorized = make_instrument(session, category_id=crypto.id)
    uncategorized = make_instrument(session)

    make_movement(
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=categorized,
        quantity="5",
        price="10",
        occurred_at=ts("2026-01-01"),
    )
    make_movement(
        session,
        account,
        type=MovementType.PURCHASE,
        instrument=uncategorized,
        quantity="5",
        price="10",
        occurred_at=ts("2026-01-01"),
    )
    make_price(session, categorized, day="2026-01-01", value="10")
    make_price(session, uncategorized, day="2026-01-01", value="10")
    as_of = date(2026, 2, 1)

    report = allocation(session, OWNER, dimension=Dimension.CATEGORY, as_of=as_of)

    crypto_bucket = _bucket(report, str(crypto.id))
    assert crypto_bucket.label == "Crypto"
    assert crypto_bucket.value_eur == Decimal("50")

    uncategorized_value = sum(bucket.value_eur for bucket in report.buckets if bucket.key is None)
    # Cash (from the -100 spent on each purchase) plus the uncategorized stock.
    assert uncategorized_value == Decimal("-100") + Decimal("50")
    assert report.total_eur == net_worth(session, OWNER, as_of=as_of).total_eur


def test_account_dimension_attributes_cash_per_account(session: Session) -> None:
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
    as_of = date(2026, 2, 1)

    report = allocation(session, OWNER, dimension=Dimension.ACCOUNT, as_of=as_of)

    assert _bucket(report, str(origin.id)).value_eur == Decimal("700")
    assert _bucket(report, str(destination.id)).value_eur == Decimal("300")
    assert report.total_eur == net_worth(session, OWNER, as_of=as_of).total_eur


def test_account_dimension_attributes_a_transferred_instrument_to_its_destination(
    session: Session,
) -> None:
    origin = make_account(session)
    destination = make_account(session)
    stock = make_instrument(session)
    make_movement(
        session,
        origin,
        type=MovementType.PURCHASE,
        instrument=stock,
        quantity="10",
        price="100",
        occurred_at=ts("2026-01-01"),
    )
    transfer_id = uuid.uuid4()
    make_movement(
        session,
        origin,
        type=MovementType.TRANSFER_OUT,
        instrument=stock,
        quantity="10",
        occurred_at=ts("2026-01-05"),
        transfer_id=transfer_id,
    )
    make_movement(
        session,
        destination,
        type=MovementType.TRANSFER_IN,
        instrument=stock,
        quantity="10",
        occurred_at=ts("2026-01-05"),
        transfer_id=transfer_id,
    )
    make_price(session, stock, day="2026-01-01", value="120")
    as_of = date(2026, 2, 1)

    report = allocation(session, OWNER, dimension=Dimension.ACCOUNT, as_of=as_of)

    # origin only carries the cash spent on the purchase; the holding itself
    # (now worth 1200) shows up entirely under the destination account.
    assert _bucket(report, str(origin.id)).value_eur == Decimal("-1000")
    assert _bucket(report, str(destination.id)).value_eur == Decimal("1200")
    assert report.total_eur == net_worth(session, OWNER, as_of=as_of).total_eur


def test_account_dimension_attributes_a_loan_by_principal_share(session: Session) -> None:
    lender_a = make_account(session)
    lender_b = make_account(session)
    loan = make_instrument(session, asset_class="loan", expected_interest="0.05")
    make_movement(
        session,
        lender_a,
        type=MovementType.PURCHASE,
        instrument=loan,
        quantity="600",
        price="1",
        occurred_at=ts("2026-01-01"),
    )
    make_movement(
        session,
        lender_b,
        type=MovementType.PURCHASE,
        instrument=loan,
        quantity="400",
        price="1",
        occurred_at=ts("2026-01-01"),
    )
    as_of = date(2026, 3, 15)  # 73 days later, matching the net-worth fixture's accrual

    report = allocation(session, OWNER, dimension=Dimension.ACCOUNT, as_of=as_of)
    expected = value_loan(session, OWNER, loan, as_of=as_of).value  # 1010

    # Cash from each disbursement (-600 / -400) plus this account's principal
    # share of the loan's value (60% / 40% of 1010).
    assert _bucket(report, str(lender_a.id)).value_eur == Decimal("-600") + expected * Decimal(
        "0.6"
    )
    assert _bucket(report, str(lender_b.id)).value_eur == Decimal("-400") + expected * Decimal(
        "0.4"
    )
    assert report.total_eur == net_worth(session, OWNER, as_of=as_of).total_eur


def test_account_dimension_attributes_a_fully_repaid_loan_to_its_last_event_account(
    session: Session,
) -> None:
    """total principal nets to zero but accrued-unpaid interest may remain."""
    lender = make_account(session)
    repayer = make_account(session)
    loan = make_instrument(session, asset_class="loan", expected_interest="0.05")
    make_movement(
        session,
        lender,
        type=MovementType.PURCHASE,
        instrument=loan,
        quantity="1000",
        price="1",
        occurred_at=ts("2026-01-01"),
    )
    make_movement(
        session,
        repayer,
        type=MovementType.PRINCIPAL_REPAYMENT,
        instrument=loan,
        quantity="1000",
        occurred_at=ts("2026-01-31"),
    )
    as_of = date(2026, 3, 15)

    report = allocation(session, OWNER, dimension=Dimension.ACCOUNT, as_of=as_of)
    # Combining a large cash figure with a ~1e-24 accrued-interest remainder in
    # the same running total hits Decimal's 28-significant-digit context
    # precision, so the two independently-summed totals may differ in their
    # last few digits — utterly immaterial for a currency amount.
    difference = abs(report.total_eur - net_worth(session, OWNER, as_of=as_of).total_eur)
    assert difference < Decimal("1e-15")


def test_other_owners_do_not_leak_into_allocation(session: Session) -> None:
    mine = make_account(session)
    theirs = make_account(session, owner_id=2)
    make_movement(
        session, mine, type=MovementType.DEPOSIT, quantity="100", occurred_at=ts("2026-01-01")
    )
    make_movement(
        session, theirs, type=MovementType.DEPOSIT, quantity="9000", occurred_at=ts("2026-01-01")
    )

    report = allocation(session, OWNER, dimension=Dimension.ACCOUNT)
    assert report.total_eur == Decimal("100")
