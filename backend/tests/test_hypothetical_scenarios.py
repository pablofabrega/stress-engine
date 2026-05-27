from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from app.domain.portfolio.models import FactorDecompositionResult, PortfolioHolding, PortfolioReturnHistory
from app.domain.risk.models import LiquidityAnalysisResult, LiquidityHoldingResult
from app.domain.scenarios.hypothetical import HypotheticalScenarioRunner
from app.domain.scenarios.models import HypotheticalScenarioDefinition


class FakePortfolioAnalytics:
    def factor_decomposition(self, holdings, start_date: date, end_date: date) -> FactorDecompositionResult:
        tech_weight = sum(holding.weight for holding in holdings if holding.sector == "Technology")
        return FactorDecompositionResult(
            alpha=0.0,
            alpha_t_stat=0.0,
            market_beta=1.2 + 0.1 * tech_weight,
            market_beta_t_stat=5.0,
            smb_exposure=0.1,
            smb_t_stat=1.0,
            hml_exposure=-0.2,
            hml_t_stat=-1.0,
            r_squared=0.9,
            observations=100,
            warnings=[],
        )

    def portfolio_return_history(self, holdings, start_date: date, end_date: date) -> PortfolioReturnHistory:
        index = pd.date_range("2024-01-01", periods=5, freq="D", name="date")
        component = pd.DataFrame(
            {
                "AAPL": [0.01, 0.02, -0.01, 0.015, -0.005],
                "TLT": [0.002, -0.001, 0.003, 0.001, 0.0],
            },
            index=index,
        )
        portfolio = component.mul(pd.Series({"AAPL": 0.6, "TLT": 0.4}), axis=1).sum(axis=1)
        return PortfolioReturnHistory(
            portfolio_returns=portfolio,
            component_returns=component,
            weights_used={"AAPL": 0.6, "TLT": 0.4},
            warnings=[],
        )


class FakeLiquidityAnalyzer:
    def analyze(self, holdings, stressed_losses, as_of_date: date) -> LiquidityAnalysisResult:
        rows = [
            LiquidityHoldingResult(
                ticker=ticker,
                adv_30d=1_000.0,
                position_pct_adv=0.1,
                days_to_liquidate_10pct=1.0,
                days_to_liquidate_20pct=0.5,
                days_to_liquidate_30pct=0.33,
                stressed_loss_dollars=loss,
                liquidity_haircut_dollars=0.0,
                liquidity_adjusted_loss_dollars=loss,
            )
            for ticker, loss in stressed_losses.items()
        ]
        total = float(sum(stressed_losses.values()))
        return LiquidityAnalysisResult(
            holdings=rows,
            stressed_loss_dollars=total,
            total_liquidity_haircut_dollars=0.0,
            liquidity_adjusted_loss_dollars=total,
            warnings=[],
        )


def test_equity_market_hypothetical_shock_applies_beta_scaled_loss() -> None:
    runner = HypotheticalScenarioRunner(
        portfolio_analytics=FakePortfolioAnalytics(),
        risk_analytics=None,
        liquidity_analyzer=FakeLiquidityAnalyzer(),
    )
    holdings = [
        PortfolioHolding(ticker="AAPL", quantity=1, sector="Technology", asset_class="Equity", market_value=600.0, weight=0.6),
        PortfolioHolding(ticker="TLT", quantity=1, sector="Fixed Income", asset_class="Treasury ETF", market_value=400.0, weight=0.4),
    ]
    scenario = HypotheticalScenarioDefinition(
        key="eq-down-10",
        name="Equity Market -10%",
        scenario_type="equity_market",
        parameters={"shock": -0.10},
        description="Broad market selloff.",
    )

    result = runner.run_scenario(holdings=holdings, scenario=scenario, as_of_date=date(2024, 2, 1))

    impacts = result.holding_impacts.set_index("ticker")
    assert np.isclose(impacts.loc["AAPL", "shock_return"], -0.126)
    assert np.isclose(impacts.loc["TLT", "shock_return"], 0.0)
    assert np.isclose(result.instantaneous_pnl_dollars, -75.6)
    assert np.isclose(result.instantaneous_return, -0.0756)
    assert result.feature_vector["equity_return"] == -0.10
    assert np.isclose(result.liquidity_adjusted_loss, -75.6)

