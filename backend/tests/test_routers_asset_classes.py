import pytest
from fastapi.testclient import TestClient

ASSET_CLASSES = "/api/asset-classes"


def test_lists_the_three_seeded_classes_in_sort_order(client: TestClient) -> None:
    response = client.get(ASSET_CLASSES)
    assert response.status_code == 200
    assert [row["code"] for row in response.json()] == ["tradable", "cash", "loan"]


def test_read_shape(client: TestClient) -> None:
    tradable = client.get(f"{ASSET_CLASSES}/tradable")
    assert tradable.status_code == 200
    assert tradable.json()["label"] == "Tradable"
    assert tradable.json()["sort_order"] == 1


def test_unknown_code_is_404(client: TestClient) -> None:
    assert client.get(f"{ASSET_CLASSES}/real_estate").status_code == 404


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("post", ASSET_CLASSES),
        ("patch", f"{ASSET_CLASSES}/tradable"),
        ("delete", f"{ASSET_CLASSES}/tradable"),
    ],
)
def test_asset_classes_are_read_only(client: TestClient, method: str, url: str) -> None:
    """An asset class is the valuation dispatch key: a new one needs Python, not a POST."""
    assert getattr(client, method)(url).status_code == 405
