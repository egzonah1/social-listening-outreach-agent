"""Shared test fixtures.

Database tests run against a real Postgres database (the `outreach_test`
database that docker-compose creates), not SQLite, so tests behave like
production. Each test runs inside a transaction that is rolled back at the
end, so tests never see each other's data and need no cleanup.
"""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.api.deps import get_connector_factory, get_run_launcher
from app.connectors.sample import SampleConnector
from app.db import models  # noqa: F401  (registers tables)
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.services.search import execute_run

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://outreach:outreach@localhost:5433/outreach_test",
)


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    # "create_savepoint" lets code under test call session.commit() safely:
    # commits go to a savepoint, and everything is rolled back afterwards.
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    """An API client whose requests and background runs use the test session."""
    app = create_app()

    def launch(run_id: int) -> None:
        execute_run(db, run_id, connector_factory=lambda platform: SampleConnector())

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_run_launcher] = lambda: launch
    app.dependency_overrides[get_connector_factory] = lambda: lambda platform: SampleConnector()
    with TestClient(app) as test_client:
        yield test_client
