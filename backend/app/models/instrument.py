from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import LoanStatus


class Instrument(Base):
    __tablename__ = "instrument"
    __table_args__ = (
        # asset_class is guarded by a FK to the `asset_class` table, not a CHECK:
        # the set of codes is still closed (it is the valuation dispatch key), but
        # the database now enforces it by referential integrity.
        CheckConstraint(
            f"status IS NULL OR status IN ({','.join(repr(v.value) for v in LoanStatus)})",
            name="ck_instrument_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    symbol: Mapped[str | None] = mapped_column(String(50))
    asset_class: Mapped[str] = mapped_column(String(20), ForeignKey("asset_class.code"))
    currency: Mapped[str] = mapped_column(String(3))

    # The open grouping axis. Nullable: an instrument need not be categorised.
    category_id: Mapped[int | None] = mapped_column(ForeignKey("category.id"), index=True)

    # Loan-only fields, NULL for tradable/cash instruments.
    maturity_date: Mapped[date | None] = mapped_column(Date)
    expected_interest: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    status: Mapped[str | None] = mapped_column(String(20))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
