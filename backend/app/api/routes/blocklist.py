"""The do-not-contact list (see app/services/blocklist.py)."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import DbSession
from app.db.models import BlockedAuthor, Post
from app.schemas.blocklist import (
    BlockAuthorRequest,
    BlockedAuthorRead,
    BlockReason,
    BlockResult,
)
from app.services.blocklist import block_author, unblock_author

router = APIRouter(tags=["blocklist"])


@router.get("/blocked-authors", response_model=list[BlockedAuthorRead])
def list_blocked(db: DbSession) -> list[BlockedAuthor]:
    return list(db.scalars(select(BlockedAuthor).order_by(BlockedAuthor.id.desc())))


@router.post("/blocked-authors", response_model=BlockResult, status_code=status.HTTP_201_CREATED)
def add_blocked(payload: BlockAuthorRequest, db: DbSession) -> BlockResult:
    """Block an author by handle, e.g. after they asked by email not to be contacted."""
    entry, deleted = block_author(db, payload.platform, payload.author_handle, payload.reason)
    return BlockResult(blocked=BlockedAuthorRead.model_validate(entry), posts_deleted=deleted)


@router.post(
    "/posts/{post_id}/block-author",
    response_model=BlockResult,
    status_code=status.HTTP_201_CREATED,
)
def block_post_author(
    post_id: int, db: DbSession, payload: BlockReason | None = None
) -> BlockResult:
    """Block the author of this post. Their posts (this one included) are deleted."""
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    reason = payload.reason if payload else None
    entry, deleted = block_author(db, post.platform, post.author_handle, reason)
    return BlockResult(blocked=BlockedAuthorRead.model_validate(entry), posts_deleted=deleted)


@router.delete("/blocked-authors/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_blocked(entry_id: int, db: DbSession) -> None:
    entry = db.get(BlockedAuthor, entry_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not on the list")
    unblock_author(db, entry)
