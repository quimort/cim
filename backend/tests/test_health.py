from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok() -> None:
    """The health endpoint responds 200 with status ok."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_every_route_lives_under_api() -> None:
    """Caddy forwards only /api/* to the backend; anything else hits the SPA.

    So a route outside /api (including FastAPI's default /docs and
    /openapi.json) would be unreachable in the deployed stack.
    """
    paths = [route.path for route in app.routes if hasattr(route, "path")]
    outside = [p for p in paths if not p.startswith("/api")]
    assert outside == [], f"routes unreachable through the proxy: {outside}"
