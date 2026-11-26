"""Shared FastAPI dependencies. Tests override these to inject fakes."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.ai.client import StructuredLLM, build_ai_client
from app.core.config import get_settings
from app.db.session import get_db, get_sessionmaker
from app.services.search import execute_run

DbSession = Annotated[Session, Depends(get_db)]
RunLauncher = Callable[[int], None]


def run_search_in_background(run_id: int) -> None:
    """Runs after the HTTP response is sent, so it needs its own DB session."""
    settings = get_settings()
    with get_sessionmaker()() as db:
        execute_run(
            db,
            run_id,
            ai=build_ai_client(settings),
            triage_model=settings.claude_triage_model,
        )


def get_run_launcher() -> RunLauncher:
    return run_search_in_background


def get_ai() -> StructuredLLM | None:
    return build_ai_client(get_settings())
