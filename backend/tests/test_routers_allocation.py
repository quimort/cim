from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

ALLOCATION = "/api/allocation"


@pytest.fixture
def account_id(client: TestClient) -> int:
    body = {"name": "Bank BBVA", "type": "bank", "currency": "EUR"}
    return int(client.post("/api/accounts", json=body).json()["id"])


def _deposit(client: TestClient, account_id: int, quantity: str, when: str) -> None:
    response = client.post(
        "/api/movements",
        json={
            "occurred_at": when,
            "account_id": account_id,
            "type": "deposit",
            "quantity": quantity,
            "currency": "EUR",
        },
    )
    assert response.status_code == 201, response.text


def test_defaults_to_asset_class_and_amounts_are_strings(
    client: TestClient, account_id: int
) -> None:
    _deposit(client, account_id, "1000", "2026-01-01T10:00:00+00:00")

    response = client.get(ALLOCATION)
    assert response.status_code == 200
    body = response.json()
    assert body["dimension"] == "asset_class"
    assert isinstance(body["total_eur"], str)
    [bucket] = body["buckets"]
    assert bucket["key"] == "cash"
    assert Decimal(bucket["value_eur"]) == 1000
    assert Decimal(bucket["weight"]) == 1


def test_by_account_attributes_cash_to_its_account(client: TestClient, account_id: int) -> None:
    _deposit(client, account_id, "1000", "2026-01-01T10:00:00+00:00")

    response = client.get(ALLOCATION, params={"by": "account"})
    assert response.status_code == 200
    body = response.json()
    assert body["dimension"] == "account"
    [bucket] = body["buckets"]
    assert bucket["key"] == str(account_id)
    assert Decimal(bucket["value_eur"]) == 1000


def test_past_date_query_reflects_ledger_state_on_that_day(
    client: TestClient, account_id: int
) -> None:
    _deposit(client, account_id, "1000", "2026-01-01T10:00:00+00:00")
    _deposit(client, account_id, "500", "2026-02-01T10:00:00+00:00")

    early = client.get(ALLOCATION, params={"date": "2026-01-15"})
    assert Decimal(early.json()["total_eur"]) == 1000

    later = client.get(ALLOCATION, params={"date": "2026-02-15"})
    assert Decimal(later.json()["total_eur"]) == 1500


def test_unknown_dimension_is_a_422(client: TestClient) -> None:
    response = client.get(ALLOCATION, params={"by": "zip_code"})
    assert response.status_code == 422


def test_there_is_no_write_method_on_allocation(client: TestClient) -> None:
    assert client.post(ALLOCATION, json={}).status_code == 405
