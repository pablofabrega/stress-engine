from datetime import date

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app.domain.data.cache import CacheDescriptor, LocalParquetCache
from app.main import app
from app.services.health import _source_health


def _write_dataset(cache: LocalParquetCache, namespace: str) -> None:
    frame = pd.DataFrame({"close": np.arange(3, dtype=float)}, index=pd.date_range("2024-01-02", periods=3, freq="B"))
    frame.index.name = "date"
    cache.write(CacheDescriptor(namespace, "AAPL", date(2024, 1, 2), date(2024, 1, 5)), frame)


def test_health_endpoint_returns_shape() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "Market Scenario and Stress Testing Workbench"
    assert payload["status"] in {"ok", "degraded"}
    assert "database" in payload
    assert len(payload["data_sources"]) == 2


def test_source_health_not_fetched_for_empty_cache(tmp_path: str) -> None:
    cache = LocalParquetCache(root_dir=tmp_path)

    health = _source_health("yfinance", "prices/yfinance", cache)

    assert health.status == "not_fetched"
    assert health.last_fetched is None


def test_source_health_ok_after_fetch(tmp_path: str) -> None:
    cache = LocalParquetCache(root_dir=tmp_path, stale_after_hours=24)
    _write_dataset(cache, "prices/yfinance")

    health = _source_health("yfinance", "prices/yfinance", cache)

    assert health.status == "ok"
    assert health.last_fetched is not None


def test_source_health_marks_stale(tmp_path: str) -> None:
    cache = LocalParquetCache(root_dir=tmp_path, stale_after_hours=0)
    _write_dataset(cache, "prices/yfinance")

    health = _source_health("yfinance", "prices/yfinance", cache)

    assert health.status == "stale"
    assert health.last_fetched is not None

