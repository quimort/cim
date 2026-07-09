import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import MovementType


class Movement(Base):
    __tablename__ = "movement"
    __table_args__ = (
        CheckConstraint(
            f"type IN ({','.join(repr(v.value) for v in MovementType)})",
            name="ck_movement_type",
        ),
        UniqueConstraint("source", "external_id", name="uq_movement_source_external_id"),
        Index("ix_movement_account_occurred_at", "account_id", "occurred_at"),
        Index("ix_movement_transfer_id", "transfer_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instrument.id"))

    type: Mapped[str] = mapped_column(String(30))
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    fee: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    currency: Mapped[str] = mapped_column(String(3))

    transfer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)

    source: Mapped[str] = mapped_column(String(50), default="manual", server_default="manual")
    external_id: Mapped[str | None] = mapped_column(String(200))

    # Soft-delete: NULL means the movement is active. Movements are never
    # updated or physically deleted — the ledger is append-only and immutable.
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
