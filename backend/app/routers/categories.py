"""HTTP surface for the ``category`` master. Translation only — logic lives in the service."""

from collections.abc import Sequence

from fastapi import APIRouter, Query, Response, status

from app.deps import DbSession
from app.models.category import Category
from app.routers._docs import error_responses
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.services import categories as service

router = APIRouter(prefix="/categories", tags=["categories"])


@router.post(
    "",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a category",
    responses=error_responses((409, "A category with this name already exists.")),
)
def create_category(payload: CategoryCreate, db: DbSession) -> Category:
    return service.create(db, payload)


@router.get("", response_model=list[CategoryRead], summary="List categories")
def list_categories(
    db: DbSession,
    include_inactive: bool = Query(default=False, description="Include deactivated categories."),
) -> Sequence[Category]:
    return service.list_all(db, include_inactive=include_inactive)


@router.get(
    "/{category_id}",
    response_model=CategoryRead,
    summary="Get a category",
    responses=error_responses((404, "No category with this id.")),
)
def get_category(category_id: int, db: DbSession) -> Category:
    return service.get(db, category_id)


@router.patch(
    "/{category_id}",
    response_model=CategoryRead,
    summary="Rename, redescribe, or (de)activate a category",
    responses=error_responses(
        (404, "No category with this id."),
        (409, "The new name collides with another category."),
    ),
)
def update_category(category_id: int, payload: CategoryUpdate, db: DbSession) -> Category:
    return service.update(db, category_id, payload)


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a category",
    responses=error_responses(
        (404, "No category with this id."),
        (409, "The category is already inactive."),
    ),
)
def deactivate_category(category_id: int, db: DbSession) -> Response:
    """Soft-delete: the row survives and instruments keep pointing at it."""
    service.deactivate(db, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
