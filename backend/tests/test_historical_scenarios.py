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
        frame = self.frames.get(ticker)
        if frame is None or frame.empty:
            return FetchResult(
                data=pd.DataFrame(columns=["adj_close"]),
                source="fake",
                cache_hit=False,
                warnings=[f"No historical data returned for ticker {ticker}."],
            )
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

    assert scenarios == {
        "2008-gfc",
        "2020-covid-crash",
        "2022-rate-tightening",
        "2018-q4-selloff",
        "2000-dot-com",
    }
    assert get_historical_scenario("2008-gfc").start_date == date(2008, 9, 1)
    assert get_historical_scenario("2020-covid-crash").end_date == date(2020, 3, 23)


def test_historical_scenario_presets_match_agents_spec_windows() -> None:
    expected = {
        "2008-gfc": (date(2008, 9, 1), date(2009, 3, 31)),
        "2020-covid-crash": (date(2020, 2, 19), date(2020, 3, 23)),
        "2022-rate-tightening": (date(2022, 1, 1), date(2022, 12, 31)),
        "2018-q4-selloff": (date(2018, 10, 1), date(2018, 12, 24)),
        "2000-dot-com": (date(2000, 3, 10), date(2002, 10, 9)),
    }

    for key, (start, end) in expected.items():
        scenario = get_historical_scenario(key)
        assert scenario.start_date == start
        assert scenario.end_date == end
        assert scenario.name
        assert scenario.description


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


def _two_day_scenario():
    scenario = get_historical_scenario("2020-covid-crash")
    return scenario.__class__(
        key=scenario.key,
        name=scenario.name,
        start_date=date(2020, 2, 20),
        end_date=date(2020, 2, 22),
        description=scenario.description,
    )


def _make_contributors() -> pd.DataFrame:
    rows = [
        {"ticker": ticker, "sector": "Equity", "asset_class": "Equity", "pnl_dollars": pnl,
         "pnl_pct_of_portfolio": 0.0, "contribution_pct_of_total_pnl": 0.0}
        for ticker, pnl in [
            ("A", -50.0), ("B", -40.0), ("C", -30.0), ("D", -20.0),
            ("E", -10.0), ("F", 5.0), ("G", 15.0), ("H", 25.0),
        ]
    ]
    return pd.DataFrame(rows)


def test_top_worst_contributors_returns_n_largest_losers() -> None:
    worst = HistoricalScenarioRunner.top_worst_contributors(_make_contributors(), n=5)

    assert list(worst["ticker"]) == ["A", "B", "C", "D", "E"]
    assert worst["pnl_dollars"].iloc[0] == -50.0


def test_top_best_contributors_returns_n_largest_gainers() -> None:
    best = HistoricalScenarioRunner.top_best_contributors(_make_contributors(), n=5)

    assert list(best["ticker"]) == ["H", "G", "F", "E", "D"]
    assert best["pnl_dollars"].iloc[0] == 25.0


def test_top_contributors_handle_empty_frame() -> None:
    empty = pd.DataFrame()

    assert HistoricalScenarioRunner.top_worst_contributors(empty).empty
    assert HistoricalScenarioRunner.top_best_contributors(empty).empty


def test_top_contributors_clamp_to_available_rows() -> None:
    contributors = _make_contributors().head(3)

    worst = HistoricalScenarioRunner.top_worst_contributors(contributors, n=5)

    assert len(worst) == 3


def test_runner_skips_ticker_with_no_data_and_surfaces_warning() -> None:
    index = pd.date_range("2020-02-17", periods=6, freq="D", name="date")
    frame_map = {
        "AAPL": pd.DataFrame({"adj_close": _prices_from_returns([0.02, 0.01, -0.10, -0.05, 0.02]).values}, index=index),
        "SPY": pd.DataFrame({"adj_close": _prices_from_returns([0.02, 0.01, -0.10, -0.05, 0.02]).values}, index=index),
        "BND": pd.DataFrame({"adj_close": _prices_from_returns([0.01, 0.00, 0.03, 0.02, -0.01]).values}, index=index),
    }
    runner = HistoricalScenarioRunner(historical_data_fetcher=FakeHistoricalDataFetcher(frame_map), correlation_window=2)
    holdings = [
        PortfolioHolding(ticker="AAPL", quantity=1, sector="Technology", asset_class="Equity", market_value=600.0, weight=0.6),
        PortfolioHolding(ticker="ZZZZ", quantity=1, sector="Unknown", asset_class="Equity", market_value=400.0, weight=0.4),
    ]

    result = runner.run_scenario(holdings=holdings, scenario=_two_day_scenario())

    assert "ZZZZ" not in set(result.contributors["ticker"])
    assert set(result.contributors["ticker"]) == {"AAPL"}
    assert any("ZZZZ" in warning for warning in result.warnings)


def test_runner_returns_empty_result_when_no_overlap() -> None:
    index = pd.date_range("2019-01-01", periods=5, freq="D", name="date")
    frame_map = {
        "AAPL": pd.DataFrame({"adj_close": _prices_from_returns([0.01, 0.01, 0.01, 0.01]).values}, index=index),
    }
    runner = HistoricalScenarioRunner(historical_data_fetcher=FakeHistoricalDataFetcher(frame_map), correlation_window=2)
    holdings = [
        PortfolioHolding(ticker="AAPL", quantity=1, sector="Technology", asset_class="Equity", market_value=600.0, weight=1.0),
    ]

    result = runner.run_scenario(holdings=holdings, scenario=_two_day_scenario())

    assert result.portfolio_path.empty
    assert result.contributors.empty
    assert result.warnings


def test_run_dispatches_via_scenario_key() -> None:
    index = pd.date_range("2020-02-17", periods=6, freq="D", name="date")
    frame_map = {
        "AAPL": pd.DataFrame({"adj_close": _prices_from_returns([0.02, 0.01, -0.10, -0.05, 0.02]).values}, index=index),
        "SPY": pd.DataFrame({"adj_close": _prices_from_returns([0.02, 0.01, -0.10, -0.05, 0.02]).values}, index=index),
        "BND": pd.DataFrame({"adj_close": _prices_from_returns([0.01, 0.00, 0.03, 0.02, -0.01]).values}, index=index),
    }
    runner = HistoricalScenarioRunner(historical_data_fetcher=FakeHistoricalDataFetcher(frame_map), correlation_window=2)
    holdings = [
        PortfolioHolding(ticker="AAPL", quantity=1, sector="Technology", asset_class="Equity", market_value=600.0, weight=1.0),
    ]

    result = runner.run(holdings=holdings, scenario_key="2020-covid-crash")

    assert result.scenario.key == "2020-covid-crash"


def test_pnl_percent_and_drawdown_consistency() -> None:
    index = pd.date_range("2020-02-17", periods=6, freq="D", name="date")
    frame_map = {
        "AAPL": pd.DataFrame({"adj_close": _prices_from_returns([0.02, 0.01, -0.10, -0.05, 0.02]).values}, index=index),
        "TLT": pd.DataFrame({"adj_close": _prices_from_returns([0.01, 0.00, 0.03, 0.02, -0.01]).values}, index=index),
        "SPY": pd.DataFrame({"adj_close": _prices_from_returns([0.02, 0.01, -0.10, -0.05, 0.02]).values}, index=index),
        "BND": pd.DataFrame({"adj_close": _prices_from_returns([0.01, 0.00, 0.03, 0.02, -0.01]).values}, index=index),
    }
    runner = HistoricalScenarioRunner(historical_data_fetcher=FakeHistoricalDataFetcher(frame_map), correlation_window=2)
    holdings = [
        PortfolioHolding(ticker="AAPL", quantity=1, sector="Technology", asset_class="Equity", market_value=600.0, weight=0.6),
        PortfolioHolding(ticker="TLT", quantity=1, sector="Fixed Income", asset_class="Treasury ETF", market_value=400.0, weight=0.4),
    ]

    path = runner.run_scenario(holdings=holdings, scenario=_two_day_scenario()).portfolio_path

    initial_value = 1000.0
    reconstructed = path["portfolio_value"] / initial_value - 1.0
    assert np.allclose(reconstructed.values, path["cumulative_return"].values)
    assert np.allclose(path["pnl_dollars"].values, (path["portfolio_value"] - initial_value).values)
    assert (path["drawdown"] <= 1e-9).all()


def test_sector_and_asset_class_breakdown_sum_to_total_pnl() -> None:
    index = pd.date_range("2020-02-17", periods=6, freq="D", name="date")
    frame_map = {
        "AAPL": pd.DataFrame({"adj_close": _prices_from_returns([0.02, 0.01, -0.10, -0.05, 0.02]).values}, index=index),
        "TLT": pd.DataFrame({"adj_close": _prices_from_returns([0.01, 0.00, 0.03, 0.02, -0.01]).values}, index=index),
        "SPY": pd.DataFrame({"adj_close": _prices_from_returns([0.02, 0.01, -0.10, -0.05, 0.02]).values}, index=index),
        "BND": pd.DataFrame({"adj_close": _prices_from_returns([0.01, 0.00, 0.03, 0.02, -0.01]).values}, index=index),
    }
    runner = HistoricalScenarioRunner(historical_data_fetcher=FakeHistoricalDataFetcher(frame_map), correlation_window=2)
    holdings = [
        PortfolioHolding(ticker="AAPL", quantity=1, sector="Technology", asset_class="Equity", market_value=600.0, weight=0.6),
        PortfolioHolding(ticker="TLT", quantity=1, sector="Fixed Income", asset_class="Treasury ETF", market_value=400.0, weight=0.4),
    ]

    result = runner.run_scenario(holdings=holdings, scenario=_two_day_scenario())
    total_pnl = result.contributors["pnl_dollars"].sum()

    assert np.isclose(result.sector_breakdown["pnl_dollars"].sum(), total_pnl)
    assert np.isclose(result.asset_class_breakdown["pnl_dollars"].sum(), total_pnl)
    assert np.isclose(result.sector_breakdown["contribution_pct_of_total_pnl"].sum(), 1.0)


def test_comparison_path_handles_missing_benchmark_leg() -> None:
    index = pd.date_range("2020-02-17", periods=6, freq="D", name="date")
    frame_map = {
        "AAPL": pd.DataFrame({"adj_close": _prices_from_returns([0.02, 0.01, -0.10, -0.05, 0.02]).values}, index=index),
        "SPY": pd.DataFrame({"adj_close": _prices_from_returns([0.02, 0.01, -0.10, -0.05, 0.02]).values}, index=index),
    }
    runner = HistoricalScenarioRunner(historical_data_fetcher=FakeHistoricalDataFetcher(frame_map), correlation_window=2)
    holdings = [
        PortfolioHolding(ticker="AAPL", quantity=1, sector="Technology", asset_class="Equity", market_value=600.0, weight=1.0),
    ]

    comparison = runner.run_scenario(holdings=holdings, scenario=_two_day_scenario()).comparison_path

    assert "spy_cumulative_return" in comparison.columns
    assert "benchmark_60_40_cumulative_return" in comparison.columns
