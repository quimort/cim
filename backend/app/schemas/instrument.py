"""API contracts for the ``instrument`` resource.

A single table carries all asset classes; the loan-only fields
(``maturity_date``, ``expected_interest``, ``status``) are meaningful only when
``asset_class == loan`` and must be absent otherwise. That cross-field rule is
contract validation, so it lives here in Pydantic. ``asset_class`` and
``currency`` are immutable once set (they define how the instrument is valued),
hence absent from the update schema.
"""

from datetime import date, datetime
from typing import Self

from pydantic import Field, model_validator

from app.models.enums import AssetClass, LoanStatus
from app.schemas.common import CurrencyCode, InterestRate, MoneyStr, RequestSchema, ResponseSchema


class InstrumentCreate(RequestSchema):
    name: str = Field(min_length=1, max_length=200)
    symbol: str | None = Field(default=None, min_length=1, max_length=50)
    asset_class: AssetClass
    currency: CurrencyCode
    maturity_date: date | None = None
    expected_interest: InterestRate | None = None
    status: LoanStatus | None = None

    @model_validator(mode="after")
    def _enforce_loan_fields(self) -> Self:
        loan_fields = {
            "maturity_date": self.maturity_date,
            "expected_interest": self.expected_interest,
            "status": self.status,
        }
        if self.asset_class is AssetClass.LOAN:
            # A loan is active unless stated otherwise; maturity/interest may
            # legitimately be unknown at creation time.
            if self.status is None:
                self.status = LoanStatus.ACTIVE
        else:
            set_fields = [name for name, value in loan_fields.items() if value is not None]
            if set_fields:
                raise ValueError(f"{', '.join(sorted(set_fields))} require asset_class=loan")
        return self


class InstrumentUpdate(RequestSchema):
    """PATCH semantics. ``asset_class`` and ``currency`` are immutable.

    Loan fields cannot be cross-checked against the stored ``asset_class`` here
    (the schema doesn't see the DB row); the router/service enforces that.
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    symbol: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None
    maturity_date: date | None = None
    expected_interest: InterestRate | None = None
    status: LoanStatus | None = None


class InstrumentRead(ResponseSchema):
    id: int
    name: str
    symbol: str | None
    asset_class: AssetClass
    currency: str
    maturity_date: date | None
    expected_interest: MoneyStr | None
    status: LoanStatus | None
    is_active: bool
    created_at: datetime
