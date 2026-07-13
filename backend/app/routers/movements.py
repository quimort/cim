"""HTTP surface for the ``movement`` ledger.

There is no PUT and no PATCH here, and there never will be: the ledger is
immutable. DELETE does not delete — it stamps the annulment flag. Corrections
are compensating movements.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Body, Query, Response, status

from app.deps import CurrentOwnerId, DbSession
from app.models.enums import MovementType
from app.models.movement import Movement
from app.routers._docs import error_responses
from app.schemas.movement import MovementCreate, MovementRead, TransferCreate, TransferRead
from app.services import movements as service

router = APIRouter(prefix="/movements", tags=["movements"])

# Module-level singletons, per ruff B008: enum/datetime-typed Query() defaults
# aren't recognized as side-effect-free the way plain int/bool/str ones are.
_TYPE_FILTER = Query(default=None, description="Filter to one movement type.")
_OCCURRED_FROM_FILTER = Query(default=None, description="Only movements at or after this time.")
_OCCURRED_TO_FILTER = Query(default=None, description="Only movements at or before this time.")

_MOVEMENT_EXAMPLES = {
    "purchase": {
        "summary": "Buy an instrument",
        "description": "instrument_id and price are required; fee is optional.",
        "value": {
            "occurred_at": "2026-03-01T10:00:00+00:00",
            "account_id": 1,
            "instrument_id": 1,
            "type": "purchase",
            "quantity": "10.5",
            "price": "108.42",
            "fee": "1.00",
            "currency": "EUR",
        },
    },
    "deposit": {
        "summary": "Deposit cash",
        "description": "No instrument_id and no price for cash movements.",
        "value": {
            "occurred_at": "2026-03-01T10:00:00+00:00",
            "account_id": 1,
            "type": "deposit",
            "quantity": "1000.00",
            "currency": "EUR",
        },
    },
    "dividend": {
        "summary": "Receive a dividend",
        "description": "instrument_id is required; price is forbidden (no unit price here).",
        "value": {
            "occurred_at": "2026-03-01T10:00:00+00:00",
            "account_id": 1,
            "instrument_id": 1,
            "type": "dividend",
            "quantity": "12.40",
            "currency": "EUR",
        },
    },
    "fee": {
        "summary": "Pay a standalone fee",
        "description": "The quantity is the fee itself, so the fee field is forbidden here.",
        "value": {
            "occurred_at": "2026-03-01T10:00:00+00:00",
            "account_id": 1,
            "type": "fee",
            "quantity": "9.99",
            "currency": "EUR",
        },
    },
}

_TRANSFER_EXAMPLE = {
    "transfer": {
        "summary": "Move cash between two owned accounts",
        "description": "Expands into two rows (transfer_out + transfer_in) sharing a transfer_id.",
        "value": {
            "occurred_at": "2026-03-01T10:00:00+00:00",
            "from_account_id": 1,
            "to_account_id": 2,
            "quantity": "500.00",
            "currency": "EUR",
        },
    }
}


@router.post(
    "",
    response_model=MovementRead,
    status_code=status.HTTP_201_CREATED,
    summary="Append a movement to the ledger",
    responses=error_responses(
        (404, "The account (or instrument, if given) does not exist, or the account isn't yours."),
        (422, "The account is inactive, or the fields don't match the movement type's rules."),
    ),
)
def create_movement(
    payload: Annotated[MovementCreate, Body(openapi_examples=_MOVEMENT_EXAMPLES)],
    db: DbSession,
    owner_id: CurrentOwnerId,
) -> Movement:
    return service.create(db, owner_id, payload)


# Declared before /{movement_id} so the path param does not swallow "transfer".
@router.post(
    "/transfer",
    response_model=TransferRead,
    status_code=status.HTTP_201_CREATED,
    summary="Transfer between two owned accounts",
    responses=error_responses(
        (404, "One of the accounts does not exist, or isn't yours."),
        (422, "from_account_id and to_account_id are the same, or an account is inactive."),
    ),
)
def create_transfer(
    payload: Annotated[TransferCreate, Body(openapi_examples=_TRANSFER_EXAMPLE)],
    db: DbSession,
    owner_id: CurrentOwnerId,
) -> TransferRead:
    """A transfer between own accounts: two linked movements, one ``transfer_id``."""
    transfer_id, out_movement, in_movement = service.create_transfer(db, owner_id, payload)
    return TransferRead(
        transfer_id=transfer_id,
        out_movement=MovementRead.model_validate(out_movement),
        in_movement=MovementRead.model_validate(in_movement),
    )


@router.get("", response_model=list[MovementRead], summary="List movements")
def list_movements(
    db: DbSession,
    owner_id: CurrentOwnerId,
    account_id: int | None = Query(default=None, description="Filter to one account."),
    instrument_id: int | None = Query(default=None, description="Filter to one instrument."),
    type: MovementType | None = _TYPE_FILTER,
    occurred_from: datetime | None = _OCCURRED_FROM_FILTER,
    occurred_to: datetime | None = _OCCURRED_TO_FILTER,
    include_voided: bool = Query(
        default=False, description="Include annulled movements (voided_at is set)."
    ),
    limit: int = Query(default=100, ge=1, le=500, description="Max rows to return."),
    offset: int = Query(default=0, ge=0, description="Rows to skip, for pagination."),
) -> Sequence[Movement]:
    """Voided movements are hidden unless ``include_voided=true``."""
    return service.list_all(
        db,
        owner_id,
        account_id=account_id,
        instrument_id=instrument_id,
        type=type,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        include_voided=include_voided,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{movement_id}",
    response_model=MovementRead,
    summary="Get a movement",
    responses=error_responses((404, "No movement with this id, or its account isn't yours.")),
)
def get_movement(movement_id: int, db: DbSession, owner_id: CurrentOwnerId) -> Movement:
    """A voided movement is still readable by id — it stays in the ledger."""
    return service.get(db, owner_id, movement_id)


@router.delete(
    "/{movement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Annul a movement",
    responses=error_responses(
        (404, "No movement with this id, or its account isn't yours."),
        (409, "The movement is already voided."),
    ),
)
def void_movement(movement_id: int, db: DbSession, owner_id: CurrentOwnerId) -> Response:
    """Annul a movement. The row survives; ``voided_at`` is stamped.

    Voiding either leg of a transfer voids both.
    """
    service.void(db, owner_id, movement_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
