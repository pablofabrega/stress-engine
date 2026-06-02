"""Wiring between persisted portfolios and the domain analytics engines."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from app.db.models.portfolio import UserPortfolio
from app.domain.portfolio.loader import PortfolioLoader
from app.domain.portfolio.models import PortfolioHolding
from app.domain.risk.analytics import RiskAnalytics
from app.domain.risk.hedges import HedgeSuggestionEngine
from app.domain.risk.models import RiskAnalyticsResult, SimilarHistoricalPeriod
from app.domain.risk.similar_periods import SimilarPeriodsFinder
from app.schemas.recommendation import HedgeSuggestionResponse
from app.schemas.risk import (
    ConcentrationResponse,
    DrawdownSummaryResponse,
    FactorExposureResponse,
    RiskSnapshotResponse,
)
from app.schemas.similar_periods import SimilarPeriodResponse

DEFAULT_LOOKBACK_DAYS = 365 * 2


def build_holdings(portfolio: UserPortfolio, loader: PortfolioLoader) -> list[PortfolioHolding]:
    """Normalize stored holdings into priced, weighted domain holdings."""

    payload = {
        holding.ticker: {"quantity": float(holding.quantity), "cost_basis": _opt_float(holding.cost_basis)}
        for holding in portfolio.holdings
    }
    if not payload:
        return []
    return loader.load_from_json(name=portfolio.name, holdings_payload=payload).holdings


def risk_snapshot(
    portfolio: UserPortfolio,
    loader: PortfolioLoader,
    risk_analytics: RiskAnalytics,
    start_date: date | None = None,
    end_date: date | None = None,
) -> RiskSnapshotResponse:
    """Compute a full risk snapshot for a portfolio over a lookback window."""

    end_date = end_date or date.today()
    start_date = start_date or (end_date - timedelta(days=DEFAULT_LOOKBACK_DAYS))
    holdings = build_holdings(portfolio, loader)
    result = risk_analytics.analyze_portfolio(holdings=holdings, start_date=start_date, end_date=end_date)
    return _serialize_risk(result, start_date=start_date, end_date=end_date)


def recommendations(
    portfolio: UserPortfolio,
    loader: PortfolioLoader,
    risk_analytics: RiskAnalytics,
    hedge_engine: HedgeSuggestionEngine,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[HedgeSuggestionResponse]:
    """Generate hedge suggestions from the portfolio's current risk profile."""

    end_date = end_date or date.today()
    start_date = start_date or (end_date - timedelta(days=DEFAULT_LOOKBACK_DAYS))
    holdings = build_holdings(portfolio, loader)
    risk_result = risk_analytics.analyze_portfolio(holdings=holdings, start_date=start_date, end_date=end_date)
    suggestions = hedge_engine.suggest(holdings=holdings, risk_summary=risk_result, as_of_date=end_date)
    return [
        HedgeSuggestionResponse(
            instrument=item.instrument,
            rationale=item.rationale,
            severity=item.severity,
            hedge_ratio=item.hedge_ratio,
            hedge_ratio_steps=item.hedge_ratio_steps,
            estimated_annual_cost_bps=item.estimated_annual_cost_bps,
            historical_effectiveness=item.historical_effectiveness,
            weakness_citation=item.weakness_citation,
        )
        for item in suggestions
    ]


def similar_periods(
    shock_vector: dict[str, float],
    finder: SimilarPeriodsFinder,
    holdings: list[PortfolioHolding] | None = None,
    top_k: int = 3,
) -> list[SimilarPeriodResponse]:
    """Return the nearest historical analog windows for a shock vector."""

    periods = finder.find(shock_vector=shock_vector, holdings=holdings, top_k=top_k)
    return [_serialize_period(period) for period in periods]


def _serialize_risk(result: RiskAnalyticsResult, start_date: date, end_date: date) -> RiskSnapshotResponse:
    drawdown = result.drawdown
    factor = result.factor_exposure_summary
    concentration = result.concentration
    return RiskSnapshotResponse(
        start_date=start_date,
        end_date=end_date,
        var_95=result.var_95,
        var_99=result.var_99,
        cvar_95=result.cvar_95,
        rolling_vol=result.latest_rolling_vol,
        drawdown=DrawdownSummaryResponse(
            max_drawdown=drawdown.max_drawdown,
            peak_date=_to_date(drawdown.peak_date),
            trough_date=_to_date(drawdown.trough_date),
            recovery_date=_to_date(drawdown.recovery_date),
            recovery_periods=drawdown.recovery_periods,
        ),
        concentration=ConcentrationResponse(
            hhi=concentration.hhi,
            top_3_weight=concentration.top_3_weight,
            top_5_weight=concentration.top_5_weight,
        ),
        factor_exposure=FactorExposureResponse(
            alpha=factor.alpha,
            alpha_t_stat=factor.alpha_t_stat,
            market_beta=factor.market_beta,
            market_beta_t_stat=factor.market_beta_t_stat,
            smb_exposure=factor.smb_exposure,
            smb_t_stat=factor.smb_t_stat,
            hml_exposure=factor.hml_exposure,
            hml_t_stat=factor.hml_t_stat,
            r_squared=factor.r_squared,
            observations=factor.observations,
        ),
        warnings=list(result.warnings),
    )


def _serialize_period(period: SimilarHistoricalPeriod) -> SimilarPeriodResponse:
    return SimilarPeriodResponse(
        start_date=_to_date(period.start_date),
        end_date=_to_date(period.end_date),
        similarity_score=period.similarity_score,
        feature_vector=period.feature_vector,
        portfolio_return=period.portfolio_return,
        outcome_narrative=period.outcome_narrative,
    )


def _to_date(value: pd.Timestamp | None) -> date | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).date()


def _opt_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
