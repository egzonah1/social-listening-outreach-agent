"""The home page dashboard: totals across campaigns and numbers for each one.

One request with a few grouped SQL queries, instead of the browser asking for
the stats of every campaign separately.
"""

from collections import defaultdict

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.db.enums import LifeEvent, OutreachRecommendation, PostStatus
from app.db.models import Campaign, Post, PostAnalysis, SearchRun
from app.schemas.campaign import (
    CampaignRead,
    CampaignSummary,
    LifeEventCount,
    Overview,
    OverviewTotals,
    SearchRunRead,
)

router = APIRouter(tags=["overview"])

# Posts a person still has to look at: not finished, and not marked "do not contact".
OPEN = (PostStatus.NEW, PostStatus.DRAFTED)


@router.get("/overview", response_model=Overview)
def overview(db: DbSession) -> Overview:
    campaigns = db.scalars(
        select(Campaign).order_by(Campaign.created_at.desc(), Campaign.id.desc())
    ).all()

    counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    rows = db.execute(
        select(Post.campaign_id, Post.status, PostAnalysis.recommendation, func.count())
        .outerjoin(PostAnalysis)
        .group_by(Post.campaign_id, Post.status, PostAnalysis.recommendation)
    ).all()
    for campaign_id, post_status, recommendation, n in rows:
        c = counts[campaign_id]
        c["posts"] += n
        if post_status in OPEN and recommendation != OutreachRecommendation.DO_NOT_CONTACT:
            c["to_review"] += n
        elif post_status == PostStatus.APPROVED:
            c["approved"] += n
        elif post_status == PostStatus.REPLIED:
            c["replied"] += n

    # The newest run of each campaign.
    newest = (
        select(SearchRun.campaign_id, func.max(SearchRun.id).label("run_id"))
        .group_by(SearchRun.campaign_id)
        .subquery()
    )
    last_runs = {
        run.campaign_id: run
        for run in db.scalars(select(SearchRun).join(newest, SearchRun.id == newest.c.run_id))
    }

    # What people are talking about. "No life event" is left out: it isn't a lead.
    by_event = db.execute(
        select(PostAnalysis.life_event, func.count())
        .where(PostAnalysis.life_event != LifeEvent.NONE)
        .group_by(PostAnalysis.life_event)
    ).all()
    life_events = sorted(
        (LifeEventCount(life_event=event, posts=n) for event, n in by_event),
        key=lambda item: (-item.posts, item.life_event.value),
    )

    summaries = [
        CampaignSummary(
            campaign=CampaignRead.model_validate(campaign),
            posts=counts[campaign.id]["posts"],
            to_review=counts[campaign.id]["to_review"],
            approved=counts[campaign.id]["approved"],
            replied=counts[campaign.id]["replied"],
            last_run=SearchRunRead.model_validate(last_runs[campaign.id])
            if campaign.id in last_runs
            else None,
        )
        for campaign in campaigns
    ]
    return Overview(
        totals=OverviewTotals(
            campaigns=len(summaries),
            posts=sum(s.posts for s in summaries),
            to_review=sum(s.to_review for s in summaries),
            approved=sum(s.approved for s in summaries),
            replied=sum(s.replied for s in summaries),
        ),
        campaigns=summaries,
        life_events=life_events,
    )
