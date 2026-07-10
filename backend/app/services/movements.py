"""Domain logic for the ``movement`` ledger.

The ledger is append-only. There is a ``create``, there is no ``update``, and
``void`` sets the annulment flag rather than deleting a row — that flag is the
only write this module ever performs against an existing movement. Corrections
are compensating movements.

Movements carry no owner column: ownership is reached by joining through the
account, which is where it is anchored.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.enums import MovementType
from app.models.movement import Movement
from app.schemas.movement import MovementCreate, TransferCreate
from app.services import accounts as accounts_service
from app.services import instruments as instruments_service
from app.services.errors import ConflictError, DomainRuleError, NotFoundError


def _require_active_account(db: Session, owner_id: int, account_id: int) -> Account:
    """Resolve an owned account and refuse to post to a deactivated one."""
    account = accounts_service.get(db, owner_id, account_id)
    if not account.is_active:
        raise DomainRuleError(f"account {account_id} is inactive")
    return account


def _require_active_instrument(db: Session, instrument_id: int) -> None:
    instrument = instruments_service.get(db, instrument_id)
    if not instrument.is_active:
        raise DomainRuleError(f"instrument {instrument_id} is inactive")


def create(db: Session, owner_id: int, payload: MovementCreate) -> Movement:
    """Append one movement.

    ``MovementCreate`` has already enforced the per-type field matrix and
    rejected raw transfer legs; what is left is the state the schema cannot
    see — that the account is ours and active, and the instrument exists.
    """
    _require_active_account(db, owner_id, payload.account_id)
    if payload.instrument_id is not None:
        _require_active_instrument(db, payload.instrument_id)

    movement = Movement(
        **payload.model_dump(),
        # Server-owned: a manual entry is never part of a transfer and has no
        # external identity. Imports (phase 1.5) will set source/external_id.
        source="manual",
        external_id=None,
        transfer_id=None,
    )
    db.add(movement)
    db.commit()
    db.refresh(movement)
    return movement


def create_transfer(
    db: Session, owner_id: int, payload: TransferCreate
) -> tuple[uuid.UUID, Movement, Movement]:
    """Expand a transfer into its two linked legs, atomically.

    A transfer is never one row: it is a ``transfer_out`` at the origin and a
    ``transfer_in`` at the destination sharing a ``transfer_id``. Both are
    committed together, so the ledger can never hold a half-transfer. This is
    also why raw legs are rejected by ``MovementCreate``.

    Returns the minted ``transfer_id`` alongside the legs: the column is
    nullable (most movements are not transfers), but here it is known to be set.
    """
    # Distinctness of the two accounts is already enforced by the schema.
    _require_active_account(db, owner_id, payload.from_account_id)
    _require_active_account(db, owner_id, payload.to_account_id)
    if payload.instrument_id is not None:
        _require_active_instrument(db, payload.instrument_id)

    transfer_id = uuid.uuid4()
    shared = {
        "occurred_at": payload.occurred_at,
        "instrument_id": payload.instrument_id,
        "quantity": payload.quantity,
        "currency": payload.currency,
        "transfer_id": transfer_id,
        "source": "manual",
        "external_id": None,
        # A transfer moves value; a wire fee is a separate `fee` movement, which
        # keeps the two legs symmetric.
        "price": None,
        "fee": None,
    }
    out_movement = Movement(
        account_id=payload.from_account_id, type=MovementType.TRANSFER_OUT, **shared
    )
    in_movement = Movement(
        account_id=payload.to_account_id, type=MovementType.TRANSFER_IN, **shared
    )

    db.add_all([out_movement, in_movement])
    db.commit()
    db.refresh(out_movement)
    db.refresh(in_movement)
    return transfer_id, out_movement, in_movement


def list_all(
    db: Session,
    owner_id: int,
    *,
    account_id: int | None = None,
    instrument_id: int | None = None,
    type: MovementType | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    include_voided: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[Movement]:
    stmt = (
        select(Movement)
        .join(Account, Movement.account_id == Account.id)
        .where(Account.owner_id == owner_id)
    )
    if not include_voided:
        stmt = stmt.where(Movement.voided_at.is_(None))
    if account_id is not None:
        stmt = stmt.where(Movement.account_id == account_id)
    if instrument_id is not None:
        stmt = stmt.where(Movement.instrument_id == instrument_id)
    if type is not None:
        stmt = stmt.where(Movement.type == type.value)
    if occurred_from is not None:
        stmt = stmt.where(Movement.occurred_at >= occurred_from)
    if occurred_to is not None:
        stmt = stmt.where(Movement.occurred_at <= occurred_to)

    stmt = stmt.order_by(Movement.occurred_at.desc(), Movement.id.desc())
    return db.execute(stmt.limit(limit).offset(offset)).scalars().all()


def get(db: Session, owner_id: int, movement_id: int) -> Movement:
    """Fetch one owned movement. Voided movements remain readable by id."""
    stmt = (
        select(Movement)
        .join(Account, Movement.account_id == Account.id)
        .where(Movement.id == movement_id, Account.owner_id == owner_id)
    )
    movement = db.execute(stmt).scalar_one_or_none()
    if movement is None:
        raise NotFoundError(f"movement {movement_id} not found")
    return movement


def void(db: Session, owner_id: int, movement_id: int) -> None:
    """Soft-delete: stamp ``voided_at``. The row itself is never mutated further.

    Both legs of a transfer are voided together — annulling one half would leave
    value that left one account but never arrived at the other.
    """
    movement = get(db, owner_id, movement_id)
    if movement.voided_at is not None:
        raise ConflictError(f"movement {movement_id} is already voided")

    now = datetime.now(UTC)
    if movement.transfer_id is None:
        movement.voided_at = now
    else:
        legs = (
            db.execute(select(Movement).where(Movement.transfer_id == movement.transfer_id))
            .scalars()
            .all()
        )
        for leg in legs:
            if leg.voided_at is None:
                leg.voided_at = now
    db.commit()
