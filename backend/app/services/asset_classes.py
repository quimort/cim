"""Read-only access to the ``asset_class`` reference table.

No create/update/delete: the codes are the valuation dispatch key, so the set of
them is a code-level decision shipped as migrations. See
:mod:`app.models.asset_class`.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset_class import AssetClassRef
from app.services.errors import NotFoundError


def list_all(db: Session) -> Sequence[AssetClassRef]:
    stmt = select(AssetClassRef).order_by(AssetClassRef.sort_order)
    return db.execute(stmt).scalars().all()


def get(db: Session, code: str) -> AssetClassRef:
    asset_class = db.get(AssetClassRef, code)
    if asset_class is None:
        raise NotFoundError(f"asset class '{code}' not found")
    return asset_class
