from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from app.domain.data.models import FetchResult
from app.domain.portfolio.analytics import PortfolioAnalytics
from app.domain.portfolio.models import FactorDecompositionResult, PortfolioHolding
from app.domain.risk.analytics import RiskAnalytics


class FakeHistoricalDataFetcher:
    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self.frames = frames

    def fetch(self, ticker: str, start_date: date, end_date: date) -> FetchResult:
        frame = self.frames.get(ticker, pd.DataFrame(columns=["adj_close"]))
        sliced = frame.loc[(frame.index >= pd.Timestamp(start_date)) & (frame.index <= pd.Timestamp(end_date))].copy()
        warnings = [] if not sliced.empty else [f"No historical data returned for ticker {ticker}."]
        return FetchResult(data=sliced, source="fake", cache_hit=False, warnings=warnings)


class FakeFamaFrenchLoader:
    def __init__(self, factors: pd.DataFrame) -> None:
        self.factors = factors

    def load(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        frame = self.factors
        if start_date is not None:
            frame = frame.loc[frame.index >= pd.Timestamp(start_date)]
        if end_date is not None:
            frame = frame.loc[frame.index <= pd.Timestamp(end_date)]
        return frame.copy()


def _prices_from_returns(returns: list[float], initial_price: float = 100.0) -> pd.DataFrame:
    levels = [initial_price]
    for daily_return in returns:
        levels.append(levels[-1] * (1.0 + daily_return))
    index = pd.date_range("2024-01-01", periods=len(levels), freq="D", name="date")
    return pd.DataFrame({"adj_close": levels}, index=index)


def test_historical_var_and_cvar_are_empirical_tail_losses() -> None:
    analytics = RiskAnalytics()
    returns = pd.Series([-0.03, -0.02, 0.01, 0.02, -0.01], index=pd.date_range("2024-01-01", periods=5, freq="D"))

    var_95 = analytics.historical_var(returns, confidence_level=0.95)
    var_99 = analytics.historical_var(returns, confidence_level=0.99)
    cvar_95 = analytics.cvar(returns, confidence_level=0.95)

    assert np.isclose(var_95, 0.028)
    assert np.isclose(var_99, 0.0296)
    assert np.isclose(cvar_95, 0.03)


def test_drawdown_summary_and_recovery_time_are_computed_from_compounded_wealth() -> None:
    analytics = RiskAnalytics()
    returns = pd.Series(
        [0.10, -0.20, 0.05, 0.10, 0.10],
        index=pd.date_range("2024-01-01", periods=5, freq="D"),
    )

    summary = analytics.drawdown_summary(returns)

    assert np.isclose(summary.max_drawdown, -0.20)
    assert summary.peak_date == pd.Timestamp("2024-01-01")
    assert summary.trough_date == pd.Timestamp("2024-01-02")
    assert summary.recovery_date == pd.Timestamp("2024-01-05")
    assert summary.recovery_periods == 3


def test_concentration_metrics_capture_hhi_and_top_weights() -> None:
    analytics = RiskAnalytics()
    holdings = [
        PortfolioHolding(ticker="A", quantity=1, weight=0.40),
        PortfolioHolding(ticker="B", quantity=1, weight=0.30),
        PortfolioHolding(ticker="C", quantity=1, weight=0.20),
        PortfolioHolding(ticker="D", quantity=1, weight=0.10),
    ]

    concentration = analytics.concentration_metrics(holdings)

    assert np.isclose(concentration.hhi, 0.30)
    assert np.isclose(concentration.top_3_weight, 0.90)
    assert np.isclose(concentration.top_5_weight, 1.00)


def test_latest_rolling_correlation_matrix_extracts_latest_snapshot() -> None:
    analytics = RiskAnalytics()
    component_returns = pd.DataFrame(
        {
            "AAPL": [0.01, 0.02, 0.03, 0.04],
            "MSFT": [0.02, 0.04, 0.06, 0.08],
        },
        index=pd.date_range("2024-01-01", periods=4, freq="D"),
    )

    latest, rolling = analytics.latest_rolling_correlation_matrix(component_returns, window=3)

    assert np.isclose(latest.loc["AAPL", "MSFT"], 1.0)
    assert not rolling.empty


def test_analyze_portfolio_composes_risk_summary() -> None:
    frames = {
        "AAPL": _prices_from_returns([0.01, -0.02, 0.03, -0.01, 0.02]),
        "TLT": _prices_from_returns([0.005, 0.004, -0.002, 0.003, 0.001]),
    }
    factor_index = pd.date_range("2024-01-01", periods=6, freq="D", name="date")
    factors = pd.DataFrame(
        {
            "mkt_rf": [0.01, -0.02, 0.03, -0.01, 0.02, 0.01],
            "smb": [0.0, 0.01, -0.01, 0.0, 0.005, -0.002],
            "hml": [0.002, -0.001, 0.0, 0.003, -0.002, 0.001],
            "rf": [0.0001] * 6,
        },
        index=factor_index,
    )
    portfolio_analytics = PortfolioAnalytics(
        historical_data_fetcher=FakeHistoricalDataFetcher(frames),
        fama_french_loader=FakeFamaFrenchLoader(factors),
    )
    risk_analytics = RiskAnalytics(portfolio_analytics=portfolio_analytics)
    holdings = [
        PortfolioHolding(ticker="AAPL", quantity=1, market_value=600.0, weight=0.6, sector="Technology"),
        PortfolioHolding(ticker="TLT", quantity=1, market_value=400.0, weight=0.4, sector="Fixed Income"),
    ]

    result = risk_analytics.analyze_portfolio(
        holdings=holdings,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 6),
        vol_window=3,
        correlation_window=3,
    )

    assert result.var_95 > 0
    assert result.var_99 > 0
    assert result.cvar_95 > 0
    assert np.isfinite(result.latest_rolling_vol)
    assert np.isfinite(result.drawdown.max_drawdown)
    assert np.isclose(result.concentration.hhi, 0.52)
    assert not result.latest_correlation_matrix.empty
    assert isinstance(result.factor_exposure_summary, FactorDecompositionResult)
    assert result.factor_exposure_summary.observations > 0
