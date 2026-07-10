"""Domain logic for the ``category`` master — the user-managed grouping axis.

A global catalog, like ``instrument``: ownership anchors on ``account.owner_id``
and a category is a description, not a holding. So no owner filter here.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services.errors import ConflictError, NotFoundError


def create(db: Session, payload: CategoryCreate) -> Category:
    category = Category(**payload.model_dump())
    db.add(category)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(f"a category named '{payload.name}' already exists") from exc
    db.refresh(category)
    return category


def list_all(db: Session, *, include_inactive: bool = False) -> Sequence[Category]:
    stmt = select(Category)
    if not include_inactive:
        stmt = stmt.where(Category.is_active.is_(True))
    return db.execute(stmt.order_by(Category.name)).scalars().all()


def get(db: Session, category_id: int) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise NotFoundError(f"category {category_id} not found")
    return category


def update(db: Session, category_id: int, payload: CategoryUpdate) -> Category:
    category = get(db, category_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(f"a category named '{payload.name}' already exists") from exc
    db.refresh(category)
    return category


def deactivate(db: Session, category_id: int) -> None:
    """Soft-delete. Instruments referencing this category are left untouched.

    A hard delete would orphan them and break historical allocation reports; the
    category simply stops appearing in pickers.
    """
    category = get(db, category_id)
    if not category.is_active:
        raise ConflictError(f"category {category_id} is already inactive")
    category.is_active = False
    db.commit()
