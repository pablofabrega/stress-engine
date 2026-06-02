from __future__ import annotations

from collections.abc import Generator
from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401  (register tables on Base.metadata)
from app.api.deps import (
    get_db,
    get_hedge_engine,
    get_historical_runner,
    get_hypothetical_runner,
    get_portfolio_loader,
    get_risk_analytics,
    get_similar_periods_finder,
)
from app.db.base import Base
from app.domain.data.models import FetchResult
from app.main import app


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """In-memory SQLite session shared across a single test via StaticPool."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, _record) -> None:  # pragma: no cover - trivial pragma
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


class FakeHistoricalDataFetcher:
    """Deterministic price source for analytics endpoints (no network)."""

    def __init__(self, frames: dict[str, pd.DataFrame] | None = None) -> None:
        self.frames = frames or {}

    def fetch(self, ticker: str, start_date: date, end_date: date) -> FetchResult:
        frame = self.frames.get(ticker)
        if frame is None or frame.empty:
            return FetchResult(
                data=pd.DataFrame(columns=["adj_close"]), source="fake", cache_hit=False, warnings=[]
            )
        sliced = frame.loc[(frame.index >= pd.Timestamp(start_date)) & (frame.index <= pd.Timestamp(end_date))].copy()
        return FetchResult(data=sliced, source="fake", cache_hit=False, warnings=[])


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient with the DB session overridden to the in-memory SQLite session."""

    def _override_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def override_analytics():
    """Helper to register fake analytics engines on the app for a test.

    Returns a callable that accepts keyword fakes (loader, risk_analytics,
    hedge_engine, similar_periods_finder) and installs them as overrides.
    """

    dependency_map = {
        "loader": get_portfolio_loader,
        "risk_analytics": get_risk_analytics,
        "hedge_engine": get_hedge_engine,
        "similar_periods_finder": get_similar_periods_finder,
        "historical_runner": get_historical_runner,
        "hypothetical_runner": get_hypothetical_runner,
    }

    def _install(**fakes: object) -> None:
        for key, value in fakes.items():
            app.dependency_overrides[dependency_map[key]] = lambda value=value: value

    yield _install
