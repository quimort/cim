"""FIFO cost basis for tradable instruments.

Positions are never stored: they are replayed from the ledger every time. The
replay itself (``apply_fifo``) is a pure function over pre-sorted movements so
it can be tested with hand-built rows and reused by any caller that already
holds the slice of ledger it cares about.

Scope: one position per ``(owner, instrument)``, aggregated across accounts.
Instrument transfers between own accounts are therefore position-neutral and
do not appear here at all — only ``purchase`` and ``sale`` touch a position.
Purchase fees are capitalized into the lot; sale fees reduce proceeds.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.enums import AssetClass, MovementType
from app.models.instrument import Instrument
from app.models.movement import Movement
from app.services.errors import DomainRuleError, NotFoundError
from app.services.valuation import _ledger
from app.services.valuation.types import Lot, TradablePosition

_ZERO = Decimal(0)

_POSITION_TYPES = (MovementType.PURCHASE, MovementType.SALE)


class _OpenLot:
    """Mutable lot used during replay; frozen into ``Lot`` at the end."""

    __slots__ = ("quantity", "cost")

    def __init__(self, quantity: Decimal, cost: Decimal) -> None:
        self.quantity = quantity
        self.cost = cost


def apply_fifo(events: Iterable[Movement]) -> tuple[list[Lot], Decimal]:
    """Replay purchases and sales of ONE instrument, in ledger order.

    Returns the open lots and the realized P&L. ``events`` must already be
    sorted ``(occurred_at, id)`` ascending and contain only ``purchase`` /
    ``sale`` rows of a single instrument — ``owned_movements_stmt`` produces
    exactly that.
    """
    lots: list[_OpenLot] = []
    realized = _ZERO

    for movement in events:
        fee = movement.fee if movement.fee is not None else _ZERO
        if movement.type == MovementType.PURCHASE:
            if movement.price is None:  # guarded by the schema; keeps mypy honest
                raise DomainRuleError(f"purchase movement {movement.id} has no price")
            lots.append(_OpenLot(movement.quantity, movement.quantity * movement.price + fee))
        elif movement.type == MovementType.SALE:
            if movement.price is None:
                raise DomainRuleError(f"sale movement {movement.id} has no price")
            proceeds = movement.quantity * movement.price - fee
            consumed_cost = _consume(lots, movement)
            realized += proceeds - consumed_cost
        else:
            raise DomainRuleError(
                f"movement type '{movement.type}' has no FIFO effect; "
                "apply_fifo expects purchases and sales only"
            )

    return [Lot(quantity=lot.quantity, cost=lot.cost) for lot in lots], realized


def _consume(lots: list[_OpenLot], sale: Movement) -> Decimal:
    """Eat lots front-to-back for one sale; return the cost basis consumed.

    The consumed cost of a partially-eaten lot is proportional, and it is
    *subtracted* from the lot's remaining cost (rather than recomputing the
    residual) so the lot's total cost never drifts from rounding.
    """
    to_consume = sale.quantity
    consumed_cost = _ZERO
    while to_consume > _ZERO and lots:
        lot = lots[0]
        if lot.quantity <= to_consume:
            consumed_cost += lot.cost
            to_consume -= lot.quantity
            lots.pop(0)
        else:
            part = lot.cost * to_consume / lot.quantity
            consumed_cost += part
            lot.quantity -= to_consume
            lot.cost -= part
            to_consume = _ZERO
    if to_consume > _ZERO:
        raise DomainRuleError(
            f"sale of {sale.quantity} exceeds held quantity by {to_consume} "
            f"for instrument {sale.instrument_id} as of {sale.occurred_at.date()}"
        )
    return consumed_cost


def position(
    db: Session, owner_id: int, instrument_id: int, *, as_of: date | None = None
) -> TradablePosition:
    """The FIFO position of one tradable instrument at ``as_of``."""
    as_of = as_of if as_of is not None else _ledger.today_utc()
    instrument = db.get(Instrument, instrument_id)
    if instrument is None:
        raise NotFoundError(f"instrument {instrument_id} not found")
    if instrument.asset_class != AssetClass.TRADABLE:
        raise DomainRuleError(
            f"instrument {instrument_id} is '{instrument.asset_class}', not tradable; "
            "FIFO positions only apply to tradables"
        )
    stmt = _ledger.owned_movements_stmt(
        owner_id, until=as_of, instrument_id=instrument_id, types=_POSITION_TYPES
    )
    events = db.execute(stmt).scalars().all()
    return _build_position(instrument, events)


def positions(db: Session, owner_id: int, *, as_of: date | None = None) -> list[TradablePosition]:
    """All tradable positions of an owner at ``as_of``, ordered by instrument id.

    Closed positions (quantity zero) are included — they still carry realized
    P&L; whether to show them is the caller's decision.
    """
    as_of = as_of if as_of is not None else _ledger.today_utc()
    stmt = (
        _ledger.owned_movements_stmt(owner_id, until=as_of, types=_POSITION_TYPES)
        .join(Instrument, Movement.instrument_id == Instrument.id)
        .where(Instrument.asset_class == AssetClass.TRADABLE.value)
    )
    by_instrument: defaultdict[int, list[Movement]] = defaultdict(list)
    for movement in db.execute(stmt).scalars():
        assert movement.instrument_id is not None  # required by type for purchase/sale
        by_instrument[movement.instrument_id].append(movement)

    result = []
    for instrument_id in sorted(by_instrument):
        instrument = db.get(Instrument, instrument_id)
        assert instrument is not None  # FK guarantees it
        result.append(_build_position(instrument, by_instrument[instrument_id]))
    return result


def _build_position(instrument: Instrument, events: Sequence[Movement]) -> TradablePosition:
    lots, realized = apply_fifo(events)
    return TradablePosition(
        instrument_id=instrument.id,
        quantity=sum((lot.quantity for lot in lots), _ZERO),
        cost_basis=sum((lot.cost for lot in lots), _ZERO),
        realized_pnl=realized,
        currency=instrument.currency,
        lots=tuple(lots),
    )
