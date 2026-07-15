"""Domain logic for the ``instrument`` master.

Instruments are a shared catalog, not owned property: ownership anchors on
``account.owner_id``, and an instrument is a description of an asset (VWCE, EUR
cash, a loan to a friend), not a holding of it. So no ``owner_id`` filter here —
holdings become owned when a ``movement`` on an owned account references them.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import AssetClass
from app.models.instrument import Instrument
from app.schemas.instrument import InstrumentCreate, InstrumentUpdate
from app.services import categories as categories_service
from app.services.errors import DomainRuleError, NotFoundError

_LOAN_ONLY_FIELDS = ("maturity_date", "expected_interest", "status")
_PRICING_FIELDS = ("price_source", "provider_ref")


def _require_active_category(db: Session, category_id: int) -> None:
    """A deactivated category may keep its existing instruments, but takes no new ones."""
    category = categories_service.get(db, category_id)
    if not category.is_active:
        raise DomainRuleError(f"category {category_id} is inactive")


def create(db: Session, payload: InstrumentCreate) -> Instrument:
    # InstrumentCreate._enforce_loan_fields already rejected loan fields on a
    # non-loan and defaulted a loan's status to active.
    if payload.category_id is not None:
        _require_active_category(db, payload.category_id)
    instrument = Instrument(**payload.model_dump())
    db.add(instrument)
    db.commit()
    db.refresh(instrument)
    return instrument


def list_all(
    db: Session,
    *,
    asset_class: AssetClass | None = None,
    category_id: int | None = None,
    include_inactive: bool = False,
) -> Sequence[Instrument]:
    stmt = select(Instrument)
    if asset_class is not None:
        stmt = stmt.where(Instrument.asset_class == asset_class.value)
    if category_id is not None:
        stmt = stmt.where(Instrument.category_id == category_id)
    if not include_inactive:
        stmt = stmt.where(Instrument.is_active.is_(True))
    return db.execute(stmt.order_by(Instrument.name)).scalars().all()


def get(db: Session, instrument_id: int) -> Instrument:
    instrument = db.get(Instrument, instrument_id)
    if instrument is None:
        raise NotFoundError(f"instrument {instrument_id} not found")
    return instrument


def update(db: Session, instrument_id: int, payload: InstrumentUpdate) -> Instrument:
    instrument = get(db, instrument_id)
    changes = payload.model_dump(exclude_unset=True)

    # The check InstrumentUpdate cannot make: it never sees the stored row, and
    # asset_class is immutable, so only here can we tell that these fields are
    # being set on something that is not a loan. Clearing them (explicit null)
    # is harmless, so only non-null values are rejected.
    if instrument.asset_class != AssetClass.LOAN.value:
        offending = [f for f in _LOAN_ONLY_FIELDS if changes.get(f) is not None]
        if offending:
            raise DomainRuleError(
                f"{', '.join(sorted(offending))} require asset_class=loan, "
                f"but instrument {instrument_id} is a {instrument.asset_class}"
            )

    # Re-categorising is allowed; moving into a dead category is not. An explicit
    # null (uncategorise) is always fine.
    if changes.get("category_id") is not None:
        _require_active_category(db, changes["category_id"])

    # Same reasoning as the loan-fields check above: only here do we see both
    # the stored asset_class and the resulting (stored + changed) pricing pair.
    if _PRICING_FIELDS[0] in changes or _PRICING_FIELDS[1] in changes:
        final_source = changes.get("price_source", instrument.price_source)
        final_ref = changes.get("provider_ref", instrument.provider_ref)
        if (final_source is None) != (final_ref is None):
            raise DomainRuleError("price_source and provider_ref must be set together")
        if final_source is not None and instrument.asset_class != AssetClass.TRADABLE.value:
            raise DomainRuleError(
                f"price_source/provider_ref require asset_class=tradable, "
                f"but instrument {instrument_id} is a {instrument.asset_class}"
            )

    for field, value in changes.items():
        setattr(instrument, field, value)
    db.commit()
    db.refresh(instrument)
    return instrument
