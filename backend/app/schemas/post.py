"""API shapes for posts, analyses, drafts and the audit log."""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.db.enums import (
    DraftStatus,
    LifeEvent,
    OutreachRecommendation,
    Platform,
    PostStatus,
    Sensitivity,
)


class AnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    relevance: int
    life_event: LifeEvent
    sensitivity: Sensitivity
    recommendation: OutreachRecommendation
    reason: str
    summary: str
    model: str


class DraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tone: str
    text: str
    original_text: str
    status: DraftStatus
    warnings: list[str]
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: int
    action: str
    details: dict[str, Any]
    created_at: datetime


class PostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    platform: Platform
    url: str
    author_handle: str
    author_display_name: str | None
    text: str
    language: str | None
    posted_at: datetime
    like_count: int
    reply_count: int
    repost_count: int
    matched_keyword: str | None
    is_sample: bool
    status: PostStatus
    analysis: AnalysisRead | None


class PostDetail(PostRead):
    drafts: list[DraftRead]
    audit: list[AuditEventRead] = []


class PostPage(BaseModel):
    items: list[PostRead]
    total: int


class GenerateDraftsRequest(BaseModel):
    instruction: Annotated[str | None, Field(max_length=300)] = None


class DraftUpdate(BaseModel):
    text: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class CampaignStats(BaseModel):
    total_posts: int
    by_status: dict[str, int]
    by_life_event: dict[str, int]
    by_recommendation: dict[str, int]
