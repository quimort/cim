"""Cash balance derivation: the ledger summed per account and currency.

There is no balance column anywhere — a balance is the fold of every movement's
cash effect. A ``purchase``/``sale`` carries an implicit cash leg (the money
that paid for, or came from, the trade), so the user records one row, not two.
Transfers move cash only when they transfer cash (``instrument_id`` NULL); an
instrument transfer changes where a holding lives, not how much cash exists.

Balances are keyed by ``(account_id, movement.currency)``: a movement's
currency may differ from its account's, so an account can hold sub-balances.
"""

from collections import defaultdict
from collections.abc import Callable
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.enums import MovementType
from app.models.movement import Movement
from app.services.errors import DomainRuleError
from app.services.valuation import _ledger
from app.services.valuation.types import CashBalance

_ZERO = Decimal(0)


def _fee(movement: Movement) -> Decimal:
    return movement.fee if movement.fee is not None else _ZERO


def _trade_total(movement: Movement) -> Decimal:
    if movement.price is None:  # guarded by the schema; keeps mypy honest
        raise DomainRuleError(f"{movement.type} movement {movement.id} has no price")
    return movement.quantity * movement.price


# The cash leg of each movement type, as a signed delta. Quantity is always a
# positive magnitude; direction lives here. This is the single source of truth
# the tests and (later) the docs point at.
_CASH_EFFECT: dict[MovementType, Callable[[Movement], Decimal]] = {
    MovementType.PURCHASE: lambda m: -(_trade_total(m) + _fee(m)),
    MovementType.SALE: lambda m: _trade_total(m) - _fee(m),
    MovementType.DIVIDEND: lambda m: m.quantity - _fee(m),
    MovementType.INTEREST: lambda m: m.quantity - _fee(m),
    MovementType.FEE: lambda m: -m.quantity,
    MovementType.DEPOSIT: lambda m: m.quantity - _fee(m),
    MovementType.WITHDRAWAL: lambda m: -(m.quantity + _fee(m)),
    # Cash moves only on cash transfers; instrument transfers relocate a
    # holding without creating or destroying cash.
    MovementType.TRANSFER_OUT: lambda m: -m.quantity if m.instrument_id is None else _ZERO,
    MovementType.TRANSFER_IN: lambda m: m.quantity if m.instrument_id is None else _ZERO,
    MovementType.PRINCIPAL_REPAYMENT: lambda m: m.quantity - _fee(m),
}


def cash_balances(
    db: Session,
    owner_id: int,
    *,
    as_of: date | None = None,
    account_id: int | None = None,
) -> list[CashBalance]:
    """Every ``(account, currency)`` cash balance of an owner at ``as_of``.

    Zero balances are included so a drained account still shows up; filtering
    is a presentation decision.
    """
    as_of = as_of if as_of is not None else _ledger.today_utc()
    stmt = _ledger.owned_movements_stmt(owner_id, until=as_of, account_id=account_id)

    balances: defaultdict[tuple[int, str], Decimal] = defaultdict(lambda: _ZERO)
    for movement in db.execute(stmt).scalars():
        effect = _CASH_EFFECT[MovementType(movement.type)]
        balances[(movement.account_id, movement.currency)] += effect(movement)

    return [
        CashBalance(account_id=acct, currency=currency, balance=balance)
        for (acct, currency), balance in sorted(balances.items())
    ]
