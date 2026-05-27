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


def test_portfolio_return_history_computes_weighted_simple_returns() -> None:
    index = pd.date_range("2024-01-01", periods=3, freq="D", name="date")
    frames = {
        "AAPL": pd.DataFrame({"adj_close": [100.0, 110.0, 121.0]}, index=index),
        "TLT": pd.DataFrame({"adj_close": [100.0, 90.0, 99.0]}, index=index),
    }
    analytics = PortfolioAnalytics(historical_data_fetcher=FakeHistoricalDataFetcher(frames))
    holdings = [
        PortfolioHolding(ticker="AAPL", quantity=10, sector="Technology", weight=0.6, market_value=600.0),
        PortfolioHolding(ticker="TLT", quantity=5, sector="Fixed Income", weight=0.4, market_value=400.0),
    ]

    result = analytics.portfolio_return_history(holdings, start_date=date(2024, 1, 1), end_date=date(2024, 1, 3))

    assert np.isnan(result.portfolio_returns.iloc[0])
    assert np.isclose(result.portfolio_returns.iloc[1], 0.02)
    assert np.isclose(result.portfolio_returns.iloc[2], 0.10)
    assert np.isclose(sum(result.weights_used.values()), 1.0)


def test_sector_weights_aggregate_holding_weights() -> None:
    analytics = PortfolioAnalytics()
    holdings = [
        PortfolioHolding(ticker="AAPL", quantity=1, sector="Technology", weight=0.4, market_value=400.0),
        PortfolioHolding(ticker="MSFT", quantity=1, sector="Technology", weight=0.2, market_value=200.0),
        PortfolioHolding(ticker="TLT", quantity=1, sector="Fixed Income", weight=0.4, market_value=400.0),
    ]

    sector_weights = analytics.sector_weights(holdings)

    assert np.isclose(sector_weights["Technology"], 0.6)
    assert np.isclose(sector_weights["Fixed Income"], 0.4)
