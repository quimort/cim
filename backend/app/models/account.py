from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Account(Base):
    __tablename__ = "account"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_account_owner_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Isolation anchor (see CLAUDE.md multi-tenant rule). Fixed default today —
    # single-user in practice — becomes a FK to `user.id` when multi-user is
    # enabled. Every owned query filters on this, hence the index.
    owner_id: Mapped[int] = mapped_column(default=1, server_default="1", index=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(50))
    currency: Mapped[str] = mapped_column(String(3))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
