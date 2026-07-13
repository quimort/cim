"""Shared ledger-walking query for the valuation services.

Every valuation reads the same slice of the ledger: the current owner's
non-voided movements up to an as-of date, in the order they happened. This
module is the single place that encodes those three rules so no strategy can
drift (forget the owner join, include voided rows, or sort differently).
"""

from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import Select, select

from app.models.account import Account
from app.models.enums import MovementType
from app.models.movement import Movement

if TYPE_CHECKING:
    from collections.abc import Iterable


def today_utc() -> date:
    """The default as-of date: today, UTC."""
    return datetime.now(UTC).date()


def as_of_cutoff(as_of: date) -> datetime:
    """The exclusive upper bound on ``occurred_at`` for an as-of date.

    ``price`` and ``exchange_rate`` are keyed by plain dates, while the ledger
    carries tz-aware datetimes; the rule bridging them is: a movement counts if
    it happened before the end of ``as_of``, UTC.
    """
    return datetime.combine(as_of + timedelta(days=1), time.min, tzinfo=UTC)


def owned_movements_stmt(
    owner_id: int,
    *,
    until: date,
    instrument_id: int | None = None,
    account_id: int | None = None,
    types: "Iterable[MovementType] | None" = None,
) -> Select[tuple[Movement]]:
    """Owner-scoped, void-filtered movements up to ``until``, in ledger order.

    Ascending ``(occurred_at, id)`` — the replay order FIFO and loan accrual
    depend on (``id`` breaks same-instant ties deterministically).
    """
    stmt = (
        select(Movement)
        .join(Account, Movement.account_id == Account.id)
        .where(
            Account.owner_id == owner_id,
            Movement.voided_at.is_(None),
            Movement.occurred_at < as_of_cutoff(until),
        )
    )
    if instrument_id is not None:
        stmt = stmt.where(Movement.instrument_id == instrument_id)
    if account_id is not None:
        stmt = stmt.where(Movement.account_id == account_id)
    if types is not None:
        stmt = stmt.where(Movement.type.in_([t.value for t in types]))
    return stmt.order_by(Movement.occurred_at, Movement.id)
