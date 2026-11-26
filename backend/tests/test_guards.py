"""Access code and usage limits for the public demo."""

from typing import Any

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.core.limits import Limit, RateLimiter

CAMPAIGN: dict[str, Any] = {
    "name": "New parents",
    "keywords": ["baby"],
    "life_events": ["new_baby"],
    "sources": ["sample"],
}


def use_settings(client: TestClient, **changes: Any) -> None:
    settings: Settings = get_settings().model_copy(update=changes)
    client.app.dependency_overrides[get_settings] = lambda: settings  # type: ignore[attr-defined]


# ---- access code ------------------------------------------------------------------


def test_no_code_configured_means_open(client: TestClient) -> None:
    assert client.get("/api/campaigns").status_code == 200
    assert client.get("/api/meta").json()["access_code_required"] is False


def test_code_required_when_configured(client: TestClient) -> None:
    use_settings(client, access_code=SecretStr("open-sesame"))

    missing = client.get("/api/campaigns")
    assert missing.status_code == 401
    assert missing.json()["detail"] == "Access code required"

    wrong = client.get("/api/campaigns", headers={"X-Access-Code": "nope"})
    assert wrong.status_code == 401
    assert wrong.json()["detail"] == "Wrong access code"

    ok = client.get("/api/campaigns", headers={"X-Access-Code": "open-sesame"})
    assert ok.status_code == 200


def test_health_and_meta_stay_open(client: TestClient) -> None:
    use_settings(client, access_code=SecretStr("open-sesame"))
    assert client.get("/api/health").status_code == 200
    meta = client.get("/api/meta")
    assert meta.status_code == 200
    assert meta.json()["access_code_required"] is True
    assert "open-sesame" not in meta.text


def test_guessing_the_code_is_limited(client: TestClient) -> None:
    use_settings(client, access_code=SecretStr("open-sesame"))
    codes = [
        client.get("/api/campaigns", headers={"X-Access-Code": f"g{i}"}).status_code
        for i in range(11)
    ]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


# ---- usage limits -----------------------------------------------------------------


def test_searches_are_limited_per_client(client: TestClient) -> None:
    use_settings(client, searches_per_hour=2)
    campaign_id = client.post("/api/campaigns", json=CAMPAIGN).json()["id"]

    statuses = [client.post(f"/api/campaigns/{campaign_id}/runs").status_code for _ in range(3)]

    assert statuses == [202, 202, 429]
    blocked = client.post(f"/api/campaigns/{campaign_id}/runs")
    assert int(blocked.headers["Retry-After"]) > 0
    assert "Limit reached" in blocked.json()["detail"]


def test_total_daily_limit_applies_to_everyone(client: TestClient) -> None:
    use_settings(client, searches_per_hour=100, searches_per_day_total=1)
    campaign_id = client.post("/api/campaigns", json=CAMPAIGN).json()["id"]

    assert client.post(f"/api/campaigns/{campaign_id}/runs").status_code == 202
    blocked = client.post(f"/api/campaigns/{campaign_id}/runs")
    assert blocked.status_code == 429
    assert "daily limit" in blocked.json()["detail"]


def test_ai_actions_are_limited(client: TestClient) -> None:
    use_settings(client, ai_actions_per_hour=1)
    # Post 999 doesn't exist, but the limit is checked before the work starts.
    assert client.post("/api/posts/999/analyze").status_code == 404
    assert client.post("/api/posts/999/analyze").status_code == 429


def test_window_slides() -> None:
    now = [0.0]
    limiter = RateLimiter(clock=lambda: now[0])
    limit = Limit("x", 2, 60)

    assert limiter.hit(limit, "a") is None
    assert limiter.hit(limit, "a") is None
    assert limiter.hit(limit, "a") == 60
    assert limiter.hit(limit, "b") is None  # other clients are counted separately
    now[0] = 61
    assert limiter.hit(limit, "a") is None


def test_zero_switches_a_limit_off() -> None:
    limiter = RateLimiter()
    assert all(limiter.hit(Limit("x", 0, 60), "a") is None for _ in range(100))
