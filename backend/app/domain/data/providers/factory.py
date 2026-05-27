from __future__ import annotations

from app.core.config import Settings
from app.domain.data.providers.base import DataProvider


def build_data_provider(settings: Settings) -> DataProvider:
    """Build the configured market data provider."""

    provider_name = settings.data_provider.lower()
    if provider_name == "yfinance":
        from app.domain.data.providers.yfinance import YFinanceDataProvider

        return YFinanceDataProvider(timeout_seconds=settings.yfinance_timeout_seconds)
    if provider_name == "polygon":
        from app.domain.data.providers.polygon import PolygonDataProvider

        return PolygonDataProvider(api_key=settings.polygon_api_key, base_url=settings.polygon_base_url)
    if provider_name == "alpaca":
        from app.domain.data.providers.alpaca import AlpacaDataProvider

        return AlpacaDataProvider(
            api_key=settings.alpaca_api_key,
            api_secret=settings.alpaca_api_secret,
            base_url=settings.alpaca_base_url,
        )
    raise ValueError(f"Unsupported DATA_PROVIDER '{settings.data_provider}'.")
