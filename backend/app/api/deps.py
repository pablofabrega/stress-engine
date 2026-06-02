"""FastAPI dependency providers.

These providers wrap the database session and the analytics engines so that
routes stay thin and tests can override them with in-memory/seeded fakes via
``app.dependency_overrides``.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.domain.portfolio.analytics import PortfolioAnalytics
from app.domain.portfolio.loader import PortfolioLoader
from app.domain.risk.analytics import RiskAnalytics
from app.domain.risk.hedges import HedgeSuggestionEngine
from app.domain.risk.similar_periods import SimilarPeriodsFinder


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for the request lifecycle."""

    yield from get_db_session()


def get_portfolio_loader() -> PortfolioLoader:
    """Provide a portfolio loader (defaults to the configured data provider)."""

    return PortfolioLoader()


def get_risk_analytics() -> RiskAnalytics:
    """Provide the risk analytics engine."""

    return RiskAnalytics(portfolio_analytics=PortfolioAnalytics())


def get_hedge_engine() -> HedgeSuggestionEngine:
    """Provide the hedge suggestion engine."""

    return HedgeSuggestionEngine()


def get_similar_periods_finder() -> SimilarPeriodsFinder:
    """Provide the similar-periods finder."""

    return SimilarPeriodsFinder()
