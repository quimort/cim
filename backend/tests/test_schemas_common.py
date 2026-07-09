import json
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.common import CurrencyCode, MoneyStr, PositiveQuantity, UnitPrice


class _MoneyModel(BaseModel):
    amount: MoneyStr


class _QuantityModel(BaseModel):
    quantity: PositiveQuantity


class _PriceModel(BaseModel):
    price: UnitPrice


class _CurrencyModel(BaseModel):
    currency: CurrencyCode


def test_string_input_parses_to_decimal() -> None:
    model = _MoneyModel.model_validate({"amount": "1234.5600"})
    assert model.amount == Decimal("1234.5600")


def test_json_output_is_a_string() -> None:
    model = _MoneyModel(amount=Decimal("1234.56"))
    payload = json.loads(model.model_dump_json())
    assert payload["amount"] == "1234.56"
    assert isinstance(payload["amount"], str)


def test_python_dump_keeps_decimal_for_the_service_layer() -> None:
    model = _MoneyModel(amount=Decimal("1234.56"))
    assert model.model_dump()["amount"] == Decimal("1234.56")
    assert isinstance(model.model_dump()["amount"], Decimal)


def test_float_input_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _QuantityModel.model_validate({"quantity": 1.5})


def test_int_input_is_accepted() -> None:
    model = _QuantityModel.model_validate({"quantity": 5})
    assert model.quantity == Decimal("5")


def test_no_scientific_notation_on_output() -> None:
    model = _MoneyModel(amount=Decimal("1E+2"))
    payload = json.loads(model.model_dump_json())
    assert payload["amount"] == "100"


def test_quantity_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        _QuantityModel.model_validate({"quantity": "0"})
    with pytest.raises(ValidationError):
        _QuantityModel.model_validate({"quantity": "-1"})


def test_quantity_scale_limit_enforced() -> None:
    # 11 decimal places exceeds the Numeric(28, 10) scale.
    with pytest.raises(ValidationError):
        _QuantityModel.model_validate({"quantity": "1.12345678901"})


def test_price_scale_limit_enforced() -> None:
    # 9 decimal places exceeds the Numeric(20, 8) scale.
    with pytest.raises(ValidationError):
        _PriceModel.model_validate({"price": "1.123456789"})


def test_currency_is_normalized_to_upper() -> None:
    model = _CurrencyModel.model_validate({"currency": "eur"})
    assert model.currency == "EUR"


@pytest.mark.parametrize("value", ["EURO", "E1", "US", "12€"])
def test_currency_rejects_bad_codes(value: str) -> None:
    with pytest.raises(ValidationError):
        _CurrencyModel.model_validate({"currency": value})


def test_money_json_schema_advertises_string() -> None:
    schema = _MoneyModel.model_json_schema()
    assert schema["properties"]["amount"]["type"] == "string"
