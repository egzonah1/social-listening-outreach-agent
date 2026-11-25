from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"


def test_unknown_route_returns_404() -> None:
    client = TestClient(create_app())

    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
