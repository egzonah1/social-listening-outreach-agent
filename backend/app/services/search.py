"""Runs a campaign's search: every keyword on every selected source.

Design choices worth knowing:
- One failing source doesn't fail the run. Its error is stored in
  `source_stats` so the UI can say "Bluesky: rate limited" while still
  showing sample or Mastodon results. The run only fails if every source fails.
- De-duplication happens in the database with INSERT ... ON CONFLICT DO NOTHING
  on the (campaign, platform, external_id) unique constraint, so running the
  same search twice never creates duplicates, even under concurrency.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.connectors.base import ConnectorError, NormalizedPost
from app.connectors.registry import ConnectorFactory, get_connector
from app.db.enums import Platform, RunStatus
from app.db.models import Campaign, Post, SearchRun

logger = logging.getLogger(__name__)

POSTS_PER_KEYWORD = 25


def create_run(db: Session, campaign: Campaign) -> SearchRun:
    run = SearchRun(campaign_id=campaign.id, status=RunStatus.QUEUED)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def execute_run(
    db: Session, run_id: int, connector_factory: ConnectorFactory = get_connector
) -> SearchRun:
    run = db.get_one(SearchRun, run_id)
    campaign = run.campaign
    run.status = RunStatus.RUNNING
    run.started_at = datetime.now(UTC)
    db.commit()

    stats: dict[str, Any] = {}
    total_found = total_new = 0
    for source in campaign.sources:
        platform = Platform(source)
        try:
            posts = _collect(platform, campaign, connector_factory)
            new = _store(db, campaign.id, run.id, posts)
            stats[platform.value] = {"found": len(posts), "new": new, "error": None}
            total_found += len(posts)
            total_new += new
        except ConnectorError as exc:
            logger.warning("Source %s failed for run %s: %s", platform, run.id, exc)
            stats[platform.value] = {"found": 0, "new": 0, "error": str(exc)}

    all_failed = bool(stats) and all(s["error"] for s in stats.values())
    run.source_stats = stats
    run.posts_found = total_found
    run.posts_new = total_new
    run.status = RunStatus.FAILED if all_failed else RunStatus.COMPLETED
    run.error = "All sources failed." if all_failed else None
    run.finished_at = datetime.now(UTC)
    db.commit()
    return run


def _collect(
    platform: Platform, campaign: Campaign, connector_factory: ConnectorFactory
) -> list[NormalizedPost]:
    connector = connector_factory(platform)
    unique: dict[str, NormalizedPost] = {}
    for keyword in campaign.keywords:
        for post in connector.search(keyword, limit=POSTS_PER_KEYWORD, language=campaign.language):
            unique.setdefault(post.external_id, post)  # first keyword that matched wins
    return list(unique.values())


def _store(db: Session, campaign_id: int, run_id: int, posts: list[NormalizedPost]) -> int:
    """Insert posts that aren't stored yet. Returns how many were new."""
    if not posts:
        return 0
    rows = [
        {
            "campaign_id": campaign_id,
            "search_run_id": run_id,
            "platform": p.platform.value,
            "external_id": p.external_id,
            "url": p.url,
            "author_handle": p.author_handle,
            "author_display_name": p.author_display_name,
            "text": p.text,
            "language": p.language,
            "posted_at": p.posted_at,
            "like_count": p.like_count,
            "reply_count": p.reply_count,
            "repost_count": p.repost_count,
            "matched_keyword": p.matched_keyword,
            "is_sample": p.is_sample,
            "status": "new",
        }
        for p in posts
    ]
    statement = (
        insert(Post)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["campaign_id", "platform", "external_id"])
        .returning(Post.id)
    )
    inserted = db.execute(statement).scalars().all()
    db.commit()
    return len(inserted)
