"""Net worth: every asset valued by its class's strategy, consolidated to EUR.

``asset_class`` is the dispatch key: each code in the (closed) reference table
maps to exactly one strategy below — FIFO x market price for ``tradable``,
ledger fold for ``cash``, principal + accrued interest for ``loan``. Adding an
asset class means writing a strategy here, which is why the class set ships as
a migration and never as a POST. Tests assert ``VALUERS`` covers the enum.

Nothing is stored: asking for a past date replays the ledger up to that date.
"""

from collections.abc import Callable
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.enums import AssetClass
from app.models.instrument import Instrument
from app.models.movement import Movement
from app.services.valuation import _ledger, cash, fifo, fx, loans, prices
from app.services.valuation.types import AssetValuation, NetWorthReport

_ZERO = Decimal(0)

Valuer = Callable[[Session, int, date], list[AssetValuation]]


def _value_tradables(db: Session, owner_id: int, as_of: date) -> list[AssetValuation]:
    """Open positions at market price. Closed positions hold no value: skipped."""
    items = []
    for position in fifo.positions(db, owner_id, as_of=as_of):
        if position.quantity == _ZERO:
            continue
        quote = prices.latest_price(db, position.instrument_id, as_of)
        native_value = position.quantity * quote.value
        items.append(
            AssetValuation(
                asset_class=AssetClass.TRADABLE.value,
                instrument_id=position.instrument_id,
                account_id=None,
                native_value=native_value,
                native_currency=quote.currency,
                value_eur=fx.convert_to_eur(db, native_value, quote.currency, as_of),
                quantity=position.quantity,
                cost_basis=position.cost_basis,
                # Assumes the quote currency matches the purchase currency —
                # true by construction in phase 1 (both come from the instrument).
                unrealized_pnl=native_value - position.cost_basis,
            )
        )
    return items


def _value_cash(db: Session, owner_id: int, as_of: date) -> list[AssetValuation]:
    return [
        AssetValuation(
            asset_class=AssetClass.CASH.value,
            instrument_id=None,
            account_id=balance.account_id,
            native_value=balance.balance,
            native_currency=balance.currency,
            value_eur=fx.convert_to_eur(db, balance.balance, balance.currency, as_of),
        )
        for balance in cash.cash_balances(db, owner_id, as_of=as_of)
    ]


def _value_loans(db: Session, owner_id: int, as_of: date) -> list[AssetValuation]:
    """Every loan instrument the owner's ledger has ever touched, valued."""
    stmt = (
        select(Instrument)
        .join(Movement, Movement.instrument_id == Instrument.id)
        .join(Account, Movement.account_id == Account.id)
        .where(
            Account.owner_id == owner_id,
            Movement.voided_at.is_(None),
            Movement.occurred_at < _ledger.as_of_cutoff(as_of),
            Instrument.asset_class == AssetClass.LOAN.value,
        )
        .distinct()
        .order_by(Instrument.id)
    )
    items = []
    for instrument in db.execute(stmt).scalars():
        valuation = loans.value_loan(db, owner_id, instrument, as_of=as_of)
        items.append(
            AssetValuation(
                asset_class=AssetClass.LOAN.value,
                instrument_id=instrument.id,
                account_id=None,
                native_value=valuation.value,
                native_currency=valuation.currency,
                value_eur=fx.convert_to_eur(db, valuation.value, valuation.currency, as_of),
            )
        )
    return items


# The closed dispatch table — one strategy per asset class, no default case.
# tests/test_valuation_net_worth.py asserts this covers the whole enum.
VALUERS: dict[AssetClass, Valuer] = {
    AssetClass.TRADABLE: _value_tradables,
    AssetClass.CASH: _value_cash,
    AssetClass.LOAN: _value_loans,
}


def net_worth(db: Session, owner_id: int, *, as_of: date | None = None) -> NetWorthReport:
    """Total net worth in EUR at ``as_of`` (default: today, UTC)."""
    as_of = as_of if as_of is not None else _ledger.today_utc()
    items: list[AssetValuation] = []
    for asset_class in AssetClass:
        items.extend(VALUERS[asset_class](db, owner_id, as_of))
    return NetWorthReport(
        as_of=as_of,
        total_eur=sum((item.value_eur for item in items), _ZERO),
        items=tuple(items),
    )
