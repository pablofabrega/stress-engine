from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from app.domain.data.constants import OHLCV_COLUMNS
from app.domain.data.exceptions import ProviderConfigurationError
from app.domain.data.providers.base import DataProvider
from app.domain.data.providers.yfinance import YFinanceDataProvider


# ---------------------------------------------------------------------------
# DataProvider interface
# ---------------------------------------------------------------------------

class TestDataProviderInterface:
    def test_cannot_instantiate_abstract_class(self) -> None:
        with pytest.raises(TypeError):
            DataProvider()  # type: ignore[abstract]

    def test_concrete_subclass_must_implement_fetch(self) -> None:
        class IncompleteProvider(DataProvider):
            provider_name = "incomplete"

        with pytest.raises(TypeError):
            IncompleteProvider()  # type: ignore[abstract]

    def test_concrete_subclass_works(self) -> None:
        class GoodProvider(DataProvider):
            provider_name = "good"

            def fetch_daily_ohlcv(self, ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
                return pd.DataFrame(columns=OHLCV_COLUMNS)

        provider = GoodProvider()
        assert provider.provider_name == "good"
        result = provider.fetch_daily_ohlcv("TEST", date(2024, 1, 1), date(2024, 1, 2))
        assert list(result.columns) == OHLCV_COLUMNS


# ---------------------------------------------------------------------------
# YFinanceDataProvider
# ---------------------------------------------------------------------------

class TestYFinanceDataProvider:
    def test_provider_name(self) -> None:
        provider = YFinanceDataProvider()
        assert provider.provider_name == "yfinance"

    def test_custom_timeout(self) -> None:
        provider = YFinanceDataProvider(timeout_seconds=10)
        assert provider.timeout_seconds == 10

    def test_default_timeout(self) -> None:
        provider = YFinanceDataProvider()
        assert provider.timeout_seconds == 30


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

class TestProviderFactory:
    def test_yfinance_provider(self) -> None:
        from app.core.config import Settings
        from app.domain.data.providers.factory import build_data_provider

        settings = Settings(DATA_PROVIDER="yfinance")
        provider = build_data_provider(settings)
        assert isinstance(provider, YFinanceDataProvider)

    def test_polygon_requires_api_key(self) -> None:
        with pytest.raises(ProviderConfigurationError):
            from app.domain.data.providers.polygon import PolygonDataProvider

            PolygonDataProvider(api_key=None, base_url="https://api.polygon.io")

    def test_alpaca_requires_credentials(self) -> None:
        with pytest.raises(ProviderConfigurationError):
            from app.domain.data.providers.alpaca import AlpacaDataProvider

            AlpacaDataProvider(api_key=None, api_secret=None, base_url="https://data.alpaca.markets")

    def test_unsupported_provider_raises(self) -> None:
        from app.domain.data.providers.factory import build_data_provider
        from app.core.config import Settings

        settings = Settings(DATA_PROVIDER="unsupported_provider")
        with pytest.raises(ValueError, match="Unsupported"):
            build_data_provider(settings)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_ohlcv_columns_present(self) -> None:
        assert "open" in OHLCV_COLUMNS
        assert "close" in OHLCV_COLUMNS
        assert "volume" in OHLCV_COLUMNS
        assert "adj_close" in OHLCV_COLUMNS

    def test_fred_series_keys(self) -> None:
        from app.domain.data.constants import FRED_SERIES

        assert FRED_SERIES["10y_treasury_yield"] == "DGS10"
        assert FRED_SERIES["2y_treasury_yield"] == "DGS2"
        assert FRED_SERIES["10y_2y_spread"] == "T10Y2Y"
        assert FRED_SERIES["vix"] == "VIXCLS"
        assert FRED_SERIES["hy_credit_spread"] == "BAMLH0A0HYM2"
        assert FRED_SERIES["usd_index"] == "DTWEXBGS"
