"""Deleting post data: on request, when removed at the source, and after retention."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_ai, get_connector_factory
from app.connectors.base import ConnectorError, NormalizedPost
from app.db.enums import DraftStatus, Platform
from app.db.models import AuditEvent, Campaign, Draft, Post
from app.services.privacy import ensure_still_available, purge_expired
from tests.fakes import FakeLLM
from tests.test_posts_api import fake_ai


class GoneConnector:
    """A source where every post has been deleted by its author."""

    platform = Platform.SAMPLE

    def search(self, query: str, **_: object) -> list[NormalizedPost]:
        return []

    def still_available(self, external_ids: Sequence[str]) -> set[str]:
        return set()


class DownConnector(GoneConnector):
    def still_available(self, external_ids: Sequence[str]) -> set[str]:
        raise ConnectorError("Bluesky returned HTTP 503.")


def make_post(db: Session, collected_days_ago: int = 0) -> Post:
    campaign = Campaign(name="Parents", keywords=["baby"], sources=["sample"])
    post = Post(
        campaign=campaign,
        platform=Platform.SAMPLE,
        external_id="s01",
        url="sample://posts/s01",
        author_handle="maya",
        text="We brought our daughter home!",
        posted_at=datetime.now(UTC),
        drafts=[Draft(tone="warm", text="Congrats!", original_text="Congrats!", model="m")],
    )
    db.add(post)
    db.flush()
    post.created_at = datetime.now(UTC) - timedelta(days=collected_days_ago)
    db.add(AuditEvent(entity_type="post", entity_id=post.id, action="x", details={"a": "b"}))
    db.commit()
    return post


def test_retention_purge_deletes_only_old_posts_and_their_drafts(db: Session) -> None:
    old = make_post(db, collected_days_ago=31)
    old_id = old.id
    recent = make_post(db, collected_days_ago=1)

    deleted = purge_expired(db, retention_days=30)

    assert deleted == 1
    assert db.get(Post, old_id) is None
    assert db.get(Post, recent.id) is not None
    assert db.scalars(select(Draft).where(Draft.post_id == old_id)).all() == []
    events = db.scalars(select(AuditEvent).where(AuditEvent.entity_id == old_id)).all()
    assert {e.action for e in events} == {"x", "post.data_deleted"}
    assert all(e.details in ({}, {"reason": "retention"}) for e in events)  # words cleared


def test_post_removed_at_source_is_deleted(db: Session) -> None:
    post = make_post(db)
    post_id = post.id

    assert ensure_still_available(db, post, lambda platform: GoneConnector()) is False
    assert db.get(Post, post_id) is None


def test_source_outage_does_not_delete_or_block(db: Session) -> None:
    post = make_post(db)

    assert ensure_still_available(db, post, lambda platform: DownConnector()) is True
    assert db.get(Post, post.id) is not None


@pytest.fixture
def post_id(client: TestClient) -> int:
    client.app.dependency_overrides[get_ai] = lambda: FakeLLM(responder=fake_ai)  # type: ignore[attr-defined]
    campaign = client.post(
        "/api/campaigns", json={"name": "Homes", "keywords": ["house"], "sources": ["sample"]}
    ).json()
    client.post(f"/api/campaigns/{campaign['id']}/runs")
    posts = client.get(f"/api/campaigns/{campaign['id']}/posts?include_do_not_contact=true")
    return int(posts.json()["items"][0]["id"])


def test_delete_endpoint_removes_post(client: TestClient, post_id: int) -> None:
    assert client.delete(f"/api/posts/{post_id}").status_code == 204
    assert client.get(f"/api/posts/{post_id}").status_code == 404


def test_drafting_a_deleted_post_returns_410_and_removes_it(
    client: TestClient, post_id: int
) -> None:
    client.app.dependency_overrides[get_connector_factory] = lambda: lambda p: GoneConnector()  # type: ignore[attr-defined]

    response = client.post(f"/api/posts/{post_id}/drafts")

    assert response.status_code == 410
    assert client.get(f"/api/posts/{post_id}").status_code == 404


def test_approving_after_the_author_deleted_the_post_returns_410(
    client: TestClient, post_id: int, db: Session
) -> None:
    detail = client.post(f"/api/posts/{post_id}/drafts").json()
    draft_id = detail["drafts"][0]["id"]
    client.app.dependency_overrides[get_connector_factory] = lambda: lambda p: GoneConnector()  # type: ignore[attr-defined]

    response = client.post(f"/api/drafts/{draft_id}/approve")

    assert response.status_code == 410
    assert db.scalars(select(Draft).where(Draft.status == DraftStatus.APPROVED)).all() == []


def test_meta_reports_contact_and_retention(client: TestClient) -> None:
    body = client.get("/api/meta").json()

    assert body["retention_days"] == 30
    assert "contact_email" in body
