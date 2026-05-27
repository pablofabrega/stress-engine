from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.domain.data.returns import ReturnsCalculator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _price_series(values: list[float], start: str = "2024-01-02") -> pd.Series:
    """Build a price Series with a DatetimeIndex."""
    idx = pd.bdate_range(start, periods=len(values))
    return pd.Series(values, index=idx, name="close", dtype=float)


def _price_dataframe(data: dict[str, list[float]], start: str = "2024-01-02") -> pd.DataFrame:
    """Build a price DataFrame with a DatetimeIndex."""
    n = len(next(iter(data.values())))
    idx = pd.bdate_range(start, periods=n)
    return pd.DataFrame(data, index=idx, dtype=float)


# ---------------------------------------------------------------------------
# simple_returns
# ---------------------------------------------------------------------------

class TestSimpleReturns:
    def test_basic_computation(self) -> None:
        prices = _price_series([100.0, 110.0, 99.0])
        result = ReturnsCalculator.simple_returns(prices)

        assert result.iloc[0] != result.iloc[0]  # NaN
        assert result.iloc[1] == pytest.approx(0.10)
        assert result.iloc[2] == pytest.approx(-0.1, abs=1e-6)

    def test_first_value_is_nan(self) -> None:
        prices = _price_series([50.0, 60.0, 70.0])
        result = ReturnsCalculator.simple_returns(prices)
        assert np.isnan(result.iloc[0])

    def test_dataframe_input(self) -> None:
        prices = _price_dataframe({"A": [100.0, 105.0], "B": [200.0, 210.0]})
        result = ReturnsCalculator.simple_returns(prices)

        assert isinstance(result, pd.DataFrame)
        assert result["A"].iloc[1] == pytest.approx(0.05)
        assert result["B"].iloc[1] == pytest.approx(0.05)

    def test_constant_prices_return_zero(self) -> None:
        prices = _price_series([100.0, 100.0, 100.0, 100.0])
        result = ReturnsCalculator.simple_returns(prices)
        np.testing.assert_array_almost_equal(result.dropna().values, [0.0, 0.0, 0.0])

    def test_preserves_index(self) -> None:
        prices = _price_series([10.0, 20.0, 30.0])
        result = ReturnsCalculator.simple_returns(prices)
        pd.testing.assert_index_equal(result.index, prices.index)


# ---------------------------------------------------------------------------
# log_returns
# ---------------------------------------------------------------------------

class TestLogReturns:
    def test_basic_computation(self) -> None:
        prices = _price_series([100.0, 110.0])
        result = ReturnsCalculator.log_returns(prices)
        expected = np.log(110.0 / 100.0)
        assert result.iloc[1] == pytest.approx(expected)

    def test_first_value_is_nan(self) -> None:
        prices = _price_series([50.0, 60.0])
        result = ReturnsCalculator.log_returns(prices)
        assert np.isnan(result.iloc[0])

    def test_log_returns_are_additive(self) -> None:
        """Log returns across two periods should sum to the total log return."""
        prices = _price_series([100.0, 120.0, 90.0])
        result = ReturnsCalculator.log_returns(prices)
        total_log_return = np.log(90.0 / 100.0)
        assert (result.iloc[1] + result.iloc[2]) == pytest.approx(total_log_return)

    def test_dataframe_input(self) -> None:
        prices = _price_dataframe({"X": [100.0, 200.0], "Y": [50.0, 75.0]})
        result = ReturnsCalculator.log_returns(prices)
        assert isinstance(result, pd.DataFrame)
        assert result["X"].iloc[1] == pytest.approx(np.log(2.0))
        assert result["Y"].iloc[1] == pytest.approx(np.log(1.5))

    def test_close_to_simple_returns_for_small_moves(self) -> None:
        """For small price moves, log and simple returns converge."""
        prices = _price_series([100.0, 100.5, 101.0, 100.8])
        simple = ReturnsCalculator.simple_returns(prices).dropna()
        log = ReturnsCalculator.log_returns(prices).dropna()
        np.testing.assert_array_almost_equal(simple.values, log.values, decimal=3)


# ---------------------------------------------------------------------------
# rolling_realized_vol
# ---------------------------------------------------------------------------

class TestRollingRealizedVol:
    def test_annualisation_factor(self) -> None:
        """Volatility is scaled by sqrt(252) by default."""
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0, 0.01, 100))
        vol = ReturnsCalculator.rolling_realized_vol(returns, window=20)

        raw_std = returns.rolling(20).std(ddof=1)
        annualized = raw_std * np.sqrt(252)
        pd.testing.assert_series_equal(vol, annualized, check_names=False)

    def test_custom_periods_per_year(self) -> None:
        np.random.seed(7)
        returns = pd.Series(np.random.normal(0, 0.02, 60))
        vol = ReturnsCalculator.rolling_realized_vol(returns, window=10, periods_per_year=52)

        raw_std = returns.rolling(10).std(ddof=1)
        expected = raw_std * np.sqrt(52)
        pd.testing.assert_series_equal(vol, expected, check_names=False)

    def test_leading_nans_equal_window_minus_one(self) -> None:
        np.random.seed(12)
        returns = pd.Series(np.random.normal(0, 0.01, 30))
        window = 10
        vol = ReturnsCalculator.rolling_realized_vol(returns, window=window)
        assert vol.iloc[:window - 1].isna().all()
        assert vol.iloc[window - 1:].notna().all()

    def test_constant_returns_give_zero_vol(self) -> None:
        returns = pd.Series([0.01] * 20)
        vol = ReturnsCalculator.rolling_realized_vol(returns, window=5)
        np.testing.assert_array_almost_equal(vol.dropna().values, 0.0)

    def test_dataframe_input(self) -> None:
        np.random.seed(0)
        returns = pd.DataFrame({"A": np.random.normal(0, 0.01, 30), "B": np.random.normal(0, 0.02, 30)})
        vol = ReturnsCalculator.rolling_realized_vol(returns, window=10)
        assert isinstance(vol, pd.DataFrame)
        assert set(vol.columns) == {"A", "B"}
        # Asset B has higher vol than A on average
        assert vol["B"].dropna().mean() > vol["A"].dropna().mean()


# ---------------------------------------------------------------------------
# rolling_correlation_matrix
# ---------------------------------------------------------------------------

class TestRollingCorrelationMatrix:
    def test_output_shape(self) -> None:
        np.random.seed(1)
        returns = _price_dataframe(
            {"A": list(np.random.normal(0, 1, 30)), "B": list(np.random.normal(0, 1, 30))}
        )
        result = ReturnsCalculator.rolling_correlation_matrix(returns, window=10)
        assert isinstance(result, pd.DataFrame)
        # Multi-index: (date, ticker) × ticker
        assert result.index.nlevels == 2

    def test_perfect_positive_correlation(self) -> None:
        vals = list(range(1, 31))
        returns = pd.DataFrame({"A": vals, "B": vals}, dtype=float)
        result = ReturnsCalculator.rolling_correlation_matrix(returns, window=5)

        last_date = result.index.get_level_values(0)[-1]
        last_block = result.loc[last_date]
        assert last_block.loc["A", "B"] == pytest.approx(1.0)

    def test_perfect_negative_correlation(self) -> None:
        vals = list(range(1, 31))
        returns = pd.DataFrame({"A": vals, "B": [-v for v in vals]}, dtype=float)
        result = ReturnsCalculator.rolling_correlation_matrix(returns, window=5)

        last_date = result.index.get_level_values(0)[-1]
        last_block = result.loc[last_date]
        assert last_block.loc["A", "B"] == pytest.approx(-1.0)

    def test_rejects_series_input(self) -> None:
        with pytest.raises(TypeError):
            ReturnsCalculator.rolling_correlation_matrix(pd.Series([1, 2, 3]), window=2)

    def test_diagonal_is_one(self) -> None:
        np.random.seed(99)
        returns = pd.DataFrame(
            {"X": np.random.normal(0, 1, 40), "Y": np.random.normal(0, 1, 40)},
            dtype=float,
        )
        result = ReturnsCalculator.rolling_correlation_matrix(returns, window=10)
        non_nan = result.dropna()
        if not non_nan.empty:
            last_date = non_nan.index.get_level_values(0)[-1]
            block = non_nan.loc[last_date]
            assert block.loc["X", "X"] == pytest.approx(1.0)
            assert block.loc["Y", "Y"] == pytest.approx(1.0)
