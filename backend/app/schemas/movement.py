"""API contracts for the ``movement`` ledger and transfers.

The ledger is append-only: there is a Create shape and a Read shape, and
**deliberately no Update** — the ledger is immutable, so a movement is never
mutated once recorded.
Corrections are compensating movements or a soft-delete (annulment), handled by
the router, never a PUT here.

``quantity`` is always a positive magnitude; direction is encoded by the
movement type (a ``sale`` or ``withdrawal`` is an outflow by definition). Each
type constrains which of ``instrument_id`` / ``price`` / ``fee`` are required,
optional, or forbidden — see ``_TYPE_RULES``.

Transfers between own accounts are two linked rows (``transfer_out`` +
``transfer_in`` sharing a ``transfer_id``). To make that invariant
unbreakable from the client side, raw transfer legs are rejected by
``MovementCreate``; a transfer is created through ``TransferCreate`` and the
service layer mints both rows atomically.
"""

from datetime import datetime
from enum import Enum
from typing import Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.models.enums import MovementType
from app.schemas.common import (
    CurrencyCode,
    FeeAmount,
    MoneyStr,
    PositiveQuantity,
    RequestSchema,
    ResponseSchema,
    UnitPrice,
)


class _Rule(Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    FORBIDDEN = "forbidden"


# Per-type rules for the three conditional fields. Transfer legs are absent on
# purpose: they may only be created via the transfer endpoint.
_TYPE_RULES: dict[MovementType, dict[str, _Rule]] = {
    MovementType.PURCHASE: {
        "instrument_id": _Rule.REQUIRED,
        "price": _Rule.REQUIRED,
        "fee": _Rule.OPTIONAL,
    },
    MovementType.SALE: {
        "instrument_id": _Rule.REQUIRED,
        "price": _Rule.REQUIRED,
        "fee": _Rule.OPTIONAL,
    },
    MovementType.DIVIDEND: {
        "instrument_id": _Rule.REQUIRED,
        "price": _Rule.FORBIDDEN,
        "fee": _Rule.OPTIONAL,
    },
    MovementType.INTEREST: {
        "instrument_id": _Rule.OPTIONAL,
        "price": _Rule.FORBIDDEN,
        "fee": _Rule.OPTIONAL,
    },
    MovementType.FEE: {
        "instrument_id": _Rule.OPTIONAL,
        "price": _Rule.FORBIDDEN,
        # The quantity is the fee, so a separate fee field would be ambiguous.
        "fee": _Rule.FORBIDDEN,
    },
    MovementType.DEPOSIT: {
        "instrument_id": _Rule.FORBIDDEN,
        "price": _Rule.FORBIDDEN,
        "fee": _Rule.OPTIONAL,
    },
    MovementType.WITHDRAWAL: {
        "instrument_id": _Rule.FORBIDDEN,
        "price": _Rule.FORBIDDEN,
        "fee": _Rule.OPTIONAL,
    },
    MovementType.PRINCIPAL_REPAYMENT: {
        "instrument_id": _Rule.REQUIRED,
        "price": _Rule.FORBIDDEN,
        "fee": _Rule.OPTIONAL,
    },
}


class MovementCreate(RequestSchema):
    occurred_at: AwareDatetime = Field(description="When it happened. Timezone-aware, required.")
    account_id: int = Field(description="Must be one of the current owner's accounts.")
    instrument_id: int | None = Field(
        default=None, description="Required/forbidden/optional depending on type — see below."
    )
    type: MovementType = Field(description="Determines which other fields are allowed.")
    quantity: PositiveQuantity = Field(
        description="Always a positive magnitude; direction is implied by type."
    )
    price: UnitPrice | None = Field(default=None, description="Unit price. Required for buy/sell.")
    fee: FeeAmount | None = Field(default=None, description="Optional transaction cost.")
    currency: CurrencyCode = Field(
        description="This movement's native currency — not necessarily the account's."
    )

    @model_validator(mode="after")
    def _enforce_type_rules(self) -> Self:
        rules = _TYPE_RULES.get(self.type)
        if rules is None:
            raise ValueError(
                f"movements of type '{self.type.value}' are created via the transfer endpoint"
            )
        for field, rule in rules.items():
            value = getattr(self, field)
            if rule is _Rule.REQUIRED and value is None:
                raise ValueError(f"'{field}' is required for '{self.type.value}' movements")
            if rule is _Rule.FORBIDDEN and value is not None:
                raise ValueError(f"'{field}' is not allowed for '{self.type.value}' movements")
        return self


class MovementRead(ResponseSchema):
    id: int
    occurred_at: datetime
    account_id: int
    instrument_id: int | None
    type: MovementType
    quantity: MoneyStr
    price: MoneyStr | None
    fee: MoneyStr | None
    currency: str
    transfer_id: UUID | None = Field(description="Set only for transfer legs; links the two rows.")
    source: str = Field(description="Where this row came from, e.g. 'manual'.")
    external_id: str | None = Field(description="External id for imported movements (phase 1.5+).")
    voided_at: datetime | None = Field(description="Set once annulled. Null means still active.")
    created_at: datetime


class TransferCreate(RequestSchema):
    """A transfer between two own accounts.

    Expands into two linked movements in the service layer. A wire fee is recorded
    separately as a ``fee`` movement, keeping a transfer exactly two symmetric
    rows — hence no ``fee`` field here.
    """

    occurred_at: AwareDatetime
    from_account_id: int = Field(description="Origin account. Must be one of the owner's.")
    to_account_id: int = Field(description="Destination account. Must differ from the origin.")
    instrument_id: int | None = Field(
        default=None, description="Set only when transferring an instrument rather than cash."
    )
    quantity: PositiveQuantity
    currency: CurrencyCode

    @model_validator(mode="after")
    def _distinct_accounts(self) -> Self:
        if self.from_account_id == self.to_account_id:
            raise ValueError("from_account_id and to_account_id must differ")
        return self


class TransferRead(ResponseSchema):
    """The two legs of a transfer, assembled by the service layer."""

    transfer_id: UUID
    out_movement: MovementRead
    in_movement: MovementRead
