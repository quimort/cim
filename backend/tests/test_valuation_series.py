"""Net worth series: net_worth() replayed at each interval step."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.enums import MovementType
from app.services.errors import DomainRuleError
from app.services.valuation import net_worth_series
from app.services.valuation.series import Interval
from tests.factories import make_account, make_movement, ts

OWNER = 1


def test_empty_ledger_yields_an_empty_series(session: Session) -> None:
    series = net_worth_series(session, OWNER)
    assert series.points == ()


def test_default_start_is_the_first_movement_and_end_includes_the_final_point(
    session: Session,
) -> None:
    account = make_account(session)
    make_movement(
        session,
        account,
        type=MovementType.DEPOSIT,
        quantity="1000",
        occurred_at=ts("2026-01-15"),
    )
    make_movement(
        session,
        account,
        type=MovementType.DEPOSIT,
        quantity="500",
        occurred_at=ts("2026-03-01"),
    )

    series = net_worth_series(session, OWNER, end=date(2026, 3, 15), interval=Interval.MONTH)

    dates = [point.as_of for point in series.points]
    assert dates[0] == date(2026, 1, 15)
    assert dates[-1] == date(2026, 3, 15)  # the end point is always included

    totals = {point.as_of: point.total_eur for point in series.points}
    assert totals[date(2026, 1, 15)] == Decimal("1000")
    assert totals[date(2026, 3, 15)] == Decimal("1500")


def test_weekly_and_daily_intervals_step_correctly(session: Session) -> None:
    account = make_account(session)
    make_movement(
        session,
        account,
        type=MovementType.DEPOSIT,
        quantity="100",
        occurred_at=ts("2026-01-01"),
    )

    daily = net_worth_series(
        session, OWNER, start=date(2026, 1, 1), end=date(2026, 1, 3), interval=Interval.DAY
    )
    assert [point.as_of for point in daily.points] == [
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 3),
    ]

    weekly = net_worth_series(
        session, OWNER, start=date(2026, 1, 1), end=date(2026, 1, 15), interval=Interval.WEEK
    )
    assert [point.as_of for point in weekly.points] == [
        date(2026, 1, 1),
        date(2026, 1, 8),
        date(2026, 1, 15),
    ]


def test_start_after_end_raises(session: Session) -> None:
    with pytest.raises(DomainRuleError, match="after"):
        net_worth_series(session, OWNER, start=date(2026, 2, 1), end=date(2026, 1, 1))


def test_too_many_points_raises(session: Session) -> None:
    with pytest.raises(DomainRuleError, match="points"):
        net_worth_series(
            session,
            OWNER,
            start=date(2020, 1, 1),
            end=date(2026, 1, 1),
            interval=Interval.DAY,
        )
