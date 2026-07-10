"""Value objects returned by the valuation services.

Frozen dataclasses, not Pydantic: services stay transport-agnostic, and the
derived endpoints (task 1e) wrap these in response schemas with money-as-string
serialization. Every amount is a ``Decimal`` in its **native currency** unless
the field name says ``eur``; nothing here is ever persisted — positions and net
worth are always derived from the ledger on demand.

No rounding or quantization happens in this layer: values carry full precision
and presentation decides how to display them.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Lot:
    """An open FIFO lot: what remains of one purchase.

    ``cost`` is the remaining total acquisition cost of the remaining quantity
    (purchase fee capitalized), not a unit price.
    """

    quantity: Decimal
    cost: Decimal


@dataclass(frozen=True, slots=True)
class TradablePosition:
    """FIFO state of one instrument for one owner, aggregated across accounts.

    Kept even when ``quantity`` is zero: a closed position still carries its
    realized P&L. Filtering is a presentation decision (task 1e).
    """

    instrument_id: int
    quantity: Decimal
    cost_basis: Decimal
    realized_pnl: Decimal
    currency: str
    lots: tuple[Lot, ...]


@dataclass(frozen=True, slots=True)
class CashBalance:
    """Derived cash in one account for one currency.

    A movement's currency may differ from its account's, so an account can hold
    several currency sub-balances.
    """

    account_id: int
    currency: str
    balance: Decimal


@dataclass(frozen=True, slots=True)
class LoanValuation:
    """Outstanding principal plus interest accrued but not yet received."""

    instrument_id: int
    outstanding_principal: Decimal
    accrued_interest: Decimal
    currency: str

    @property
    def value(self) -> Decimal:
        return self.outstanding_principal + self.accrued_interest


@dataclass(frozen=True, slots=True)
class AssetValuation:
    """One line of a net-worth report, whatever the asset class.

    Exactly one of ``instrument_id`` / ``account_id`` is set for tradables and
    loans vs cash. ``quantity`` / ``cost_basis`` / ``unrealized_pnl`` are only
    meaningful for tradables and are ``None`` elsewhere.
    """

    asset_class: str
    instrument_id: int | None
    account_id: int | None
    native_value: Decimal
    native_currency: str
    value_eur: Decimal
    quantity: Decimal | None = None
    cost_basis: Decimal | None = None
    unrealized_pnl: Decimal | None = None


@dataclass(frozen=True, slots=True)
class NetWorthReport:
    as_of: date
    total_eur: Decimal
    items: tuple[AssetValuation, ...]
