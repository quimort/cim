"""Positions enriched with market price — the ``GET /positions`` payload.

``fifo.positions`` returns the bare FIFO state (quantity, cost basis, realized
P&L); this wraps it with the instrument's name and, for open positions, a
market valuation. Closed positions carry no market exposure, so they get no
price lookup — a missing quote for an instrument nobody holds anymore must not
break the endpoint.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.instrument import Instrument
from app.services.valuation import _ledger, fifo, fx, prices
from app.services.valuation.types import ValuedPosition

_ZERO = Decimal(0)


def valued_positions(
    db: Session, owner_id: int, *, as_of: date | None = None, include_closed: bool = False
) -> list[ValuedPosition]:
    """Every tradable position of an owner at ``as_of``, valued at market price.

    Closed positions (quantity zero) are omitted unless ``include_closed`` —
    they still carry realized P&L but no market value.
    """
    as_of = as_of if as_of is not None else _ledger.today_utc()
    result = []
    for pos in fifo.positions(db, owner_id, as_of=as_of):
        if pos.quantity == _ZERO and not include_closed:
            continue
        instrument = db.get(Instrument, pos.instrument_id)
        assert instrument is not None  # FK guarantees it
        if pos.quantity == _ZERO:
            market_value = unrealized_pnl = value_eur = None
        else:
            quote = prices.latest_price(db, pos.instrument_id, as_of)
            market_value = pos.quantity * quote.value
            unrealized_pnl = market_value - pos.cost_basis
            value_eur = fx.convert_to_eur(db, market_value, quote.currency, as_of)
        result.append(
            ValuedPosition(
                instrument_id=pos.instrument_id,
                instrument_name=instrument.name,
                quantity=pos.quantity,
                cost_basis=pos.cost_basis,
                realized_pnl=pos.realized_pnl,
                currency=pos.currency,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                value_eur=value_eur,
            )
        )
    return result
