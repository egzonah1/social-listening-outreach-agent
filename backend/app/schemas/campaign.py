"""API request/response shapes for campaigns and search runs.

Pydantic validates every request before our code runs: a campaign with no
keywords or an unknown source is rejected with a clear 422 error.
"""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.db.enums import LifeEvent, Platform, RunStatus

Keyword = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]


class CampaignBase(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    description: Annotated[str | None, Field(max_length=1000)] = None
    keywords: Annotated[list[Keyword], Field(min_length=1, max_length=10)]
    life_events: list[LifeEvent] = []
    sources: Annotated[list[Platform], Field(min_length=1)]
    language: Annotated[str | None, Field(pattern=r"^[a-z]{2}$")] = "en"

    @field_validator("keywords", "life_events", "sources")
    @classmethod
    def remove_duplicates(cls, values: list[Any]) -> list[Any]:
        return list(dict.fromkeys(values))  # keeps the original order


class CampaignCreate(CampaignBase):
    pass


class CampaignUpdate(BaseModel):
    """Every field optional: only the fields sent are changed (PATCH)."""

    name: Annotated[
        str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
    ] = None
    description: Annotated[str | None, Field(max_length=1000)] = None
    keywords: Annotated[list[Keyword] | None, Field(min_length=1, max_length=10)] = None
    life_events: list[LifeEvent] | None = None
    sources: Annotated[list[Platform] | None, Field(min_length=1)] = None
    language: Annotated[str | None, Field(pattern=r"^[a-z]{2}$")] = None


class CampaignRead(CampaignBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class SearchRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    status: RunStatus
    source_stats: dict[str, Any]
    posts_found: int
    posts_new: int
    posts_analyzed: int
    posts_drafted: int
    error: str | None
    triage_error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class CampaignSummary(BaseModel):
    """One campaign on the home page, with its own numbers."""

    campaign: CampaignRead
    posts: int
    to_review: int
    approved: int
    replied: int
    last_run: SearchRunRead | None


class OverviewTotals(BaseModel):
    campaigns: int
    posts: int
    to_review: int
    approved: int
    replied: int


class Overview(BaseModel):
    totals: OverviewTotals
    campaigns: list[CampaignSummary]
