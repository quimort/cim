"""HTTP surface for the ``asset_class`` reference table.

Only GET is declared, so POST/PATCH/DELETE answer 405 for free. That is the
point: an asset class is the valuation dispatch key, and a new one needs a
valuation strategy in Python, not a row inserted over HTTP.
"""

from collections.abc import Sequence

from fastapi import APIRouter

from app.deps import DbSession
from app.models.asset_class import AssetClassRef
from app.routers._docs import error_responses
from app.schemas.asset_class import AssetClassRead
from app.services import asset_classes as service

router = APIRouter(prefix="/asset-classes", tags=["asset-classes"])


@router.get(
    "",
    response_model=list[AssetClassRead],
    summary="List the seeded asset classes",
    response_description="The asset classes, ordered for display.",
)
def list_asset_classes(db: DbSession) -> Sequence[AssetClassRef]:
    return service.list_all(db)


@router.get(
    "/{code}",
    response_model=AssetClassRead,
    summary="Get one asset class",
    responses=error_responses((404, "No asset class with this code.")),
)
def get_asset_class(code: str, db: DbSession) -> AssetClassRef:
    return service.get(db, code)
