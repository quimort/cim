from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.instrument import Instrument
from tests.factories import make_price

POSITIONS = "/api/positions"
WHEN = "2026-01-01T10:00:00+00:00"


@pytest.fixture
def account_id(client: TestClient) -> int:
    body = {"name": "Broker IBKR", "type": "broker", "currency": "EUR"}
    return int(client.post("/api/accounts", json=body).json()["id"])


@pytest.fixture
def instrument_id(client: TestClient) -> int:
    body = {"name": "VWCE", "asset_class": "tradable", "currency": "EUR"}
    return int(client.post("/api/instruments", json=body).json()["id"])


def _purchase(client: TestClient, account_id: int, instrument_id: int) -> None:
    response = client.post(
        "/api/movements",
        json={
            "occurred_at": WHEN,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "type": "purchase",
            "quantity": "10",
            "price": "100",
            "currency": "EUR",
        },
    )
    assert response.status_code == 201, response.text


def test_position_amounts_are_strings_and_precise(
    client: TestClient, session: Session, account_id: int, instrument_id: int
) -> None:
    _purchase(client, account_id, instrument_id)
    instrument = session.get(Instrument, instrument_id)
    assert instrument is not None
    make_price(session, instrument, day="2026-01-01", value="120")

    response = client.get(POSITIONS)
    assert response.status_code == 200
    [position] = response.json()
    assert isinstance(position["market_value"], str)
    assert Decimal(position["quantity"]) == 10
    assert Decimal(position["market_value"]) == 1200
    assert Decimal(position["unrealized_pnl"]) == 200


def test_past_date_query_reflects_the_price_on_that_day(
    client: TestClient, session: Session, account_id: int, instrument_id: int
) -> None:
    """The ledger's payoff: an old ?date= answers with the state back then."""
    _purchase(client, account_id, instrument_id)
    instrument = session.get(Instrument, instrument_id)
    assert instrument is not None
    make_price(session, instrument, day="2026-01-01", value="100")
    make_price(session, instrument, day="2026-02-01", value="150")

    early = client.get(POSITIONS, params={"date": "2026-01-15"})
    assert early.status_code == 200
    assert Decimal(early.json()[0]["market_value"]) == 1000

    later = client.get(POSITIONS, params={"date": "2026-02-15"})
    assert later.status_code == 200
    assert Decimal(later.json()[0]["market_value"]) == 1500


def test_missing_price_is_a_422(client: TestClient, account_id: int, instrument_id: int) -> None:
    _purchase(client, account_id, instrument_id)
    response = client.get(POSITIONS)
    assert response.status_code == 422


def test_closed_positions_are_hidden_unless_requested(
    client: TestClient, session: Session, account_id: int, instrument_id: int
) -> None:
    _purchase(client, account_id, instrument_id)
    sale = client.post(
        "/api/movements",
        json={
            "occurred_at": "2026-01-05T10:00:00+00:00",
            "account_id": account_id,
            "instrument_id": instrument_id,
            "type": "sale",
            "quantity": "10",
            "price": "110",
            "currency": "EUR",
        },
    )
    assert sale.status_code == 201, sale.text

    assert client.get(POSITIONS).json() == []

    [position] = client.get(POSITIONS, params={"include_closed": "true"}).json()
    assert Decimal(position["quantity"]) == 0
    assert Decimal(position["realized_pnl"]) == 100
    assert position["market_value"] is None


def test_there_is_no_write_method_on_positions(client: TestClient) -> None:
    assert client.post(POSITIONS, json={}).status_code == 405
