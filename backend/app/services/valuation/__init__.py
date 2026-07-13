"""Valuation services — everything derived from the ledger, nothing stored.

Public API for the derived endpoints (task 1e) and phase-2 services:

    from app.services import valuation

    valuation.positions(db, owner_id, as_of=...)
    valuation.cash_balances(db, owner_id, as_of=...)
    valuation.value_loan(db, owner_id, instrument, as_of=...)
    valuation.net_worth(db, owner_id, as_of=...)
    valuation.valued_positions(db, owner_id, as_of=...)
    valuation.net_worth_series(db, owner_id, start=..., end=..., interval=...)
    valuation.allocation(db, owner_id, dimension=..., as_of=...)
"""

from app.services.valuation.allocation import Dimension, allocation
from app.services.valuation.cash import cash_balances
from app.services.valuation.fifo import apply_fifo, position, positions
from app.services.valuation.fx import convert_to_eur, rate_to_eur
from app.services.valuation.loans import value_loan
from app.services.valuation.net_worth import VALUERS, net_worth
from app.services.valuation.prices import latest_price
from app.services.valuation.series import Interval, net_worth_series
from app.services.valuation.types import (
    AllocationBucket,
    AllocationReport,
    AssetValuation,
    CashBalance,
    LoanValuation,
    Lot,
    NetWorthPoint,
    NetWorthReport,
    NetWorthSeries,
    TradablePosition,
    ValuedPosition,
)
from app.services.valuation.valued_positions import valued_positions

__all__ = [
    "VALUERS",
    "AllocationBucket",
    "AllocationReport",
    "AssetValuation",
    "CashBalance",
    "Dimension",
    "Interval",
    "LoanValuation",
    "Lot",
    "NetWorthPoint",
    "NetWorthReport",
    "NetWorthSeries",
    "TradablePosition",
    "ValuedPosition",
    "allocation",
    "apply_fifo",
    "cash_balances",
    "convert_to_eur",
    "latest_price",
    "net_worth",
    "net_worth_series",
    "position",
    "positions",
    "rate_to_eur",
    "value_loan",
    "valued_positions",
]
