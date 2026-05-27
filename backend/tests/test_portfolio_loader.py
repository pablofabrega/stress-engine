from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from app.domain.data.models import FetchResult
from app.domain.portfolio.loader import PortfolioLoader
from app.domain.portfolio.metadata import SecurityMetadataResolver


class FakeHistoricalDataFetcher:
    def __init__(self, price_map: dict[str, float | None]) -> None:
        self.price_map = price_map

    def fetch(self, ticker: str, start_date: date, end_date: date) -> FetchResult:
        price = self.price_map.get(ticker)
        if price is None:
            return FetchResult(
                data=pd.DataFrame(columns=["adj_close"]),
                source="fake",
                cache_hit=False,
                warnings=[f"No historical data returned for ticker {ticker}."],
            )
        frame = pd.DataFrame(
            {"adj_close": [price - 1.0, price]},
            index=pd.date_range("2024-01-01", periods=2, freq="D", name="date"),
        )
        return FetchResult(data=frame, source="fake", cache_hit=False)


def test_load_from_json_normalizes_weights_and_tags_holdings() -> None:
    loader = PortfolioLoader(
        metadata_resolver=SecurityMetadataResolver(use_yfinance_fallback=False),
        historical_data_fetcher=FakeHistoricalDataFetcher({"AAPL": 200.0, "TLT": 100.0}),
    )

    result = loader.load_from_json(
        name="Interview Portfolio",
        holdings_payload={
            "AAPL": {"quantity": 10, "cost_basis": 150.0},
            "TLT": {"quantity": 5, "cost_basis": 90.0},
        },
    )

    assert result.name == "Interview Portfolio"
    assert np.isclose(sum(holding.weight for holding in result.holdings), 1.0)
    assert result.total_market_value == 2500.0
    assert {holding.ticker for holding in result.holdings} == {"AAPL", "TLT"}
    sectors = {holding.ticker: holding.sector for holding in result.holdings}
    assert sectors["AAPL"] == "Technology"
    assert sectors["TLT"] == "Fixed Income"


def test_load_from_csv_aggregates_duplicate_rows() -> None:
    csv_text = """ticker,quantity,cost_basis
AAPL,4,150
AAPL,6,180
MSFT,3,400
"""
    loader = PortfolioLoader(
        metadata_resolver=SecurityMetadataResolver(use_yfinance_fallback=False),
        historical_data_fetcher=FakeHistoricalDataFetcher({"AAPL": 210.0, "MSFT": 420.0}),
    )

    result = loader.load_from_csv(name="CSV Portfolio", csv_source=csv_text)

    holdings = {holding.ticker: holding for holding in result.holdings}
    assert set(holdings) == {"AAPL", "MSFT"}
    assert holdings["AAPL"].quantity == 10.0
    assert np.isclose(holdings["AAPL"].cost_basis or 0.0, 168.0)


def test_load_preset_materializes_target_weights_into_holdings() -> None:
    loader = PortfolioLoader(
        metadata_resolver=SecurityMetadataResolver(use_yfinance_fallback=False),
        historical_data_fetcher=FakeHistoricalDataFetcher({"SPY": 500.0, "BND": 75.0}),
    )

    result = loader.load_preset("classic-60-40", total_notional=1_000_000.0)

    weights = {holding.ticker: holding.weight for holding in result.holdings}
    assert np.isclose(weights["SPY"], 0.60)
    assert np.isclose(weights["BND"], 0.40)
    assert np.isclose(result.total_market_value, 1_000_000.0)

