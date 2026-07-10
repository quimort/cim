from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Account, Movement

MOVEMENTS = "/api/movements"
TRANSFER = f"{MOVEMENTS}/transfer"
WHEN = "2026-03-01T10:00:00+00:00"


@pytest.fixture
def account_id(client: TestClient) -> int:
    body = {"name": "Broker IBKR", "type": "broker", "currency": "EUR"}
    return int(client.post("/api/accounts", json=body).json()["id"])


@pytest.fixture
def other_account_id(client: TestClient) -> int:
    body = {"name": "Bank BBVA", "type": "bank", "currency": "EUR"}
    return int(client.post("/api/accounts", json=body).json()["id"])


@pytest.fixture
def instrument_id(client: TestClient) -> int:
    body = {"name": "VWCE", "asset_class": "tradable", "currency": "EUR"}
    return int(client.post("/api/instruments", json=body).json()["id"])


def _purchase(client: TestClient, account_id: int, instrument_id: int, **overrides: object) -> dict:
    body: dict[str, object] = {
        "occurred_at": WHEN,
        "account_id": account_id,
        "instrument_id": instrument_id,
        "type": "purchase",
        "quantity": "10.5",
        "price": "108.42",
        "currency": "EUR",
    }
    body.update(overrides)
    response = client.post(MOVEMENTS, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _deposit(client: TestClient, account_id: int, **overrides: object) -> dict:
    body: dict[str, object] = {
        "occurred_at": WHEN,
        "account_id": account_id,
        "type": "deposit",
        "quantity": "1000",
        "currency": "EUR",
    }
    body.update(overrides)
    response = client.post(MOVEMENTS, json=body)
    assert response.status_code == 201, response.text
    return response.json()


# --- append ---------------------------------------------------------------


def test_purchase_amounts_come_back_as_strings(
    client: TestClient, account_id: int, instrument_id: int
) -> None:
    movement = _purchase(client, account_id, instrument_id)
    assert movement["quantity"] == "10.5000000000"
    assert movement["price"] == "108.42000000"
    assert movement["source"] == "manual"
    assert movement["voided_at"] is None
    assert movement["transfer_id"] is None


def test_high_precision_quantity_survives_the_round_trip(
    client: TestClient, account_id: int, instrument_id: int
) -> None:
    """Crypto needs >= 8 decimals; a float would have silently mangled this."""
    movement = _purchase(client, account_id, instrument_id, quantity="0.12345678")
    assert movement["quantity"] == "0.1234567800"


def test_a_json_float_amount_is_rejected(
    client: TestClient, account_id: int, instrument_id: int
) -> None:
    response = client.post(
        MOVEMENTS,
        json={
            "occurred_at": WHEN,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "type": "purchase",
            "quantity": 10.5,
            "price": "108.42",
            "currency": "EUR",
        },
    )
    assert response.status_code == 422


def test_a_purchase_without_a_price_is_rejected(
    client: TestClient, account_id: int, instrument_id: int
) -> None:
    response = client.post(
        MOVEMENTS,
        json={
            "occurred_at": WHEN,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "type": "purchase",
            "quantity": "10.5",
            "currency": "EUR",
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize("leg", ["transfer_out", "transfer_in"])
def test_raw_transfer_legs_cannot_be_posted_directly(
    client: TestClient, account_id: int, leg: str
) -> None:
    """A lone leg would leave value leaving an account and never arriving."""
    response = client.post(
        MOVEMENTS,
        json={
            "occurred_at": WHEN,
            "account_id": account_id,
            "type": leg,
            "quantity": "100",
            "currency": "EUR",
        },
    )
    assert response.status_code == 422


def test_a_movement_in_a_currency_other_than_the_accounts_is_allowed(
    client: TestClient, account_id: int, instrument_id: int
) -> None:
    """A EUR-reporting broker can hold a USD purchase. Never assume EUR."""
    movement = _purchase(client, account_id, instrument_id, currency="USD")
    assert movement["currency"] == "USD"


def test_posting_to_an_inactive_account_is_rejected(
    client: TestClient, account_id: int, instrument_id: int
) -> None:
    client.patch(f"/api/accounts/{account_id}", json={"is_active": False})
    response = client.post(
        MOVEMENTS,
        json={
            "occurred_at": WHEN,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "type": "purchase",
            "quantity": "1",
            "price": "1",
            "currency": "EUR",
        },
    )
    assert response.status_code == 422


def test_posting_to_another_owners_account_is_404(client: TestClient, session: Session) -> None:
    foreign = Account(name="Not mine", type="bank", currency="EUR", owner_id=2)
    session.add(foreign)
    session.commit()

    response = client.post(
        MOVEMENTS,
        json={
            "occurred_at": WHEN,
            "account_id": foreign.id,
            "type": "deposit",
            "quantity": "1000",
            "currency": "EUR",
        },
    )
    assert response.status_code == 404


def test_unknown_instrument_is_404(client: TestClient, account_id: int) -> None:
    response = client.post(
        MOVEMENTS,
        json={
            "occurred_at": WHEN,
            "account_id": account_id,
            "instrument_id": 999,
            "type": "purchase",
            "quantity": "1",
            "price": "1",
            "currency": "EUR",
        },
    )
    assert response.status_code == 404


# --- the ledger is immutable ----------------------------------------------


@pytest.mark.parametrize("method", ["put", "patch"])
def test_a_movement_can_never_be_updated(
    client: TestClient, account_id: int, method: str
) -> None:
    """RULE: never implement PUT on movements. Asserted, not merely documented."""
    movement = _deposit(client, account_id)
    response = getattr(client, method)(
        f"{MOVEMENTS}/{movement['id']}", json={"quantity": "999999"}
    )
    assert response.status_code == 405


# --- transfers ------------------------------------------------------------


def test_transfer_creates_two_linked_legs(
    client: TestClient, account_id: int, other_account_id: int
) -> None:
    response = client.post(
        TRANSFER,
        json={
            "occurred_at": WHEN,
            "from_account_id": account_id,
            "to_account_id": other_account_id,
            "quantity": "500",
            "currency": "EUR",
        },
    )
    assert response.status_code == 201, response.text
    transfer = response.json()

    out_leg, in_leg = transfer["out_movement"], transfer["in_movement"]
    assert out_leg["transfer_id"] == in_leg["transfer_id"] == transfer["transfer_id"]
    assert out_leg["type"] == "transfer_out"
    assert in_leg["type"] == "transfer_in"
    assert out_leg["account_id"] == account_id
    assert in_leg["account_id"] == other_account_id
    assert out_leg["quantity"] == in_leg["quantity"] == "500.0000000000"


def test_a_transfer_to_the_same_account_is_rejected(client: TestClient, account_id: int) -> None:
    response = client.post(
        TRANSFER,
        json={
            "occurred_at": WHEN,
            "from_account_id": account_id,
            "to_account_id": account_id,
            "quantity": "500",
            "currency": "EUR",
        },
    )
    assert response.status_code == 422


def test_a_transfer_to_another_owners_account_is_404(
    client: TestClient, account_id: int, session: Session
) -> None:
    foreign = Account(name="Not mine", type="bank", currency="EUR", owner_id=2)
    session.add(foreign)
    session.commit()

    response = client.post(
        TRANSFER,
        json={
            "occurred_at": WHEN,
            "from_account_id": account_id,
            "to_account_id": foreign.id,
            "quantity": "500",
            "currency": "EUR",
        },
    )
    assert response.status_code == 404
    # And nothing was written: a half-transfer must never exist.
    assert client.get(MOVEMENTS).json() == []


# --- voiding (soft-delete) ------------------------------------------------


def test_delete_voids_without_removing(client: TestClient, account_id: int) -> None:
    movement = _deposit(client, account_id)
    assert client.delete(f"{MOVEMENTS}/{movement['id']}").status_code == 204

    # Still readable by id — it stays in the ledger.
    voided = client.get(f"{MOVEMENTS}/{movement['id']}")
    assert voided.status_code == 200
    assert voided.json()["voided_at"] is not None

    assert client.get(MOVEMENTS).json() == []
    listed = client.get(MOVEMENTS, params={"include_voided": True}).json()
    assert [m["id"] for m in listed] == [movement["id"]]


def test_voiding_twice_is_a_conflict(client: TestClient, account_id: int) -> None:
    movement = _deposit(client, account_id)
    client.delete(f"{MOVEMENTS}/{movement['id']}")
    assert client.delete(f"{MOVEMENTS}/{movement['id']}").status_code == 409


def test_voiding_one_leg_of_a_transfer_voids_both(
    client: TestClient, account_id: int, other_account_id: int
) -> None:
    """Annulling half a transfer would leave the ledger unbalanced."""
    transfer = client.post(
        TRANSFER,
        json={
            "occurred_at": WHEN,
            "from_account_id": account_id,
            "to_account_id": other_account_id,
            "quantity": "500",
            "currency": "EUR",
        },
    ).json()

    assert client.delete(f"{MOVEMENTS}/{transfer['out_movement']['id']}").status_code == 204

    legs = client.get(MOVEMENTS, params={"include_voided": True}).json()
    assert len(legs) == 2
    assert all(leg["voided_at"] is not None for leg in legs)


def test_voiding_another_owners_movement_is_404(client: TestClient, session: Session) -> None:
    foreign = Account(name="Not mine", type="bank", currency="EUR", owner_id=2)
    session.add(foreign)
    session.flush()
    movement = Movement(
        occurred_at=datetime(2026, 3, 1, tzinfo=UTC),
        account_id=foreign.id,
        type="deposit",
        quantity=Decimal("1000"),
        currency="EUR",
        source="manual",
    )
    session.add(movement)
    session.commit()

    assert client.delete(f"{MOVEMENTS}/{movement.id}").status_code == 404
    assert client.get(f"{MOVEMENTS}/{movement.id}").status_code == 404


# --- listing & filters ----------------------------------------------------


def test_filters_by_account_and_type(
    client: TestClient, account_id: int, other_account_id: int, instrument_id: int
) -> None:
    _purchase(client, account_id, instrument_id)
    _deposit(client, account_id)
    _deposit(client, other_account_id)

    by_account = client.get(MOVEMENTS, params={"account_id": account_id}).json()
    assert len(by_account) == 2

    by_type = client.get(MOVEMENTS, params={"type": "deposit"}).json()
    assert len(by_type) == 2

    both = client.get(MOVEMENTS, params={"account_id": account_id, "type": "deposit"}).json()
    assert len(both) == 1


def test_filters_by_date_range(client: TestClient, account_id: int) -> None:
    _deposit(client, account_id, occurred_at="2026-01-15T10:00:00+00:00")
    _deposit(client, account_id, occurred_at="2026-06-15T10:00:00+00:00")

    listed = client.get(
        MOVEMENTS,
        params={
            "occurred_from": "2026-06-01T00:00:00+00:00",
            "occurred_to": "2026-12-31T00:00:00+00:00",
        },
    ).json()
    assert len(listed) == 1
    assert listed[0]["occurred_at"].startswith("2026-06-15")


def test_another_owners_movements_are_never_listed(
    client: TestClient, account_id: int, session: Session
) -> None:
    _deposit(client, account_id)
    foreign = Account(name="Not mine", type="bank", currency="EUR", owner_id=2)
    session.add(foreign)
    session.flush()
    session.add(
        Movement(
            occurred_at=datetime(2026, 3, 1, tzinfo=UTC),
            account_id=foreign.id,
            type="deposit",
            quantity=Decimal("9999"),
            currency="EUR",
            source="manual",
        )
    )
    session.commit()

    listed = client.get(MOVEMENTS, params={"include_voided": True}).json()
    assert len(listed) == 1
    assert listed[0]["account_id"] == account_id
