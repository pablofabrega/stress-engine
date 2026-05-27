from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from app.domain.data.models import FetchResult
from app.domain.portfolio.analytics import FIXED_INCOME_DURATION_ESTIMATES, PortfolioAnalytics
from app.domain.portfolio.models import PortfolioHolding


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

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


def _holdings(*specs: tuple[str, float, float, str, str]) -> list[PortfolioHolding]:
    """Build holdings from (ticker, quantity, market_value, asset_class, sector) tuples."""
    total_mv = sum(s[2] for s in specs)
    return [
        PortfolioHolding(
            ticker=t,
            quantity=q,
            market_value=mv,
            weight=mv / total_mv if total_mv > 0 else 0.0,
            asset_class=ac,
            sector=sec,
        )
        for t, q, mv, ac, sec in specs
    ]


# ---------------------------------------------------------------------------
# current_market_value
# ---------------------------------------------------------------------------

class TestCurrentMarketValue:
    def test_sums_holdings(self) -> None:
        holdings = _holdings(
            ("AAPL", 100, 18000.0, "Equity", "Technology"),
            ("MSFT", 50, 20000.0, "Equity", "Technology"),
        )
        analytics = PortfolioAnalytics(historical_data_fetcher=FakeHistoricalDataFetcher({}))
        assert analytics.current_market_value(holdings) == pytest.approx(38000.0)

    def test_empty_portfolio(self) -> None:
        analytics = PortfolioAnalytics(historical_data_fetcher=FakeHistoricalDataFetcher({}))
        assert analytics.current_market_value([]) == 0.0


# ---------------------------------------------------------------------------
# holding_weights
# ---------------------------------------------------------------------------

class TestHoldingWeights:
    def test_returns_ticker_weight_map(self) -> None:
        holdings = _holdings(
            ("AAPL", 100, 60000.0, "Equity", "Technology"),
            ("BND", 200, 40000.0, "Fixed Income ETF", "Fixed Income"),
        )
        analytics = PortfolioAnalytics(historical_data_fetcher=FakeHistoricalDataFetcher({}))
        weights = analytics.holding_weights(holdings)

        assert weights["AAPL"] == pytest.approx(0.6)
        assert weights["BND"] == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# sector_weights
# ---------------------------------------------------------------------------

class TestSectorWeights:
    def test_aggregates_by_sector(self) -> None:
        holdings = _holdings(
            ("AAPL", 100, 18000.0, "Equity", "Technology"),
            ("MSFT", 50, 12000.0, "Equity", "Technology"),
            ("BND", 200, 20000.0, "Fixed Income ETF", "Fixed Income"),
        )
        analytics = PortfolioAnalytics(historical_data_fetcher=FakeHistoricalDataFetcher({}))
        sw = analytics.sector_weights(holdings)

        assert sw["Technology"] == pytest.approx(0.6)
        assert sw["Fixed Income"] == pytest.approx(0.4)

    def test_sorted_alphabetically(self) -> None:
        holdings = _holdings(
            ("XLU", 50, 5000.0, "Sector ETF", "Utilities"),
            ("AAPL", 100, 5000.0, "Equity", "Technology"),
        )
        analytics = PortfolioAnalytics(historical_data_fetcher=FakeHistoricalDataFetcher({}))
        sw = analytics.sector_weights(holdings)
        assert list(sw.keys()) == sorted(sw.keys())


# ---------------------------------------------------------------------------
# portfolio_return_history
# ---------------------------------------------------------------------------

class TestPortfolioReturnHistory:
    def test_weighted_returns(self) -> None:
        idx = pd.date_range("2024-01-02", periods=5, freq="B")
        frames = {
            "A": pd.DataFrame({"adj_close": [100.0, 110.0, 105.0, 108.0, 112.0]}, index=idx),
            "B": pd.DataFrame({"adj_close": [50.0, 48.0, 52.0, 51.0, 55.0]}, index=idx),
        }
        holdings = _holdings(
            ("A", 100, 60000.0, "Equity", "Tech"),
            ("B", 200, 40000.0, "Equity", "Finance"),
        )
        analytics = PortfolioAnalytics(
            historical_data_fetcher=FakeHistoricalDataFetcher(frames),
        )
        history = analytics.portfolio_return_history(holdings, date(2024, 1, 2), date(2024, 1, 8))

        assert not history.portfolio_returns.empty
        assert len(history.component_returns.columns) == 2
        assert history.weights_used["A"] == pytest.approx(0.6)
        assert history.weights_used["B"] == pytest.approx(0.4)

    def test_empty_when_no_data(self) -> None:
        holdings = _holdings(("MISSING", 100, 10000.0, "Equity", "Tech"))
        analytics = PortfolioAnalytics(
            historical_data_fetcher=FakeHistoricalDataFetcher({}),
        )
        history = analytics.portfolio_return_history(holdings, date(2024, 1, 1), date(2024, 3, 1))

        assert history.portfolio_returns.empty
        assert history.component_returns.empty
        assert len(history.warnings) > 0

    def test_single_holding_returns_match_asset(self) -> None:
        idx = pd.date_range("2024-01-02", periods=4, freq="B")
        prices = [100.0, 110.0, 105.0, 115.0]
        frames = {"SPY": pd.DataFrame({"adj_close": prices}, index=idx)}
        holdings = _holdings(("SPY", 100, 50000.0, "Equity ETF", "Broad Market"))
        analytics = PortfolioAnalytics(
            historical_data_fetcher=FakeHistoricalDataFetcher(frames),
        )
        history = analytics.portfolio_return_history(holdings, date(2024, 1, 2), date(2024, 1, 5))

        expected = pd.Series(prices, index=idx).pct_change()
        pd.testing.assert_series_equal(
            history.portfolio_returns.dropna(),
            expected.dropna().rename("portfolio_return"),
            check_names=False,
        )


# ---------------------------------------------------------------------------
# estimate_dv01
# ---------------------------------------------------------------------------

class TestEstimateDV01:
    def test_known_fi_holding(self) -> None:
        holdings = _holdings(("TLT", 100, 100000.0, "Treasury ETF", "Fixed Income"))
        analytics = PortfolioAnalytics(historical_data_fetcher=FakeHistoricalDataFetcher({}))
        summary = analytics.estimate_dv01(holdings)

        assert len(summary.holdings) == 1
        result = summary.holdings[0]
        assert result.ticker == "TLT"
        assert result.estimated_duration == 17.0
        expected_dv01 = 100000.0 * 17.0 * 0.0001
        assert result.dv01 == pytest.approx(expected_dv01)
        assert summary.total_dv01 == pytest.approx(expected_dv01)

    def test_equity_holdings_skipped(self) -> None:
        holdings = _holdings(
            ("AAPL", 100, 18000.0, "Equity", "Technology"),
            ("MSFT", 50, 20000.0, "Equity", "Technology"),
        )
        analytics = PortfolioAnalytics(historical_data_fetcher=FakeHistoricalDataFetcher({}))
        summary = analytics.estimate_dv01(holdings)

        assert len(summary.holdings) == 0
        assert summary.total_dv01 == 0.0

    def test_mixed_portfolio(self) -> None:
        holdings = _holdings(
            ("AAPL", 100, 18000.0, "Equity", "Technology"),
            ("BND", 500, 35000.0, "Fixed Income ETF", "Fixed Income"),
            ("TLT", 100, 9000.0, "Treasury ETF", "Fixed Income"),
        )
        analytics = PortfolioAnalytics(historical_data_fetcher=FakeHistoricalDataFetcher({}))
        summary = analytics.estimate_dv01(holdings)

        assert len(summary.holdings) == 2
        tickers = {r.ticker for r in summary.holdings}
        assert tickers == {"BND", "TLT"}

        bnd_dv01 = 35000.0 * 6.5 * 0.0001
        tlt_dv01 = 9000.0 * 17.0 * 0.0001
        assert summary.total_dv01 == pytest.approx(bnd_dv01 + tlt_dv01)

    def test_unknown_fi_ticker_uses_default_duration(self) -> None:
        holdings = _holdings(("XBND", 100, 50000.0, "Fixed Income ETF", "Fixed Income"))
        analytics = PortfolioAnalytics(historical_data_fetcher=FakeHistoricalDataFetcher({}))
        summary = analytics.estimate_dv01(holdings)

        assert len(summary.holdings) == 1
        assert summary.holdings[0].estimated_duration == 5.0
        assert len(summary.warnings) == 1
        assert "default 5.0" in summary.warnings[0]

    def test_credit_etf_included(self) -> None:
        holdings = _holdings(("HYG", 200, 16000.0, "Credit ETF", "Fixed Income"))
        analytics = PortfolioAnalytics(historical_data_fetcher=FakeHistoricalDataFetcher({}))
        summary = analytics.estimate_dv01(holdings)

        assert len(summary.holdings) == 1
        assert summary.holdings[0].estimated_duration == 3.8

    def test_duration_estimates_table_complete(self) -> None:
        expected_tickers = {"BND", "TLT", "IEF", "SHY", "AGG", "TIPS", "LQD", "HYG", "JNK"}
        assert expected_tickers.issubset(FIXED_INCOME_DURATION_ESTIMATES.keys())

    def test_empty_portfolio(self) -> None:
        analytics = PortfolioAnalytics(historical_data_fetcher=FakeHistoricalDataFetcher({}))
        summary = analytics.estimate_dv01([])
        assert summary.total_dv01 == 0.0
        assert len(summary.holdings) == 0
