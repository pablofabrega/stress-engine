from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from app.domain.data.models import FetchResult
from app.domain.portfolio.models import PortfolioHolding
from app.domain.risk.liquidity import LiquidityRiskAnalyzer


class FakeHistoricalDataFetcher:
    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self.frames = frames

    def fetch(self, ticker: str, start_date: date, end_date: date) -> FetchResult:
        frame = self.frames.get(ticker, pd.DataFrame(columns=["volume"]))
        sliced = frame.loc[(frame.index >= pd.Timestamp(start_date)) & (frame.index <= pd.Timestamp(end_date))].copy()
        warnings = [] if not sliced.empty else [f"No historical data returned for ticker {ticker}."]
        return FetchResult(data=sliced, source="fake", cache_hit=False, warnings=warnings)


def test_liquidity_analyzer_computes_adv_days_to_liquidate_and_haircut() -> None:
    index = pd.date_range("2024-01-01", periods=35, freq="D", name="date")
    frames = {
        "ILLQ": pd.DataFrame({"volume": [100.0] * len(index)}, index=index),
        "LQD": pd.DataFrame({"volume": [10_000.0] * len(index)}, index=index),
    }
    analyzer = LiquidityRiskAnalyzer(historical_data_fetcher=FakeHistoricalDataFetcher(frames))
    holdings = [
        PortfolioHolding(ticker="ILLQ", quantity=100.0, market_value=1_000.0),
        PortfolioHolding(ticker="LQD", quantity=100.0, market_value=1_000.0),
    ]
    stressed_losses = {"ILLQ": -500.0, "LQD": -100.0}

    result = analyzer.analyze(holdings=holdings, stressed_losses=stressed_losses, as_of_date=date(2024, 2, 4))

    table = {row.ticker: row for row in result.holdings}
    assert np.isclose(table["ILLQ"].adv_30d, 100.0)
    assert np.isclose(table["ILLQ"].days_to_liquidate_10pct, 10.0)
    assert np.isclose(table["ILLQ"].liquidity_haircut_dollars, 20.0)
    assert np.isclose(table["ILLQ"].liquidity_adjusted_loss_dollars, -520.0)
    assert np.isclose(table["LQD"].days_to_liquidate_10pct, 0.1)
    assert np.isclose(table["LQD"].liquidity_haircut_dollars, 0.0)
    assert np.isclose(result.liquidity_adjusted_loss_dollars, -620.0)

