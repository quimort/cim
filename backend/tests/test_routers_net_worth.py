from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

NET_WORTH = "/api/net-worth"
SERIES = "/api/net-worth/series"


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


def test_net_worth_amounts_are_strings(client: TestClient, account_id: int) -> None:
    _deposit(client, account_id, "1000", "2026-01-01T10:00:00+00:00")

    response = client.get(NET_WORTH)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["total_eur"], str)
    assert Decimal(body["total_eur"]) == 1000
    assert Decimal(body["items"][0]["value_eur"]) == 1000


def test_past_date_query_reflects_ledger_state_on_that_day(
    client: TestClient, account_id: int
) -> None:
    """The ledger's payoff: an old ?date= answers with the total back then."""
    _deposit(client, account_id, "1000", "2026-01-01T10:00:00+00:00")
    _deposit(client, account_id, "500", "2026-02-01T10:00:00+00:00")

    early = client.get(NET_WORTH, params={"date": "2026-01-15"})
    assert Decimal(early.json()["total_eur"]) == 1000

    later = client.get(NET_WORTH, params={"date": "2026-02-15"})
    assert Decimal(later.json()["total_eur"]) == 1500


def test_series_defaults_to_monthly_and_includes_the_final_point(
    client: TestClient, account_id: int
) -> None:
    _deposit(client, account_id, "1000", "2026-01-01T10:00:00+00:00")

    response = client.get(SERIES, params={"to": "2026-03-01"})
    assert response.status_code == 200
    body = response.json()
    assert body["interval"] == "month"
    assert body["points"][-1]["as_of"] == "2026-03-01"
    assert Decimal(body["points"][-1]["total_eur"]) == 1000


def test_series_from_after_to_is_a_422(client: TestClient, account_id: int) -> None:
    _deposit(client, account_id, "1000", "2026-01-01T10:00:00+00:00")
    response = client.get(SERIES, params={"from": "2026-02-01", "to": "2026-01-01"})
    assert response.status_code == 422


def test_series_rejects_an_unknown_interval(client: TestClient, account_id: int) -> None:
    response = client.get(SERIES, params={"interval": "fortnight"})
    assert response.status_code == 422


def test_there_is_no_write_method_on_net_worth(client: TestClient) -> None:
    assert client.post(NET_WORTH, json={}).status_code == 405
    assert client.post(SERIES, json={}).status_code == 405
