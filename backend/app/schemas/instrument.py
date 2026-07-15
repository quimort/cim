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

from app.models.enums import AssetClass, LoanStatus, PriceSource
from app.schemas.common import CurrencyCode, InterestRate, MoneyStr, RequestSchema, ResponseSchema


class InstrumentCreate(RequestSchema):
    name: str = Field(min_length=1, max_length=200)
    symbol: str | None = Field(default=None, min_length=1, max_length=50, description="Ticker.")
    asset_class: AssetClass = Field(
        description="The valuation dispatch key. Fixed for the instrument's lifetime."
    )
    currency: CurrencyCode = Field(description="ISO 4217 code. Fixed for the instrument's life.")
    category_id: int | None = Field(
        default=None, description="Optional grouping (ETF, crypto, ...). Never affects valuation."
    )
    maturity_date: date | None = Field(default=None, description="Loan only.")
    expected_interest: InterestRate | None = Field(default=None, description="Loan only.")
    status: LoanStatus | None = Field(
        default=None, description="Loan only. Defaults to 'active' when omitted."
    )
    price_source: PriceSource | None = Field(
        default=None,
        description="Market-data provider for the price batch script. Tradable only.",
    )
    provider_ref: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Provider-specific id (yfinance ticker, CoinGecko coin id). Tradable only.",
    )

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

    @model_validator(mode="after")
    def _enforce_pricing_fields(self) -> Self:
        if (self.price_source is None) != (self.provider_ref is None):
            raise ValueError("price_source and provider_ref must be set together")
        if self.price_source is not None and self.asset_class is not AssetClass.TRADABLE:
            raise ValueError("price_source/provider_ref require asset_class=tradable")
        return self


class InstrumentUpdate(RequestSchema):
    """PATCH semantics. ``asset_class`` and ``currency`` are immutable.

    Loan and pricing fields cannot be cross-checked against the stored
    ``asset_class`` here (the schema doesn't see the DB row); the service
    enforces that against the stored row plus these changes.
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    symbol: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None
    category_id: int | None = Field(
        default=None, description="Pass null to uncategorise. Must reference an active category."
    )
    maturity_date: date | None = None
    expected_interest: InterestRate | None = None
    status: LoanStatus | None = None
    price_source: PriceSource | None = None
    provider_ref: str | None = Field(default=None, min_length=1, max_length=100)


class InstrumentRead(ResponseSchema):
    id: int
    name: str
    symbol: str | None
    asset_class: AssetClass
    currency: str
    category_id: int | None
    maturity_date: date | None
    expected_interest: MoneyStr | None
    status: LoanStatus | None
    price_source: PriceSource | None
    provider_ref: str | None
    is_active: bool
    created_at: datetime
