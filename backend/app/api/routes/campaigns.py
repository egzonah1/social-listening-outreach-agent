"""Campaign CRUD and search runs."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import select

from app.api.deps import DbSession, RunLauncher, get_run_launcher
from app.db.models import Campaign, SearchRun
from app.schemas.campaign import CampaignCreate, CampaignRead, CampaignUpdate, SearchRunRead
from app.services.search import create_run

router = APIRouter(tags=["campaigns"])


def _get_campaign_or_404(db: DbSession, campaign_id: int) -> Campaign:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    return campaign


@router.post("/campaigns", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
def create_campaign(payload: CampaignCreate, db: DbSession) -> Campaign:
    campaign = Campaign(**payload.model_dump(mode="json"))
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.get("/campaigns", response_model=list[CampaignRead])
def list_campaigns(db: DbSession) -> list[Campaign]:
    return list(db.scalars(select(Campaign).order_by(Campaign.created_at.desc())))


@router.get("/campaigns/{campaign_id}", response_model=CampaignRead)
def get_campaign(campaign_id: int, db: DbSession) -> Campaign:
    return _get_campaign_or_404(db, campaign_id)


@router.patch("/campaigns/{campaign_id}", response_model=CampaignRead)
def update_campaign(campaign_id: int, payload: CampaignUpdate, db: DbSession) -> Campaign:
    campaign = _get_campaign_or_404(db, campaign_id)
    # exclude_unset: only change fields the client actually sent.
    for field, value in payload.model_dump(mode="json", exclude_unset=True).items():
        setattr(campaign, field, value)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.delete("/campaigns/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(campaign_id: int, db: DbSession) -> Response:
    db.delete(_get_campaign_or_404(db, campaign_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/campaigns/{campaign_id}/runs",
    response_model=SearchRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_run(
    campaign_id: int,
    db: DbSession,
    background_tasks: BackgroundTasks,
    launch: Annotated[RunLauncher, Depends(get_run_launcher)],
) -> SearchRun:
    """Start a search. Returns at once (202 Accepted); the UI polls the run for progress."""
    run = create_run(db, _get_campaign_or_404(db, campaign_id))
    background_tasks.add_task(launch, run.id)
    return run


@router.get("/campaigns/{campaign_id}/runs", response_model=list[SearchRunRead])
def list_runs(campaign_id: int, db: DbSession) -> list[SearchRun]:
    _get_campaign_or_404(db, campaign_id)
    query = select(SearchRun).where(SearchRun.campaign_id == campaign_id)
    return list(db.scalars(query.order_by(SearchRun.id.desc())))


@router.get("/runs/{run_id}", response_model=SearchRunRead)
def get_run(run_id: int, db: DbSession) -> SearchRun:
    run = db.get(SearchRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Search run not found")
    return run
