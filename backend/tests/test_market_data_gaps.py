"""Gap-fill window computation and currency discovery (task 1f)."""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.services.market_data.gaps import (
    DEFAULT_LOOKBACK_DAYS,
    currencies_in_use,
    fetch_window,
    last_fx_date,
    last_price_date,
)
from tests.factories import make_account, make_fx, make_instrument, make_price


def test_fetch_window_with_no_prior_history_uses_the_lookback() -> None:
    today = date(2026, 7, 13)
    start, end = fetch_window(None, today)

    assert start == today - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    assert end == today


def test_fetch_window_with_prior_history_starts_at_the_last_day_inclusive() -> None:
    today = date(2026, 7, 13)
    last = date(2026, 7, 10)

    start, end = fetch_window(last, today)

    assert start == last  # inclusive: the last stored day is re-fetched too
    assert end == today


def test_fetch_window_when_last_is_today_is_a_single_day() -> None:
    today = date(2026, 7, 13)
    assert fetch_window(today, today) == (today, today)


def test_fetch_window_custom_lookback() -> None:
    today = date(2026, 7, 13)
    start, _ = fetch_window(None, today, lookback_days=7)
    assert start == today - timedelta(days=7)


def test_last_price_date_returns_the_most_recent_row(session: Session) -> None:
    instrument = make_instrument(session)
    make_price(session, instrument, day="2026-01-05", value="10")
    make_price(session, instrument, day="2026-01-10", value="11")

    assert last_price_date(session, instrument.id) == date(2026, 1, 10)


def test_last_price_date_is_none_without_history(session: Session) -> None:
    instrument = make_instrument(session)
    assert last_price_date(session, instrument.id) is None


def test_last_fx_date_returns_the_most_recent_row(session: Session) -> None:
    make_fx(session, day="2026-01-05", base="USD", quote="EUR", rate="0.9")
    make_fx(session, day="2026-01-10", base="USD", quote="EUR", rate="0.95")

    assert last_fx_date(session, "USD", "EUR") == date(2026, 1, 10)


def test_currencies_in_use_unions_instrument_and_account_currencies(session: Session) -> None:
    make_instrument(session, currency="USD")
    make_account(session, currency="GBP")
    make_instrument(session, currency="EUR")

    assert currencies_in_use(session) == {"USD", "GBP"}


def test_currencies_in_use_excludes_inactive_rows(session: Session) -> None:
    instrument = make_instrument(session, currency="USD")
    instrument.is_active = False
    session.commit()

    account = make_account(session, currency="GBP")
    account.is_active = False
    session.commit()

    assert currencies_in_use(session) == set()
