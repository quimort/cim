"""HTTP surface for portfolio allocation breakdowns.

Read-only, like every other derived endpoint: a breakdown is a regrouping of
``net_worth()``'s numbers, never a stored figure.
"""

from datetime import date

from fastapi import APIRouter, Query

from app.deps import CurrentOwnerId, DbSession
from app.routers._docs import error_responses
from app.schemas.valuation import AllocationRead
from app.services import valuation
from app.services.valuation.allocation import Dimension

router = APIRouter(prefix="/allocation", tags=["allocation"])

_AS_OF_FILTER = Query(
    default=None, alias="date", description="Value as of this date. Defaults to today."
)
_DIMENSION_FILTER = Query(
    default=Dimension.ASSET_CLASS, alias="by", description="How to group net worth."
)


@router.get(
    "",
    response_model=AllocationRead,
    summary="Net worth broken down by one dimension",
    responses=error_responses(
        (422, "A held asset has no price, or a currency has no exchange rate, on this date."),
    ),
)
def get_allocation(
    db: DbSession,
    owner_id: CurrentOwnerId,
    by: Dimension = _DIMENSION_FILTER,
    as_of: date | None = _AS_OF_FILTER,
) -> valuation.AllocationReport:
    return valuation.allocation(db, owner_id, dimension=by, as_of=as_of)
