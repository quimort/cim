"""Orchestration tests (task 1f): provider dispatch, skip/failure isolation,
dry-run, and idempotency — all with fake fetchers, no network.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import PriceSource
from app.models.exchange_rate import ExchangeRate
from app.models.price import Price
from app.services.market_data.runner import run_update
from app.services.market_data.types import FxRate, Quote
from tests.factories import make_instrument

TODAY = date(2026, 7, 13)


def _fixed_quotes(day: date, value: str) -> list[Quote]:
    return [Quote(day=day, value=Decimal(value))]


def _prices_written(session: Session) -> list[Price]:
    return list(session.execute(select(Price)).scalars().all())


def test_null_price_source_instruments_are_skipped(session: Session) -> None:
    make_instrument(session)  # no price_source

    summary = run_update(
        session,
        quote_fetchers={},
        fx_fetcher=lambda currencies, start, end: [],
        today=TODAY,
    )

    assert summary.instruments_skipped == 1
    assert summary.instruments_ok == 0
    assert _prices_written(session) == []


def test_provider_dispatch_calls_the_matching_fetcher(session: Session) -> None:
    yf_instrument = make_instrument(
        session, currency="EUR", price_source="yfinance", provider_ref="VWCE.DE"
    )
    cg_instrument = make_instrument(
        session, currency="EUR", price_source="coingecko", provider_ref="bitcoin"
    )
    calls: list[str] = []

    def yfinance_fetcher(provider_ref: str, currency: str, start: date, end: date) -> list[Quote]:
        calls.append(f"yfinance:{provider_ref}")
        return _fixed_quotes(end, "10")

    def coingecko_fetcher(provider_ref: str, currency: str, start: date, end: date) -> list[Quote]:
        calls.append(f"coingecko:{provider_ref}")
        return _fixed_quotes(end, "20")

    summary = run_update(
        session,
        quote_fetchers={
            PriceSource.YFINANCE: yfinance_fetcher,
            PriceSource.COINGECKO: coingecko_fetcher,
        },
        fx_fetcher=lambda currencies, start, end: [],
        today=TODAY,
    )

    assert summary.instruments_ok == 2
    assert set(calls) == {"yfinance:VWCE.DE", "coingecko:bitcoin"}
    written = {row.instrument_id: row.value for row in _prices_written(session)}
    assert written[yf_instrument.id] == Decimal("10")
    assert written[cg_instrument.id] == Decimal("20")


def test_one_instrument_failing_does_not_abort_the_others(session: Session) -> None:
    make_instrument(session, price_source="yfinance", provider_ref="BROKEN")
    good = make_instrument(session, price_source="yfinance", provider_ref="VWCE.DE")

    def flaky_fetcher(provider_ref: str, currency: str, start: date, end: date) -> list[Quote]:
        if provider_ref == "BROKEN":
            raise RuntimeError("provider is down")
        return _fixed_quotes(end, "10")

    summary = run_update(
        session,
        quote_fetchers={PriceSource.YFINANCE: flaky_fetcher},
        fx_fetcher=lambda currencies, start, end: [],
        today=TODAY,
    )

    assert summary.instruments_ok == 1
    assert summary.instruments_failed == 1
    assert len(summary.failures) == 1
    written = _prices_written(session)
    assert len(written) == 1
    assert written[0].instrument_id == good.id


def test_dry_run_writes_nothing(session: Session) -> None:
    make_instrument(session, price_source="yfinance", provider_ref="VWCE.DE")

    summary = run_update(
        session,
        quote_fetchers={
            PriceSource.YFINANCE: lambda ref, currency, start, end: _fixed_quotes(end, "10")
        },
        fx_fetcher=lambda currencies, start, end: [],
        today=TODAY,
        dry_run=True,
    )

    assert summary.instruments_ok == 1
    assert summary.prices_written == 1  # reported, but rolled back
    assert _prices_written(session) == []


def test_running_twice_does_not_duplicate_rows(session: Session) -> None:
    make_instrument(session, price_source="yfinance", provider_ref="VWCE.DE")
    fetcher = {
        PriceSource.YFINANCE: lambda ref, currency, start, end: _fixed_quotes(end, "10"),
    }

    run_update(session, quote_fetchers=fetcher, fx_fetcher=lambda c, s, e: [], today=TODAY)
    run_update(session, quote_fetchers=fetcher, fx_fetcher=lambda c, s, e: [], today=TODAY)

    assert len(_prices_written(session)) == 1


def test_fx_failure_does_not_prevent_price_writes(session: Session) -> None:
    make_instrument(session, currency="USD", price_source="yfinance", provider_ref="VWCE.DE")

    def failing_fx(currencies: set[str], start: date, end: date) -> list[FxRate]:
        raise RuntimeError("frankfurter is down")

    summary = run_update(
        session,
        quote_fetchers={
            PriceSource.YFINANCE: lambda ref, currency, start, end: _fixed_quotes(end, "10")
        },
        fx_fetcher=failing_fx,
        today=TODAY,
    )

    assert summary.instruments_ok == 1
    assert summary.fx_failed is True
    assert not summary.ok
    assert len(_prices_written(session)) == 1
    assert session.execute(select(ExchangeRate)).scalars().all() == []


def test_fx_step_writes_rates_for_currencies_in_use(session: Session) -> None:
    make_instrument(session, currency="USD")  # no price_source, but drives FX discovery

    summary = run_update(
        session,
        quote_fetchers={},
        fx_fetcher=lambda currencies, start, end: [
            FxRate(day=end, base=c, quote="EUR", rate=Decimal("0.9")) for c in currencies
        ],
        today=TODAY,
    )

    assert summary.fx_rows_written == 1
    rows = session.execute(select(ExchangeRate)).scalars().all()
    assert [r.base_currency for r in rows] == ["USD"]
