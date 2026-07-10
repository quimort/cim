"""Loan valuation: outstanding principal plus accrued, unpaid interest.

Ledger conventions for a loan instrument:
- disbursement  = ``purchase`` of the loan instrument with ``price = 1``
  (principal lent = quantity x price);
- ``principal_repayment`` reduces principal by its quantity;
- ``interest`` movements are interest actually received — they reduce the
  accrued (not-yet-paid) interest, floored at zero.

Accrual model (phase-1 simple, documented so phase 2 can refine it):
``expected_interest`` is an annual rate as a fraction (0.05 = 5%), simple
linear accrual with an actual/365 day count, computed segment-wise on the
outstanding principal between principal-changing events, from the first
disbursement to the as-of date. ``maturity_date`` and ``status`` do not enter
the math: a repaid loan naturally values ~0 once its repayments are recorded.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.enums import AssetClass, MovementType
from app.models.instrument import Instrument
from app.services.errors import DomainRuleError
from app.services.valuation import _ledger
from app.services.valuation.types import LoanValuation

_ZERO = Decimal(0)
_DAYS_PER_YEAR = Decimal(365)

_LOAN_TYPES = (
    MovementType.PURCHASE,
    MovementType.PRINCIPAL_REPAYMENT,
    MovementType.INTEREST,
)


def value_loan(
    db: Session, owner_id: int, instrument: Instrument, *, as_of: date | None = None
) -> LoanValuation:
    """Principal outstanding and interest accrued-but-unpaid at ``as_of``."""
    if instrument.asset_class != AssetClass.LOAN:
        raise DomainRuleError(
            f"instrument {instrument.id} is '{instrument.asset_class}', not a loan"
        )
    if instrument.expected_interest is None:
        raise DomainRuleError(
            f"loan instrument {instrument.id} has no expected_interest rate; "
            "set it before valuing the loan"
        )
    as_of = as_of if as_of is not None else _ledger.today_utc()
    rate = instrument.expected_interest

    stmt = _ledger.owned_movements_stmt(
        owner_id, until=as_of, instrument_id=instrument.id, types=_LOAN_TYPES
    )
    events = db.execute(stmt).scalars().all()

    principal = _ZERO
    accrued = _ZERO
    interest_received = _ZERO
    segment_start: date | None = None  # None until the first disbursement

    def accrue_until(day: date) -> None:
        nonlocal accrued
        if segment_start is not None and principal > _ZERO:
            days = Decimal((day - segment_start).days)
            accrued += principal * rate * days / _DAYS_PER_YEAR

    for movement in events:
        event_date = movement.occurred_at.date()
        if movement.type == MovementType.INTEREST:
            interest_received += movement.quantity
            continue
        # Principal-changing event: close the running segment first.
        accrue_until(event_date)
        if movement.type == MovementType.PURCHASE:
            if movement.price is None:  # guarded by the schema; keeps mypy honest
                raise DomainRuleError(f"purchase movement {movement.id} has no price")
            principal += movement.quantity * movement.price
        else:  # principal_repayment
            principal -= movement.quantity
        segment_start = event_date

    accrue_until(as_of)

    return LoanValuation(
        instrument_id=instrument.id,
        outstanding_principal=principal,
        accrued_interest=max(accrued - interest_received, _ZERO),
        currency=instrument.currency,
    )
