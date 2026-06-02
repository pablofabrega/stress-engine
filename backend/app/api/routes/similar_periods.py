from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_portfolio_loader, get_similar_periods_finder
from app.domain.portfolio.loader import PortfolioLoader
from app.domain.risk.similar_periods import SimilarPeriodsFinder
from app.schemas.similar_periods import SimilarPeriodsRequest, SimilarPeriodsResponse
from app.services import analytics_service, portfolio_service

router = APIRouter(prefix="/similar-periods", tags=["similar-periods"])


@router.post("", response_model=SimilarPeriodsResponse)
def find_similar_periods(
    request: SimilarPeriodsRequest,
    db: Session = Depends(get_db),
    loader: PortfolioLoader = Depends(get_portfolio_loader),
    finder: SimilarPeriodsFinder = Depends(get_similar_periods_finder),
) -> SimilarPeriodsResponse:
    holdings = None
    if request.portfolio_id is not None:
        portfolio = portfolio_service.get_portfolio(db, request.portfolio_id)
        if portfolio is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")
        holdings = analytics_service.build_holdings(portfolio, loader)

    periods = analytics_service.similar_periods(
        shock_vector=request.shock_vector,
        finder=finder,
        holdings=holdings,
        top_k=request.top_k,
    )
    return SimilarPeriodsResponse(periods=periods)
