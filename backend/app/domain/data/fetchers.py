from __future__ import annotations

from datetime import date

import pandas as pd
import structlog

from app.core.config import get_settings
from app.domain.data.cache import CacheDescriptor, LocalParquetCache
from app.domain.data.constants import FRED_SERIES
from app.domain.data.models import FetchResult
from app.domain.data.providers.base import DataProvider
from app.domain.data.providers.factory import build_data_provider
from app.domain.data.fred import FredClient

logger = structlog.get_logger(__name__)


class HistoricalDataFetcher:
    """Fetch daily OHLCV data with local parquet caching and warning propagation."""

    def __init__(
        self,
        provider: DataProvider | None = None,
        cache: LocalParquetCache | None = None,
    ) -> None:
        settings = get_settings()
        self.provider = provider or build_data_provider(settings)
        self.cache = cache or LocalParquetCache(settings.data_cache_dir, stale_after_hours=settings.data_stale_after_hours)

    def fetch(self, ticker: str, start_date: date, end_date: date) -> FetchResult:
        descriptor = CacheDescriptor(
            namespace=f"prices/{self.provider.provider_name}",
            identifier=ticker.upper(),
            start_date=start_date,
            end_date=end_date,
        )
        cached = self.cache.read(descriptor)
        if cached is not None:
            return FetchResult(
                data=cached.data,
                source=self.provider.provider_name,
                cache_hit=True,
                stale=cached.stale,
                fetched_at=cached.fetched_at,
                warnings=["Cached market data is stale."] if cached.stale else [],
            )

        data = self.provider.fetch_daily_ohlcv(ticker=ticker, start_date=start_date, end_date=end_date)
        if data.empty:
            warning = f"No historical data returned for ticker {ticker.upper()}."
            logger.warning("historical_data_missing", ticker=ticker.upper(), provider=self.provider.provider_name)
            return FetchResult(data=data, source=self.provider.provider_name, cache_hit=False, warnings=[warning])

        self.cache.write(descriptor, data)
        return FetchResult(data=data, source=self.provider.provider_name, cache_hit=False)


class MacroDataFetcher:
    """Fetch FRED macro series and align them into a daily dataframe."""

    def __init__(
        self,
        fred_client: FredClient | None = None,
        cache: LocalParquetCache | None = None,
    ) -> None:
        settings = get_settings()
        self.fred_client = fred_client or FredClient()
        self.cache = cache or LocalParquetCache(settings.data_cache_dir, stale_after_hours=settings.data_stale_after_hours)

    def fetch_series(self, series_id: str, start_date: date, end_date: date) -> FetchResult:
        descriptor = CacheDescriptor(
            namespace="macro/fred",
            identifier=series_id,
            start_date=start_date,
            end_date=end_date,
        )
        cached = self.cache.read(descriptor)
        if cached is not None:
            return FetchResult(
                data=cached.data,
                source="fred",
                cache_hit=True,
                stale=cached.stale,
                fetched_at=cached.fetched_at,
                warnings=["Cached macro data is stale."] if cached.stale else [],
            )

        data = self.fred_client.fetch_series(series_id=series_id, start_date=start_date, end_date=end_date)
        if data.empty:
            warning = f"No macro data returned for FRED series {series_id}."
            logger.warning("macro_data_missing", series_id=series_id)
            return FetchResult(data=data, source="fred", cache_hit=False, warnings=[warning])

        self.cache.write(descriptor, data)
        return FetchResult(data=data, source="fred", cache_hit=False)

    def fetch_default_macro_bundle(self, start_date: date, end_date: date) -> pd.DataFrame:
        bundle: list[pd.DataFrame] = []
        for label, series_id in FRED_SERIES.items():
            result = self.fetch_series(series_id=series_id, start_date=start_date, end_date=end_date)
            if result.data.empty:
                continue
            series_frame = result.data.rename(columns={"value": label})
            bundle.append(series_frame[[label]])

        if not bundle:
            return pd.DataFrame()

        combined = pd.concat(bundle, axis=1).sort_index()
        combined.index.name = "date"
        return combined

