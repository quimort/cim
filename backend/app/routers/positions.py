"""HTTP surface for derived tradable positions.

Read-only: no POST/PUT/DELETE here, ever — a position is never entered
directly, it is replayed from the ``movement`` ledger on every request.
"""

from datetime import date

from fastapi import APIRouter, Query

from app.deps import CurrentOwnerId, DbSession
from app.routers._docs import error_responses
from app.schemas.valuation import PositionRead
from app.services import valuation

router = APIRouter(prefix="/positions", tags=["positions"])

_AS_OF_FILTER = Query(
    default=None, alias="date", description="Value as of this date. Defaults to today."
)
_INCLUDE_CLOSED_FILTER = Query(
    default=False, description="Include closed (zero-quantity) positions."
)


@router.get(
    "",
    response_model=list[PositionRead],
    summary="List current tradable positions",
    responses=error_responses(
        (422, "A held instrument has no price on or before the requested date."),
    ),
)
def list_positions(
    db: DbSession,
    owner_id: CurrentOwnerId,
    as_of: date | None = _AS_OF_FILTER,
    include_closed: bool = _INCLUDE_CLOSED_FILTER,
) -> list[valuation.ValuedPosition]:
    return valuation.valued_positions(db, owner_id, as_of=as_of, include_closed=include_closed)
