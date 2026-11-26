"""Public facts the app shows in its footer: who to contact and how long data is kept."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import __version__
from app.core.config import Settings, get_settings

router = APIRouter(tags=["meta"])


class MetaResponse(BaseModel):
    app_name: str
    version: str
    contact_email: str | None
    retention_days: int
    access_code_required: bool


@router.get("/meta", response_model=MetaResponse)
def meta(settings: Annotated[Settings, Depends(get_settings)]) -> MetaResponse:
    return MetaResponse(
        app_name=settings.app_name,
        version=__version__,
        contact_email=settings.contact_email,
        retention_days=settings.retention_days,
        access_code_required=bool(settings.access_code and settings.access_code.get_secret_value()),
    )
