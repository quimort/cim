"""API contracts for the ``account`` resource.

``owner_id`` never appears here: it is a server-side isolation anchor (ownership
always traces back to the account's owner and is never duplicated on
client-facing fields), not client data. ``currency`` is set at
creation and immutable afterwards — movements are already denominated in it and
changing it would silently corrupt every derived valuation.
"""

from datetime import datetime

from pydantic import Field

from app.schemas.common import CurrencyCode, RequestSchema, ResponseSchema


class AccountCreate(RequestSchema):
    name: str = Field(min_length=1, max_length=100)
    type: str = Field(min_length=1, max_length=50)
    currency: CurrencyCode


class AccountUpdate(RequestSchema):
    """PATCH semantics: only the provided fields change.

    The router applies ``model_dump(exclude_unset=True)`` so an omitted field is
    left untouched. ``currency`` is intentionally absent (immutable).
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    type: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None


class AccountRead(ResponseSchema):
    id: int
    name: str
    type: str
    currency: str
    is_active: bool
    created_at: datetime
