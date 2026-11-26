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
