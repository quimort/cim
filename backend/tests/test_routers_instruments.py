import pytest
from fastapi.testclient import TestClient

INSTRUMENTS = "/api/instruments"


def _create(client: TestClient, **overrides: object) -> dict:
    body = {"name": "Vanguard FTSE All-World", "asset_class": "tradable", "currency": "EUR"}
    body.update(overrides)
    response = client.post(INSTRUMENTS, json=body)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize("asset_class", ["tradable", "cash", "loan"])
def test_create_each_asset_class(client: TestClient, asset_class: str) -> None:
    instrument = _create(client, name=f"An {asset_class}", asset_class=asset_class)
    assert instrument["asset_class"] == asset_class


def test_a_loan_defaults_to_active(client: TestClient) -> None:
    assert _create(client, name="Loan to Ana", asset_class="loan")["status"] == "active"


def test_expected_interest_round_trips_as_a_string(client: TestClient) -> None:
    """Money and rates leave as JSON strings, never as floats."""
    instrument = _create(
        client, name="Loan to Ana", asset_class="loan", expected_interest="0.055000"
    )
    assert instrument["expected_interest"] == "0.055000"


def test_expected_interest_as_a_json_float_is_rejected(client: TestClient) -> None:
    response = client.post(
        INSTRUMENTS,
        json={
            "name": "Loan to Ana",
            "asset_class": "loan",
            "currency": "EUR",
            "expected_interest": 0.055,
        },
    )
    assert response.status_code == 422


def test_loan_fields_on_a_non_loan_are_rejected_at_create(client: TestClient) -> None:
    """The schema can see this one: asset_class is in the same payload."""
    response = client.post(
        INSTRUMENTS,
        json={
            "name": "VWCE",
            "asset_class": "tradable",
            "currency": "EUR",
            "maturity_date": "2030-01-01",
        },
    )
    assert response.status_code == 422


def test_loan_fields_on_a_stored_non_loan_are_rejected_at_patch(client: TestClient) -> None:
    """The schema cannot see this one — asset_class is immutable and lives in the DB,
    so only the service can catch it."""
    instrument = _create(client)
    response = client.patch(
        f"{INSTRUMENTS}/{instrument['id']}", json={"maturity_date": "2030-01-01"}
    )
    assert response.status_code == 422
    assert "asset_class=loan" in response.json()["detail"]


def test_patch_loan_fields_on_an_actual_loan_is_allowed(client: TestClient) -> None:
    loan = _create(client, name="Loan to Ana", asset_class="loan")
    response = client.patch(f"{INSTRUMENTS}/{loan['id']}", json={"status": "repaid"})
    assert response.status_code == 200
    assert response.json()["status"] == "repaid"


def test_asset_class_filter(client: TestClient) -> None:
    _create(client, name="VWCE", asset_class="tradable")
    _create(client, name="EUR cash", asset_class="cash")

    listed = client.get(INSTRUMENTS, params={"asset_class": "cash"}).json()
    assert [i["name"] for i in listed] == ["EUR cash"]


def test_unknown_asset_class_filter_is_422(client: TestClient) -> None:
    assert client.get(INSTRUMENTS, params={"asset_class": "nonsense"}).status_code == 422


def test_inactive_instruments_are_hidden_unless_requested(client: TestClient) -> None:
    instrument = _create(client)
    client.patch(f"{INSTRUMENTS}/{instrument['id']}", json={"is_active": False})

    assert client.get(INSTRUMENTS).json() == []
    assert len(client.get(INSTRUMENTS, params={"include_inactive": True}).json()) == 1


def test_get_unknown_instrument_is_404(client: TestClient) -> None:
    assert client.get(f"{INSTRUMENTS}/999").status_code == 404


# --- categories: the open grouping axis, orthogonal to asset_class ------------


def _create_category(client: TestClient, name: str = "ETF") -> int:
    return int(client.post("/api/categories", json={"name": name}).json()["id"])


def test_create_with_a_category(client: TestClient) -> None:
    category_id = _create_category(client)
    assert _create(client, category_id=category_id)["category_id"] == category_id


def test_category_is_optional(client: TestClient) -> None:
    assert _create(client)["category_id"] is None


def test_unknown_category_is_404(client: TestClient) -> None:
    response = client.post(
        INSTRUMENTS,
        json={"name": "VWCE", "asset_class": "tradable", "currency": "EUR", "category_id": 999},
    )
    assert response.status_code == 404


def test_an_inactive_category_takes_no_new_instruments(client: TestClient) -> None:
    category_id = _create_category(client)
    client.delete(f"/api/categories/{category_id}")

    response = client.post(
        INSTRUMENTS,
        json={
            "name": "VWCE",
            "asset_class": "tradable",
            "currency": "EUR",
            "category_id": category_id,
        },
    )
    assert response.status_code == 422


def test_patch_cannot_move_an_instrument_into_an_inactive_category(client: TestClient) -> None:
    instrument = _create(client)
    category_id = _create_category(client)
    client.delete(f"/api/categories/{category_id}")

    response = client.patch(f"{INSTRUMENTS}/{instrument['id']}", json={"category_id": category_id})
    assert response.status_code == 422


def test_patch_can_uncategorise(client: TestClient) -> None:
    category_id = _create_category(client)
    instrument = _create(client, category_id=category_id)

    response = client.patch(f"{INSTRUMENTS}/{instrument['id']}", json={"category_id": None})
    assert response.status_code == 200
    assert response.json()["category_id"] is None


def test_category_filter(client: TestClient) -> None:
    etf = _create_category(client, "ETF")
    crypto = _create_category(client, "Crypto")
    _create(client, name="VWCE", category_id=etf)
    _create(client, name="BTC", category_id=crypto)

    listed = client.get(INSTRUMENTS, params={"category_id": crypto}).json()
    assert [i["name"] for i in listed] == ["BTC"]


def test_asset_class_and_category_are_independent(client: TestClient) -> None:
    """A REIT is `tradable` (how it's valued) and `real estate` (how it's grouped)."""
    real_estate = _create_category(client, "Real estate")
    reit = _create(client, name="REIT", asset_class="tradable", category_id=real_estate)
    assert reit["asset_class"] == "tradable"
    assert reit["category_id"] == real_estate


# --- price_source / provider_ref: routing for the price batch (task 1f) -------


def test_create_with_price_source_and_provider_ref(client: TestClient) -> None:
    instrument = _create(client, price_source="yfinance", provider_ref="VWCE.DE")
    assert instrument["price_source"] == "yfinance"
    assert instrument["provider_ref"] == "VWCE.DE"


def test_pricing_fields_are_optional(client: TestClient) -> None:
    instrument = _create(client)
    assert instrument["price_source"] is None
    assert instrument["provider_ref"] is None


def test_price_source_without_provider_ref_is_rejected_at_create(client: TestClient) -> None:
    response = client.post(
        INSTRUMENTS,
        json={
            "name": "VWCE",
            "asset_class": "tradable",
            "currency": "EUR",
            "price_source": "yfinance",
        },
    )
    assert response.status_code == 422


def test_provider_ref_without_price_source_is_rejected_at_create(client: TestClient) -> None:
    response = client.post(
        INSTRUMENTS,
        json={
            "name": "VWCE",
            "asset_class": "tradable",
            "currency": "EUR",
            "provider_ref": "VWCE.DE",
        },
    )
    assert response.status_code == 422


def test_pricing_fields_on_a_non_tradable_are_rejected_at_create(client: TestClient) -> None:
    response = client.post(
        INSTRUMENTS,
        json={
            "name": "EUR cash",
            "asset_class": "cash",
            "currency": "EUR",
            "price_source": "yfinance",
            "provider_ref": "n/a",
        },
    )
    assert response.status_code == 422


def test_pricing_fields_on_a_stored_non_tradable_are_rejected_at_patch(client: TestClient) -> None:
    """asset_class is immutable and lives in the DB — only the service catches this."""
    instrument = _create(client, name="EUR cash", asset_class="cash")
    response = client.patch(
        f"{INSTRUMENTS}/{instrument['id']}",
        json={"price_source": "yfinance", "provider_ref": "n/a"},
    )
    assert response.status_code == 422
    assert "asset_class=tradable" in response.json()["detail"]


def test_patch_sets_and_clears_pricing_fields(client: TestClient) -> None:
    instrument = _create(client)

    set_response = client.patch(
        f"{INSTRUMENTS}/{instrument['id']}",
        json={"price_source": "coingecko", "provider_ref": "bitcoin"},
    )
    assert set_response.status_code == 200
    assert set_response.json()["price_source"] == "coingecko"
    assert set_response.json()["provider_ref"] == "bitcoin"

    clear_response = client.patch(
        f"{INSTRUMENTS}/{instrument['id']}",
        json={"price_source": None, "provider_ref": None},
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["price_source"] is None
    assert clear_response.json()["provider_ref"] is None


def test_patch_provider_ref_alone_leaving_inconsistent_state_is_rejected(
    client: TestClient,
) -> None:
    instrument = _create(client, price_source="yfinance", provider_ref="VWCE.DE")

    response = client.patch(f"{INSTRUMENTS}/{instrument['id']}", json={"provider_ref": None})
    assert response.status_code == 422
