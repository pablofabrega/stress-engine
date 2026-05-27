from __future__ import annotations

from datetime import date

import pandas as pd

from app.domain.data.cache import LocalParquetCache
from app.domain.data.fetchers import HistoricalDataFetcher
from app.domain.data.providers.base import DataProvider


class FakeProvider(DataProvider):
    provider_name = "fake"

    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame
        self.calls = 0

    def fetch_daily_ohlcv(self, ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
        self.calls += 1
        return self.frame.copy()


def test_historical_fetcher_uses_cache_after_first_fetch(tmp_path) -> None:
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    frame = pd.DataFrame(
        {
            "open": [10.0, 11.0, 12.0],
            "high": [11.0, 12.0, 13.0],
            "low": [9.0, 10.0, 11.0],
            "close": [10.5, 11.5, 12.5],
            "adj_close": [10.5, 11.5, 12.5],
            "volume": [100, 110, 120],
            "dividends": [0.0, 0.0, 0.0],
            "stock_splits": [0.0, 0.0, 0.0],
        },
        index=dates,
    )
    frame.index.name = "date"

    provider = FakeProvider(frame=frame)
    cache = LocalParquetCache(root_dir=tmp_path, stale_after_hours=24)
    fetcher = HistoricalDataFetcher(provider=provider, cache=cache)

    first = fetcher.fetch("TEST", date(2024, 1, 1), date(2024, 1, 3))
    second = fetcher.fetch("TEST", date(2024, 1, 1), date(2024, 1, 3))

    assert provider.calls == 1
    assert first.cache_hit is False
    assert second.cache_hit is True
    pd.testing.assert_frame_equal(first.data, second.data)


def test_historical_fetcher_surfaces_warning_for_missing_ticker(tmp_path) -> None:
    empty_frame = pd.DataFrame(
        columns=["open", "high", "low", "close", "adj_close", "volume", "dividends", "stock_splits"]
    )
    provider = FakeProvider(frame=empty_frame)
    cache = LocalParquetCache(root_dir=tmp_path, stale_after_hours=24)
    fetcher = HistoricalDataFetcher(provider=provider, cache=cache)

    result = fetcher.fetch("MISSING", date(2024, 1, 1), date(2024, 1, 3))

    assert result.data.empty
    assert result.cache_hit is False
    assert result.warnings == ["No historical data returned for ticker MISSING."]
