from fastapi.testclient import TestClient

from app import __version__
from app.core.config import Settings
from app.main import create_app


def test_health_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__


def test_unknown_route_returns_404() -> None:
    client = TestClient(create_app())

    response = client.get("/api/does-not-exist")

    assert response.status_code == 404


def test_database_url_from_neon_gets_the_driver_name() -> None:
    neon = "postgresql://user:pw@ep-x.eu-central-1.aws.neon.tech/neondb?sslmode=require"
    assert Settings(database_url=neon).database_url == (
        "postgresql+psycopg://user:pw@ep-x.eu-central-1.aws.neon.tech/neondb?sslmode=require"
    )
    assert Settings(database_url="postgres://u@h/d").database_url == "postgresql+psycopg://u@h/d"
    already = "postgresql+psycopg://u@h/d"
    assert Settings(database_url=already).database_url == already
