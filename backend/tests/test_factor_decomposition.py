from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from app.domain.data.models import FetchResult
from app.domain.portfolio.analytics import PortfolioAnalytics
from app.domain.portfolio.models import PortfolioHolding


class FakeHistoricalDataFetcher:
    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self.frames = frames

    def fetch(self, ticker: str, start_date: date, end_date: date) -> FetchResult:
        frame = self.frames.get(ticker, pd.DataFrame(columns=["adj_close"]))
        warnings = [] if not frame.empty else [f"No historical data returned for ticker {ticker}."]
        return FetchResult(data=frame, source="fake", cache_hit=False, warnings=warnings)


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


def test_factor_decomposition_recovers_known_exposures() -> None:
    index = pd.date_range("2024-01-01", periods=30, freq="D", name="date")
    factors = pd.DataFrame(
        {
            "mkt_rf": np.linspace(-0.02, 0.025, len(index)),
            "smb": 0.01 * np.sin(np.linspace(0, 4 * np.pi, len(index))),
            "hml": 0.008 * np.cos(np.linspace(0, 3 * np.pi, len(index))),
            "rf": np.full(len(index), 0.0001),
        },
        index=index,
    )
    deterministic_noise = pd.Series(np.tile([0.00015, -0.00010, 0.00005], 10), index=index)
    excess_returns = 0.001 + 1.2 * factors["mkt_rf"] + 0.35 * factors["smb"] - 0.45 * factors["hml"] + deterministic_noise
    portfolio_returns = excess_returns + factors["rf"]
    analytics = PortfolioAnalytics(
        historical_data_fetcher=FakeHistoricalDataFetcher({}),
        fama_french_loader=FakeFamaFrenchLoader(factors),
    )

    result = analytics.factor_decomposition_from_returns(portfolio_returns=portfolio_returns, fama_french_factors=factors)

    assert np.isclose(result.market_beta, 1.2, atol=0.03)
    assert np.isclose(result.smb_exposure, 0.35, atol=0.05)
    assert np.isclose(result.hml_exposure, -0.45, atol=0.05)
    assert np.isclose(result.alpha, 0.001, atol=0.0003)
    assert result.observations == 30
    assert result.r_squared > 0.99


def test_factor_decomposition_returns_warning_without_overlap() -> None:
    returns_index = pd.date_range("2024-01-01", periods=3, freq="D", name="date")
    factor_index = pd.date_range("2024-02-01", periods=3, freq="D", name="date")
    frames = {"PORT": pd.DataFrame({"adj_close": [100.0, 101.0, 102.0]}, index=returns_index)}
    factors = pd.DataFrame(
        {
            "mkt_rf": [0.01, 0.01, 0.01],
            "smb": [0.0, 0.0, 0.0],
            "hml": [0.0, 0.0, 0.0],
            "rf": [0.0001, 0.0001, 0.0001],
        },
        index=factor_index,
    )
    analytics = PortfolioAnalytics(
        historical_data_fetcher=FakeHistoricalDataFetcher(frames),
        fama_french_loader=FakeFamaFrenchLoader(factors),
    )
    holdings = [PortfolioHolding(ticker="PORT", quantity=1, weight=1.0, market_value=100.0)]

    result = analytics.factor_decomposition(holdings, start_date=date(2024, 1, 1), end_date=date(2024, 2, 3))

    assert result.observations == 0
    assert np.isnan(result.market_beta)
    assert result.warnings == ["No overlapping observations were available for factor decomposition."]
