"""HTTP surface for the ``account`` master. Translation only — logic lives in the service."""

from collections.abc import Sequence

from fastapi import APIRouter, Query, status

from app.deps import CurrentOwnerId, DbSession
from app.models.account import Account
from app.routers._docs import error_responses
from app.schemas.account import AccountCreate, AccountRead, AccountUpdate
from app.services import accounts as service

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post(
    "",
    response_model=AccountRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
    responses=error_responses((409, "An account with this name already exists for this owner.")),
)
def create_account(payload: AccountCreate, db: DbSession, owner_id: CurrentOwnerId) -> Account:
    return service.create(db, owner_id, payload)


@router.get("", response_model=list[AccountRead], summary="List accounts")
def list_accounts(
    db: DbSession,
    owner_id: CurrentOwnerId,
    include_inactive: bool = Query(default=False, description="Include deactivated accounts."),
) -> Sequence[Account]:
    return service.list_all(db, owner_id, include_inactive=include_inactive)


@router.get(
    "/{account_id}",
    response_model=AccountRead,
    summary="Get an account",
    responses=error_responses((404, "No account with this id, or it belongs to another owner.")),
)
def get_account(account_id: int, db: DbSession, owner_id: CurrentOwnerId) -> Account:
    return service.get(db, owner_id, account_id)


@router.patch(
    "/{account_id}",
    response_model=AccountRead,
    summary="Rename, retype, or (de)activate an account",
    responses=error_responses(
        (404, "No account with this id, or it belongs to another owner."),
        (409, "The new name collides with another of this owner's accounts."),
    ),
)
def update_account(
    account_id: int, payload: AccountUpdate, db: DbSession, owner_id: CurrentOwnerId
) -> Account:
    """Rename, retype, or deactivate.

    There is no DELETE: deactivation is ``{"is_active": false}``, because an
    account with movements behind it cannot be removed without orphaning ledger
    history.
    """
    return service.update(db, owner_id, account_id, payload)
