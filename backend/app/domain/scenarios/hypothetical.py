from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.domain.data.fetchers import HistoricalDataFetcher
from app.domain.portfolio.analytics import PortfolioAnalytics
from app.domain.portfolio.models import PortfolioHolding
from app.domain.risk.analytics import RiskAnalytics
from app.domain.risk.constants import EQUITY_RATE_SENSITIVITY, FIXED_INCOME_DURATIONS, VIX_POSITIVE_TICKERS
from app.domain.risk.liquidity import LiquidityRiskAnalyzer
from app.domain.scenarios.models import HypotheticalScenarioDefinition, HypotheticalScenarioResult


class HypotheticalScenarioRunner:
    """Apply instantaneous hypothetical shocks to holdings and summarize the resulting portfolio damage."""

    def __init__(
        self,
        historical_data_fetcher: HistoricalDataFetcher | None = None,
        portfolio_analytics: PortfolioAnalytics | None = None,
        risk_analytics: RiskAnalytics | None = None,
        liquidity_analyzer: LiquidityRiskAnalyzer | None = None,
    ) -> None:
        self.historical_data_fetcher = historical_data_fetcher or HistoricalDataFetcher()
        self.portfolio_analytics = portfolio_analytics or PortfolioAnalytics(historical_data_fetcher=self.historical_data_fetcher)
        self.risk_analytics = risk_analytics or RiskAnalytics(portfolio_analytics=self.portfolio_analytics)
        self.liquidity_analyzer = liquidity_analyzer or LiquidityRiskAnalyzer(historical_data_fetcher=self.historical_data_fetcher)

    def run_scenario(
        self,
        holdings: list[PortfolioHolding],
        scenario: HypotheticalScenarioDefinition,
        as_of_date: date | None = None,
        lookback_days: int = 252,
    ) -> HypotheticalScenarioResult:
        """
        Run a hypothetical shock against current holdings.

        The engine applies a deterministic instantaneous shock to each holding, computes post-shock weights,
        estimates a 30-day drawdown path from historical portfolio volatility, and applies a liquidity haircut.
        """

        as_of_date = as_of_date or date.today()
        lookback_start = as_of_date - timedelta(days=max(lookback_days, 365))
        factor_before = self.portfolio_analytics.factor_decomposition(holdings, start_date=lookback_start, end_date=as_of_date)
        portfolio_beta = factor_before.market_beta if np.isfinite(factor_before.market_beta) else 1.0
        historical_returns = self.portfolio_analytics.portfolio_return_history(
            holdings=holdings,
            start_date=lookback_start,
            end_date=as_of_date,
        )
        sector_correlations = self._sector_correlation_map(holdings=holdings, component_returns=historical_returns.component_returns)

        rows: list[dict[str, float | str]] = []
        stressed_losses: dict[str, float] = {}
        warnings = list(historical_returns.warnings) + list(factor_before.warnings)

        for holding in holdings:
            pre_value = self._base_position_value(holding)
            shock_return = self._shock_return_for_holding(
                holding=holding,
                scenario=scenario,
                portfolio_beta=portfolio_beta,
                sector_correlations=sector_correlations,
            )
            shock_return = float(np.clip(shock_return, -0.95, 1.50))
            pnl = pre_value * shock_return
            post_value = pre_value + pnl
            stressed_losses[holding.ticker] = pnl
            rows.append(
                {
                    "ticker": holding.ticker,
                    "sector": holding.sector,
                    "asset_class": holding.asset_class,
                    "pre_shock_value": pre_value,
                    "shock_return": shock_return,
                    "pnl_dollars": pnl,
                    "post_shock_value": post_value,
                }
            )

        impacts = pd.DataFrame(rows).sort_values("pnl_dollars").reset_index(drop=True)
        total_pre = float(impacts["pre_shock_value"].sum())
        total_pnl = float(impacts["pnl_dollars"].sum())
        instantaneous_return = total_pnl / total_pre if total_pre > 0 else float("nan")

        shocked_holdings = self._shock_holdings(holdings=holdings, impacts=impacts)
        factor_after = self.portfolio_analytics.factor_decomposition(
            shocked_holdings,
            start_date=lookback_start,
            end_date=as_of_date,
        )
        simulated_path = self._simulate_drawdown_path(
            portfolio_returns=historical_returns.portfolio_returns,
            initial_value=total_pre,
            instantaneous_return=instantaneous_return,
        )
        liquidity = self.liquidity_analyzer.analyze(
            holdings=holdings,
            stressed_losses=stressed_losses,
            as_of_date=as_of_date,
        )
        warnings.extend(liquidity.warnings)
        warnings.extend(factor_after.warnings)

        return HypotheticalScenarioResult(
            scenario=scenario,
            holding_impacts=impacts,
            instantaneous_pnl_dollars=total_pnl,
            instantaneous_return=instantaneous_return,
            simulated_drawdown_path=simulated_path,
            factor_exposure_before=self._factor_summary_frame(factor_before),
            factor_exposure_after=self._factor_summary_frame(factor_after),
            liquidity_adjusted_loss=liquidity.liquidity_adjusted_loss_dollars,
            liquidity_table=self._liquidity_frame(liquidity),
            feature_vector=self._feature_vector(scenario=scenario),
            warnings=warnings,
        )

    def _shock_return_for_holding(
        self,
        holding: PortfolioHolding,
        scenario: HypotheticalScenarioDefinition,
        portfolio_beta: float,
        sector_correlations: dict[str, float],
    ) -> float:
        scenario_type = scenario.scenario_type
        params = scenario.parameters
        if scenario_type == "equity_market":
            shock = float(params.get("shock", 0.0))
            return shock * portfolio_beta if self._is_equity_like(holding) else 0.0

        if scenario_type == "rates":
            bps_change = float(params.get("bps_change", 0.0))
            rate_change = bps_change / 10000.0
            if self._is_fixed_income_like(holding):
                return -self._duration_for_holding(holding) * rate_change
            if self._is_equity_like(holding):
                equity_duration = EQUITY_RATE_SENSITIVITY.get(holding.sector, EQUITY_RATE_SENSITIVITY["Unknown"])
                return -equity_duration * rate_change
            return 0.0

        if scenario_type == "tech_selloff":
            shock = float(params.get("shock", 0.0))
            if holding.sector == "Technology":
                return shock
            if self._is_equity_like(holding):
                spillover = sector_correlations.get(holding.sector, 0.30)
                return shock * max(spillover, 0.0) * 0.35
            return 0.0

        if scenario_type == "vix_spike":
            current_vix = float(params.get("current_vix", 20.0))
            target_vix = float(params.get("target_vix", current_vix))
            relative_move = (target_vix - current_vix) / current_vix if current_vix != 0 else 0.0
            if holding.ticker.upper() in VIX_POSITIVE_TICKERS:
                return 0.60 * relative_move
            if self._is_equity_like(holding):
                return -0.08 * relative_move * max(portfolio_beta, 0.5)
            return 0.0

        if scenario_type == "oil_shock":
            shock = float(params.get("shock", 0.0))
            if holding.sector == "Energy":
                return 0.80 * shock
            if self._is_fixed_income_like(holding):
                return -0.15 * shock
            if self._is_equity_like(holding):
                return -0.10 * shock
            return 0.0

        if scenario_type == "hy_credit_selloff":
            spread_change_bps = float(params.get("spread_change_bps", 0.0))
            spread_change = spread_change_bps / 10000.0
            if holding.ticker.upper() in {"HYG", "JNK"}:
                return -4.0 * spread_change
            if holding.ticker.upper() == "LQD":
                return -2.0 * spread_change
            if self._is_equity_like(holding):
                return -0.35 * spread_change * max(portfolio_beta, 0.5)
            return 0.0

        if scenario_type == "custom":
            factor = str(params.get("factor", "")).upper()
            magnitude = float(params.get("magnitude", 0.0))
            if factor == holding.ticker.upper() or factor == holding.sector.upper() or factor == holding.asset_class.upper():
                return magnitude
            if factor == "RATES":
                rate_scenario = HypotheticalScenarioDefinition(
                    key=scenario.key,
                    name=scenario.name,
                    scenario_type="rates",
                    parameters={"bps_change": magnitude * 10000.0},
                    description=scenario.description,
                )
                return self._shock_return_for_holding(holding, rate_scenario, portfolio_beta, sector_correlations)
            if factor == "EQUITY_MARKET":
                eq_scenario = HypotheticalScenarioDefinition(
                    key=scenario.key,
                    name=scenario.name,
                    scenario_type="equity_market",
                    parameters={"shock": magnitude},
                    description=scenario.description,
                )
                return self._shock_return_for_holding(holding, eq_scenario, portfolio_beta, sector_correlations)
            return 0.0

        raise ValueError(f"Unsupported hypothetical scenario type '{scenario_type}'.")

    def _shock_holdings(self, holdings: list[PortfolioHolding], impacts: pd.DataFrame) -> list[PortfolioHolding]:
        shocked = deepcopy(holdings)
        impact_map = impacts.set_index("ticker").to_dict(orient="index")
        total_post = float(impacts["post_shock_value"].sum())
        for holding in shocked:
            impact = impact_map[holding.ticker]
            holding.market_value = float(impact["post_shock_value"])
            holding.weight = holding.market_value / total_post if total_post > 0 else 0.0
        return shocked

    def _simulate_drawdown_path(
        self,
        portfolio_returns: pd.Series,
        initial_value: float,
        instantaneous_return: float,
        horizon_days: int = 30,
    ) -> pd.DataFrame:
        """Create a deterministic 30-day volatility-scaled stress path from the instantaneous shock."""

        cleaned = portfolio_returns.dropna().astype(float)
        daily_vol = float(cleaned.std(ddof=1)) if len(cleaned) >= 2 else 0.01
        scale = min(max(abs(instantaneous_return) / max(daily_vol, 1e-6), 0.5), 3.0)
        days = np.arange(0, horizon_days + 1)
        extension = daily_vol * np.sqrt(days / max(horizon_days, 1)) * scale * 0.40
        signed_extension = -extension if instantaneous_return <= 0 else extension * -0.5
        path_return = instantaneous_return + signed_extension
        path_value = initial_value * (1.0 + path_return)

        return pd.DataFrame(
            {
                "day": days,
                "projected_return": path_return,
                "projected_value": path_value,
                "projected_drawdown": path_value / np.maximum.accumulate(path_value) - 1.0,
            }
        )

    def _sector_correlation_map(self, holdings: list[PortfolioHolding], component_returns: pd.DataFrame) -> dict[str, float]:
        if component_returns.empty:
            return {}

        sector_members: dict[str, list[str]] = {}
        for holding in holdings:
            if holding.ticker in component_returns.columns:
                sector_members.setdefault(holding.sector, []).append(holding.ticker)

        sector_returns: dict[str, pd.Series] = {}
        for sector, tickers in sector_members.items():
            sector_returns[sector] = component_returns[tickers].mean(axis=1)

        if "Technology" not in sector_returns:
            return {}

        tech_series = sector_returns["Technology"]
        correlations: dict[str, float] = {}
        for sector, series in sector_returns.items():
            aligned = pd.concat([tech_series.rename("tech"), series.rename("sector")], axis=1).dropna()
            correlations[sector] = float(aligned.corr().iloc[0, 1]) if len(aligned) >= 2 else 0.0
        return correlations

    def _feature_vector(self, scenario: HypotheticalScenarioDefinition) -> dict[str, float]:
        params = scenario.parameters
        scenario_type = scenario.scenario_type
        vector = {
            "equity_return": 0.0,
            "vol_change": 0.0,
            "rate_change_10y": 0.0,
            "credit_spread_change": 0.0,
            "equity_bond_correlation_shift": 0.0,
        }
        if scenario_type == "equity_market":
            vector["equity_return"] = float(params.get("shock", 0.0))
            vector["vol_change"] = abs(vector["equity_return"]) * 25.0
        elif scenario_type == "rates":
            vector["rate_change_10y"] = float(params.get("bps_change", 0.0)) / 100.0
            vector["equity_bond_correlation_shift"] = 0.15 if vector["rate_change_10y"] > 0 else -0.10
        elif scenario_type == "tech_selloff":
            vector["equity_return"] = float(params.get("shock", 0.0)) * 0.75
            vector["vol_change"] = abs(vector["equity_return"]) * 20.0
            vector["equity_bond_correlation_shift"] = -0.05
        elif scenario_type == "vix_spike":
            current_vix = float(params.get("current_vix", 20.0))
            target_vix = float(params.get("target_vix", current_vix))
            vector["vol_change"] = target_vix - current_vix
            vector["equity_return"] = -0.01 * max(target_vix - current_vix, 0.0)
        elif scenario_type == "oil_shock":
            shock = float(params.get("shock", 0.0))
            vector["rate_change_10y"] = 0.20 * shock
            vector["equity_return"] = -0.08 * shock
        elif scenario_type == "hy_credit_selloff":
            vector["credit_spread_change"] = float(params.get("spread_change_bps", 0.0)) / 100.0
            vector["equity_return"] = -0.20 * vector["credit_spread_change"]
            vector["equity_bond_correlation_shift"] = 0.10
        elif scenario_type == "custom":
            factor = str(params.get("factor", "")).upper()
            magnitude = float(params.get("magnitude", 0.0))
            if factor in {"SPY", "EQUITY_MARKET"}:
                vector["equity_return"] = magnitude
            elif factor == "RATES":
                vector["rate_change_10y"] = magnitude
            elif factor in {"HYG", "JNK", "HY_CREDIT"}:
                vector["credit_spread_change"] = abs(magnitude)
            else:
                vector["equity_return"] = magnitude * 0.5
        return vector

    def _factor_summary_frame(self, result) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "alpha": result.alpha,
                    "market_beta": result.market_beta,
                    "smb_exposure": result.smb_exposure,
                    "hml_exposure": result.hml_exposure,
                    "r_squared": result.r_squared,
                    "observations": result.observations,
                }
            ]
        )

    def _liquidity_frame(self, result) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "ticker": item.ticker,
                    "adv_30d": item.adv_30d,
                    "position_pct_adv": item.position_pct_adv,
                    "days_to_liquidate_10pct": item.days_to_liquidate_10pct,
                    "days_to_liquidate_20pct": item.days_to_liquidate_20pct,
                    "days_to_liquidate_30pct": item.days_to_liquidate_30pct,
                    "stressed_loss_dollars": item.stressed_loss_dollars,
                    "liquidity_haircut_dollars": item.liquidity_haircut_dollars,
                    "liquidity_adjusted_loss_dollars": item.liquidity_adjusted_loss_dollars,
                }
                for item in result.holdings
            ]
        )

    def _is_equity_like(self, holding: PortfolioHolding) -> bool:
        asset = holding.asset_class.lower()
        return "equity" in asset or asset in {"etf", "inverse etf", "sector etf"}

    def _is_fixed_income_like(self, holding: PortfolioHolding) -> bool:
        asset = holding.asset_class.lower()
        return "fixed income" in asset or "treasury" in asset or "credit" in asset

    def _duration_for_holding(self, holding: PortfolioHolding) -> float:
        return FIXED_INCOME_DURATIONS.get(holding.ticker.upper(), 5.0)

    def _base_position_value(self, holding: PortfolioHolding) -> float:
        if holding.market_value > 0:
            return float(holding.market_value)
        reference_price = holding.current_price or holding.cost_basis or 1.0
        return float(holding.quantity * reference_price)
