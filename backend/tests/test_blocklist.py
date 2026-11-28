"""The do-not-contact list: blocking deletes an author's posts and keeps them out of searches."""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, BlockedAuthor, Post
from app.services.blocklist import normalize_handle
from tests.test_campaigns_api import create

BABY: dict[str, Any] = {"keywords": ["#newbaby", "baby"], "life_events": ["new_baby"]}


def run_search(client: TestClient, campaign_id: int) -> dict[str, Any]:
    started = client.post(f"/api/campaigns/{campaign_id}/runs").json()
    run: dict[str, Any] = client.get(f"/api/runs/{started['id']}").json()
    return run


def handles(db: Session) -> set[str]:
    return set(db.scalars(select(Post.author_handle)))


def test_handles_are_normalized() -> None:
    assert normalize_handle("  @Maya.Sample ") == "maya.sample"


def test_blocking_from_a_post_deletes_the_authors_posts_in_every_campaign(
    client: TestClient, db: Session
) -> None:
    first = create(client, name="Parents", **BABY)
    second = create(client, name="Parents again", **BABY)
    run_search(client, first["id"])
    run_search(client, second["id"])
    maya = db.scalars(select(Post).where(Post.author_handle == "maya.sample")).all()
    assert len(maya) == 2  # same post, once per campaign

    response = client.post(f"/api/posts/{maya[0].id}/block-author", json={"reason": "Asked by DM"})

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["posts_deleted"] == 2
    assert body["blocked"]["author_handle"] == "maya.sample"
    assert body["blocked"]["reason"] == "Asked by DM"
    assert "maya.sample" not in handles(db)
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "author.blocked")).one()
    assert event.details == {"platform": "sample", "posts_deleted": 2}  # no handle in the log


def test_blocked_author_is_skipped_by_later_searches(client: TestClient, db: Session) -> None:
    campaign = create(client, **BABY)
    added = client.post(
        "/api/blocked-authors", json={"platform": "sample", "author_handle": "@Maya.Sample"}
    )
    assert added.status_code == 201
    assert added.json()["posts_deleted"] == 0

    run = run_search(client, campaign["id"])

    assert run["posts_new"] > 0
    assert "maya.sample" not in handles(db)


def test_blocking_twice_keeps_one_entry_and_unblock_removes_it(
    client: TestClient, db: Session
) -> None:
    for _ in range(2):
        client.post(
            "/api/blocked-authors", json={"platform": "sample", "author_handle": "maya.sample"}
        )
    listed = client.get("/api/blocked-authors").json()
    assert len(listed) == 1

    assert client.delete(f"/api/blocked-authors/{listed[0]['id']}").status_code == 204
    assert client.get("/api/blocked-authors").json() == []
    assert db.scalars(select(BlockedAuthor)).all() == []
    assert client.delete(f"/api/blocked-authors/{listed[0]['id']}").status_code == 404


def test_block_unknown_post_is_404(client: TestClient) -> None:
    assert client.post("/api/posts/999999/block-author").status_code == 404


def test_invalid_block_request_is_rejected(client: TestClient) -> None:
    bad = client.post("/api/blocked-authors", json={"platform": "twitter", "author_handle": "x"})
    assert bad.status_code == 422
    empty = client.post("/api/blocked-authors", json={"platform": "sample", "author_handle": " "})
    assert empty.status_code == 422
