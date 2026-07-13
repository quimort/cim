"""The ``category`` table: the open, user-managed grouping axis.

Orthogonal to ``asset_class`` on purpose. ``asset_class`` answers *how is this
valued*; a category answers *how do I want to see it grouped* (ETF, crypto, P2P
loan, real estate). A REIT is ``tradable`` and categorised "real estate"; a
savings account is ``cash`` and categorised "emergency fund". Linking a category
back to an asset class would force nonsense mappings — real estate is neither
tradable, cash, nor a loan — so it carries no such link.

Categories are never hard-deleted: an instrument may reference one, and past
allocation reports must keep resolving. Deactivation only hides it from pickers.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Category(Base):
    __tablename__ = "category"
    __table_args__ = (UniqueConstraint("name", name="uq_category_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
