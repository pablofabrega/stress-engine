from __future__ import annotations

import numpy as np
import pandas as pd

from app.domain.data.returns import ReturnsCalculator


def test_simple_returns_matches_expected_series() -> None:
    prices = pd.Series([100.0, 110.0, 121.0], index=pd.date_range("2024-01-01", periods=3, freq="D"))

    returns = ReturnsCalculator.simple_returns(prices)

    assert np.isnan(returns.iloc[0])
    assert np.isclose(returns.iloc[1], 0.1)
    assert np.isclose(returns.iloc[2], 0.1)


def test_log_returns_matches_compounded_growth() -> None:
    prices = pd.Series([100.0, 110.0], index=pd.date_range("2024-01-01", periods=2, freq="D"))

    returns = ReturnsCalculator.log_returns(prices)

    assert np.isnan(returns.iloc[0])
    assert np.isclose(returns.iloc[1], np.log(1.1))


def test_rolling_realized_vol_is_annualized() -> None:
    returns = pd.Series([0.01, -0.02, 0.03], index=pd.date_range("2024-01-01", periods=3, freq="D"))

    realized_vol = ReturnsCalculator.rolling_realized_vol(returns, window=2, periods_per_year=252)

    expected = np.std([0.01, -0.02], ddof=1) * np.sqrt(252)
    assert np.isnan(realized_vol.iloc[0])
    assert np.isclose(realized_vol.iloc[1], expected)


def test_rolling_correlation_matrix_tracks_pairwise_relationships() -> None:
    returns = pd.DataFrame(
        {
            "asset_a": [0.01, 0.02, 0.03, 0.04],
            "asset_b": [0.02, 0.04, 0.06, 0.08],
        },
        index=pd.date_range("2024-01-01", periods=4, freq="D"),
    )

    correlation = ReturnsCalculator.rolling_correlation_matrix(returns, window=3)

    latest = correlation.loc[pd.Timestamp("2024-01-04")]
    assert np.isclose(latest.loc["asset_a", "asset_b"], 1.0)
    assert np.isclose(latest.loc["asset_b", "asset_a"], 1.0)
