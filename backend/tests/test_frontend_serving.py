"""The built React app is served by FastAPI, with index.html for app routes."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def _dist(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>app</html>")
    (tmp_path / "assets" / "app-abc123.js").write_text("console.log(1)")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    return tmp_path


def test_serves_index_and_assets(tmp_path: Path) -> None:
    client = TestClient(create_app(frontend_dir=_dist(tmp_path)))

    home = client.get("/")
    assert home.status_code == 200
    assert "app" in home.text
    assert home.headers["cache-control"] == "no-cache"

    asset = client.get("/assets/app-abc123.js")
    assert asset.status_code == 200
    assert "immutable" in asset.headers["cache-control"]
    assert client.get("/favicon.svg").status_code == 200


def test_app_routes_fall_back_to_index(tmp_path: Path) -> None:
    client = TestClient(create_app(frontend_dir=_dist(tmp_path)))
    page = client.get("/campaigns/42")
    assert page.status_code == 200
    assert "app" in page.text


def test_api_routes_still_work_and_unknown_api_is_404(tmp_path: Path) -> None:
    client = TestClient(create_app(frontend_dir=_dist(tmp_path)))
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/nope").status_code == 404


def test_files_outside_dist_cannot_be_read(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    _dist(dist)
    (tmp_path / "secret.txt").write_text("secret")
    client = TestClient(create_app(frontend_dir=dist))
    response = client.get("/..%2Fsecret.txt")
    assert "secret" not in response.text


def test_no_frontend_folder_means_api_only(tmp_path: Path) -> None:
    client = TestClient(create_app(frontend_dir=tmp_path))
    assert client.get("/").status_code == 404
    assert client.get("/api/health").status_code == 200
