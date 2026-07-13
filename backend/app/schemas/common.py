"""Shared building blocks for the API contracts.

Money is the delicate part. Two invariants govern money here: never a ``float`` for
money, and amounts travel over JSON as **strings** (``"1234.56"``) so JSON's
float representation can never introduce rounding error. The type aliases below
enforce both directions of that contract and make OpenAPI advertise ``string``,
so the generated TypeScript types are strings too.
"""

from decimal import Decimal
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    WithJsonSchema,
)


def _reject_float(value: Any) -> Any:
    """Refuse JSON floats before they can lose precision.

    By the time Pydantic hands us a JSON number with a fractional part it is
    already a Python ``float`` — precision is already gone. Silently converting
    it would hide the very bug the "amounts as strings" rule exists to prevent,
    so we reject it and force the client to send a string.
    """
    if isinstance(value, float):
        raise ValueError('amounts must be sent as JSON strings (e.g. "1234.56"), not numbers')
    return value


def _decimal_to_str(value: Decimal) -> str:
    """Serialize a Decimal without scientific notation.

    ``str(Decimal("1E+2"))`` yields ``"1E+2"``; ``format(value, "f")`` yields
    ``"100"``. The wire format must always be plain decimal digits.
    """
    return format(value, "f")


_NO_FLOAT = BeforeValidator(_reject_float)
_MONEY_SERIALIZER = PlainSerializer(_decimal_to_str, return_type=str, when_used="json")
_MONEY_JSON_SCHEMA = WithJsonSchema(
    {"type": "string", "pattern": r"^-?\d+(\.\d+)?$", "examples": ["1234.56"]}
)

# Read-side money: string in JSON, no scale re-check (the DB already guarantees
# it). ``when_used="json"`` means ``model_dump()`` still yields a Decimal, which
# is what the service layer consumes.
MoneyStr = Annotated[Decimal, _NO_FLOAT, _MONEY_SERIALIZER, _MONEY_JSON_SCHEMA]

# Create-side aliases. Scales mirror the corresponding NUMERIC columns so an
# out-of-range amount is a 422 rather than a DB error.
PositiveQuantity = Annotated[
    Decimal,
    _NO_FLOAT,
    Field(gt=0, max_digits=28, decimal_places=10),
    _MONEY_SERIALIZER,
    _MONEY_JSON_SCHEMA,
]
UnitPrice = Annotated[
    Decimal,
    _NO_FLOAT,
    Field(gt=0, max_digits=20, decimal_places=8),
    _MONEY_SERIALIZER,
    _MONEY_JSON_SCHEMA,
]
FeeAmount = Annotated[
    Decimal,
    _NO_FLOAT,
    Field(ge=0, max_digits=20, decimal_places=8),
    _MONEY_SERIALIZER,
    _MONEY_JSON_SCHEMA,
]
InterestRate = Annotated[
    Decimal,
    _NO_FLOAT,
    Field(max_digits=10, decimal_places=6),
    _MONEY_SERIALIZER,
    _MONEY_JSON_SCHEMA,
]

# A three-letter ISO 4217 code, normalized to upper-case. The code always reads
# the currency; it never assumes EUR.
CurrencyCode = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z]{3}$")
]


class RequestSchema(BaseModel):
    """Base for request bodies. Unknown keys are contract violations.

    ``extra="forbid"`` also stops a client from setting server-owned fields
    (``owner_id``, ``transfer_id``, ``source``, ``id`` …): they simply aren't
    declared, so sending them is a 422.
    """

    model_config = ConfigDict(extra="forbid")


class ResponseSchema(BaseModel):
    """Base for read shapes, built directly from ORM objects."""

    model_config = ConfigDict(from_attributes=True)


class ErrorDetail(BaseModel):
    """Shape of every 4xx response. Matches what ``main.py``'s domain-error
    handlers return for ``NotFoundError`` (404), ``ConflictError`` (409), and
    ``DomainRuleError`` (422)."""

    detail: str = Field(description="Human-readable explanation of what went wrong.")
