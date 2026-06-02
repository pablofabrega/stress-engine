from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from app.domain.data.models import FetchResult
from app.domain.portfolio.models import FactorDecompositionResult, PortfolioHolding
from app.domain.risk.constants import DEFAULT_HEDGE_COST_BPS
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


def _risk_summary(beta: float = 1.0, cvar_95: float = 0.0, latest_rolling_vol: float = 0.18) -> RiskAnalyticsResult:
    return RiskAnalyticsResult(
        var_95=0.03,
        var_99=0.05,
        cvar_95=cvar_95,
        latest_rolling_vol=latest_rolling_vol,
        drawdown=DrawdownSummary(-0.25, None, None, None, None),
        concentration=ConcentrationMetrics(0.3, 0.8, 1.0),
        latest_correlation_matrix=pd.DataFrame(),
        rolling_correlation_matrix=pd.DataFrame(),
        factor_exposure_summary=FactorDecompositionResult(0.0, 0.0, beta, 4.0, 0.1, 1.0, -0.1, -1.0, 0.9, 100, []),
        warnings=[],
    )


def _cash(weight: float = 1.0, market_value: float = 1_000.0) -> PortfolioHolding:
    return PortfolioHolding(
        ticker="CASH", quantity=1, market_value=market_value, weight=weight, sector="Cash", asset_class="Cash"
    )


def _empty_engine() -> HedgeSuggestionEngine:
    return HedgeSuggestionEngine(historical_data_fetcher=FakeHistoricalDataFetcher({}))


def test_high_beta_triggers_inverse_equity_hedge_only() -> None:
    holdings = [PortfolioHolding(ticker="SPY", quantity=1, market_value=1_000.0, weight=1.0, sector="Broad Market", asset_class="Equity")]

    suggestions = _empty_engine().suggest(holdings=holdings, risk_summary=_risk_summary(beta=1.35))

    assert [s.instrument for s in suggestions] == ["SH"]
    sh = suggestions[0]
    assert sh.hedge_ratio == pytest.approx(0.35)  # beta - 1.00
    assert sh.severity == "high"  # beta > 1.3
    assert sh.estimated_annual_cost_bps == DEFAULT_HEDGE_COST_BPS["SH"]
    assert sh.historical_effectiveness is None  # no scenario provided


def test_beta_between_1_1_and_1_3_is_medium_severity() -> None:
    holdings = [PortfolioHolding(ticker="SPY", quantity=1, market_value=1_000.0, weight=1.0, sector="Broad Market", asset_class="Equity")]

    suggestions = _empty_engine().suggest(holdings=holdings, risk_summary=_risk_summary(beta=1.2))

    assert suggestions[0].severity == "medium"
    assert suggestions[0].hedge_ratio == pytest.approx(0.2)


def test_beta_at_threshold_does_not_trigger_equity_hedge() -> None:
    holdings = [PortfolioHolding(ticker="SPY", quantity=1, market_value=1_000.0, weight=1.0, sector="Broad Market", asset_class="Equity")]

    suggestions = _empty_engine().suggest(holdings=holdings, risk_summary=_risk_summary(beta=1.1))

    assert suggestions == []


def test_equity_hedge_effectiveness_uses_inverse_benchmark_return() -> None:
    holdings = [PortfolioHolding(ticker="SPY", quantity=1, market_value=1_000.0, weight=1.0, sector="Broad Market", asset_class="Equity")]
    scenario_result = type(
        "ScenarioResult",
        (),
        {
            "comparison_path": pd.DataFrame({"spy_cumulative_return": [-0.20]}),
            "portfolio_path": pd.DataFrame({"pnl_dollars": [-200.0]}),
            "scenario": type("ScenarioDef", (), {"start_date": date(2020, 2, 20), "end_date": date(2020, 2, 22)})(),
        },
    )()

    suggestions = _empty_engine().suggest(
        holdings=holdings, risk_summary=_risk_summary(beta=1.35), scenario_result=scenario_result
    )

    # offset = hedge_ratio(0.35) * -benchmark(-0.20) * pv(1000) = 70; / scenario_loss(200) = 0.35
    assert suggestions[0].historical_effectiveness == pytest.approx(0.35)


def test_high_duration_triggers_treasury_hedge_only() -> None:
    holdings = [PortfolioHolding(ticker="TLT", quantity=1, market_value=1_000.0, weight=1.0, sector="Fixed Income", asset_class="Treasury ETF")]

    suggestions = _empty_engine().suggest(holdings=holdings, risk_summary=_risk_summary(beta=0.2))

    assert [s.instrument for s in suggestions] == ["TLT"]
    tlt = suggestions[0]
    assert tlt.hedge_ratio == pytest.approx(1.0)  # portfolio is 100% TLT
    assert tlt.severity == "high"


def test_tech_concentration_above_40pct_triggers_qqq_only() -> None:
    holdings = [
        PortfolioHolding(ticker="AAPL", quantity=1, market_value=500.0, weight=0.5, sector="Technology", asset_class="Equity"),
        _cash(weight=0.5, market_value=500.0),
    ]

    suggestions = _empty_engine().suggest(holdings=holdings, risk_summary=_risk_summary(beta=1.0))

    assert [s.instrument for s in suggestions] == ["QQQ"]
    assert suggestions[0].hedge_ratio == pytest.approx(0.5)  # tech weight
    assert suggestions[0].severity == "high"


def test_tech_concentration_at_40pct_does_not_trigger() -> None:
    holdings = [
        PortfolioHolding(ticker="AAPL", quantity=1, market_value=400.0, weight=0.4, sector="Technology", asset_class="Equity"),
        _cash(weight=0.6, market_value=600.0),
    ]

    suggestions = _empty_engine().suggest(holdings=holdings, risk_summary=_risk_summary(beta=1.0))

    assert suggestions == []


def test_high_yield_exposure_triggers_credit_rotation_only() -> None:
    holdings = [
        PortfolioHolding(ticker="HYG", quantity=1, market_value=200.0, weight=0.2, sector="Fixed Income", asset_class="Credit ETF"),
        _cash(weight=0.8, market_value=800.0),
    ]

    suggestions = _empty_engine().suggest(holdings=holdings, risk_summary=_risk_summary(beta=0.2))

    assert [s.instrument for s in suggestions] == ["LQD"]
    assert suggestions[0].hedge_ratio == pytest.approx(0.2)  # credit weight
    assert suggestions[0].severity == "medium"


def test_elevated_cvar_triggers_cash_buffer_with_kelly_sizing() -> None:
    suggestions = _empty_engine().suggest(
        holdings=[_cash()], risk_summary=_risk_summary(beta=0.5, cvar_95=0.10, latest_rolling_vol=0.10)
    )

    assert [s.instrument for s in suggestions] == ["Cash / T-Bills"]
    # min(max(cvar/vol^2 * 1%, 5%), 25%) = min(max(0.10/0.01*0.01, 0.05), 0.25) = 0.10
    assert suggestions[0].hedge_ratio == pytest.approx(0.10)


def test_cash_buffer_is_capped_at_25pct() -> None:
    suggestions = _empty_engine().suggest(
        holdings=[_cash()], risk_summary=_risk_summary(beta=0.5, cvar_95=0.30, latest_rolling_vol=0.10)
    )

    assert suggestions[0].hedge_ratio == pytest.approx(0.25)


def test_cash_buffer_not_triggered_below_cvar_threshold() -> None:
    suggestions = _empty_engine().suggest(
        holdings=[_cash()], risk_summary=_risk_summary(beta=0.5, cvar_95=0.02, latest_rolling_vol=0.10)
    )

    assert suggestions == []


def test_no_triggers_returns_empty_list() -> None:
    suggestions = _empty_engine().suggest(holdings=[_cash()], risk_summary=_risk_summary(beta=0.9, cvar_95=0.0))

    assert suggestions == []


def test_empty_or_zero_value_portfolio_returns_no_suggestions() -> None:
    engine = _empty_engine()

    assert engine.suggest(holdings=[], risk_summary=_risk_summary(beta=1.5)) == []
    zero_value = [PortfolioHolding(ticker="CASH", quantity=0, market_value=0.0, weight=0.0, sector="Cash", asset_class="Cash")]
    assert engine.suggest(holdings=zero_value, risk_summary=_risk_summary(beta=1.5)) == []


def test_non_finite_market_beta_is_skipped() -> None:
    holdings = [PortfolioHolding(ticker="SPY", quantity=1, market_value=1_000.0, weight=1.0, sector="Broad Market", asset_class="Equity")]

    suggestions = _empty_engine().suggest(holdings=holdings, risk_summary=_risk_summary(beta=float("nan")))

    assert suggestions == []


def test_suggestions_are_capped_at_five() -> None:
    suggestions = _empty_engine().suggest(holdings=[_cash()], risk_summary=_risk_summary(beta=0.9, cvar_95=0.0))

    assert len(suggestions) <= 5


def test_suggestions_are_deterministic() -> None:
    holdings = [PortfolioHolding(ticker="SPY", quantity=1, market_value=1_000.0, weight=1.0, sector="Broad Market", asset_class="Equity")]
    engine = _empty_engine()

    first = engine.suggest(holdings=holdings, risk_summary=_risk_summary(beta=1.35))
    second = engine.suggest(holdings=holdings, risk_summary=_risk_summary(beta=1.35))

    assert [(s.instrument, s.hedge_ratio, s.severity) for s in first] == [
        (s.instrument, s.hedge_ratio, s.severity) for s in second
    ]

