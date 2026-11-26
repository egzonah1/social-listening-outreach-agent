from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.ai.schemas import DraftSet, DraftVariant, PostTriage, TriageBatch
from app.api.deps import get_ai
from app.db.enums import LifeEvent, OutreachRecommendation, Sensitivity
from tests.fakes import FakeLLM
from tests.test_triage import ids_in


def fake_ai(schema: type, user: str) -> TriageBatch | DraftSet:
    if schema is TriageBatch:
        results = []
        for post_id in ids_in(user):
            grief = post_id % 2 == 0  # every second post is "grief"
            results.append(
                PostTriage(
                    post_id=post_id,
                    relevance=40 if grief else 90,
                    life_event=LifeEvent.BEREAVEMENT if grief else LifeEvent.HOME_PURCHASE,
                    sensitivity=Sensitivity.HIGH if grief else Sensitivity.LOW,
                    recommendation=OutreachRecommendation.DO_NOT_CONTACT
                    if grief
                    else OutreachRecommendation.ENGAGE,
                    reason="r",
                    summary="s",
                )
            )
        return TriageBatch(results=results)
    return DraftSet(
        variants=[
            DraftVariant(tone="warm", text="Congratulations on the new home!"),
            DraftVariant(tone="helpful", text="Congrats! Enjoy settling in."),
            DraftVariant(tone="brief", text="Congrats!"),
        ]
    )


@pytest.fixture
def campaign_with_posts(client: TestClient) -> dict[str, Any]:
    """Creates a campaign, runs it against sample data, and triages with the fake AI."""
    ai = FakeLLM(responder=fake_ai)
    client.app.dependency_overrides[get_ai] = lambda: ai  # type: ignore[attr-defined]
    campaign = client.post(
        "/api/campaigns",
        json={"name": "Homes", "keywords": ["#firsthome", "house"], "sources": ["sample"]},
    ).json()
    client.post(f"/api/campaigns/{campaign['id']}/runs")
    posts = client.get(f"/api/campaigns/{campaign['id']}/posts?include_do_not_contact=true")
    for post in posts.json()["items"]:
        client.post(f"/api/posts/{post['id']}/analyze")
    return {"campaign": campaign}


def test_inbox_hides_do_not_contact_and_sorts_by_relevance(
    client: TestClient, campaign_with_posts: dict[str, Any]
) -> None:
    cid = campaign_with_posts["campaign"]["id"]

    everything = client.get(f"/api/campaigns/{cid}/posts?include_do_not_contact=true").json()
    inbox = client.get(f"/api/campaigns/{cid}/posts").json()

    assert inbox["total"] < everything["total"]
    recs = {p["analysis"]["recommendation"] for p in inbox["items"]}
    assert "do_not_contact" not in recs
    scores = [p["analysis"]["relevance"] for p in inbox["items"]]
    assert scores == sorted(scores, reverse=True)


def test_filter_by_life_event(client: TestClient, campaign_with_posts: dict[str, Any]) -> None:
    cid = campaign_with_posts["campaign"]["id"]

    homes = client.get(f"/api/campaigns/{cid}/posts?life_event=home_purchase").json()

    assert homes["total"] > 0
    assert all(p["analysis"]["life_event"] == "home_purchase" for p in homes["items"])


def test_draft_approve_and_reply_flow(
    client: TestClient, campaign_with_posts: dict[str, Any]
) -> None:
    cid = campaign_with_posts["campaign"]["id"]
    post_id = client.get(f"/api/campaigns/{cid}/posts").json()["items"][0]["id"]

    detail = client.post(f"/api/posts/{post_id}/drafts", json={"instruction": "shorter"}).json()
    assert [d["tone"] for d in detail["drafts"]] == ["warm", "helpful", "brief"]

    draft_id = detail["drafts"][0]["id"]
    assert client.post(f"/api/posts/{post_id}/replied").status_code == 409  # not approved yet
    edited = client.patch(f"/api/drafts/{draft_id}", json={"text": "Congrats on the keys!"})
    assert edited.json()["text"] == "Congrats on the keys!"
    assert client.post(f"/api/drafts/{draft_id}/approve").json()["status"] == "approved"
    assert client.post(f"/api/drafts/{draft_id}/approve").status_code == 409  # already done

    final = client.post(f"/api/posts/{post_id}/replied").json()
    assert final["status"] == "replied"
    assert [e["action"] for e in final["audit"]][:2] == ["post.replied_manually", "draft.approved"]


def test_stats_count_posts(client: TestClient, campaign_with_posts: dict[str, Any]) -> None:
    cid = campaign_with_posts["campaign"]["id"]

    stats = client.get(f"/api/campaigns/{cid}/stats").json()

    assert stats["total_posts"] == sum(stats["by_life_event"].values())
    assert stats["by_recommendation"]["do_not_contact"] > 0


def test_drafting_without_ai_key_returns_503(client: TestClient) -> None:
    client.app.dependency_overrides[get_ai] = lambda: None  # type: ignore[attr-defined]
    campaign = client.post(
        "/api/campaigns", json={"name": "X", "keywords": ["#grief"], "sources": ["sample"]}
    ).json()
    client.post(f"/api/campaigns/{campaign['id']}/runs")
    post_id = client.get(f"/api/campaigns/{campaign['id']}/posts").json()["items"][0]["id"]

    response = client.post(f"/api/posts/{post_id}/drafts")

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]
