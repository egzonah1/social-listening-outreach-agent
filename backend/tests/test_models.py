from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.enums import (
    LifeEvent,
    OutreachRecommendation,
    Platform,
    PostStatus,
    Sensitivity,
)
from app.db.models import Campaign, Draft, Post, PostAnalysis


def make_post(campaign: Campaign, external_id: str = "at://did:plc:abc/post/1") -> Post:
    return Post(
        campaign=campaign,
        platform=Platform.BLUESKY,
        external_id=external_id,
        url="https://bsky.app/profile/someone/post/1",
        author_handle="someone.bsky.social",
        text="We just brought our daughter home from the hospital!",
        posted_at=datetime(2026, 11, 20, 9, 30, tzinfo=UTC),
    )


def test_campaign_with_post_analysis_and_draft_round_trips(db: Session) -> None:
    campaign = Campaign(name="New parents", keywords=["newborn", "#newbaby"], sources=["bluesky"])
    post = make_post(campaign)
    post.analysis = PostAnalysis(
        relevance=88,
        life_event=LifeEvent.NEW_BABY,
        sensitivity=Sensitivity.LOW,
        recommendation=OutreachRecommendation.ENGAGE,
        reason="Author describes bringing a newborn home.",
        summary="New parent celebrating a birth.",
        model="claude-haiku-5-5",
    )
    post.drafts.append(
        Draft(tone="warm", text="Congratulations!", original_text="Congratulations!", model="m")
    )
    db.add(campaign)
    db.commit()

    stored = db.scalars(select(Post)).one()
    assert stored.status == PostStatus.NEW  # default applied
    assert stored.campaign.keywords == ["newborn", "#newbaby"]  # JSON list survives
    assert stored.analysis is not None
    assert stored.analysis.life_event == LifeEvent.NEW_BABY
    assert [d.tone for d in stored.drafts] == ["warm"]
    assert stored.created_at is not None  # filled by the database


def test_same_post_cannot_be_stored_twice_in_a_campaign(db: Session) -> None:
    campaign = Campaign(name="Homebuyers")
    db.add_all([make_post(campaign), make_post(campaign)])

    with pytest.raises(IntegrityError):
        db.commit()


def test_deleting_campaign_deletes_its_posts(db: Session) -> None:
    campaign = Campaign(name="Temporary")
    db.add(make_post(campaign))
    db.commit()

    db.delete(campaign)
    db.commit()

    assert db.scalars(select(Post)).all() == []
