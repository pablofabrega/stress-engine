from __future__ import annotations

from datetime import date

import pandas as pd

from app.domain.data.cache import LocalParquetCache
from app.domain.data.constants import FRED_SERIES
from app.domain.data.fetchers import MacroDataFetcher


class FakeFredClient:
    """In-memory stub that returns controlled macro series data."""

    def __init__(self, data: dict[str, pd.DataFrame] | None = None) -> None:
        self._data = data or {}
        self.calls: list[str] = []

    def fetch_series(self, series_id: str, start_date: date, end_date: date) -> pd.DataFrame:
        self.calls.append(series_id)
        return self._data.get(series_id, pd.DataFrame(columns=["value"]))


def _series_frame(values: list[float], start: str = "2024-01-02") -> pd.DataFrame:
    idx = pd.bdate_range(start, periods=len(values))
    frame = pd.DataFrame({"value": values}, index=idx)
    frame.index.name = "date"
    return frame


class TestMacroDataFetcherSingleSeries:
    def test_fetch_and_cache(self, tmp_path: str) -> None:
        fred = FakeFredClient({"DGS10": _series_frame([4.5, 4.6, 4.7])})
        cache = LocalParquetCache(root_dir=tmp_path)
        fetcher = MacroDataFetcher(fred_client=fred, cache=cache)

        first = fetcher.fetch_series("DGS10", date(2024, 1, 2), date(2024, 1, 4))
        second = fetcher.fetch_series("DGS10", date(2024, 1, 2), date(2024, 1, 4))

        assert first.cache_hit is False
        assert second.cache_hit is True
        assert len(fred.calls) == 1
        pd.testing.assert_frame_equal(first.data, second.data, check_freq=False)

    def test_empty_series_returns_warning(self, tmp_path: str) -> None:
        fred = FakeFredClient()
        cache = LocalParquetCache(root_dir=tmp_path)
        fetcher = MacroDataFetcher(fred_client=fred, cache=cache)

        result = fetcher.fetch_series("UNKNOWN", date(2024, 1, 1), date(2024, 6, 1))

        assert result.data.empty
        assert len(result.warnings) == 1
        assert "UNKNOWN" in result.warnings[0]

    def test_source_is_fred(self, tmp_path: str) -> None:
        fred = FakeFredClient({"VIXCLS": _series_frame([15.0])})
        fetcher = MacroDataFetcher(fred_client=fred, cache=LocalParquetCache(root_dir=tmp_path))

        result = fetcher.fetch_series("VIXCLS", date(2024, 1, 2), date(2024, 1, 2))
        assert result.source == "fred"


class TestMacroDataFetcherBundle:
    def test_bundle_combines_all_available_series(self, tmp_path: str) -> None:
        data = {}
        for label, series_id in FRED_SERIES.items():
            data[series_id] = _series_frame([1.0, 2.0, 3.0])

        fred = FakeFredClient(data)
        cache = LocalParquetCache(root_dir=tmp_path)
        fetcher = MacroDataFetcher(fred_client=fred, cache=cache)

        bundle = fetcher.fetch_default_macro_bundle(date(2024, 1, 2), date(2024, 1, 4))

        assert not bundle.empty
        for label in FRED_SERIES:
            assert label in bundle.columns

    def test_bundle_skips_missing_series(self, tmp_path: str) -> None:
        data = {"DGS10": _series_frame([4.5, 4.6])}
        fred = FakeFredClient(data)
        cache = LocalParquetCache(root_dir=tmp_path)
        fetcher = MacroDataFetcher(fred_client=fred, cache=cache)

        bundle = fetcher.fetch_default_macro_bundle(date(2024, 1, 2), date(2024, 1, 3))

        assert not bundle.empty
        assert "10y_treasury_yield" in bundle.columns
        assert "vix" not in bundle.columns

    def test_bundle_empty_when_all_series_missing(self, tmp_path: str) -> None:
        fred = FakeFredClient()
        cache = LocalParquetCache(root_dir=tmp_path)
        fetcher = MacroDataFetcher(fred_client=fred, cache=cache)

        bundle = fetcher.fetch_default_macro_bundle(date(2024, 1, 2), date(2024, 1, 4))
        assert bundle.empty

    def test_bundle_index_is_named_date(self, tmp_path: str) -> None:
        data = {"DGS10": _series_frame([1.0, 2.0])}
        fred = FakeFredClient(data)
        fetcher = MacroDataFetcher(fred_client=fred, cache=LocalParquetCache(root_dir=tmp_path))

        bundle = fetcher.fetch_default_macro_bundle(date(2024, 1, 2), date(2024, 1, 3))
        assert bundle.index.name == "date"
