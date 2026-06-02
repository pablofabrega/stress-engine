from __future__ import annotations

from datetime import date

import pandas as pd

from app.domain.data.returns import ReturnsCalculator
from app.domain.portfolio.analytics import PortfolioAnalytics
from app.domain.portfolio.models import FactorDecompositionResult, PortfolioHolding
from app.domain.risk.models import ConcentrationMetrics, DrawdownSummary, RiskAnalyticsResult


class RiskAnalytics:
    """Portfolio risk analytics built from portfolio returns, holdings, and factor exposures."""

    def __init__(self, portfolio_analytics: PortfolioAnalytics | None = None) -> None:
        self.portfolio_analytics = portfolio_analytics or PortfolioAnalytics()

    def historical_var(self, returns: pd.Series, confidence_level: float) -> float:
        """
        Compute historical Value at Risk from the empirical return distribution.

        Formula: VaR_c = -Q_{1-c}(R), where Q is the empirical quantile of returns and c is the confidence level.
        The returned value is a positive loss number when the left tail is negative.
        """

        cleaned = self._clean_return_series(returns)
        if cleaned.empty:
            return float("nan")
        quantile = float(cleaned.quantile(1.0 - confidence_level))
        return -quantile

    def cvar(self, returns: pd.Series, confidence_level: float) -> float:
        """
        Compute Conditional Value at Risk as the average of losses worse than VaR.

        Formula: CVaR_c = -E[R | R <= Q_{1-c}(R)].
        The returned value is a positive loss number when tail returns are negative.
        """

        cleaned = self._clean_return_series(returns)
        if cleaned.empty:
            return float("nan")
        threshold = float(cleaned.quantile(1.0 - confidence_level))
        tail = cleaned.loc[cleaned <= threshold]
        if tail.empty:
            return float("nan")
        return -float(tail.mean())

    def rolling_realized_vol(
        self,
        returns: pd.Series,
        window: int = 21,
        periods_per_year: int = 252,
    ) -> pd.Series:
        """
        Compute rolling annualized realized volatility from portfolio returns.

        Formula: sigma_t = std(R_{t-window+1:t}) * sqrt(periods_per_year).
        """

        return ReturnsCalculator.rolling_realized_vol(returns, window=window, periods_per_year=periods_per_year)

    def drawdown_summary(self, returns: pd.Series) -> DrawdownSummary:
        """
        Compute maximum drawdown and recovery timing from compounded portfolio returns.

        Wealth is formed as W_t = product(1 + R_t). Drawdown is W_t / max_{s<=t}(W_s) - 1.
        Recovery occurs on the first date after the trough where wealth exceeds the prior peak wealth.
        """

        cleaned = self._clean_return_series(returns)
        if cleaned.empty:
            return DrawdownSummary(
                max_drawdown=float("nan"),
                peak_date=None,
                trough_date=None,
                recovery_date=None,
                recovery_periods=None,
            )

        wealth = (1.0 + cleaned).cumprod()
        running_peak = wealth.cummax()
        drawdown = wealth / running_peak - 1.0

        trough_date = drawdown.idxmin()
        max_drawdown = float(drawdown.loc[trough_date])
        peak_date = wealth.loc[:trough_date].idxmax()
        peak_value = float(wealth.loc[peak_date])

        post_trough = wealth.loc[wealth.index > trough_date]
        recovered = post_trough.loc[post_trough >= peak_value]
        recovery_date = recovered.index[0] if not recovered.empty else None
        recovery_periods = (
            int(cleaned.index.get_loc(recovery_date) - cleaned.index.get_loc(trough_date))
            if recovery_date is not None
            else None
        )

        return DrawdownSummary(
            max_drawdown=max_drawdown,
            peak_date=pd.Timestamp(peak_date),
            trough_date=pd.Timestamp(trough_date),
            recovery_date=pd.Timestamp(recovery_date) if recovery_date is not None else None,
            recovery_periods=recovery_periods,
        )

    def concentration_metrics(self, holdings: list[PortfolioHolding]) -> ConcentrationMetrics:
        """
        Compute weight concentration metrics from normalized holdings.

        HHI is defined as sum_i w_i^2. Top-3 and top-5 weights are the sums of the largest position weights.
        """

        weights = pd.Series([holding.weight for holding in holdings], dtype=float)
        if weights.empty:
            return ConcentrationMetrics(hhi=float("nan"), top_3_weight=float("nan"), top_5_weight=float("nan"))

        sorted_weights = weights.sort_values(ascending=False)
        return ConcentrationMetrics(
            hhi=float((weights**2).sum()),
            top_3_weight=float(sorted_weights.head(3).sum()),
            top_5_weight=float(sorted_weights.head(5).sum()),
        )

    def latest_rolling_correlation_matrix(
        self,
        component_returns: pd.DataFrame,
        window: int = 63,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Compute the full rolling holding correlation surface and extract the latest matrix.

        The rolling output uses pandas pairwise rolling correlations. The latest matrix corresponds to the last
        date with enough observations to form a full correlation estimate.
        """

        if component_returns.empty:
            empty = pd.DataFrame()
            return empty, empty

        cleaned = component_returns.dropna(how="all")
        rolling = ReturnsCalculator.rolling_correlation_matrix(cleaned, window=window)
        if rolling.empty:
            empty = pd.DataFrame()
            return empty, rolling

        valid_dates = rolling.index.get_level_values(0).unique()
        latest_date = valid_dates[-1]
        latest = rolling.loc[latest_date]
        return latest, rolling

    def analyze_portfolio(
        self,
        holdings: list[PortfolioHolding],
        start_date: date,
        end_date: date,
        vol_window: int = 21,
        correlation_window: int = 63,
    ) -> RiskAnalyticsResult:
        """
        Compute a full risk summary for a portfolio over a historical lookback window.

        This method combines historical tail risk, realized volatility, drawdown, concentration, rolling
        correlation, and Fama-French factor exposure estimates into one deterministic result bundle.
        """

        return_history = self.portfolio_analytics.portfolio_return_history(
            holdings=holdings,
            start_date=start_date,
            end_date=end_date,
        )
        factor_summary = self.portfolio_analytics.factor_decomposition(
            holdings=holdings,
            start_date=start_date,
            end_date=end_date,
        )
        rolling_vol = self.rolling_realized_vol(return_history.portfolio_returns, window=vol_window)
        latest_correlation, rolling_correlation = self.latest_rolling_correlation_matrix(
            return_history.component_returns,
            window=correlation_window,
        )

        warnings = list(return_history.warnings)
        warnings.extend(factor_summary.warnings)

        return RiskAnalyticsResult(
            var_95=self.historical_var(return_history.portfolio_returns, confidence_level=0.95),
            var_99=self.historical_var(return_history.portfolio_returns, confidence_level=0.99),
            cvar_95=self.cvar(return_history.portfolio_returns, confidence_level=0.95),
            latest_rolling_vol=float(rolling_vol.dropna().iloc[-1]) if not rolling_vol.dropna().empty else float("nan"),
            drawdown=self.drawdown_summary(return_history.portfolio_returns),
            concentration=self.concentration_metrics(holdings),
            latest_correlation_matrix=latest_correlation,
            rolling_correlation_matrix=rolling_correlation,
            factor_exposure_summary=factor_summary,
            warnings=warnings,
        )

    def factor_exposure_summary(
        self,
        holdings: list[PortfolioHolding],
        start_date: date,
        end_date: date,
    ) -> FactorDecompositionResult:
        """Return the portfolio's Fama-French factor exposure summary for the requested window."""

        return self.portfolio_analytics.factor_decomposition(holdings=holdings, start_date=start_date, end_date=end_date)

    def _clean_return_series(self, returns: pd.Series) -> pd.Series:
        cleaned = returns.astype(float).dropna()
        cleaned.name = returns.name
        return cleaned

