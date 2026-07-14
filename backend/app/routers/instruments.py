"""HTTP surface for the ``instrument`` master. Translation only — logic lives in the service."""

from collections.abc import Sequence

from fastapi import APIRouter, Query, status

from app.deps import DbSession
from app.models.enums import AssetClass
from app.models.instrument import Instrument
from app.routers._docs import error_responses
from app.schemas.instrument import InstrumentCreate, InstrumentRead, InstrumentUpdate
from app.services import instruments as service

router = APIRouter(prefix="/instruments", tags=["instruments"])

# A module-level singleton, per ruff B008: enum-typed Query() defaults aren't
# recognized as side-effect-free the way plain int/bool/str ones are.
_ASSET_CLASS_FILTER = Query(default=None, description="Filter by valuation dispatch key.")


@router.post(
    "",
    response_model=InstrumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an instrument",
    responses=error_responses(
        (404, "category_id was given but no such category exists."),
        (
            422,
            "Loan-only or pricing fields were set on a mismatched asset_class, "
            "the category is inactive, or price_source/provider_ref weren't set together.",
        ),
    ),
)
def create_instrument(payload: InstrumentCreate, db: DbSession) -> Instrument:
    return service.create(db, payload)


@router.get("", response_model=list[InstrumentRead], summary="List instruments")
def list_instruments(
    db: DbSession,
    asset_class: AssetClass | None = _ASSET_CLASS_FILTER,
    category_id: int | None = Query(default=None, description="Filter by grouping category."),
    include_inactive: bool = Query(default=False, description="Include deactivated instruments."),
) -> Sequence[Instrument]:
    """Typing the query param as the enum gets validation and OpenAPI docs for free."""
    return service.list_all(
        db,
        asset_class=asset_class,
        category_id=category_id,
        include_inactive=include_inactive,
    )


@router.get(
    "/{instrument_id}",
    response_model=InstrumentRead,
    summary="Get an instrument",
    responses=error_responses((404, "No instrument with this id.")),
)
def get_instrument(instrument_id: int, db: DbSession) -> Instrument:
    return service.get(db, instrument_id)


@router.patch(
    "/{instrument_id}",
    response_model=InstrumentRead,
    summary="Update an instrument",
    responses=error_responses(
        (404, "No instrument with this id, or category_id refers to a nonexistent category."),
        (
            422,
            "Loan-only or pricing fields were set on a mismatched asset_class, "
            "the new category is inactive, or price_source/provider_ref weren't set together.",
        ),
    ),
)
def update_instrument(instrument_id: int, payload: InstrumentUpdate, db: DbSession) -> Instrument:
    return service.update(db, instrument_id, payload)
