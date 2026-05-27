from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.domain.portfolio.models import FactorDecompositionResult


@dataclass(slots=True)
class ConcentrationMetrics:
    """Concentration summary derived from normalized portfolio weights."""

    hhi: float
    top_3_weight: float
    top_5_weight: float


@dataclass(slots=True)
class DrawdownSummary:
    """Drawdown magnitude and recovery statistics for a return series."""

    max_drawdown: float
    peak_date: pd.Timestamp | None
    trough_date: pd.Timestamp | None
    recovery_date: pd.Timestamp | None
    recovery_periods: int | None


@dataclass(slots=True)
class RiskAnalyticsResult:
    """Risk summary bundle for a portfolio over a chosen lookback period."""

    var_95: float
    var_99: float
    cvar_95: float
    latest_rolling_vol: float
    drawdown: DrawdownSummary
    concentration: ConcentrationMetrics
    latest_correlation_matrix: pd.DataFrame
    rolling_correlation_matrix: pd.DataFrame
    factor_exposure_summary: FactorDecompositionResult
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LiquidityHoldingResult:
    """Liquidity profile and haircut estimate for a single holding."""

    ticker: str
    adv_30d: float
    position_pct_adv: float
    days_to_liquidate_10pct: float
    days_to_liquidate_20pct: float
    days_to_liquidate_30pct: float
    stressed_loss_dollars: float
    liquidity_haircut_dollars: float
    liquidity_adjusted_loss_dollars: float


@dataclass(slots=True)
class LiquidityAnalysisResult:
    """Portfolio-level liquidity-adjusted stress summary."""

    holdings: list[LiquidityHoldingResult]
    stressed_loss_dollars: float
    total_liquidity_haircut_dollars: float
    liquidity_adjusted_loss_dollars: float
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class HedgeSuggestion:
    """Explainable hedge recommendation linked to a measurable portfolio weakness."""

    instrument: str
    rationale: str
    severity: str
    hedge_ratio: float
    hedge_ratio_steps: list[str]
    estimated_annual_cost_bps: float
    historical_effectiveness: float | None
    weakness_citation: str


@dataclass(slots=True)
class SimilarHistoricalPeriod:
    """Nearest historical 30-day analog for a hypothetical shock vector."""

    start_date: pd.Timestamp
    end_date: pd.Timestamp
    similarity_score: float
    feature_vector: dict[str, float]
    portfolio_return: float | None
    outcome_narrative: str
