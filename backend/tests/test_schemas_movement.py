from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

import app.schemas as schemas
from app.models.enums import MovementType
from app.schemas.movement import MovementCreate, TransferCreate

_OCCURRED = datetime(2026, 1, 2, tzinfo=UTC)


def _base(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "occurred_at": _OCCURRED.isoformat(),
        "account_id": 1,
        "quantity": "10",
        "currency": "EUR",
    }
    payload.update(overrides)
    return payload


# One minimal valid payload per directly-creatable movement type.
_VALID: dict[MovementType, dict[str, Any]] = {
    MovementType.PURCHASE: _base(type="purchase", instrument_id=1, price="100"),
    MovementType.SALE: _base(type="sale", instrument_id=1, price="100"),
    MovementType.DIVIDEND: _base(type="dividend", instrument_id=1),
    MovementType.INTEREST: _base(type="interest"),
    MovementType.FEE: _base(type="fee"),
    MovementType.DEPOSIT: _base(type="deposit"),
    MovementType.WITHDRAWAL: _base(type="withdrawal"),
    MovementType.PRINCIPAL_REPAYMENT: _base(type="principal_repayment", instrument_id=1),
}


@pytest.mark.parametrize("payload", _VALID.values(), ids=[t.value for t in _VALID])
def test_valid_payload_per_type(payload: dict[str, Any]) -> None:
    model = MovementCreate.model_validate(payload)
    assert model.type.value == payload["type"]


@pytest.mark.parametrize(
    "payload",
    [
        _base(type="purchase", price="100"),  # missing instrument_id
        _base(type="purchase", instrument_id=1),  # missing price
        _base(type="deposit", instrument_id=1),  # instrument forbidden
        _base(type="dividend", instrument_id=1, price="100"),  # price forbidden
        _base(type="fee", fee="1"),  # fee forbidden
        _base(type="withdrawal", price="100"),  # price forbidden
    ],
    ids=[
        "purchase-no-instrument",
        "purchase-no-price",
        "deposit-with-instrument",
        "dividend-with-price",
        "fee-with-fee",
        "withdrawal-with-price",
    ],
)
def test_type_matrix_rejects_bad_shape(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        MovementCreate.model_validate(payload)


@pytest.mark.parametrize("leg", ["transfer_out", "transfer_in"])
def test_transfer_legs_rejected_by_movement_create(leg: str) -> None:
    with pytest.raises(ValidationError, match="transfer endpoint"):
        MovementCreate.model_validate(_base(type=leg, instrument_id=1))


def test_transfer_create_valid() -> None:
    model = TransferCreate.model_validate(
        {
            "occurred_at": _OCCURRED.isoformat(),
            "from_account_id": 1,
            "to_account_id": 2,
            "quantity": "50",
            "currency": "EUR",
        }
    )
    assert model.from_account_id == 1
    assert model.to_account_id == 2


def test_transfer_create_rejects_same_account() -> None:
    with pytest.raises(ValidationError, match="must differ"):
        TransferCreate.model_validate(
            {
                "occurred_at": _OCCURRED.isoformat(),
                "from_account_id": 1,
                "to_account_id": 1,
                "quantity": "50",
                "currency": "EUR",
            }
        )


@pytest.mark.parametrize("field", ["owner_id", "transfer_id", "source", "id"])
def test_extra_server_fields_forbidden(field: str) -> None:
    with pytest.raises(ValidationError):
        MovementCreate.model_validate(_base(type="deposit", **{field: 1}))


def test_naive_occurred_at_rejected() -> None:
    with pytest.raises(ValidationError):
        MovementCreate.model_validate(_base(type="deposit", occurred_at="2026-01-02T00:00:00"))


def test_no_movement_update_schema_exists() -> None:
    # The immutable-ledger rule: there must never be a way to PUT a movement.
    assert not hasattr(schemas, "MovementUpdate")
