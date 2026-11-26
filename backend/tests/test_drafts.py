from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.schemas import DraftSet, DraftVariant
from app.db.enums import (
    DraftStatus,
    LifeEvent,
    OutreachRecommendation,
    Platform,
    PostStatus,
    Sensitivity,
)
from app.db.models import AuditEvent, Campaign, Post, PostAnalysis
from app.services.drafts import (
    WorkflowError,
    approve_draft,
    edit_draft,
    generate_drafts,
    mark_replied,
    reject_draft,
)
from tests.fakes import FakeLLM


def three_drafts(schema: type, user: str) -> DraftSet:
    return DraftSet(
        variants=[
            DraftVariant(tone="warm", text="Congratulations, what wonderful news!"),
            DraftVariant(tone="helpful", text="Congrats! Sleep when the baby sleeps."),
            DraftVariant(tone="brief", text="Congratulations!"),
        ]
    )


@pytest.fixture
def post(db: Session) -> Post:
    campaign = Campaign(name="Parents", keywords=["baby"], sources=["bluesky"])
    post = Post(
        campaign=campaign,
        platform=Platform.BLUESKY,
        external_id="at://x/1",
        url="https://bsky.app/profile/x/post/1",
        author_handle="maya.bsky.social",
        text="We brought our daughter home!",
        posted_at=datetime(2026, 11, 24, tzinfo=UTC),
        analysis=PostAnalysis(
            relevance=85,
            life_event=LifeEvent.NEW_BABY,
            sensitivity=Sensitivity.LOW,
            recommendation=OutreachRecommendation.ENGAGE,
            reason="r",
            summary="s",
            model="m",
        ),
    )
    db.add(post)
    db.commit()
    return post


def test_generate_creates_three_checked_drafts(db: Session, post: Post) -> None:
    ai = FakeLLM(responder=three_drafts)

    drafts = generate_drafts(db, post, ai, model="opus", instruction="keep it short")

    assert [d.tone for d in drafts] == ["warm", "helpful", "brief"]
    assert all(d.warnings == [] for d in drafts)
    assert post.status == PostStatus.DRAFTED
    assert "character limit: 300" in ai.calls[0]["user"]
    assert "keep it short" in ai.calls[0]["user"]


def test_regenerating_replaces_only_unreviewed_drafts(db: Session, post: Post) -> None:
    ai = FakeLLM(responder=three_drafts)
    first = generate_drafts(db, post, ai, model="opus")
    approve_draft(db, first[0])

    generate_drafts(db, post, ai, model="opus")

    assert len(post.drafts) == 4  # the approved one is kept
    assert sum(d.status == DraftStatus.APPROVED for d in post.drafts) == 1


def test_full_review_workflow_is_audited(db: Session, post: Post) -> None:
    drafts = generate_drafts(db, post, FakeLLM(responder=three_drafts), model="opus")

    edit_draft(db, drafts[0], "Congratulations! Click here for a free quote")
    assert drafts[0].warnings  # guardrails re-run after a human edit
    edit_draft(db, drafts[0], "Congratulations to you both!")
    approve_draft(db, drafts[0])
    reject_draft(db, drafts[1])
    mark_replied(db, post)

    assert post.status == PostStatus.REPLIED
    actions = db.scalars(select(AuditEvent.action).order_by(AuditEvent.id)).all()
    assert actions == [
        "drafts.generated",
        "draft.edited",
        "draft.edited",
        "draft.approved",
        "draft.rejected",
        "post.replied_manually",
    ]


def test_cannot_mark_replied_without_approval(db: Session, post: Post) -> None:
    with pytest.raises(WorkflowError):
        mark_replied(db, post)


def test_cannot_edit_an_approved_draft(db: Session, post: Post) -> None:
    draft = generate_drafts(db, post, FakeLLM(responder=three_drafts), model="opus")[0]
    approve_draft(db, draft)

    with pytest.raises(WorkflowError):
        edit_draft(db, draft, "changed")
