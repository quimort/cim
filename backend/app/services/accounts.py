"""Domain logic for the ``account`` master.

Every function takes an ``owner_id`` and filters on it. There is no unscoped
read path here, deliberately: the single-user phase must not leave behind a
query that would need undoing to support a second user.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.account import Account
from app.schemas.account import AccountCreate, AccountUpdate
from app.services.errors import ConflictError, NotFoundError


def create(db: Session, owner_id: int, payload: AccountCreate) -> Account:
    account = Account(**payload.model_dump(), owner_id=owner_id)
    db.add(account)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(f"an account named '{payload.name}' already exists") from exc
    db.refresh(account)
    return account


def list_all(db: Session, owner_id: int, *, include_inactive: bool = False) -> Sequence[Account]:
    stmt = select(Account).where(Account.owner_id == owner_id)
    if not include_inactive:
        stmt = stmt.where(Account.is_active.is_(True))
    return db.execute(stmt.order_by(Account.name)).scalars().all()


def get(db: Session, owner_id: int, account_id: int) -> Account:
    """Fetch one owned account, or raise ``NotFoundError``.

    Also the ownership gate the movements service leans on: routing every
    account lookup through here means a movement can never be attached to
    somebody else's account.
    """
    stmt = select(Account).where(Account.id == account_id, Account.owner_id == owner_id)
    account = db.execute(stmt).scalar_one_or_none()
    if account is None:
        raise NotFoundError(f"account {account_id} not found")
    return account


def update(db: Session, owner_id: int, account_id: int, payload: AccountUpdate) -> Account:
    account = get(db, owner_id, account_id)
    # exclude_unset: an omitted field is left untouched, rather than nulled.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(f"an account named '{payload.name}' already exists") from exc
    db.refresh(account)
    return account
