from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Post

VALID: dict[str, Any] = {
    "name": "First-time homebuyers",
    "keywords": ["#firsthome", "mortgage"],
    "life_events": ["home_purchase"],
    "sources": ["sample"],
}


def create(client: TestClient, **overrides: Any) -> dict[str, Any]:
    response = client.post("/api/campaigns", json={**VALID, **overrides})
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def test_create_list_get_campaign(client: TestClient) -> None:
    created = create(client, keywords=["#firsthome", "#firsthome", "  mortgage "])

    assert created["keywords"] == ["#firsthome", "mortgage"]  # trimmed and de-duplicated
    assert created["language"] == "en"
    assert [c["id"] for c in client.get("/api/campaigns").json()] == [created["id"]]
    assert client.get(f"/api/campaigns/{created['id']}").json()["name"] == VALID["name"]


def test_invalid_campaign_is_rejected(client: TestClient) -> None:
    bad_payloads: list[dict[str, Any]] = [{"keywords": []}, {"sources": ["myspace"]}, {"name": ""}]
    for bad in bad_payloads:
        response = client.post("/api/campaigns", json={**VALID, **bad})
        assert response.status_code == 422, bad


def test_patch_changes_only_sent_fields(client: TestClient) -> None:
    created = create(client)

    response = client.patch(f"/api/campaigns/{created['id']}", json={"name": "Renamed"})

    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"
    assert response.json()["keywords"] == created["keywords"]


def test_delete_and_missing_campaign(client: TestClient) -> None:
    created = create(client)

    assert client.delete(f"/api/campaigns/{created['id']}").status_code == 204
    assert client.get(f"/api/campaigns/{created['id']}").status_code == 404
    assert client.delete(f"/api/campaigns/{created['id']}").status_code == 404


def test_deleting_a_campaign_deletes_its_posts_and_clears_their_history(
    client: TestClient, db: Session
) -> None:
    campaign = create(client)
    client.post(f"/api/campaigns/{campaign['id']}/runs")
    post_ids = list(db.scalars(select(Post.id).where(Post.campaign_id == campaign["id"])))
    assert post_ids
    db.add(AuditEvent(entity_type="post", entity_id=post_ids[0], action="x", details={"a": "b"}))
    db.commit()

    assert client.delete(f"/api/campaigns/{campaign['id']}").status_code == 204

    assert db.scalars(select(Post).where(Post.id.in_(post_ids))).all() == []
    old = db.scalars(select(AuditEvent).where(AuditEvent.action == "x")).one()
    assert old.details == {}  # the person's words are gone from the history too
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "campaign.deleted")).one()
    assert event.details == {"posts": len(post_ids)}


def test_run_collects_posts_and_reports_progress(client: TestClient) -> None:
    campaign = create(client)

    started = client.post(f"/api/campaigns/{campaign['id']}/runs")
    assert started.status_code == 202
    assert started.json()["status"] == "queued"

    # TestClient runs background tasks before returning, so the run is finished now.
    run = client.get(f"/api/runs/{started.json()['id']}").json()
    assert run["status"] == "completed"
    assert run["posts_new"] > 0
    assert run["source_stats"]["sample"]["error"] is None

    second = client.post(f"/api/campaigns/{campaign['id']}/runs").json()
    again = client.get(f"/api/runs/{second['id']}").json()
    assert again["posts_found"] == run["posts_found"]
    assert again["posts_new"] == 0  # nothing stored twice
