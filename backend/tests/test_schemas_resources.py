import json
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models import Account, ExchangeRate, Instrument, Movement, Price
from app.models.enums import AssetClass, LoanStatus, MovementType
from app.schemas.account import AccountRead, AccountUpdate
from app.schemas.exchange_rate import ExchangeRateRead
from app.schemas.instrument import InstrumentCreate, InstrumentRead, InstrumentUpdate
from app.schemas.movement import MovementCreate, MovementRead
from app.schemas.price import PriceRead

# `session` comes from tests/conftest.py.


def test_account_read_from_orm_has_no_owner_id(session: Session) -> None:
    account = Account(name="Broker", type="broker", currency="EUR", owner_id=7)
    session.add(account)
    session.flush()

    read = AccountRead.model_validate(account)
    assert read.currency == "EUR"
    assert "owner_id" not in read.model_dump()


def test_account_update_rejects_currency() -> None:
    with pytest.raises(ValidationError):
        AccountUpdate.model_validate({"currency": "USD"})


def test_movement_read_serializes_money_as_strings(session: Session) -> None:
    account = Account(name="Broker", type="broker", currency="EUR")
    instrument = Instrument(name="ETF", asset_class=AssetClass.TRADABLE, currency="EUR")
    session.add_all([account, instrument])
    session.flush()

    movement = Movement(
        occurred_at=datetime.now(UTC),
        account_id=account.id,
        instrument_id=instrument.id,
        type=MovementType.PURCHASE,
        quantity=Decimal("1.23456789"),
        price=Decimal("100.12345678"),
        fee=Decimal("0.99"),
        currency="EUR",
    )
    session.add(movement)
    session.flush()

    payload = json.loads(MovementRead.model_validate(movement).model_dump_json())
    assert payload["quantity"] == "1.23456789"
    assert payload["price"] == "100.12345678"
    assert isinstance(payload["quantity"], str)


def test_price_and_fx_read_from_orm(session: Session) -> None:
    instrument = Instrument(name="ETF", asset_class=AssetClass.TRADABLE, currency="EUR")
    session.add(instrument)
    session.flush()

    price = Price(
        instrument_id=instrument.id, date=date(2026, 1, 2), value=Decimal("10.5"), currency="EUR"
    )
    fx = ExchangeRate(
        date=date(2026, 1, 2),
        base_currency="EUR",
        quote_currency="USD",
        rate=Decimal("1.0876543210"),
    )
    session.add_all([price, fx])
    session.flush()

    price_payload = json.loads(PriceRead.model_validate(price).model_dump_json())
    fx_payload = json.loads(ExchangeRateRead.model_validate(fx).model_dump_json())
    assert price_payload["value"] == "10.5"
    assert fx_payload["rate"] == "1.0876543210"


def test_instrument_loan_fields_forbidden_for_non_loan() -> None:
    with pytest.raises(ValidationError, match="asset_class=loan"):
        InstrumentCreate.model_validate(
            {
                "name": "ETF",
                "asset_class": "tradable",
                "currency": "EUR",
                "maturity_date": "2030-01-01",
            }
        )


def test_instrument_loan_defaults_status_active() -> None:
    model = InstrumentCreate.model_validate(
        {"name": "Loan to X", "asset_class": "loan", "currency": "EUR"}
    )
    assert model.status is LoanStatus.ACTIVE


def test_instrument_loan_accepts_all_loan_fields() -> None:
    model = InstrumentCreate.model_validate(
        {
            "name": "Loan to X",
            "asset_class": "loan",
            "currency": "EUR",
            "maturity_date": "2030-01-01",
            "expected_interest": "0.045",
            "status": "active",
        }
    )
    assert model.expected_interest == Decimal("0.045")


def test_instrument_update_allows_partial() -> None:
    model = InstrumentUpdate.model_validate({"name": "Renamed"})
    assert model.model_dump(exclude_unset=True) == {"name": "Renamed"}


def test_instrument_read_serializes_interest_as_string(session: Session) -> None:
    instrument = Instrument(
        name="Loan",
        asset_class=AssetClass.LOAN,
        currency="EUR",
        expected_interest=Decimal("0.045000"),
        status=LoanStatus.ACTIVE,
    )
    session.add(instrument)
    session.flush()

    payload = json.loads(InstrumentRead.model_validate(instrument).model_dump_json())
    assert payload["expected_interest"] == "0.045000"


def test_money_json_schema_is_string_in_both_modes() -> None:
    validation = MovementCreate.model_json_schema(mode="validation")
    assert validation["properties"]["quantity"]["type"] == "string"

    serialization = MovementRead.model_json_schema(mode="serialization")
    assert serialization["properties"]["quantity"]["type"] == "string"
