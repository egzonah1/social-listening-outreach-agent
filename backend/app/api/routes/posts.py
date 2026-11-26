"""Reviewing posts and working with reply drafts."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.ai.client import AIError, StructuredLLM
from app.api.deps import DbSession, get_ai
from app.core.config import Settings, get_settings
from app.db.enums import LifeEvent, OutreachRecommendation, Platform, PostStatus, Sensitivity
from app.db.models import AuditEvent, Campaign, Draft, Post, PostAnalysis
from app.schemas.post import (
    AuditEventRead,
    CampaignStats,
    DraftRead,
    DraftUpdate,
    GenerateDraftsRequest,
    PostDetail,
    PostPage,
    PostRead,
)
from app.services import drafts as workflow
from app.services.drafts import WorkflowError
from app.services.triage import triage_posts

router = APIRouter(tags=["posts"])

AI = Annotated[StructuredLLM | None, Depends(get_ai)]
AppSettings = Annotated[Settings, Depends(get_settings)]


# ---- helpers -----------------------------------------------------------------


def _post_or_404(db: DbSession, post_id: int) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    return post


def _draft_or_404(db: DbSession, draft_id: int) -> Draft:
    draft = db.get(Draft, draft_id)
    if draft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Draft not found")
    return draft


def _require_ai(ai: StructuredLLM | None) -> StructuredLLM:
    if ai is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "AI is not configured on the server."
        )
    return ai


def _detail(db: DbSession, post: Post) -> PostDetail:
    draft_ids = [d.id for d in post.drafts]
    events = db.scalars(
        select(AuditEvent)
        .where(
            or_(
                (AuditEvent.entity_type == "post") & (AuditEvent.entity_id == post.id),
                (AuditEvent.entity_type == "draft") & AuditEvent.entity_id.in_(draft_ids),
            )
        )
        .order_by(AuditEvent.id.desc())
    ).all()
    detail = PostDetail.model_validate(post)
    detail.audit = [AuditEventRead.model_validate(e) for e in events]
    return detail


# ---- posts -------------------------------------------------------------------


@router.get("/campaigns/{campaign_id}/posts", response_model=PostPage)
def list_posts(
    campaign_id: int,
    db: DbSession,
    life_event: LifeEvent | None = None,
    sensitivity: Sensitivity | None = None,
    post_status: Annotated[PostStatus | None, Query(alias="status")] = None,
    platform: Platform | None = None,
    include_do_not_contact: bool = False,
    sort: Literal["relevance", "newest"] = "relevance",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PostPage:
    """The review inbox. 'Do not contact' posts are hidden unless asked for."""
    if db.get(Campaign, campaign_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    query = select(Post).outerjoin(PostAnalysis).where(Post.campaign_id == campaign_id)
    if life_event:
        query = query.where(PostAnalysis.life_event == life_event)
    if sensitivity:
        query = query.where(PostAnalysis.sensitivity == sensitivity)
    if post_status:
        query = query.where(Post.status == post_status)
    if platform:
        query = query.where(Post.platform == platform)
    if not include_do_not_contact:
        query = query.where(
            or_(
                PostAnalysis.id.is_(None),
                PostAnalysis.recommendation != OutreachRecommendation.DO_NOT_CONTACT,
            )
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    if sort == "relevance":
        query = query.order_by(PostAnalysis.relevance.desc().nulls_last(), Post.posted_at.desc())
    else:
        query = query.order_by(Post.posted_at.desc())
    posts = db.scalars(query.options(selectinload(Post.analysis)).limit(limit).offset(offset)).all()
    return PostPage(items=[PostRead.model_validate(p) for p in posts], total=total)


@router.get("/campaigns/{campaign_id}/stats", response_model=CampaignStats)
def campaign_stats(campaign_id: int, db: DbSession) -> CampaignStats:
    if db.get(Campaign, campaign_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")

    def counts(column: object) -> dict[str, int]:
        rows = db.execute(
            select(column, func.count())  # type: ignore[call-overload]
            .select_from(Post)
            .outerjoin(PostAnalysis)
            .where(Post.campaign_id == campaign_id)
            .group_by(column)
        ).all()
        return {str(getattr(key, "value", key) or "unanalysed"): n for key, n in rows}

    by_status = counts(Post.status)
    return CampaignStats(
        total_posts=sum(by_status.values()),
        by_status=by_status,
        by_life_event=counts(PostAnalysis.life_event),
        by_recommendation=counts(PostAnalysis.recommendation),
    )


@router.get("/posts/{post_id}", response_model=PostDetail)
def get_post(post_id: int, db: DbSession) -> PostDetail:
    return _detail(db, _post_or_404(db, post_id))


@router.post("/posts/{post_id}/analyze", response_model=PostDetail)
def analyze_post(post_id: int, db: DbSession, ai: AI, settings: AppSettings) -> PostDetail:
    post = _post_or_404(db, post_id)
    try:
        triage_posts(db, [post], _require_ai(ai), settings.claude_triage_model)
    except AIError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    db.refresh(post)
    return _detail(db, post)


@router.post("/posts/{post_id}/drafts", response_model=PostDetail)
def create_drafts(
    post_id: int,
    db: DbSession,
    ai: AI,
    settings: AppSettings,
    payload: GenerateDraftsRequest | None = None,
) -> PostDetail:
    post = _post_or_404(db, post_id)
    instruction = payload.instruction if payload else None
    try:
        workflow.generate_drafts(
            db, post, _require_ai(ai), settings.claude_draft_model, instruction
        )
    except AIError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return _detail(db, post)


@router.post("/posts/{post_id}/replied", response_model=PostDetail)
def mark_replied(post_id: int, db: DbSession) -> PostDetail:
    post = _post_or_404(db, post_id)
    try:
        workflow.mark_replied(db, post)
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _detail(db, post)


@router.post("/posts/{post_id}/dismiss", response_model=PostDetail)
def dismiss(post_id: int, db: DbSession) -> PostDetail:
    post = _post_or_404(db, post_id)
    workflow.dismiss_post(db, post)
    return _detail(db, post)


# ---- drafts ------------------------------------------------------------------


@router.patch("/drafts/{draft_id}", response_model=DraftRead)
def update_draft(draft_id: int, payload: DraftUpdate, db: DbSession) -> Draft:
    try:
        return workflow.edit_draft(db, _draft_or_404(db, draft_id), payload.text)
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("/drafts/{draft_id}/approve", response_model=DraftRead)
def approve(draft_id: int, db: DbSession) -> Draft:
    try:
        return workflow.approve_draft(db, _draft_or_404(db, draft_id))
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("/drafts/{draft_id}/reject", response_model=DraftRead)
def reject(draft_id: int, db: DbSession) -> Draft:
    try:
        return workflow.reject_draft(db, _draft_or_404(db, draft_id))
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
