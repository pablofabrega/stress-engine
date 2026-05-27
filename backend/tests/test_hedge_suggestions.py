from __future__ import annotations

from datetime import date

import pandas as pd

from app.domain.data.models import FetchResult
from app.domain.portfolio.models import FactorDecompositionResult, PortfolioHolding
from app.domain.risk.hedges import HedgeSuggestionEngine
from app.domain.risk.models import ConcentrationMetrics, DrawdownSummary, RiskAnalyticsResult


class FakeHistoricalDataFetcher:
    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self.frames = frames

    def fetch(self, ticker: str, start_date: date, end_date: date) -> FetchResult:
        frame = self.frames.get(ticker, pd.DataFrame(columns=["adj_close"]))
        return FetchResult(data=frame.copy(), source="fake", cache_hit=False, warnings=[])


def test_hedge_suggestion_engine_emits_expected_triggered_suggestions() -> None:
    index = pd.date_range("2020-02-20", periods=3, freq="D", name="date")
    frames = {
        "TLT": pd.DataFrame({"adj_close": [100.0, 98.0, 96.0]}, index=index),
        "LQD": pd.DataFrame({"adj_close": [100.0, 99.0, 98.0]}, index=index),
        "HYG": pd.DataFrame({"adj_close": [100.0, 95.0, 92.0]}, index=index),
    }
    engine = HedgeSuggestionEngine(historical_data_fetcher=FakeHistoricalDataFetcher(frames))
    holdings = [
        PortfolioHolding(ticker="AAPL", quantity=1, market_value=450.0, weight=0.45, sector="Technology", asset_class="Equity"),
        PortfolioHolding(ticker="MSFT", quantity=1, market_value=150.0, weight=0.15, sector="Technology", asset_class="Equity"),
        PortfolioHolding(ticker="TLT", quantity=1, market_value=200.0, weight=0.20, sector="Fixed Income", asset_class="Treasury ETF"),
        PortfolioHolding(ticker="HYG", quantity=1, market_value=200.0, weight=0.20, sector="Fixed Income", asset_class="Credit ETF"),
    ]
    risk_summary = RiskAnalyticsResult(
        var_95=0.03,
        var_99=0.05,
        cvar_95=0.04,
        latest_rolling_vol=0.18,
        drawdown=DrawdownSummary(-0.25, None, None, None, None),
        concentration=ConcentrationMetrics(0.325, 0.80, 1.00),
        latest_correlation_matrix=pd.DataFrame(),
        rolling_correlation_matrix=pd.DataFrame(),
        factor_exposure_summary=FactorDecompositionResult(0.0, 0.0, 1.35, 4.0, 0.1, 1.0, -0.1, -1.0, 0.9, 100, []),
        warnings=[],
    )
    scenario_result = type(
        "ScenarioResult",
        (),
        {
            "comparison_path": pd.DataFrame({"spy_cumulative_return": [-0.20]}),
            "portfolio_path": pd.DataFrame({"pnl_dollars": [-200.0]}),
            "scenario": type("ScenarioDef", (), {"start_date": date(2020, 2, 20), "end_date": date(2020, 2, 22)})(),
        },
    )()

    suggestions = engine.suggest(holdings=holdings, risk_summary=risk_summary, scenario_result=scenario_result)

    instruments = [suggestion.instrument for suggestion in suggestions]
    assert instruments == ["SH", "TLT", "QQQ", "LQD", "Cash / T-Bills"]

