from __future__ import annotations

import numpy as np
import pandas as pd


class ReturnsCalculator:
    """Vectorized return and risk utility methods for price time series."""

    @staticmethod
    def simple_returns(prices: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
        """
        Compute simple returns as r_t = P_t / P_{t-1} - 1.

        The first observation is undefined because there is no prior price.
        """

        return prices.astype(float).pct_change()

    @staticmethod
    def log_returns(prices: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
        """
        Compute log returns as ln(P_t / P_{t-1}).

        Log returns are additive across time under compounding assumptions.
        """

        return np.log(prices.astype(float) / prices.astype(float).shift(1))

    @staticmethod
    def rolling_realized_vol(
        returns: pd.Series | pd.DataFrame,
        window: int,
        periods_per_year: int = 252,
    ) -> pd.Series | pd.DataFrame:
        """
        Compute annualized rolling realized volatility.

        Formula: sigma_t = std(r_{t-window+1:t}) * sqrt(periods_per_year)
        """

        return returns.astype(float).rolling(window=window).std(ddof=1) * np.sqrt(periods_per_year)

    @staticmethod
    def rolling_correlation_matrix(returns: pd.DataFrame, window: int) -> pd.DataFrame:
        """
        Compute rolling pairwise correlation matrices for a multi-asset return panel.

        The output is indexed by date and variable pair using pandas' pairwise rolling correlation format.
        """

        if not isinstance(returns, pd.DataFrame):
            raise TypeError("rolling_correlation_matrix requires a pandas DataFrame.")
        return returns.astype(float).rolling(window=window).corr(pairwise=True)

