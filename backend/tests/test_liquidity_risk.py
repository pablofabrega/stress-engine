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
        frame = self.frames.get(ticker)
        if frame is None or frame.empty:
            return FetchResult(
                data=pd.DataFrame(columns=["volume"]),
                source="fake",
                cache_hit=False,
                warnings=[f"No historical data returned for ticker {ticker}."],
            )
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


def _constant_volume_frame(volume: float, periods: int = 35) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=periods, freq="D", name="date")
    return pd.DataFrame({"volume": [volume] * periods}, index=index)


def test_adv_uses_only_the_trailing_30_observations() -> None:
    index = pd.date_range("2024-01-01", periods=40, freq="D", name="date")
    volume = [99_999.0] * 10 + [200.0] * 30
    analyzer = LiquidityRiskAnalyzer(
        historical_data_fetcher=FakeHistoricalDataFetcher({"AAA": pd.DataFrame({"volume": volume}, index=index)})
    )
    holdings = [PortfolioHolding(ticker="AAA", quantity=300.0, market_value=1_000.0)]

    result = analyzer.analyze(holdings=holdings, stressed_losses={"AAA": -1_000.0}, as_of_date=date(2024, 2, 9))

    row = result.holdings[0]
    assert np.isclose(row.adv_30d, 200.0)
    assert np.isclose(row.position_pct_adv, 1.5)


def test_days_to_liquidate_scale_inversely_with_participation_rate() -> None:
    analyzer = LiquidityRiskAnalyzer(
        historical_data_fetcher=FakeHistoricalDataFetcher({"AAA": _constant_volume_frame(200.0)})
    )
    holdings = [PortfolioHolding(ticker="AAA", quantity=300.0, market_value=1_000.0)]

    result = analyzer.analyze(holdings=holdings, stressed_losses={"AAA": -1_000.0}, as_of_date=date(2024, 2, 4))

    row = result.holdings[0]
    assert np.isclose(row.days_to_liquidate_10pct, 15.0)
    assert np.isclose(row.days_to_liquidate_20pct, 7.5)
    assert np.isclose(row.days_to_liquidate_30pct, 5.0)
    assert np.isclose(row.liquidity_haircut_dollars, 60.0)
    assert np.isclose(row.liquidity_adjusted_loss_dollars, -1_060.0)


def test_no_haircut_when_days_to_liquidate_is_exactly_five() -> None:
    analyzer = LiquidityRiskAnalyzer(
        historical_data_fetcher=FakeHistoricalDataFetcher({"AAA": _constant_volume_frame(200.0)})
    )
    holdings = [PortfolioHolding(ticker="AAA", quantity=100.0, market_value=1_000.0)]

    result = analyzer.analyze(holdings=holdings, stressed_losses={"AAA": -1_000.0}, as_of_date=date(2024, 2, 4))

    row = result.holdings[0]
    assert np.isclose(row.days_to_liquidate_10pct, 5.0)
    assert np.isclose(row.liquidity_haircut_dollars, 0.0)
    assert np.isclose(row.liquidity_adjusted_loss_dollars, -1_000.0)


def test_gains_are_never_haircut_even_when_illiquid() -> None:
    analyzer = LiquidityRiskAnalyzer(
        historical_data_fetcher=FakeHistoricalDataFetcher({"AAA": _constant_volume_frame(200.0)})
    )
    holdings = [PortfolioHolding(ticker="AAA", quantity=300.0, market_value=1_000.0)]

    result = analyzer.analyze(holdings=holdings, stressed_losses={"AAA": 500.0}, as_of_date=date(2024, 2, 4))

    row = result.holdings[0]
    assert row.days_to_liquidate_10pct > 5
    assert np.isclose(row.liquidity_haircut_dollars, 0.0)
    assert np.isclose(row.liquidity_adjusted_loss_dollars, 500.0)


def test_haircut_multiplier_and_participation_rates_are_parameterized() -> None:
    analyzer = LiquidityRiskAnalyzer(
        historical_data_fetcher=FakeHistoricalDataFetcher({"AAA": _constant_volume_frame(200.0)})
    )
    holdings = [PortfolioHolding(ticker="AAA", quantity=300.0, market_value=1_000.0)]

    result = analyzer.analyze(
        holdings=holdings,
        stressed_losses={"AAA": -1_000.0},
        as_of_date=date(2024, 2, 4),
        participation_rates=(0.05, 0.10, 0.15),
        haircut_multiplier=0.04,
    )

    row = result.holdings[0]
    assert np.isclose(row.days_to_liquidate_10pct, 30.0)
    assert np.isclose(row.liquidity_haircut_dollars, 240.0)


def test_missing_volume_data_yields_nan_metrics_and_warning() -> None:
    analyzer = LiquidityRiskAnalyzer(historical_data_fetcher=FakeHistoricalDataFetcher({}))
    holdings = [PortfolioHolding(ticker="GHOST", quantity=100.0, market_value=1_000.0)]

    result = analyzer.analyze(holdings=holdings, stressed_losses={"GHOST": -500.0}, as_of_date=date(2024, 2, 4))

    row = result.holdings[0]
    assert np.isnan(row.adv_30d)
    assert np.isnan(row.position_pct_adv)
    assert np.isnan(row.days_to_liquidate_10pct)
    assert np.isclose(row.liquidity_haircut_dollars, 0.0)
    assert np.isclose(row.liquidity_adjusted_loss_dollars, -500.0)
    assert result.warnings


def test_holdings_are_ranked_by_days_to_liquidate_descending() -> None:
    frames = {
        "ILLQ": _constant_volume_frame(100.0),
        "LIQ": _constant_volume_frame(10_000.0),
    }
    analyzer = LiquidityRiskAnalyzer(historical_data_fetcher=FakeHistoricalDataFetcher(frames))
    holdings = [
        PortfolioHolding(ticker="LIQ", quantity=100.0, market_value=1_000.0),
        PortfolioHolding(ticker="ILLQ", quantity=100.0, market_value=1_000.0),
        PortfolioHolding(ticker="GHOST", quantity=100.0, market_value=1_000.0),
    ]

    result = analyzer.analyze(
        holdings=holdings,
        stressed_losses={"LIQ": -100.0, "ILLQ": -500.0, "GHOST": -100.0},
        as_of_date=date(2024, 2, 4),
    )

    ranked_tickers = [row.ticker for row in result.holdings]
    assert ranked_tickers[0] == "ILLQ"
    assert ranked_tickers[-1] == "GHOST"


def test_portfolio_totals_sum_holding_level_values() -> None:
    frames = {
        "ILLQ": _constant_volume_frame(100.0),
        "LIQ": _constant_volume_frame(10_000.0),
    }
    analyzer = LiquidityRiskAnalyzer(historical_data_fetcher=FakeHistoricalDataFetcher(frames))
    holdings = [
        PortfolioHolding(ticker="ILLQ", quantity=100.0, market_value=1_000.0),
        PortfolioHolding(ticker="LIQ", quantity=100.0, market_value=1_000.0),
    ]
    stressed_losses = {"ILLQ": -500.0, "LIQ": -100.0}

    result = analyzer.analyze(holdings=holdings, stressed_losses=stressed_losses, as_of_date=date(2024, 2, 4))

    assert np.isclose(result.stressed_loss_dollars, sum(r.stressed_loss_dollars for r in result.holdings))
    assert np.isclose(result.total_liquidity_haircut_dollars, sum(r.liquidity_haircut_dollars for r in result.holdings))
    assert np.isclose(result.liquidity_adjusted_loss_dollars, sum(r.liquidity_adjusted_loss_dollars for r in result.holdings))
    assert np.isclose(result.stressed_loss_dollars, -600.0)


def test_empty_portfolio_returns_zeroed_totals() -> None:
    analyzer = LiquidityRiskAnalyzer(historical_data_fetcher=FakeHistoricalDataFetcher({}))

    result = analyzer.analyze(holdings=[], stressed_losses={}, as_of_date=date(2024, 2, 4))

    assert result.holdings == []
    assert np.isclose(result.stressed_loss_dollars, 0.0)
    assert np.isclose(result.total_liquidity_haircut_dollars, 0.0)
    assert np.isclose(result.liquidity_adjusted_loss_dollars, 0.0)

