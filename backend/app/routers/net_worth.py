"""HTTP surface for net worth: a snapshot and a time series.

Both are pure replays of the ledger — nothing here is ever written.
"""

from datetime import date

from fastapi import APIRouter, Query

from app.deps import CurrentOwnerId, DbSession
from app.routers._docs import error_responses
from app.schemas.valuation import NetWorthRead, NetWorthSeriesRead
from app.services import valuation
from app.services.valuation.series import Interval

router = APIRouter(prefix="/net-worth", tags=["net-worth"])

_AS_OF_FILTER = Query(
    default=None, alias="date", description="Value as of this date. Defaults to today."
)
_FROM_FILTER = Query(
    default=None, alias="from", description="First point. Defaults to the first ever movement."
)
_TO_FILTER = Query(default=None, alias="to", description="Last point. Defaults to today.")
_INTERVAL_FILTER = Query(default=Interval.MONTH, description="Step between points.")

_VALUATION_ERROR = (
    422,
    "A held asset has no price, or a currency has no exchange rate, for the requested date.",
)


@router.get(
    "",
    response_model=NetWorthRead,
    summary="Total net worth in EUR",
    responses=error_responses(_VALUATION_ERROR),
)
def get_net_worth(
    db: DbSession, owner_id: CurrentOwnerId, as_of: date | None = _AS_OF_FILTER
) -> valuation.NetWorthReport:
    return valuation.net_worth(db, owner_id, as_of=as_of)


@router.get(
    "/series",
    response_model=NetWorthSeriesRead,
    summary="Net worth over time, for charts",
    responses=error_responses(
        (
            422,
            "A held asset has no price or exchange rate for some point in range, "
            "from is after to, or the range would produce too many points.",
        ),
    ),
)
def get_net_worth_series(
    db: DbSession,
    owner_id: CurrentOwnerId,
    from_: date | None = _FROM_FILTER,
    to: date | None = _TO_FILTER,
    interval: Interval = _INTERVAL_FILTER,
) -> valuation.NetWorthSeries:
    return valuation.net_worth_series(db, owner_id, start=from_, end=to, interval=interval)
