from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Account

ACCOUNTS = "/api/accounts"


def _create(client: TestClient, name: str = "Broker IBKR", **overrides: object) -> dict:
    body = {"name": name, "type": "broker", "currency": "EUR", **overrides}
    response = client.post(ACCOUNTS, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_returns_201_and_normalizes_currency(client: TestClient) -> None:
    account = _create(client, currency="eur")
    assert account["currency"] == "EUR"
    assert account["is_active"] is True


def test_owner_id_never_appears_in_a_response(client: TestClient) -> None:
    """owner_id is a server-side isolation anchor, not client data."""
    assert "owner_id" not in _create(client)


def test_owner_id_in_the_request_body_is_rejected(client: TestClient) -> None:
    """extra='forbid' stops a client from choosing its own owner."""
    response = client.post(
        ACCOUNTS, json={"name": "X", "type": "broker", "currency": "EUR", "owner_id": 2}
    )
    assert response.status_code == 422


def test_duplicate_name_for_the_same_owner_is_a_conflict(client: TestClient) -> None:
    _create(client, name="Broker IBKR")
    body = {"name": "Broker IBKR", "type": "bank", "currency": "EUR"}
    assert client.post(ACCOUNTS, json=body).status_code == 409


def test_get_unknown_account_is_404(client: TestClient) -> None:
    assert client.get(f"{ACCOUNTS}/999").status_code == 404


def test_patch_renames_and_leaves_omitted_fields_untouched(client: TestClient) -> None:
    account = _create(client, name="Old name")
    response = client.patch(f"{ACCOUNTS}/{account['id']}", json={"name": "New name"})
    assert response.status_code == 200
    assert response.json()["name"] == "New name"
    assert response.json()["type"] == account["type"]


def test_patch_cannot_change_currency(client: TestClient) -> None:
    account = _create(client)
    response = client.patch(f"{ACCOUNTS}/{account['id']}", json={"currency": "USD"})
    assert response.status_code == 422


def test_deactivated_accounts_are_hidden_unless_requested(client: TestClient) -> None:
    account = _create(client)
    client.patch(f"{ACCOUNTS}/{account['id']}", json={"is_active": False})

    assert client.get(ACCOUNTS).json() == []
    listed = client.get(ACCOUNTS, params={"include_inactive": True}).json()
    assert [a["id"] for a in listed] == [account["id"]]


def test_another_owners_account_is_invisible(client: TestClient, session: Session) -> None:
    """The isolation guarantee: not merely forbidden, but indistinguishable from absent.

    A 403 here would confirm the row exists.
    """
    foreign = Account(name="Not mine", type="bank", currency="EUR", owner_id=2)
    session.add(foreign)
    session.commit()

    assert client.get(ACCOUNTS).json() == []
    assert client.get(f"{ACCOUNTS}/{foreign.id}").status_code == 404
    assert client.patch(f"{ACCOUNTS}/{foreign.id}", json={"name": "Mine now"}).status_code == 404
