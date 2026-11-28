from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.connectors.base import ConnectorError, NormalizedPost, SourceConnector
from app.connectors.sample import SampleConnector
from app.db.enums import Platform, RunStatus
from app.db.models import Campaign, Post
from app.services.search import create_run, execute_run


class FailingConnector:
    platform = Platform.BLUESKY

    def search(self, query: str, **kwargs: object) -> list[NormalizedPost]:
        raise ConnectorError("Bluesky rate limit reached.")

    def still_available(self, external_ids: Sequence[str]) -> set[str]:
        raise ConnectorError("Bluesky rate limit reached.")


def factory(platform: Platform) -> SourceConnector:
    return FailingConnector() if platform == Platform.BLUESKY else SampleConnector()


def make_campaign(db: Session, sources: list[str]) -> Campaign:
    campaign = Campaign(name="Parents", keywords=["baby", "newbaby"], sources=sources)
    db.add(campaign)
    db.commit()
    return campaign


def test_one_failing_source_does_not_fail_the_run(db: Session) -> None:
    campaign = make_campaign(db, ["bluesky", "sample"])

    run = execute_run(db, create_run(db, campaign).id, connector_factory=factory)

    assert run.status == RunStatus.COMPLETED
    assert run.source_stats["bluesky"]["error"] == "Bluesky rate limit reached."
    assert run.source_stats["sample"]["new"] > 0
    assert run.finished_at is not None and run.finished_at <= datetime.now(UTC)


def test_run_fails_when_every_source_fails(db: Session) -> None:
    campaign = make_campaign(db, ["bluesky"])

    run = execute_run(db, create_run(db, campaign).id, connector_factory=factory)

    assert run.status == RunStatus.FAILED
    assert run.error == "All sources failed."


def test_post_matching_two_keywords_is_stored_once(db: Session) -> None:
    campaign = make_campaign(db, ["sample"])

    run = execute_run(db, create_run(db, campaign).id, connector_factory=factory)

    stored = db.scalar(select(func.count()).select_from(Post))
    assert stored == run.posts_new == run.posts_found


class RepeatingConnector:
    """An author who posted the same words twice, plus a different post."""

    platform = Platform.BLUESKY

    def search(self, query: str, **kwargs: object) -> list[NormalizedPost]:
        def post(external_id: str, text: str, handle: str = "joe.bsky.social") -> NormalizedPost:
            return NormalizedPost(
                platform=Platform.BLUESKY,
                external_id=external_id,
                url=f"https://bsky.app/{external_id}",
                author_handle=handle,
                author_display_name=None,
                text=text,
                language="en",
                posted_at=datetime.now(UTC),
                matched_keyword=query,
            )

        return [
            post("a", "We opened our  theatre!"),
            post("b", "we opened our theatre!"),  # same words, other post id
            post("c", "We opened our theatre!", handle="ana.bsky.social"),  # other author
        ]

    def still_available(self, external_ids: Sequence[str]) -> set[str]:
        return set(external_ids)


def test_same_text_from_same_author_is_stored_once(db: Session) -> None:
    campaign = make_campaign(db, ["bluesky"])

    run = execute_run(
        db, create_run(db, campaign).id, connector_factory=lambda p: RepeatingConnector()
    )
    again = execute_run(
        db, create_run(db, campaign).id, connector_factory=lambda p: RepeatingConnector()
    )

    stored = db.scalars(select(Post.external_id).order_by(Post.external_id)).all()
    assert stored == ["a", "c"]
    assert run.posts_new == 2
    assert again.posts_new == 0  # repeats are recognised in later searches too
