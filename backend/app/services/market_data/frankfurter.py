"""FX rates from the Frankfurter API (ECB reference rates, EUR base, keyless).

https://api.frankfurter.dev/v1/{start}..{end}?symbols=USD,GBP,... returns, for
each business day in the window, "1 EUR = X <currency>". ``fx.py``'s module
docstring documents the convention the batch script must write: a row
``(base, quote=EUR, rate)`` means "1 base = rate EUR" — the inverse of what
Frankfurter reports — so every rate is inverted once here, at ingest.

ECB publishes on business days only; missing weekends are fine, since
``rate_to_eur`` looks up the latest rate on or before the as-of date.
"""

import json
from datetime import date
from decimal import Decimal

import httpx

from app.services.market_data.types import FxRate, quantize_rate

_BASE_URL = "https://api.frankfurter.dev/v1"


def fetch_fx_rates(
    client: httpx.Client, currencies: set[str], start: date, end: date
) -> list[FxRate]:
    """EUR-based rates for ``currencies`` over ``[start, end]``, in the direct convention."""
    if not currencies:
        return []

    url = f"{_BASE_URL}/{start.isoformat()}..{end.isoformat()}"
    response = client.get(url, params={"symbols": ",".join(sorted(currencies))})
    response.raise_for_status()
    # parse_float=Decimal: the ECB rate never touches a Python float.
    payload = json.loads(response.text, parse_float=Decimal)

    rates: list[FxRate] = []
    for day_str, day_rates in payload["rates"].items():
        day = date.fromisoformat(day_str)
        for currency, eur_to_currency in day_rates.items():
            rates.append(
                FxRate(
                    day=day,
                    base=currency,
                    quote="EUR",
                    rate=quantize_rate(Decimal(1) / eur_to_currency),
                )
            )
    return rates
