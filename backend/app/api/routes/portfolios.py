from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db,
    get_hedge_engine,
    get_portfolio_loader,
    get_risk_analytics,
)
from app.domain.portfolio.loader import PortfolioLoader
from app.domain.risk.analytics import RiskAnalytics
from app.domain.risk.hedges import HedgeSuggestionEngine
from app.schemas.common import MessageResponse
from app.schemas.portfolio import (
    HoldingsUpdateRequest,
    PortfolioCreateRequest,
    PortfolioDetailResponse,
    PortfolioResponse,
)
from app.schemas.recommendation import RecommendationsResponse
from app.schemas.risk import RiskSnapshotResponse
from app.services import analytics_service, portfolio_service

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


def _get_or_404(db: Session, portfolio_id: uuid.UUID):
    portfolio = portfolio_service.get_portfolio(db, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")
    return portfolio


@router.post("", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED)
def create_portfolio(request: PortfolioCreateRequest, db: Session = Depends(get_db)) -> PortfolioResponse:
    portfolio = portfolio_service.create_portfolio(db, name=request.name, holdings=request.holdings)
    return PortfolioResponse.model_validate(portfolio)


@router.get("/{portfolio_id}", response_model=PortfolioDetailResponse)
def get_portfolio(portfolio_id: uuid.UUID, db: Session = Depends(get_db)) -> PortfolioDetailResponse:
    portfolio = _get_or_404(db, portfolio_id)
    return PortfolioDetailResponse(
        id=portfolio.id,
        name=portfolio.name,
        created_at=portfolio.created_at,
        holdings=list(portfolio.holdings),
        analytics=portfolio_service.nominal_analytics(portfolio),
    )


@router.post("/{portfolio_id}/holdings", response_model=PortfolioResponse)
def update_holdings(
    portfolio_id: uuid.UUID,
    request: HoldingsUpdateRequest,
    db: Session = Depends(get_db),
) -> PortfolioResponse:
    portfolio = _get_or_404(db, portfolio_id)
    portfolio = portfolio_service.upsert_holdings(db, portfolio, request.holdings)
    return PortfolioResponse.model_validate(portfolio)


@router.delete("/{portfolio_id}", response_model=MessageResponse)
def delete_portfolio(portfolio_id: uuid.UUID, db: Session = Depends(get_db)) -> MessageResponse:
    portfolio = _get_or_404(db, portfolio_id)
    portfolio_service.delete_portfolio(db, portfolio)
    return MessageResponse(detail="Portfolio deleted.")


@router.get("/{portfolio_id}/risk", response_model=RiskSnapshotResponse)
def get_portfolio_risk(
    portfolio_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    loader: PortfolioLoader = Depends(get_portfolio_loader),
    risk_analytics: RiskAnalytics = Depends(get_risk_analytics),
) -> RiskSnapshotResponse:
    portfolio = _get_or_404(db, portfolio_id)
    return analytics_service.risk_snapshot(
        portfolio=portfolio,
        loader=loader,
        risk_analytics=risk_analytics,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/{portfolio_id}/recommendations", response_model=RecommendationsResponse)
def get_portfolio_recommendations(
    portfolio_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    loader: PortfolioLoader = Depends(get_portfolio_loader),
    risk_analytics: RiskAnalytics = Depends(get_risk_analytics),
    hedge_engine: HedgeSuggestionEngine = Depends(get_hedge_engine),
) -> RecommendationsResponse:
    portfolio = _get_or_404(db, portfolio_id)
    suggestions = analytics_service.recommendations(
        portfolio=portfolio,
        loader=loader,
        risk_analytics=risk_analytics,
        hedge_engine=hedge_engine,
        start_date=start_date,
        end_date=end_date,
    )
    return RecommendationsResponse(portfolio_id=str(portfolio.id), suggestions=suggestions)
