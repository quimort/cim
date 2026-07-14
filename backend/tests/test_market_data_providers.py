"""Provider boundary tests (task 1f): float->Decimal conversion, no float ever
reaching storage, and the FX inversion/downsampling logic — all with the
network mocked (``httpx.MockTransport``), no real API calls.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pandas as pd
import pytest

from app.services.market_data import coingecko, frankfurter, yfinance_provider
from app.services.market_data.types import FX_SCALE, ROUNDING, Quote
from app.services.market_data.yfinance_provider import (
    _candidate_from_quote,
    _series_to_quotes,
    resolve_symbol,
)

# --- yfinance: the pandas/float -> Decimal boundary ----------------------------


def test_series_to_quotes_converts_via_str_and_skips_nan() -> None:
    index = pd.DatetimeIndex(["2026-01-05", "2026-01-06", "2026-01-07"])
    values = pd.Series([10.5, float("nan"), 11.123456789])

    quotes = _series_to_quotes(index, values)

    assert quotes == [
        Quote(day=date(2026, 1, 5), value=Decimal("10.50000000")),
        Quote(day=date(2026, 1, 7), value=Decimal("11.12345679")),
    ]


# --- Frankfurter: JSON parsed as Decimal, inverted to the direct convention ----


def _mock_client(payload: object) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_fx_rates_inverts_to_direct_convention_and_quantizes() -> None:
    payload = {"rates": {"2026-01-05": {"USD": 1.1, "GBP": 0.85}}}
    client = _mock_client(payload)

    rates = frankfurter.fetch_fx_rates(client, {"USD", "GBP"}, date(2026, 1, 5), date(2026, 1, 5))

    by_base = {r.base: r for r in rates}
    assert by_base["USD"].quote == "EUR"
    assert by_base["USD"].day == date(2026, 1, 5)
    assert by_base["USD"].rate == (Decimal(1) / Decimal("1.1")).quantize(FX_SCALE, ROUNDING)
    assert by_base["GBP"].rate == (Decimal(1) / Decimal("0.85")).quantize(FX_SCALE, ROUNDING)


def test_fetch_fx_rates_with_no_currencies_makes_no_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not be called")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert frankfurter.fetch_fx_rates(client, set(), date(2026, 1, 5), date(2026, 1, 5)) == []


# --- CoinGecko: downsampling to one quote per UTC day --------------------------


def test_fetch_quotes_keeps_the_last_point_per_day_within_the_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(coingecko.time, "sleep", lambda _seconds: None)

    def epoch_ms(dt: datetime) -> int:
        return int(dt.timestamp() * 1000)

    payload = {
        "prices": [
            [epoch_ms(datetime(2026, 1, 5, 1, 0, tzinfo=UTC)), 100.0],
            [epoch_ms(datetime(2026, 1, 5, 23, 0, tzinfo=UTC)), 105.0],
            [epoch_ms(datetime(2026, 1, 6, 12, 0, tzinfo=UTC)), 110.0],
            [epoch_ms(datetime(2026, 1, 7, 12, 0, tzinfo=UTC)), 999.0],  # outside the window
        ]
    }
    client = _mock_client(payload)

    quotes = coingecko.fetch_quotes(client, "bitcoin", "eur", date(2026, 1, 5), date(2026, 1, 6))

    assert quotes == [
        Quote(day=date(2026, 1, 5), value=Decimal("105.00000000")),
        Quote(day=date(2026, 1, 6), value=Decimal("110.00000000")),
    ]


# --- resolve_symbol: ISIN -> Yahoo symbol, for tagging funds ------------------

# A real Yahoo fund row: the search hit's `shortname` is the useless symbol
# itself, so name/currency must come from `info` instead.
_FUND_HIT = {"symbol": "0P000015J7.F", "quoteType": "MUTUALFUND", "exchange": "FRA"}
_FUND_INFO = {
    "quoteType": "MUTUALFUND",
    "currency": "EUR",
    "longName": "Vanguard Global Stock Index Fund EUR Hedged Acc",
    "exchange": "FRA",
}


class _FakeSearch:
    def __init__(self, quotes: list[dict[str, object]]) -> None:
        self.quotes = quotes


def _patch_yf(
    monkeypatch: pytest.MonkeyPatch,
    quotes: list[dict[str, object]],
    info: dict[str, object] | None = None,
) -> None:
    monkeypatch.setattr(
        yfinance_provider.yf, "Search", lambda query, max_results=6: _FakeSearch(quotes)
    )
    monkeypatch.setattr(
        yfinance_provider.yf,
        "Ticker",
        lambda symbol: type("_T", (), {"info": info if info is not None else {}})(),
    )


def test_candidate_prefers_info_over_the_junk_search_shortname() -> None:
    candidate = _candidate_from_quote(_FUND_HIT, _FUND_INFO)

    assert candidate.symbol == "0P000015J7.F"
    assert candidate.quote_type == "MUTUALFUND"
    assert candidate.currency == "EUR"
    assert candidate.name == "Vanguard Global Stock Index Fund EUR Hedged Acc"


def test_candidate_falls_back_when_info_is_empty() -> None:
    candidate = _candidate_from_quote(_FUND_HIT, {})

    assert candidate.symbol == "0P000015J7.F"
    assert candidate.quote_type == "MUTUALFUND"  # from the search hit
    assert candidate.currency is None
    assert candidate.name == "0P000015J7.F"  # nothing better available


def test_resolve_symbol_maps_a_fund_isin(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_yf(monkeypatch, [_FUND_HIT], _FUND_INFO)

    candidates = resolve_symbol("IE00B03HD316")

    assert len(candidates) == 1
    assert candidates[0].symbol == "0P000015J7.F"
    assert candidates[0].currency == "EUR"


def test_resolve_symbol_returns_empty_on_no_match(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_yf(monkeypatch, [])
    assert resolve_symbol("not-a-real-isin") == []


def test_resolve_symbol_respects_max_results(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_yf(monkeypatch, [_FUND_HIT] * 5, _FUND_INFO)
    assert len(resolve_symbol("vanguard", max_results=2)) == 2


def test_resolve_symbol_skips_rows_without_a_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_yf(monkeypatch, [{"quoteType": "EQUITY"}, _FUND_HIT], _FUND_INFO)

    candidates = resolve_symbol("whatever")

    assert [c.symbol for c in candidates] == ["0P000015J7.F"]


def test_resolve_symbol_survives_a_dead_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    """A symbol whose `info` blows up must not sink the whole lookup."""

    def exploding_ticker(symbol: str) -> object:
        raise RuntimeError("yahoo says no")

    monkeypatch.setattr(
        yfinance_provider.yf, "Search", lambda query, max_results=6: _FakeSearch([_FUND_HIT])
    )
    monkeypatch.setattr(yfinance_provider.yf, "Ticker", exploding_ticker)

    candidates = resolve_symbol("IE00B03HD316")

    assert [c.symbol for c in candidates] == ["0P000015J7.F"]
    assert candidates[0].currency is None
