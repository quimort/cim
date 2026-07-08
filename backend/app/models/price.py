from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Price(Base):
    __tablename__ = "price"
    __table_args__ = (UniqueConstraint("instrument_id", "date", name="uq_price_instrument_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instrument.id"))
    date: Mapped[date] = mapped_column(Date)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    currency: Mapped[str] = mapped_column(String(3))
