"""The do-not-contact list: authors who must never be contacted again.

Blocking an author deletes every post of theirs the app holds (in all
campaigns), and later searches skip them before anything is stored. This is
how a "please don't contact me" request is honoured for good, even after the
30-day retention has removed the original post.
"""

from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.connectors.base import NormalizedPost
from app.db.enums import Platform
from app.db.models import AuditEvent, BlockedAuthor, Post
from app.services.privacy import delete_posts


def normalize_handle(handle: str) -> str:
    """Handles are case-insensitive; people often type a leading @."""
    return handle.strip().lstrip("@").lower()


def block_author(
    db: Session, platform: Platform, handle: str, reason: str | None = None
) -> tuple[BlockedAuthor, int]:
    """Add the author to the list (if not there yet) and delete their posts.

    Returns the list entry and how many posts were deleted.
    """
    handle = normalize_handle(handle)
    entry = db.scalar(
        select(BlockedAuthor).where(
            BlockedAuthor.platform == platform, BlockedAuthor.author_handle == handle
        )
    )
    if entry is None:
        entry = BlockedAuthor(platform=platform, author_handle=handle, reason=reason or None)
        db.add(entry)
        db.flush()
    post_ids = list(
        db.scalars(
            select(Post.id).where(
                Post.platform == platform, func.lower(Post.author_handle) == handle
            )
        )
    )
    if post_ids:
        delete_posts(db, post_ids, "author_blocked")
    # The handle is not repeated in the log: the list entry is the only copy.
    db.add(
        AuditEvent(
            entity_type="blocked_author",
            entity_id=entry.id,
            action="author.blocked",
            details={"platform": platform.value, "posts_deleted": len(post_ids)},
        )
    )
    db.commit()
    db.refresh(entry)
    return entry, len(post_ids)


def unblock_author(db: Session, entry: BlockedAuthor) -> None:
    db.add(
        AuditEvent(
            entity_type="blocked_author",
            entity_id=entry.id,
            action="author.unblocked",
            details={"platform": entry.platform.value},
        )
    )
    db.delete(entry)
    db.commit()


def drop_blocked(db: Session, posts: Iterable[NormalizedPost]) -> list[NormalizedPost]:
    """Remove posts by blocked authors, before they are ever stored."""
    posts = list(posts)
    if not posts:
        return posts
    platforms = {p.platform for p in posts}
    blocked = {
        (row.platform, row.author_handle)
        for row in db.execute(
            select(BlockedAuthor.platform, BlockedAuthor.author_handle).where(
                BlockedAuthor.platform.in_(platforms)
            )
        )
    }
    return [p for p in posts if (p.platform, normalize_handle(p.author_handle)) not in blocked]
