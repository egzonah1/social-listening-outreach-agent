"""CSV export of approved replies."""

import csv
import io
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent
from app.services.export import COLUMNS, safe_cell
from tests.test_campaigns_api import create
from tests.test_posts_api import campaign_with_posts  # noqa: F401  (shared fixture)


def rows(response_text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(response_text.lstrip("﻿"))))


def test_export_holds_only_approved_replies(
    client: TestClient,
    db: Session,
    campaign_with_posts: dict[str, Any],  # noqa: F811
) -> None:
    cid = campaign_with_posts["campaign"]["id"]
    post = client.get(f"/api/campaigns/{cid}/posts").json()["items"][0]
    drafts = client.post(f"/api/posts/{post['id']}/drafts").json()["drafts"]
    client.patch(f"/api/drafts/{drafts[0]['id']}", json={"text": "=Congrats, neighbour!"})
    client.post(f"/api/drafts/{drafts[0]['id']}/approve")

    response = client.get(f"/api/campaigns/{cid}/export.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="approved-replies-campaign-' in response.headers["content-disposition"]
    assert response.headers["x-row-count"] == "1"
    assert response.text.startswith("﻿")
    [row] = rows(response.text)
    assert list(row) == COLUMNS
    assert row["approved_reply"] == "'=Congrats, neighbour!"  # can't run as a formula
    assert row["post_url"] == post["url"]
    assert row["life_event"] == "home_purchase"
    assert row["post_status"] == "approved"
    assert post["text"] not in response.text  # the person's own words are not exported
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "campaign.exported")).one()
    assert event.details == {"replies": 1}


def test_export_with_nothing_approved_has_only_the_header(client: TestClient) -> None:
    campaign = create(client, name="Empty")
    response = client.get(f"/api/campaigns/{campaign['id']}/export.csv")
    assert response.status_code == 200
    assert rows(response.text) == []
    assert client.get("/api/campaigns/999999/export.csv").status_code == 404


def test_safe_cell_neutralises_formulas() -> None:
    assert safe_cell("=1+1") == "'=1+1"
    assert safe_cell("@maya") == "'@maya"
    assert safe_cell("Congrats!") == "Congrats!"
