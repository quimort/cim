"""Value objects and shared constants for the price/FX batch (task 1f).

Frozen dataclasses, not Pydantic: this package is transport-agnostic and never
runs inside the API process. Quantization happens once, at ingest, to the
exact scale of the column each value lands in — ``price.value`` is
``Numeric(20, 8)``, ``exchange_rate.rate`` is ``Numeric(20, 10)``.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

PRICE_SCALE = Decimal("1E-8")
FX_SCALE = Decimal("1E-10")
ROUNDING = ROUND_HALF_EVEN


def quantize_price(value: Decimal) -> Decimal:
    return value.quantize(PRICE_SCALE, rounding=ROUNDING)


def quantize_rate(value: Decimal) -> Decimal:
    return value.quantize(FX_SCALE, rounding=ROUNDING)


@dataclass(frozen=True, slots=True)
class Quote:
    """One day's closing price for an instrument, in its native currency."""

    day: date
    value: Decimal


@dataclass(frozen=True, slots=True)
class FxRate:
    """One day's rate for a currency pair: 1 ``base`` = ``rate`` ``quote``."""

    day: date
    base: str
    quote: str
    rate: Decimal


@dataclass(slots=True)
class RunSummary:
    """Outcome of one batch run, printed by the CLI entrypoint."""

    prices_written: int = 0
    fx_rows_written: int = 0
    instruments_ok: int = 0
    instruments_skipped: int = 0
    instruments_failed: int = 0
    fx_failed: bool = False
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.instruments_failed == 0 and not self.fx_failed


# (provider_ref, currency, start, end) -> quotes for that instrument's window.
QuoteFetcher = Callable[[str, str, date, date], Sequence[Quote]]

# (currencies, start, end) -> FX rows covering that window.
FxFetcher = Callable[[set[str], date, date], Sequence[FxRate]]
