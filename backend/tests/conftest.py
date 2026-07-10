"""Shared test fixtures.

Tests run against in-memory SQLite rather than Postgres: fast, and enough to
exercise the routers and the service layer. The Postgres-specific behaviour of
``NUMERIC`` / ``Uuid`` / ``DateTime(timezone=True)`` is checked by hand against a
real database — see the verification notes in the task plan.
"""

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event, insert
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models.asset_class import ASSET_CLASS_SEED, AssetClassRef


@pytest.fixture
def engine() -> Engine:
    # StaticPool keeps every connection pointed at the same in-memory database.
    # Without it, the TestClient's request would open a second connection and
    # find an empty schema. check_same_thread is off for the same reason:
    # TestClient may run the request on another thread.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite ignores foreign keys unless asked, so FK violations would pass
    # silently here and only surface against Postgres.
    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    # In production the migration seeds these rows. Without them every instrument
    # insert would violate the instrument.asset_class foreign key.
    with engine.begin() as connection:
        connection.execute(insert(AssetClassRef), [dict(row) for row in ASSET_CLASS_SEED])

    return engine


@pytest.fixture
def session(engine: Engine) -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(session: Session) -> Generator[TestClient, None, None]:
    """A TestClient whose requests run on the same session the test can inspect."""

    def _override_get_db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
