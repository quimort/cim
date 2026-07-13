"""Guards on the enriched OpenAPI metadata (app intro, tags, error responses,
request examples, field descriptions). Behavioural tests live elsewhere; this
file only checks that the documentation exists — not that it's phrased well.
"""

from fastapi.testclient import TestClient

_EXPECTED_TAGS = {
    "health",
    "accounts",
    "asset-classes",
    "categories",
    "instruments",
    "movements",
    "positions",
    "net-worth",
    "allocation",
}


def test_app_has_a_description(client: TestClient) -> None:
    spec = client.get("/api/openapi.json").json()
    assert len(spec["info"]["description"]) > 100


def test_every_tag_is_documented(client: TestClient) -> None:
    spec = client.get("/api/openapi.json").json()
    tags = {tag["name"]: tag["description"] for tag in spec["tags"]}
    assert set(tags) == _EXPECTED_TAGS
    assert all(len(description) > 10 for description in tags.values())


def test_movement_delete_documents_its_error_responses(client: TestClient) -> None:
    spec = client.get("/api/openapi.json").json()
    responses = spec["paths"]["/api/movements/{movement_id}"]["delete"]["responses"]
    assert "404" in responses
    assert "409" in responses
    for code in ("404", "409"):
        ref = responses[code]["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith("ErrorDetail")


def test_asset_classes_get_documents_404(client: TestClient) -> None:
    spec = client.get("/api/openapi.json").json()
    responses = spec["paths"]["/api/asset-classes/{code}"]["get"]["responses"]
    assert "404" in responses


def test_create_movement_has_selectable_examples(client: TestClient) -> None:
    spec = client.get("/api/openapi.json").json()
    body = spec["paths"]["/api/movements"]["post"]["requestBody"]["content"]["application/json"]
    examples = body["examples"]
    assert {"purchase", "deposit", "dividend", "fee"} <= set(examples)
    assert examples["deposit"]["value"]["type"] == "deposit"


def test_create_transfer_has_an_example(client: TestClient) -> None:
    spec = client.get("/api/openapi.json").json()
    body = spec["paths"]["/api/movements/transfer"]["post"]["requestBody"]["content"][
        "application/json"
    ]
    assert "transfer" in body["examples"]


def test_field_descriptions_are_present(client: TestClient) -> None:
    spec = client.get("/api/openapi.json").json()
    schemas = spec["components"]["schemas"]

    quantity = schemas["MovementCreate"]["properties"]["quantity"]
    assert "description" in quantity

    currency = schemas["AccountCreate"]["properties"]["currency"]
    assert "description" in currency
