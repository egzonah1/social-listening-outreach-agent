"""Shared FastAPI dependencies. Tests override these to inject fakes."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db, get_sessionmaker
from app.services.search import execute_run

DbSession = Annotated[Session, Depends(get_db)]
RunLauncher = Callable[[int], None]


def run_search_in_background(run_id: int) -> None:
    """Runs after the HTTP response is sent, so it needs its own DB session."""
    with get_sessionmaker()() as db:
        execute_run(db, run_id)


def get_run_launcher() -> RunLauncher:
    return run_search_in_background
