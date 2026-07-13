"""Net worth over time — one full ledger replay per point, nothing cached.

Each point is `net_worth()` at a stepped date, so this is the most expensive
derived query in the service layer: the point count is capped so a careless
daily request over years of history cannot turn into thousands of replays.
"""

from calendar import monthrange
from collections.abc import Callable
from datetime import date, timedelta
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.movement import Movement
from app.services.errors import DomainRuleError
from app.services.valuation import _ledger
from app.services.valuation.net_worth import net_worth
from app.services.valuation.types import NetWorthPoint, NetWorthSeries

_MAX_POINTS = 1000


class Interval(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


def _add_month(day: date) -> date:
    year = day.year + day.month // 12
    month = day.month % 12 + 1
    # Clamp so e.g. Jan 31 + 1 month lands on Feb 28/29, not an invalid date.
    clamped_day = min(day.day, monthrange(year, month)[1])
    return date(year, month, clamped_day)


_STEP: dict[Interval, Callable[[date], date]] = {
    Interval.DAY: lambda day: day + timedelta(days=1),
    Interval.WEEK: lambda day: day + timedelta(days=7),
    Interval.MONTH: _add_month,
}


def _first_movement_date(db: Session, owner_id: int) -> date | None:
    stmt = (
        select(func.min(Movement.occurred_at))
        .join(Account, Movement.account_id == Account.id)
        .where(Account.owner_id == owner_id, Movement.voided_at.is_(None))
    )
    earliest = db.execute(stmt).scalar_one_or_none()
    return earliest.date() if earliest is not None else None


def net_worth_series(
    db: Session,
    owner_id: int,
    *,
    start: date | None = None,
    end: date | None = None,
    interval: Interval = Interval.MONTH,
) -> NetWorthSeries:
    """Net worth at each ``interval`` step from ``start`` to ``end``, inclusive.

    ``start`` defaults to the date of the owner's first movement (no
    movements at all yields an empty series); ``end`` defaults to today.
    """
    end = end if end is not None else _ledger.today_utc()
    if start is None:
        start = _first_movement_date(db, owner_id)
        if start is None:
            return NetWorthSeries(interval=interval.value, points=())
    if start > end:
        raise DomainRuleError(f"start date {start} is after end date {end}")

    step = _STEP[interval]
    dates: list[date] = []
    current = start
    while current < end:
        dates.append(current)
        if len(dates) > _MAX_POINTS:
            raise DomainRuleError(
                f"the requested range would produce more than {_MAX_POINTS} points; "
                "narrow the date range or choose a coarser interval"
            )
        current = step(current)
    dates.append(end)

    points = tuple(
        NetWorthPoint(as_of=day, total_eur=net_worth(db, owner_id, as_of=day).total_eur)
        for day in dates
    )
    return NetWorthSeries(interval=interval.value, points=points)
