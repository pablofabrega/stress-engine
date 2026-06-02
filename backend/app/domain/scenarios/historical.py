from __future__ import annotations

from datetime import timedelta

import pandas as pd

from app.domain.data.fetchers import HistoricalDataFetcher
from app.domain.data.returns import ReturnsCalculator
from app.domain.portfolio.models import PortfolioHolding
from app.domain.scenarios.base import ScenarioRunner
from app.domain.scenarios.models import HistoricalScenarioDefinition, HistoricalScenarioResult
from app.domain.scenarios.presets import get_historical_scenario


class HistoricalScenarioRunner(ScenarioRunner):
    """Replay historical daily returns over a fixed scenario window using real market data."""

    def __init__(
        self,
        historical_data_fetcher: HistoricalDataFetcher | None = None,
        correlation_window: int = 63,
    ) -> None:
        self.historical_data_fetcher = historical_data_fetcher or HistoricalDataFetcher()
        self.correlation_window = correlation_window

    def run(self, holdings: list[PortfolioHolding], scenario_key: str) -> HistoricalScenarioResult:
        scenario = get_historical_scenario(scenario_key)
        return self.run_scenario(holdings=holdings, scenario=scenario)

    def run_scenario(
        self,
        holdings: list[PortfolioHolding],
        scenario: HistoricalScenarioDefinition,
    ) -> HistoricalScenarioResult:
        """
        Replay a scenario window using realized daily returns.

        Current holding notionals are shocked through the historical return path with no rebalancing inside the window.
        """

        extended_start = scenario.start_date - timedelta(days=max(self.correlation_window * 3, 30))
        tickers = [holding.ticker for holding in holdings]
        price_panel, warnings = self._build_price_panel(tickers=tickers, start_date=extended_start, end_date=scenario.end_date)
        scenario_returns = self._extract_scenario_returns(price_panel=price_panel, scenario=scenario, warnings=warnings)
        effective_holdings = self._available_holdings(holdings=holdings, return_columns=scenario_returns.columns)

        base_position_values = pd.Series(
            {holding.ticker: self._base_position_value(holding) for holding in effective_holdings},
            dtype=float,
        )
        base_position_values = base_position_values[base_position_values > 0]
        if base_position_values.empty or scenario_returns.empty:
            return HistoricalScenarioResult(
                scenario=scenario,
                portfolio_path=pd.DataFrame(),
                comparison_path=pd.DataFrame(),
                contributors=pd.DataFrame(),
                sector_breakdown=pd.DataFrame(),
                asset_class_breakdown=pd.DataFrame(),
                correlation_before=pd.DataFrame(),
                correlation_during=pd.DataFrame(),
                correlation_shift=pd.DataFrame(),
                significant_correlation_shifts=pd.DataFrame(),
                warnings=warnings + ["Scenario replay could not be computed because no priced holdings overlapped the scenario window."],
            )

        effective_returns = scenario_returns[base_position_values.index]
        holding_value_path = (1.0 + effective_returns.fillna(0.0)).cumprod().mul(base_position_values, axis=1)
        initial_value = float(base_position_values.sum())
        portfolio_value = holding_value_path.sum(axis=1)
        cumulative_return = portfolio_value / initial_value - 1.0
        pnl_dollars = portfolio_value - initial_value
        drawdown = portfolio_value / portfolio_value.cummax() - 1.0

        portfolio_path = pd.DataFrame(
            {
                "portfolio_value": portfolio_value,
                "pnl_dollars": pnl_dollars,
                "cumulative_return": cumulative_return,
                "drawdown": drawdown,
            }
        )
        comparison_path = self._build_comparison_path(scenario=scenario)
        contributors = self._build_contributors(holdings=effective_holdings, holding_value_path=holding_value_path)
        sector_breakdown = self._aggregate_contributions(contributors=contributors, group_field="sector")
        asset_class_breakdown = self._aggregate_contributions(contributors=contributors, group_field="asset_class")
        correlation_before, correlation_during, correlation_shift, significant_shift = self._build_correlation_analysis(
            price_panel=price_panel,
            scenario=scenario,
            columns=list(base_position_values.index),
        )

        return HistoricalScenarioResult(
            scenario=scenario,
            portfolio_path=portfolio_path,
            comparison_path=comparison_path,
            contributors=contributors,
            sector_breakdown=sector_breakdown,
            asset_class_breakdown=asset_class_breakdown,
            correlation_before=correlation_before,
            correlation_during=correlation_during,
            correlation_shift=correlation_shift,
            significant_correlation_shifts=significant_shift,
            warnings=warnings,
        )

    def _build_price_panel(self, tickers: list[str], start_date, end_date) -> tuple[pd.DataFrame, list[str]]:
        warnings: list[str] = []
        price_columns: list[pd.Series] = []
        for ticker in tickers:
            result = self.historical_data_fetcher.fetch(ticker=ticker, start_date=start_date, end_date=end_date)
            if result.data.empty:
                warnings.extend(result.warnings)
                continue
            price_column = "adj_close" if "adj_close" in result.data.columns else "close"
            series = result.data[price_column].astype(float).rename(ticker)
            price_columns.append(series)
            warnings.extend(result.warnings)

        if not price_columns:
            return pd.DataFrame(), warnings

        price_panel = pd.concat(price_columns, axis=1).sort_index()
        price_panel.index.name = "date"
        return price_panel, warnings

    def _extract_scenario_returns(
        self,
        price_panel: pd.DataFrame,
        scenario: HistoricalScenarioDefinition,
        warnings: list[str],
    ) -> pd.DataFrame:
        if price_panel.empty:
            return pd.DataFrame()

        returns = ReturnsCalculator.simple_returns(price_panel)
        scenario_returns = returns.loc[(returns.index >= pd.Timestamp(scenario.start_date)) & (returns.index <= pd.Timestamp(scenario.end_date))]
        if scenario_returns.empty:
            warnings.append("Scenario window had no overlapping return observations for the provided holdings.")
        return scenario_returns.dropna(axis=1, how="all")

    def _available_holdings(self, holdings: list[PortfolioHolding], return_columns: pd.Index) -> list[PortfolioHolding]:
        available = [holding for holding in holdings if holding.ticker in return_columns]
        return available

    def _base_position_value(self, holding: PortfolioHolding) -> float:
        if holding.market_value > 0:
            return float(holding.market_value)
        reference_price = holding.current_price or holding.cost_basis or 1.0
        return float(holding.quantity * reference_price)

    def _build_comparison_path(self, scenario: HistoricalScenarioDefinition) -> pd.DataFrame:
        benchmark_tickers = ["SPY", "BND"]
        price_panel, warnings = self._build_price_panel(
            tickers=benchmark_tickers,
            start_date=scenario.start_date - timedelta(days=14),
            end_date=scenario.end_date,
        )
        returns = self._extract_scenario_returns(price_panel=price_panel, scenario=scenario, warnings=warnings)
        if returns.empty:
            return pd.DataFrame()

        comparison = pd.DataFrame(index=returns.index)
        if "SPY" in returns.columns:
            comparison["spy_cumulative_return"] = (1.0 + returns["SPY"].fillna(0.0)).cumprod() - 1.0

        benchmark_weights = pd.Series({"SPY": 0.60, "BND": 0.40}, dtype=float)
        available = benchmark_weights.index.intersection(returns.columns)
        if not available.empty:
            effective_weights = benchmark_weights.loc[available]
            effective_weights = effective_weights / effective_weights.sum()
            base_values = effective_weights * 1.0
            benchmark_value_path = (1.0 + returns[available].fillna(0.0)).cumprod().mul(base_values, axis=1).sum(axis=1)
            comparison["benchmark_60_40_cumulative_return"] = benchmark_value_path / float(base_values.sum()) - 1.0

        return comparison

    def _build_contributors(self, holdings: list[PortfolioHolding], holding_value_path: pd.DataFrame) -> pd.DataFrame:
        base_values = pd.Series({holding.ticker: self._base_position_value(holding) for holding in holdings}, dtype=float)
        final_values = holding_value_path.iloc[-1]
        pnl = final_values - base_values
        total_pnl = float(pnl.sum())

        rows = []
        for holding in holdings:
            ticker_pnl = float(pnl.get(holding.ticker, 0.0))
            rows.append(
                {
                    "ticker": holding.ticker,
                    "sector": holding.sector,
                    "asset_class": holding.asset_class,
                    "pnl_dollars": ticker_pnl,
                    "pnl_pct_of_portfolio": ticker_pnl / float(base_values.sum()) if float(base_values.sum()) > 0 else 0.0,
                    "contribution_pct_of_total_pnl": ticker_pnl / total_pnl if total_pnl != 0 else 0.0,
                }
            )

        contributors = pd.DataFrame(rows).sort_values("pnl_dollars")
        return contributors.reset_index(drop=True)

    @staticmethod
    def top_worst_contributors(contributors: pd.DataFrame, n: int = 5) -> pd.DataFrame:
        """
        Return the ``n`` holdings with the most negative PnL during the scenario.

        Contributors are sorted ascending by ``pnl_dollars`` so the worst losers appear first.
        """

        if contributors.empty:
            return contributors
        return contributors.sort_values("pnl_dollars").head(n).reset_index(drop=True)

    @staticmethod
    def top_best_contributors(contributors: pd.DataFrame, n: int = 5) -> pd.DataFrame:
        """
        Return the ``n`` holdings with the most positive PnL during the scenario.

        Contributors are sorted descending by ``pnl_dollars`` so the strongest gainers appear first.
        """

        if contributors.empty:
            return contributors
        return contributors.sort_values("pnl_dollars", ascending=False).head(n).reset_index(drop=True)

    def _aggregate_contributions(self, contributors: pd.DataFrame, group_field: str) -> pd.DataFrame:
        if contributors.empty:
            return pd.DataFrame()

        total_pnl = float(contributors["pnl_dollars"].sum())
        grouped = contributors.groupby(group_field, as_index=False)["pnl_dollars"].sum()
        grouped["contribution_pct_of_total_pnl"] = grouped["pnl_dollars"] / total_pnl if total_pnl != 0 else 0.0
        return grouped.sort_values("pnl_dollars").reset_index(drop=True)

    def _build_correlation_analysis(
        self,
        price_panel: pd.DataFrame,
        scenario: HistoricalScenarioDefinition,
        columns: list[str],
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        if len(columns) < 2 or price_panel.empty:
            empty = pd.DataFrame()
            return empty, empty, empty, empty

        returns = ReturnsCalculator.simple_returns(price_panel[columns]).dropna(how="all")
        before_returns = returns.loc[returns.index < pd.Timestamp(scenario.start_date)].tail(self.correlation_window)
        during_returns = returns.loc[
            (returns.index >= pd.Timestamp(scenario.start_date)) & (returns.index <= pd.Timestamp(scenario.end_date))
        ]
        if not before_returns.empty:
            assert before_returns.index.max() < pd.Timestamp(scenario.start_date), "Lookahead assertion failed for pre-scenario returns."

        correlation_before = before_returns.corr() if len(before_returns) >= 2 else pd.DataFrame()
        correlation_during = during_returns.corr() if len(during_returns) >= 2 else pd.DataFrame()
        if correlation_before.empty or correlation_during.empty:
            empty = pd.DataFrame()
            return correlation_before, correlation_during, empty, empty

        aligned_before, aligned_during = correlation_before.align(correlation_during, join="outer")
        correlation_shift = aligned_during - aligned_before
        significant_shift = correlation_shift.abs() > 0.2
        return aligned_before, aligned_during, correlation_shift, significant_shift
