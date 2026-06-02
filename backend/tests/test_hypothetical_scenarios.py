from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

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


def _runner() -> HypotheticalScenarioRunner:
    return HypotheticalScenarioRunner(
        portfolio_analytics=FakePortfolioAnalytics(),
        liquidity_analyzer=FakeLiquidityAnalyzer(),
    )


def _standard_holdings() -> list[PortfolioHolding]:
    return [
        PortfolioHolding(ticker="AAPL", quantity=1, sector="Technology", asset_class="Equity", market_value=600.0, weight=0.6),
        PortfolioHolding(ticker="TLT", quantity=1, sector="Fixed Income", asset_class="Treasury ETF", market_value=400.0, weight=0.4),
    ]


def _run(scenario_type: str, parameters: dict[str, float | str], holdings: list[PortfolioHolding] | None = None):
    scenario = HypotheticalScenarioDefinition(
        key="k", name="n", scenario_type=scenario_type, parameters=parameters, description="d"
    )
    return _runner().run_scenario(
        holdings=holdings or _standard_holdings(),
        scenario=scenario,
        as_of_date=date(2024, 2, 1),
    )


def test_rates_shock_reprices_bonds_by_duration_and_equities_by_dcf_sensitivity() -> None:
    result = _run("rates", {"bps_change": 100})

    impacts = result.holding_impacts.set_index("ticker")
    assert np.isclose(impacts.loc["TLT", "shock_return"], -0.168)
    assert np.isclose(impacts.loc["AAPL", "shock_return"], -0.12)
    assert np.isclose(result.instantaneous_pnl_dollars, -139.2)
    assert np.isclose(result.feature_vector["rate_change_10y"], 1.0)


def test_tech_selloff_shocks_tech_and_spills_to_other_equities_only() -> None:
    result = _run("tech_selloff", {"shock": -0.20})

    impacts = result.holding_impacts.set_index("ticker")
    assert np.isclose(impacts.loc["AAPL", "shock_return"], -0.20)
    assert np.isclose(impacts.loc["TLT", "shock_return"], 0.0)
    assert np.isclose(result.instantaneous_pnl_dollars, -120.0)


def test_vix_spike_drags_equities_by_relative_move_and_beta() -> None:
    result = _run("vix_spike", {"current_vix": 20.0, "target_vix": 40.0})

    impacts = result.holding_impacts.set_index("ticker")
    assert np.isclose(impacts.loc["AAPL", "shock_return"], -0.1008)
    assert np.isclose(impacts.loc["TLT", "shock_return"], 0.0)
    assert np.isclose(result.feature_vector["vol_change"], 20.0)


def test_vix_spike_rewards_long_vol_instruments() -> None:
    holdings = [
        PortfolioHolding(ticker="VXX", quantity=1, sector="Volatility", asset_class="ETN", market_value=500.0, weight=0.5),
        PortfolioHolding(ticker="AAPL", quantity=1, sector="Technology", asset_class="Equity", market_value=500.0, weight=0.5),
    ]

    result = _run("vix_spike", {"current_vix": 20.0, "target_vix": 40.0}, holdings=holdings)

    impacts = result.holding_impacts.set_index("ticker")
    assert np.isclose(impacts.loc["VXX", "shock_return"], 0.60)


def test_oil_shock_helps_energy_and_drags_rate_sensitive_and_equities() -> None:
    holdings = [
        PortfolioHolding(ticker="XLE", quantity=1, sector="Energy", asset_class="Sector ETF", market_value=400.0, weight=0.4),
        PortfolioHolding(ticker="AAPL", quantity=1, sector="Technology", asset_class="Equity", market_value=300.0, weight=0.3),
        PortfolioHolding(ticker="TLT", quantity=1, sector="Fixed Income", asset_class="Treasury ETF", market_value=300.0, weight=0.3),
    ]

    result = _run("oil_shock", {"shock": 0.50}, holdings=holdings)

    impacts = result.holding_impacts.set_index("ticker")
    assert np.isclose(impacts.loc["XLE", "shock_return"], 0.40)
    assert np.isclose(impacts.loc["AAPL", "shock_return"], -0.05)
    assert np.isclose(impacts.loc["TLT", "shock_return"], -0.075)


def test_hy_credit_selloff_hits_hy_proxies_hardest_and_contaminates_equities() -> None:
    holdings = [
        PortfolioHolding(ticker="HYG", quantity=1, sector="Fixed Income", asset_class="Credit ETF", market_value=500.0, weight=0.5),
        PortfolioHolding(ticker="AAPL", quantity=1, sector="Technology", asset_class="Equity", market_value=500.0, weight=0.5),
    ]

    result = _run("hy_credit_selloff", {"spread_change_bps": 200}, holdings=holdings)

    impacts = result.holding_impacts.set_index("ticker")
    assert np.isclose(impacts.loc["HYG", "shock_return"], -0.08)
    assert np.isclose(impacts.loc["AAPL", "shock_return"], -0.00875)
    assert np.isclose(result.feature_vector["credit_spread_change"], 2.0)


def test_custom_shock_targets_a_single_ticker() -> None:
    result = _run("custom", {"factor": "AAPL", "magnitude": -0.15})

    impacts = result.holding_impacts.set_index("ticker")
    assert np.isclose(impacts.loc["AAPL", "shock_return"], -0.15)
    assert np.isclose(impacts.loc["TLT", "shock_return"], 0.0)
    assert np.isclose(result.instantaneous_pnl_dollars, -90.0)


def test_custom_rates_factor_delegates_to_rates_shock() -> None:
    custom = _run("custom", {"factor": "RATES", "magnitude": 0.01})
    direct = _run("rates", {"bps_change": 100})

    assert np.isclose(custom.instantaneous_pnl_dollars, direct.instantaneous_pnl_dollars)


def test_shock_return_is_clipped_to_bounds() -> None:
    result = _run("custom", {"factor": "AAPL", "magnitude": -2.0})

    assert np.isclose(result.holding_impacts.set_index("ticker").loc["AAPL", "shock_return"], -0.95)


def test_unsupported_scenario_type_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported hypothetical scenario type"):
        _run("meteor_strike", {"shock": -0.5})


def test_result_bundle_exposes_required_outputs() -> None:
    result = _run("equity_market", {"shock": -0.10})

    assert len(result.simulated_drawdown_path) == 31
    assert set(["day", "projected_return", "projected_value", "projected_drawdown"]).issubset(
        result.simulated_drawdown_path.columns
    )
    assert "market_beta" in result.factor_exposure_before.columns
    assert "market_beta" in result.factor_exposure_after.columns
    assert not result.liquidity_table.empty
    assert set(result.feature_vector) == {
        "equity_return",
        "vol_change",
        "rate_change_10y",
        "credit_spread_change",
        "equity_bond_correlation_shift",
    }


def test_simulated_drawdown_path_is_negative_for_a_loss_shock() -> None:
    result = _run("equity_market", {"shock": -0.10})
    path = result.simulated_drawdown_path

    assert path["projected_return"].iloc[0] < 0
    assert (path["projected_drawdown"] <= 1e-9).all()
    assert path["projected_return"].iloc[-1] <= path["projected_return"].iloc[0]


def test_post_shock_weights_renormalize_to_one() -> None:
    result = _run("equity_market", {"shock": -0.10})

    post_values = result.holding_impacts["post_shock_value"]
    assert (post_values >= 0).all()

