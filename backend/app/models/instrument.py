from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import AssetClass, LoanStatus


class Instrument(Base):
    __tablename__ = "instrument"
    __table_args__ = (
        CheckConstraint(
            f"asset_class IN ({','.join(repr(v.value) for v in AssetClass)})",
            name="ck_instrument_asset_class",
        ),
        CheckConstraint(
            f"status IS NULL OR status IN ({','.join(repr(v.value) for v in LoanStatus)})",
            name="ck_instrument_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    symbol: Mapped[str | None] = mapped_column(String(50))
    asset_class: Mapped[str] = mapped_column(String(20))
    currency: Mapped[str] = mapped_column(String(3))

    # Loan-only fields, NULL for tradable/cash instruments.
    maturity_date: Mapped[date | None] = mapped_column(Date)
    expected_interest: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    status: Mapped[str | None] = mapped_column(String(20))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
