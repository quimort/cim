"""Stock/ETF/fund quotes via yfinance (``instrument.price_source == "yfinance"``).

Per-instrument calls, not a batched ``yf.download``: one bad ticker fails
alone rather than aborting a whole batch, and yfinance is not meaningfully
rate-limited at the scale of a personal portfolio.

Investment funds (fondos) need no separate provider: Yahoo carries them as
``MUTUALFUND`` quotes under an opaque ``0P…`` symbol, whose daily ``Close`` is
the fund's NAV. ``resolve_symbol`` exists only to find that symbol from an
ISIN; the batch itself always reads a concrete ``provider_ref``, so a scheduled
run never does a lookup.
"""

import math
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import yfinance as yf

from app.services.market_data.types import Quote, quantize_price


def fetch_quotes(provider_ref: str, currency: str, start: date, end: date) -> list[Quote]:
    """Daily closes for one ticker over the inclusive window ``[start, end]``.

    ``currency`` is accepted for signature parity with ``QuoteFetcher``;
    yfinance has no such parameter (the ticker's currency is fixed).
    """
    del currency
    history = yf.Ticker(provider_ref).history(
        start=start, end=end + timedelta(days=1), auto_adjust=False
    )
    return _series_to_quotes(history.index, history["Close"])


def _series_to_quotes(index: Any, values: Any) -> list[Quote]:
    """The one place a pandas/float boundary is crossed, converting to Decimal.

    ``Decimal(str(value))`` — never ``Decimal(value)`` directly — takes the
    shortest round-trip string repr of the float instead of its exact (and
    misleading) binary value.
    """
    quotes: list[Quote] = []
    for timestamp, value in zip(index, values, strict=True):
        if math.isnan(float(value)):
            continue
        quotes.append(Quote(day=timestamp.date(), value=quantize_price(Decimal(str(value)))))
    return quotes


@dataclass(frozen=True, slots=True)
class SymbolCandidate:
    """A Yahoo symbol that might be the instrument you mean.

    ``symbol`` is what goes in ``instrument.provider_ref``; ``quote_type`` tells
    an ETF from a MUTUALFUND, and ``currency`` is the share class's currency —
    it must match ``instrument.currency`` or the EUR conversion misvalues it.
    """

    symbol: str
    quote_type: str
    exchange: str
    name: str
    currency: str | None


def resolve_symbol(query: str, *, max_results: int = 6) -> list[SymbolCandidate]:
    """Yahoo symbols matching an ISIN (or a name), for tagging an instrument.

    Interactive helper for ``scripts/resolve_symbol.py`` — never called by the
    batch. A search hit alone is not enough: for ``0P…`` fund rows Yahoo returns
    the symbol itself as ``shortname``, so the real name and the currency have
    to come from the per-symbol ``info`` payload.
    """
    quotes = yf.Search(query, max_results=max_results).quotes
    candidates: list[SymbolCandidate] = []
    for quote in quotes[:max_results]:
        symbol = quote.get("symbol")
        if not symbol:
            continue
        try:
            info = yf.Ticker(symbol).info
        except Exception:  # noqa: BLE001 - a dead symbol must not sink the others
            info = {}
        candidates.append(_candidate_from_quote(quote, info))
    return candidates


def _candidate_from_quote(quote: Any, info: Any) -> SymbolCandidate:
    """Pure mapping of the two yfinance payloads — the unit-test target."""
    symbol = str(quote.get("symbol"))
    name = info.get("longName") or info.get("shortName") or quote.get("shortname") or symbol
    return SymbolCandidate(
        symbol=symbol,
        quote_type=str(info.get("quoteType") or quote.get("quoteType") or "UNKNOWN"),
        exchange=str(info.get("exchange") or quote.get("exchange") or ""),
        name=str(name),
        currency=str(info["currency"]) if info.get("currency") else None,
    )
