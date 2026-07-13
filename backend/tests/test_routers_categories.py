from fastapi.testclient import TestClient

CATEGORIES = "/api/categories"
INSTRUMENTS = "/api/instruments"


def _create(client: TestClient, name: str = "ETF", **overrides: object) -> dict:
    body = {"name": name, **overrides}
    response = client.post(CATEGORIES, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_returns_201(client: TestClient) -> None:
    category = _create(client, description="Exchange-traded funds")
    assert category["name"] == "ETF"
    assert category["description"] == "Exchange-traded funds"
    assert category["is_active"] is True


def test_duplicate_name_is_a_conflict(client: TestClient) -> None:
    _create(client, name="Crypto")
    assert client.post(CATEGORIES, json={"name": "Crypto"}).status_code == 409


def test_patch_renames(client: TestClient) -> None:
    category = _create(client, name="Old")
    response = client.patch(f"{CATEGORIES}/{category['id']}", json={"name": "New"})
    assert response.status_code == 200
    assert response.json()["name"] == "New"


def test_get_unknown_category_is_404(client: TestClient) -> None:
    assert client.get(f"{CATEGORIES}/999").status_code == 404


def test_delete_is_a_soft_delete(client: TestClient) -> None:
    category = _create(client)
    assert client.delete(f"{CATEGORIES}/{category['id']}").status_code == 204

    # The row survives and is still readable by id.
    fetched = client.get(f"{CATEGORIES}/{category['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["is_active"] is False

    assert client.get(CATEGORIES).json() == []
    listed = client.get(CATEGORIES, params={"include_inactive": True}).json()
    assert [c["id"] for c in listed] == [category["id"]]


def test_deleting_twice_is_a_conflict(client: TestClient) -> None:
    category = _create(client)
    client.delete(f"{CATEGORIES}/{category['id']}")
    assert client.delete(f"{CATEGORIES}/{category['id']}").status_code == 409


def test_deactivating_a_category_leaves_its_instruments_intact(client: TestClient) -> None:
    """The whole point of soft-delete: historical grouping must keep resolving."""
    category = _create(client, name="Real estate")
    instrument = client.post(
        INSTRUMENTS,
        json={
            "name": "REIT",
            "asset_class": "tradable",
            "currency": "EUR",
            "category_id": category["id"],
        },
    ).json()

    client.delete(f"{CATEGORIES}/{category['id']}")

    still_there = client.get(f"{INSTRUMENTS}/{instrument['id']}").json()
    assert still_there["category_id"] == category["id"]
