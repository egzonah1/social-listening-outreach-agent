"""Shapes Claude must return. Structured outputs guarantee valid JSON in this
shape; Pydantic then validates it again (e.g. relevance between 0 and 100)."""

from typing import Literal

from pydantic import BaseModel, Field

from app.db.enums import LifeEvent, OutreachRecommendation, Sensitivity

Tone = Literal["warm", "helpful", "brief"]


class PostTriage(BaseModel):
    post_id: int
    relevance: int = Field(
        ge=0, le=100, description="How relevant to a life-insurance conversation"
    )
    life_event: LifeEvent
    sensitivity: Sensitivity
    recommendation: OutreachRecommendation
    reason: str = Field(description="One or two sentences explaining the decision")
    summary: str = Field(description="One short sentence describing the post")


class TriageBatch(BaseModel):
    results: list[PostTriage]


class DraftVariant(BaseModel):
    tone: Tone
    text: str


class DraftSet(BaseModel):
    variants: list[DraftVariant]
