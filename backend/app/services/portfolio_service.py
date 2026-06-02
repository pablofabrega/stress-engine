"""Database-backed portfolio CRUD and nominal analytics."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models.portfolio import Holding, UserPortfolio
from app.schemas.portfolio import HoldingInput, PortfolioAnalyticsSummary

_UNKNOWN_SECTOR = "Unknown"


def create_portfolio(db: Session, name: str, holdings: Iterable[HoldingInput]) -> UserPortfolio:
    """Persist a new portfolio and its holdings."""

    portfolio = UserPortfolio(name=name)
    for holding in holdings:
        portfolio.holdings.append(_to_holding(holding))
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return portfolio


def get_portfolio(db: Session, portfolio_id: uuid.UUID) -> UserPortfolio | None:
    """Return a portfolio with its holdings eagerly loaded, or ``None``."""

    stmt = (
        select(UserPortfolio)
        .where(UserPortfolio.id == portfolio_id)
        .options(selectinload(UserPortfolio.holdings))
    )
    return db.execute(stmt).scalar_one_or_none()


def list_portfolios(db: Session) -> list[UserPortfolio]:
    """Return all portfolios (with holdings) ordered by creation time."""

    stmt = (
        select(UserPortfolio)
        .options(selectinload(UserPortfolio.holdings))
        .order_by(UserPortfolio.created_at)
    )
    return list(db.execute(stmt).scalars().all())


def upsert_holdings(db: Session, portfolio: UserPortfolio, holdings: Iterable[HoldingInput]) -> UserPortfolio:
    """Add new holdings or update existing ones (matched case-insensitively by ticker)."""

    existing = {holding.ticker.upper(): holding for holding in portfolio.holdings}
    for incoming in holdings:
        ticker = incoming.ticker.upper()
        if ticker in existing:
            current = existing[ticker]
            current.quantity = incoming.quantity
            current.cost_basis = incoming.cost_basis
            if incoming.asset_class is not None:
                current.asset_class = incoming.asset_class
            if incoming.sector is not None:
                current.sector = incoming.sector
        else:
            new_holding = _to_holding(incoming)
            portfolio.holdings.append(new_holding)
            existing[ticker] = new_holding
    db.commit()
    db.refresh(portfolio)
    return portfolio


def delete_portfolio(db: Session, portfolio: UserPortfolio) -> None:
    """Delete a portfolio (holdings cascade)."""

    db.delete(portfolio)
    db.commit()


def nominal_analytics(portfolio: UserPortfolio) -> PortfolioAnalyticsSummary:
    """Compute deterministic nominal weights without any market-data fetch.

    Notional per holding is ``quantity * cost_basis`` when a cost basis is
    present, otherwise ``quantity``. Weights are the notional share of the total.
    """

    notionals: dict[str, float] = {}
    sector_notionals: dict[str, float] = defaultdict(float)
    for holding in portfolio.holdings:
        quantity = float(holding.quantity)
        notional = quantity * float(holding.cost_basis) if holding.cost_basis is not None else quantity
        notionals[holding.ticker] = notionals.get(holding.ticker, 0.0) + notional
        sector_notionals[holding.sector or _UNKNOWN_SECTOR] += notional

    total = sum(notionals.values())
    if total <= 0:
        return PortfolioAnalyticsSummary(total_notional=0.0, holding_weights={}, sector_weights={})

    holding_weights = {ticker: value / total for ticker, value in notionals.items()}
    sector_weights = {sector: value / total for sector, value in sector_notionals.items()}
    return PortfolioAnalyticsSummary(
        total_notional=total,
        holding_weights=holding_weights,
        sector_weights=sector_weights,
    )


def _to_holding(holding: HoldingInput) -> Holding:
    return Holding(
        ticker=holding.ticker.upper(),
        quantity=holding.quantity,
        cost_basis=holding.cost_basis,
        asset_class=holding.asset_class,
        sector=holding.sector,
    )
