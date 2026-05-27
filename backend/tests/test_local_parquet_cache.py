from __future__ import annotations

from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest

from app.domain.data.cache import CacheDescriptor, LocalParquetCache


def _sample_frame() -> pd.DataFrame:
    idx = pd.date_range("2024-01-02", periods=5, freq="B")
    return pd.DataFrame(
        {
            "open": np.arange(5, dtype=float),
            "close": np.arange(5, dtype=float) + 0.5,
        },
        index=idx,
    )


def _descriptor(**overrides: str | date) -> CacheDescriptor:
    defaults: dict[str, str | date] = {
        "namespace": "prices/yfinance",
        "identifier": "AAPL",
        "start_date": date(2024, 1, 2),
        "end_date": date(2024, 1, 8),
    }
    defaults.update(overrides)
    return CacheDescriptor(**defaults)  # type: ignore[arg-type]


class TestLocalParquetCacheWriteRead:
    def test_round_trip(self, tmp_path: str) -> None:
        cache = LocalParquetCache(root_dir=tmp_path)
        desc = _descriptor()
        frame = _sample_frame()
        frame.index.name = "date"

        cache.write(desc, frame)
        result = cache.read(desc)

        assert result is not None
        pd.testing.assert_frame_equal(result.data, frame, check_freq=False)

    def test_read_returns_none_on_miss(self, tmp_path: str) -> None:
        cache = LocalParquetCache(root_dir=tmp_path)
        result = cache.read(_descriptor())
        assert result is None

    def test_exists_flag(self, tmp_path: str) -> None:
        cache = LocalParquetCache(root_dir=tmp_path)
        desc = _descriptor()
        assert cache.exists(desc) is False

        cache.write(desc, _sample_frame())
        assert cache.exists(desc) is True

    def test_different_descriptors_are_isolated(self, tmp_path: str) -> None:
        cache = LocalParquetCache(root_dir=tmp_path)
        desc_a = _descriptor(identifier="AAPL")
        desc_b = _descriptor(identifier="MSFT")

        cache.write(desc_a, _sample_frame())
        assert cache.exists(desc_a)
        assert not cache.exists(desc_b)

    def test_different_date_ranges_are_isolated(self, tmp_path: str) -> None:
        cache = LocalParquetCache(root_dir=tmp_path)
        desc_a = _descriptor(start_date=date(2024, 1, 1), end_date=date(2024, 3, 1))
        desc_b = _descriptor(start_date=date(2024, 6, 1), end_date=date(2024, 9, 1))

        cache.write(desc_a, _sample_frame())
        assert cache.exists(desc_a)
        assert not cache.exists(desc_b)


class TestLocalParquetCacheStaleness:
    def test_fresh_data_is_not_stale(self, tmp_path: str) -> None:
        cache = LocalParquetCache(root_dir=tmp_path, stale_after_hours=24)
        desc = _descriptor()
        cache.write(desc, _sample_frame())

        result = cache.read(desc)
        assert result is not None
        assert result.stale is False

    def test_stale_threshold_zero_marks_as_stale(self, tmp_path: str) -> None:
        cache = LocalParquetCache(root_dir=tmp_path, stale_after_hours=0)
        desc = _descriptor()
        cache.write(desc, _sample_frame())

        result = cache.read(desc)
        assert result is not None
        assert result.stale is True


class TestLocalParquetCacheDescribe:
    def test_describe_returns_dict(self, tmp_path: str) -> None:
        cache = LocalParquetCache(root_dir=tmp_path)
        desc = _descriptor()
        info = cache.describe(desc)
        assert info["namespace"] == desc.namespace
        assert info["identifier"] == desc.identifier


class TestLocalParquetCacheSanitization:
    def test_special_characters_in_identifier(self, tmp_path: str) -> None:
        cache = LocalParquetCache(root_dir=tmp_path)
        desc = _descriptor(identifier="BRK/B")
        cache.write(desc, _sample_frame())
        assert cache.exists(desc)
        result = cache.read(desc)
        assert result is not None
        assert len(result.data) == 5
