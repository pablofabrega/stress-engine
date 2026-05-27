from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from app.domain.data.models import FetchResult
from app.domain.portfolio.models import PortfolioHolding
from app.domain.scenarios.historical import HistoricalScenarioRunner
from app.domain.scenarios.presets import get_historical_scenario, list_historical_scenarios


class FakeHistoricalDataFetcher:
    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self.frames = frames

    def fetch(self, ticker: str, start_date: date, end_date: date) -> FetchResult:
        frame = self.frames.get(ticker, pd.DataFrame(columns=["adj_close"]))
        sliced = frame.loc[(frame.index >= pd.Timestamp(start_date)) & (frame.index <= pd.Timestamp(end_date))].copy()
        warnings = [] if not sliced.empty else [f"No historical data returned for ticker {ticker}."]
        return FetchResult(data=sliced, source="fake", cache_hit=False, warnings=warnings)


def _prices_from_returns(returns: list[float], initial_price: float = 100.0) -> pd.Series:
    levels = [initial_price]
    for daily_return in returns:
        levels.append(levels[-1] * (1.0 + daily_return))
    return pd.Series(levels)


def test_historical_scenario_presets_include_phase_five_windows() -> None:
    scenarios = {scenario.key for scenario in list_historical_scenarios()}

    assert scenarios == {"2008-gfc", "2020-covid-crash"}
    assert get_historical_scenario("2008-gfc").start_date == date(2008, 9, 1)
    assert get_historical_scenario("2020-covid-crash").end_date == date(2020, 3, 23)


def test_historical_runner_builds_expected_path_and_attribution() -> None:
    index = pd.date_range("2020-02-17", periods=6, freq="D", name="date")
    frame_map = {
        "AAPL": pd.DataFrame({"adj_close": _prices_from_returns([0.02, 0.01, -0.10, -0.05, 0.02]).values}, index=index),
        "TLT": pd.DataFrame({"adj_close": _prices_from_returns([0.01, 0.00, 0.03, 0.02, -0.01]).values}, index=index),
        "SPY": pd.DataFrame({"adj_close": _prices_from_returns([0.02, 0.01, -0.10, -0.05, 0.02]).values}, index=index),
        "BND": pd.DataFrame({"adj_close": _prices_from_returns([0.01, 0.00, 0.03, 0.02, -0.01]).values}, index=index),
    }
    runner = HistoricalScenarioRunner(historical_data_fetcher=FakeHistoricalDataFetcher(frame_map), correlation_window=2)
    scenario = get_historical_scenario("2020-covid-crash")
    scenario = scenario.__class__(
        key=scenario.key,
        name=scenario.name,
        start_date=date(2020, 2, 20),
        end_date=date(2020, 2, 22),
        description=scenario.description,
    )
    holdings = [
        PortfolioHolding(ticker="AAPL", quantity=1, sector="Technology", asset_class="Equity", market_value=600.0, weight=0.6),
        PortfolioHolding(ticker="TLT", quantity=1, sector="Fixed Income", asset_class="Treasury ETF", market_value=400.0, weight=0.4),
    ]

    result = runner.run_scenario(holdings=holdings, scenario=scenario)

    assert np.isclose(result.portfolio_path["portfolio_value"].iloc[-1], 939.2976)
    assert np.isclose(result.portfolio_path["pnl_dollars"].iloc[-1], -60.7024)
    assert np.isclose(result.portfolio_path["drawdown"].iloc[-1], -0.01334285714285699)
    assert np.isclose(result.comparison_path["spy_cumulative_return"].iloc[-1], -0.1279)
    assert np.isclose(result.comparison_path["benchmark_60_40_cumulative_return"].iloc[-1], -0.0607024)

    contributors = result.contributors.set_index("ticker")
    assert np.isclose(contributors.loc["AAPL", "pnl_dollars"], -76.74)
    assert np.isclose(contributors.loc["TLT", "pnl_dollars"], 16.0376)

    sector_breakdown = result.sector_breakdown.set_index("sector")
    assert np.isclose(sector_breakdown.loc["Technology", "pnl_dollars"], -76.74)
    assert np.isclose(sector_breakdown.loc["Fixed Income", "pnl_dollars"], 16.0376)


def test_historical_runner_flags_correlation_shift() -> None:
    index = pd.date_range("2020-02-17", periods=6, freq="D", name="date")
    frame_map = {
        "AAPL": pd.DataFrame({"adj_close": _prices_from_returns([0.02, 0.01, -0.10, -0.05, 0.02]).values}, index=index),
        "TLT": pd.DataFrame({"adj_close": _prices_from_returns([0.01, 0.00, 0.03, 0.02, -0.01]).values}, index=index),
        "SPY": pd.DataFrame({"adj_close": _prices_from_returns([0.02, 0.01, -0.10, -0.05, 0.02]).values}, index=index),
        "BND": pd.DataFrame({"adj_close": _prices_from_returns([0.01, 0.00, 0.03, 0.02, -0.01]).values}, index=index),
    }
    runner = HistoricalScenarioRunner(historical_data_fetcher=FakeHistoricalDataFetcher(frame_map), correlation_window=2)
    scenario = get_historical_scenario("2020-covid-crash")
    scenario = scenario.__class__(
        key=scenario.key,
        name=scenario.name,
        start_date=date(2020, 2, 20),
        end_date=date(2020, 2, 22),
        description=scenario.description,
    )
    holdings = [
        PortfolioHolding(ticker="AAPL", quantity=1, sector="Technology", asset_class="Equity", market_value=600.0, weight=0.6),
        PortfolioHolding(ticker="TLT", quantity=1, sector="Fixed Income", asset_class="Treasury ETF", market_value=400.0, weight=0.4),
    ]

    result = runner.run_scenario(holdings=holdings, scenario=scenario)

    assert np.isclose(result.correlation_before.loc["AAPL", "TLT"], 1.0)
    assert result.correlation_shift.loc["AAPL", "TLT"] < -1.9
    assert bool(result.significant_correlation_shifts.loc["AAPL", "TLT"]) is True
