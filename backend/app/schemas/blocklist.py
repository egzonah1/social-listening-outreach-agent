"""API shapes for the do-not-contact list."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.db.enums import Platform


class BlockedAuthorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: Platform
    author_handle: str
    reason: str | None
    created_at: datetime


class BlockAuthorRequest(BaseModel):
    platform: Platform
    author_handle: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None


class BlockReason(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None


class BlockResult(BaseModel):
    blocked: BlockedAuthorRead
    posts_deleted: int
