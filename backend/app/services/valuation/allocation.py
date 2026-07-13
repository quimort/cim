"""Portfolio allocation — net worth broken down along one dimension.

Three dimensions (``asset_class``, ``category``, ``currency``) simply regroup
the same ``AssetValuation`` rows ``net_worth()`` already produces: no new
ledger replay needed. The fourth, ``account``, does need one: cash is already
keyed by account (``cash.cash_balances``), but tradables and loans are
aggregated *across* accounts by design (see ``fifo.py`` and ``loans.py``), so
attributing them per account means folding the ledger a second time, this
time grouped by account rather than by owner. Every dimension's buckets sum
to exactly the same total as ``net_worth()`` — tested.
"""

from collections import defaultdict
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.asset_class import AssetClassRef
from app.models.category import Category
from app.models.enums import AssetClass, MovementType
from app.models.instrument import Instrument
from app.models.movement import Movement
from app.services.errors import DomainRuleError
from app.services.valuation import _ledger, cash, fx, loans, prices
from app.services.valuation.net_worth import net_worth
from app.services.valuation.types import AllocationBucket, AllocationReport, NetWorthReport

_ZERO = Decimal(0)

_TRADABLE_ACCOUNT_TYPES = (
    MovementType.PURCHASE,
    MovementType.SALE,
    MovementType.TRANSFER_OUT,
    MovementType.TRANSFER_IN,
)
_TRADABLE_DELTA: dict[MovementType, Callable[[Movement], Decimal]] = {
    MovementType.PURCHASE: lambda m: m.quantity,
    MovementType.SALE: lambda m: -m.quantity,
    MovementType.TRANSFER_OUT: lambda m: -m.quantity,
    MovementType.TRANSFER_IN: lambda m: m.quantity,
}

_LOAN_ACCOUNT_TYPES = (MovementType.PURCHASE, MovementType.PRINCIPAL_REPAYMENT)


class Dimension(StrEnum):
    ASSET_CLASS = "asset_class"
    CATEGORY = "category"
    CURRENCY = "currency"
    ACCOUNT = "account"


def allocation(
    db: Session, owner_id: int, *, dimension: Dimension, as_of: date | None = None
) -> AllocationReport:
    """Net worth grouped by ``dimension`` at ``as_of``."""
    as_of = as_of if as_of is not None else _ledger.today_utc()

    if dimension is Dimension.ACCOUNT:
        return _allocation_by_account(db, owner_id, as_of)

    report = net_worth(db, owner_id, as_of=as_of)
    if dimension is Dimension.ASSET_CLASS:
        totals, labels = _group_by_asset_class(db, report)
    elif dimension is Dimension.CURRENCY:
        totals, labels = _group_by_currency(report)
    else:
        totals, labels = _group_by_category(db, report)
    return _build_report(as_of, dimension, report.total_eur, totals, labels)


def _group_by_asset_class(
    db: Session, report: NetWorthReport
) -> tuple[dict[str | None, Decimal], dict[str | None, str]]:
    labels: dict[str | None, str] = {
        row.code: row.label for row in db.execute(select(AssetClassRef)).scalars()
    }
    totals: defaultdict[str | None, Decimal] = defaultdict(lambda: _ZERO)
    for item in report.items:
        totals[item.asset_class] += item.value_eur
    return dict(totals), labels


def _group_by_currency(
    report: NetWorthReport,
) -> tuple[dict[str | None, Decimal], dict[str | None, str]]:
    totals: defaultdict[str | None, Decimal] = defaultdict(lambda: _ZERO)
    for item in report.items:
        totals[item.native_currency] += item.value_eur
    return dict(totals), {currency: currency for currency in totals if currency is not None}


def _group_by_category(
    db: Session, report: NetWorthReport
) -> tuple[dict[str | None, Decimal], dict[str | None, str]]:
    instrument_ids = {
        item.instrument_id for item in report.items if item.instrument_id is not None
    }
    category_by_instrument: dict[int, int | None] = {}
    if instrument_ids:
        instrument_stmt = select(Instrument.id, Instrument.category_id).where(
            Instrument.id.in_(instrument_ids)
        )
        for instrument_id, category_id in db.execute(instrument_stmt):
            category_by_instrument[instrument_id] = category_id

    category_ids = {cid for cid in category_by_instrument.values() if cid is not None}
    labels: dict[str | None, str] = {None: "Uncategorized"}
    if category_ids:
        category_stmt = select(Category.id, Category.name).where(Category.id.in_(category_ids))
        for category_id, name in db.execute(category_stmt):
            labels[str(category_id)] = name

    totals: defaultdict[str | None, Decimal] = defaultdict(lambda: _ZERO)
    for item in report.items:
        category_id = (
            category_by_instrument.get(item.instrument_id)
            if item.instrument_id is not None
            else None
        )
        key = str(category_id) if category_id is not None else None
        totals[key] += item.value_eur
    return dict(totals), labels


def _tradable_quantities_by_account(
    db: Session, owner_id: int, as_of: date
) -> dict[int, dict[int, Decimal]]:
    """Net quantity of every tradable instrument, folded per account.

    Purchases/sales change the aggregate position; instrument transfers only
    relocate it between accounts. Summing across accounts for one instrument
    therefore reproduces exactly the aggregate FIFO quantity from ``fifo.py``.
    """
    stmt = (
        _ledger.owned_movements_stmt(owner_id, until=as_of, types=_TRADABLE_ACCOUNT_TYPES)
        .join(Instrument, Movement.instrument_id == Instrument.id)
        .where(Instrument.asset_class == AssetClass.TRADABLE.value)
    )
    result: defaultdict[int, defaultdict[int, Decimal]] = defaultdict(
        lambda: defaultdict(lambda: _ZERO)
    )
    for movement in db.execute(stmt).scalars():
        assert movement.instrument_id is not None  # guarded by the join above
        delta = _TRADABLE_DELTA[MovementType(movement.type)](movement)
        result[movement.instrument_id][movement.account_id] += delta
    return {instrument_id: dict(by_account) for instrument_id, by_account in result.items()}


def _owner_loan_instruments(db: Session, owner_id: int, as_of: date) -> list[Instrument]:
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
    return list(db.execute(stmt).scalars())


def _loan_events_by_account(
    db: Session, owner_id: int, instrument_id: int, as_of: date
) -> list[Movement]:
    stmt = _ledger.owned_movements_stmt(
        owner_id, until=as_of, instrument_id=instrument_id, types=_LOAN_ACCOUNT_TYPES
    )
    return list(db.execute(stmt).scalars())


def _loan_principal_by_account(events: list[Movement]) -> dict[int, Decimal]:
    principal: defaultdict[int, Decimal] = defaultdict(lambda: _ZERO)
    for movement in events:
        if movement.type == MovementType.PURCHASE:
            if movement.price is None:  # guarded by the schema; keeps mypy honest
                raise DomainRuleError(f"purchase movement {movement.id} has no price")
            principal[movement.account_id] += movement.quantity * movement.price
        else:  # principal_repayment
            principal[movement.account_id] -= movement.quantity
    return dict(principal)


def _allocation_by_account(db: Session, owner_id: int, as_of: date) -> AllocationReport:
    accounts = {
        account.id: account.name
        for account in db.execute(
            select(Account).where(Account.owner_id == owner_id)
        ).scalars()
    }
    totals: defaultdict[str | None, Decimal] = defaultdict(lambda: _ZERO)

    for balance in cash.cash_balances(db, owner_id, as_of=as_of):
        totals[str(balance.account_id)] += fx.convert_to_eur(
            db, balance.balance, balance.currency, as_of
        )

    for instrument_id, per_account_qty in _tradable_quantities_by_account(
        db, owner_id, as_of
    ).items():
        if all(qty == _ZERO for qty in per_account_qty.values()):
            continue
        quote = prices.latest_price(db, instrument_id, as_of)
        for account_id, qty in per_account_qty.items():
            if qty == _ZERO:
                continue
            totals[str(account_id)] += fx.convert_to_eur(
                db, qty * quote.value, quote.currency, as_of
            )

    for instrument in _owner_loan_instruments(db, owner_id, as_of):
        valuation = loans.value_loan(db, owner_id, instrument, as_of=as_of)
        value_eur = fx.convert_to_eur(db, valuation.value, valuation.currency, as_of)
        events = _loan_events_by_account(db, owner_id, instrument.id, as_of)
        per_account_principal = _loan_principal_by_account(events)
        total_principal = sum(per_account_principal.values(), _ZERO)
        if total_principal != _ZERO:
            # Weights sum to 1 across every account that touched this loan (even a
            # negative share), so the loan's full value is always fully attributed.
            for account_id, principal in per_account_principal.items():
                if principal == _ZERO:
                    continue
                totals[str(account_id)] += value_eur * principal / total_principal
        elif value_eur != _ZERO and events:
            # Principal nets to zero (fully repaid) but interest is still owed:
            # attribute it to the account of the most recent principal event.
            totals[str(events[-1].account_id)] += value_eur

    labels: dict[str | None, str] = {str(acc_id): name for acc_id, name in accounts.items()}
    total_eur = sum(totals.values(), _ZERO)
    return _build_report(as_of, Dimension.ACCOUNT, total_eur, dict(totals), labels)


def _build_report(
    as_of: date,
    dimension: Dimension,
    total_eur: Decimal,
    totals: dict[str | None, Decimal],
    labels: dict[str | None, str],
) -> AllocationReport:
    buckets = [
        AllocationBucket(
            key=key,
            label=labels.get(key, key if key is not None else "Uncategorized"),
            value_eur=value,
            weight=(value / total_eur) if total_eur != _ZERO else None,
        )
        for key, value in totals.items()
    ]
    buckets.sort(key=lambda bucket: bucket.value_eur, reverse=True)
    return AllocationReport(
        as_of=as_of, dimension=dimension.value, total_eur=total_eur, buckets=tuple(buckets)
    )
