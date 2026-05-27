from __future__ import annotations

from datetime import date

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from app.domain.data.constants import OHLCV_COLUMNS
from app.domain.data.exceptions import ProviderConfigurationError
from app.domain.data.providers.base import DataProvider


class PolygonDataProvider(DataProvider):
    """Daily OHLCV provider backed by Polygon aggregate bars."""

    provider_name = "polygon"

    def __init__(self, api_key: str | None, base_url: str) -> None:
        if not api_key:
            raise ProviderConfigurationError("POLYGON_API_KEY is required when DATA_PROVIDER=polygon.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    @retry(wait=wait_exponential(multiplier=1, min=1, max=4), stop=stop_after_attempt(3), reraise=True)
    def fetch_daily_ohlcv(self, ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
        url = (
            f"{self.base_url}/v2/aggs/ticker/{ticker.upper()}/range/1/day/"
            f"{start_date.isoformat()}/{end_date.isoformat()}"
        )
        params = {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": self.api_key}

        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        results = payload.get("results", [])
        if not results:
            return pd.DataFrame(columns=OHLCV_COLUMNS)

        frame = pd.DataFrame(results)
        index = pd.DatetimeIndex(pd.to_datetime(frame["t"], unit="ms", utc=True).dt.tz_localize(None).dt.normalize())
        normalized = pd.DataFrame(
            {
                "open": frame["o"],
                "high": frame["h"],
                "low": frame["l"],
                "close": frame["c"],
                "adj_close": frame["c"],
                "volume": frame["v"],
                "dividends": 0.0,
                "stock_splits": 0.0,
            },
            index=index,
        )
        normalized.index.name = "date"
        return normalized.sort_index()
