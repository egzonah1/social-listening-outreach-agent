"""Database engine and per-request sessions.

We use SQLAlchemy's synchronous API. FastAPI runs plain `def` endpoints in a
thread pool, so sync database calls don't block the server, and the code is
simpler to read and debug than async SQLAlchemy.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    # pool_pre_ping checks a connection is alive before using it. Serverless
    # Postgres (Neon) closes idle connections, so this avoids random errors.
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
