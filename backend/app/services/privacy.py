"""Data protection: removing collected posts when they should no longer be kept.

A post's data (the post, its AI analysis and its drafts) is deleted in three cases:
- a person asks for it ("delete this post's data" in the app),
- the author deleted the post, or hid their account, at the source,
- it is older than the retention period (30 days by default).

Bluesky's developer guidelines require apps to delete content on request. The
audit log keeps a record that a deletion happened, but the details of earlier
events for that post are cleared, so no copy of the person's words remains.
"""

import argparse
import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.connectors.base import ConnectorError
from app.connectors.registry import ConnectorFactory
from app.db.models import AuditEvent, Draft, Post

logger = logging.getLogger(__name__)

DeletionReason = Literal["user_request", "removed_at_source", "retention"]


def delete_post_data(db: Session, post: Post, reason: DeletionReason) -> None:
    _delete_posts(db, [post.id], reason)
    db.commit()


def ensure_still_available(db: Session, post: Post, connector_factory: ConnectorFactory) -> bool:
    """True if the post is still public. If it is gone, deletes our copy and returns False.

    If the source can't be reached we don't block the person's work: the check is
    repeated before approval, and the retention purge catches the rest.
    """
    try:
        available = connector_factory(post.platform).still_available([post.external_id])
    except ConnectorError as exc:
        logger.warning("Could not check post %s at the source: %s", post.id, exc)
        return True
    if post.external_id in available:
        return True
    delete_post_data(db, post, "removed_at_source")
    return False


def purge_expired(db: Session, retention_days: int, now: datetime | None = None) -> int:
    """Delete every post collected more than `retention_days` ago. Returns how many."""
    cutoff = (now or datetime.now(UTC)) - timedelta(days=retention_days)
    post_ids = list(db.scalars(select(Post.id).where(Post.created_at < cutoff)))
    if post_ids:
        _delete_posts(db, post_ids, "retention")
        db.add(
            AuditEvent(
                entity_type="system",
                entity_id=0,
                action="retention.purged",
                actor="system",
                details={"posts": len(post_ids), "retention_days": retention_days},
            )
        )
    db.commit()
    return len(post_ids)


def _delete_posts(db: Session, post_ids: Sequence[int], reason: DeletionReason) -> None:
    draft_ids = list(db.scalars(select(Draft.id).where(Draft.post_id.in_(post_ids))))
    # Earlier events may hold the person's words (e.g. a regenerate instruction): clear them.
    db.execute(
        update(AuditEvent)
        .where(
            or_(
                (AuditEvent.entity_type == "post") & AuditEvent.entity_id.in_(post_ids),
                (AuditEvent.entity_type == "draft") & AuditEvent.entity_id.in_(draft_ids),
            )
        )
        .values(details={})
    )
    actor = "user" if reason == "user_request" else "system"
    db.add_all(
        AuditEvent(
            entity_type="post",
            entity_id=post_id,
            action="post.data_deleted",
            actor=actor,
            details={"reason": reason},
        )
        for post_id in post_ids
    )
    # Analyses and drafts go with the post (ON DELETE CASCADE in the database).
    db.execute(delete(Post).where(Post.id.in_(post_ids)))
    db.expire_all()


def main() -> None:
    """`python -m app.services.privacy purge` deletes expired posts (e.g. from a daily job)."""
    from app.core.config import get_settings
    from app.db.session import get_sessionmaker

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("command", choices=["purge"])
    parser.parse_args()
    settings = get_settings()
    with get_sessionmaker()() as db:
        count = purge_expired(db, settings.retention_days)
    print(f"Deleted {count} post(s) older than {settings.retention_days} days.")


if __name__ == "__main__":
    main()
