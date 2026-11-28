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

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.ai.client import AIError, StructuredLLM
from app.connectors.base import ConnectorError, NormalizedPost
from app.connectors.registry import ConnectorFactory, get_connector
from app.db.enums import DraftStatus, OutreachRecommendation, Platform, RunStatus
from app.db.models import Campaign, Draft, Post, PostAnalysis, SearchRun
from app.services.blocklist import drop_blocked
from app.services.drafts import generate_drafts
from app.services.triage import triage_posts

logger = logging.getLogger(__name__)

POSTS_PER_KEYWORD = 25


def create_run(db: Session, campaign: Campaign) -> SearchRun:
    run = SearchRun(campaign_id=campaign.id, status=RunStatus.QUEUED)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def execute_run(
    db: Session,
    run_id: int,
    connector_factory: ConnectorFactory = get_connector,
    ai: StructuredLLM | None = None,
    triage_model: str = "",
    draft_model: str = "",
    predraft_limit: int = 0,
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
            fresh = drop_repeated_text(db, campaign.id, drop_blocked(db, posts))
            new = _store(db, campaign.id, run.id, fresh)
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
    run.error = "All sources failed." if all_failed else None
    db.commit()  # posts are visible from here on; AI results appear as they finish

    if not all_failed:
        _triage_run_posts(db, run, ai, triage_model)
        if ai is not None and predraft_limit > 0:
            _predraft(db, run, ai, draft_model, predraft_limit)

    # "completed" only once sorting and drafting are done, so the UI knows when to stop waiting.
    run.status = RunStatus.FAILED if all_failed else RunStatus.COMPLETED
    run.finished_at = datetime.now(UTC)
    db.commit()
    return run


def _triage_run_posts(db: Session, run: SearchRun, ai: StructuredLLM | None, model: str) -> None:
    """Analyse this campaign's posts that have no analysis yet."""
    if ai is None:
        run.triage_error = "AI triage is not configured (no AI API key)."
        return
    pending = db.scalars(
        select(Post)
        .where(Post.campaign_id == run.campaign_id, ~Post.analysis.has())
        .order_by(Post.posted_at.desc())
    ).all()
    try:
        run.posts_analyzed = triage_posts(db, pending, ai, model)
    except AIError as exc:
        logger.warning("Triage failed for run %s: %s", run.id, exc)
        run.triage_error = str(exc)


def _predraft(db: Session, run: SearchRun, ai: StructuredLLM, model: str, limit: int) -> None:
    """Write replies for the most relevant posts now, so they're ready when someone opens them.

    Only posts the triage says may be contacted, best first. A failure on one post
    doesn't stop the others; the reviewer can still ask for drafts on demand.
    """
    candidates = db.scalars(
        select(Post)
        .join(Post.analysis)
        .where(
            Post.campaign_id == run.campaign_id,
            PostAnalysis.recommendation != OutreachRecommendation.DO_NOT_CONTACT,
            ~Post.drafts.any(Draft.status == DraftStatus.SUGGESTED),
        )
        .order_by(PostAnalysis.relevance.desc(), Post.posted_at.desc())
        .limit(limit)
    ).all()
    for post in candidates:
        try:
            generate_drafts(db, post, ai, model)
            run.posts_drafted += 1
            db.commit()
        except AIError as exc:
            logger.warning("Pre-drafting failed for post %s: %s", post.id, exc)
            db.rollback()


def _collect(
    platform: Platform, campaign: Campaign, connector_factory: ConnectorFactory
) -> list[NormalizedPost]:
    connector = connector_factory(platform)
    unique: dict[str, NormalizedPost] = {}
    for keyword in campaign.keywords:
        for post in connector.search(keyword, limit=POSTS_PER_KEYWORD, language=campaign.language):
            unique.setdefault(post.external_id, post)  # first keyword that matched wins
    return list(unique.values())


def _text_key(handle: str, text: str) -> tuple[str, str]:
    """Same author + same words (ignoring case and spacing) = the same message."""
    return handle.strip().lower(), " ".join(text.lower().split())


def drop_repeated_text(
    db: Session, campaign_id: int, posts: list[NormalizedPost]
) -> list[NormalizedPost]:
    """Skip posts whose author already said exactly this in another post.

    People often post the same text twice (or delete and post it again). These
    are different posts with different ids, so the id check doesn't catch them,
    but a reviewer should see the message only once.
    """
    if not posts:
        return posts
    handles = {p.author_handle for p in posts}
    seen = {
        _text_key(handle, text)
        for handle, text in db.execute(
            select(Post.author_handle, Post.text).where(
                Post.campaign_id == campaign_id, Post.author_handle.in_(handles)
            )
        )
    }
    unique: list[NormalizedPost] = []
    for post in posts:
        key = _text_key(post.author_handle, post.text)
        if key in seen:
            continue
        seen.add(key)
        unique.append(post)
    return unique


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
