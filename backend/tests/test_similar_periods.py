from __future__ import annotations

from datetime import date

import pandas as pd

from app.domain.data.models import FetchResult
from app.domain.portfolio.models import PortfolioHolding
from app.domain.risk.similar_periods import SimilarPeriodsFinder


class FakeHistoricalDataFetcher:
    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self.frames = frames

    def fetch(self, ticker: str, start_date: date, end_date: date) -> FetchResult:
        frame = self.frames.get(ticker, pd.DataFrame(columns=["adj_close"]))
        sliced = frame.loc[(frame.index >= pd.Timestamp(start_date)) & (frame.index <= pd.Timestamp(end_date))].copy()
        return FetchResult(data=sliced, source="fake", cache_hit=False, warnings=[])


class FakeMacroDataFetcher:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame

    def fetch_default_macro_bundle(self, start_date: date, end_date: date) -> pd.DataFrame:
        return self.frame.loc[(self.frame.index >= pd.Timestamp(start_date)) & (self.frame.index <= pd.Timestamp(end_date))].copy()


def test_similar_periods_finder_returns_ranked_windows() -> None:
    index = pd.date_range("2024-01-01", periods=12, freq="D", name="date")
    spy = pd.DataFrame({"adj_close": [100, 99, 97, 95, 96, 98, 97, 95, 93, 92, 94, 96]}, index=index)
    bnd = pd.DataFrame({"adj_close": [100, 100.2, 100.1, 100.0, 99.9, 100.1, 100.0, 99.8, 99.7, 99.6, 99.8, 100.0]}, index=index)
    macro = pd.DataFrame(
        {
            "10y_treasury_yield": [4.0, 4.02, 4.05, 4.10, 4.08, 4.06, 4.09, 4.14, 4.20, 4.25, 4.18, 4.12],
            "vix": [15, 16, 18, 22, 21, 19, 20, 24, 28, 30, 25, 20],
            "hy_credit_spread": [3.0, 3.05, 3.10, 3.30, 3.20, 3.15, 3.18, 3.40, 3.60, 3.75, 3.50, 3.30],
        },
        index=index,
    )
    finder = SimilarPeriodsFinder(
        historical_data_fetcher=FakeHistoricalDataFetcher({"SPY": spy, "BND": bnd, "AAPL": spy}),
        macro_data_fetcher=FakeMacroDataFetcher(macro),
    )
    holdings = [PortfolioHolding(ticker="AAPL", quantity=1, market_value=100.0, weight=1.0, sector="Technology", asset_class="Equity")]

    periods = finder.find(
        shock_vector={
            "equity_return": -0.05,
            "vol_change": 6.0,
            "rate_change_10y": 0.15,
            "credit_spread_change": 0.35,
            "equity_bond_correlation_shift": 0.10,
        },
        holdings=holdings,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 12),
        window_days=3,
        top_k=3,
    )

    assert len(periods) == 3
    assert periods[0].similarity_score >= periods[1].similarity_score >= periods[2].similarity_score
    assert periods[0].portfolio_return is not None
