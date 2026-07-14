"""Crypto quotes via the CoinGecko public API (``instrument.price_source == "coingecko"``).

The free tier rejects ``interval=daily`` (an Enterprise-only parameter), so a
plain ``/market_chart`` call returns whatever native granularity CoinGecko
picks for the requested range (5-minute, hourly, or daily) and this module
downsamples it itself: last sample of each UTC day, filtered to the window.
``REQUEST_DELAY_SECONDS`` throttles calls to stay within the free-tier rate
limit (roughly 5-15 requests/minute).
"""

import json
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import httpx

from app.services.market_data.types import Quote, quantize_price

_BASE_URL = "https://api.coingecko.com/api/v3"
_USER_AGENT = "cim-price-batch/1.0"
REQUEST_DELAY_SECONDS = 2.5


def fetch_quotes(
    client: httpx.Client, provider_ref: str, currency: str, start: date, end: date
) -> list[Quote]:
    """Daily closes for one CoinGecko coin id over the inclusive window ``[start, end]``.

    Bind ``client`` via ``functools.partial`` before use — the runner's
    ``QuoteFetcher`` signature is ``(provider_ref, currency, start, end)``.
    """
    days = (end - start).days + 1
    time.sleep(REQUEST_DELAY_SECONDS)
    response = client.get(
        f"{_BASE_URL}/coins/{provider_ref}/market_chart",
        params={"vs_currency": currency.lower(), "days": days},
        headers={"User-Agent": _USER_AGENT},
    )
    response.raise_for_status()
    # parse_float=Decimal: the price never touches a Python float.
    payload = json.loads(response.text, parse_float=Decimal)
    return _downsample(payload["prices"], start, end)


def _downsample(points: list[list[Any]], start: date, end: date) -> list[Quote]:
    """Keep the last sample of each UTC day, within ``[start, end]``.

    Points arrive in chronological order, so later same-day samples overwrite
    earlier ones in the dict, leaving the last one.
    """
    by_day: dict[date, Decimal] = {}
    for ms_epoch, price in points:
        day = datetime.fromtimestamp(int(ms_epoch) / 1000, tz=UTC).date()
        if start <= day <= end:
            by_day[day] = price
    return [Quote(day=day, value=quantize_price(price)) for day, price in sorted(by_day.items())]
