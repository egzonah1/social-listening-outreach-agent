"""Database tables.

    campaigns ─┬─< search_runs
               └─< posts ─┬── post_analyses   (one per post, written by AI triage)
                          └─< drafts          (reply suggestions, edited by a person)
    audit_events                              (append-only log of who did what)

`─<` means one-to-many. Deleting a campaign deletes its runs, posts,
analyses and drafts (ON DELETE CASCADE), which also serves data retention.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.enums import (
    DraftStatus,
    LifeEvent,
    OutreachRecommendation,
    Platform,
    PostStatus,
    RunStatus,
    Sensitivity,
)


def str_enum(enum_cls: type[StrEnum], length: int = 32) -> SAEnum:
    """Store a Python enum as its string value in a VARCHAR column."""
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
    )


class Campaign(TimestampMixin, Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    # Lists are stored as JSON: simple, portable, and we never query inside them.
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    life_events: Mapped[list[str]] = mapped_column(JSON, default=list)
    sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    language: Mapped[str | None] = mapped_column(String(8))  # e.g. "en"

    runs: Mapped[list["SearchRun"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", passive_deletes=True
    )
    posts: Mapped[list["Post"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", passive_deletes=True
    )


class SearchRun(TimestampMixin, Base):
    """One execution of a campaign's search across its sources."""

    __tablename__ = "search_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[RunStatus] = mapped_column(str_enum(RunStatus), default=RunStatus.QUEUED)
    # Per-source results, e.g. {"bluesky": {"found": 40, "new": 12, "error": null}}
    source_stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    posts_found: Mapped[int] = mapped_column(Integer, default=0)
    posts_new: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    campaign: Mapped[Campaign] = relationship(back_populates="runs")


class Post(TimestampMixin, Base):
    """A public post collected from a source, plus where it is in review."""

    __tablename__ = "posts"
    # The same post can't be stored twice for one campaign (de-duplication).
    __table_args__ = (UniqueConstraint("campaign_id", "platform", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    search_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("search_runs.id", ondelete="SET NULL")
    )
    platform: Mapped[Platform] = mapped_column(str_enum(Platform))
    external_id: Mapped[str] = mapped_column(String(512))  # the platform's own id / URI
    url: Mapped[str] = mapped_column(String(1024))
    author_handle: Mapped[str] = mapped_column(String(255))
    author_display_name: Mapped[str | None] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(16))
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, default=0)
    repost_count: Mapped[int] = mapped_column(Integer, default=0)
    matched_keyword: Mapped[str | None] = mapped_column(String(255))
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[PostStatus] = mapped_column(
        str_enum(PostStatus), default=PostStatus.NEW, index=True
    )

    campaign: Mapped[Campaign] = relationship(back_populates="posts")
    analysis: Mapped["PostAnalysis | None"] = relationship(
        back_populates="post", cascade="all, delete-orphan", passive_deletes=True
    )
    drafts: Mapped[list["Draft"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Draft.id",
    )


class PostAnalysis(TimestampMixin, Base):
    """The AI triage result for one post."""

    __tablename__ = "post_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), unique=True)
    relevance: Mapped[int] = mapped_column(Integer)  # 0-100
    life_event: Mapped[LifeEvent] = mapped_column(str_enum(LifeEvent), index=True)
    sensitivity: Mapped[Sensitivity] = mapped_column(str_enum(Sensitivity))
    recommendation: Mapped[OutreachRecommendation] = mapped_column(str_enum(OutreachRecommendation))
    reason: Mapped[str] = mapped_column(Text)  # why the model decided this, shown to the user
    summary: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(64))  # which Claude model produced it

    post: Mapped[Post] = relationship(back_populates="analysis")


class Draft(TimestampMixin, Base):
    """A suggested reply. `original_text` keeps what the AI wrote; `text` is the edited version."""

    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    tone: Mapped[str] = mapped_column(String(32))  # e.g. "warm", "helpful", "brief"
    text: Mapped[str] = mapped_column(Text)
    original_text: Mapped[str] = mapped_column(Text)
    status: Mapped[DraftStatus] = mapped_column(
        str_enum(DraftStatus), default=DraftStatus.SUGGESTED
    )
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)  # guardrail check results
    model: Mapped[str] = mapped_column(String(64))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    post: Mapped[Post] = relationship(back_populates="drafts")


class AuditEvent(Base):
    """Append-only record of important actions (draft generated, edited, approved...)."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32))  # "post", "draft", "campaign"
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(64))  # e.g. "draft.approved"
    actor: Mapped[str] = mapped_column(String(64), default="user")
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
