from __future__ import annotations

from datetime import date, timedelta

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from app.domain.data.constants import OHLCV_COLUMNS
from app.domain.data.exceptions import ProviderConfigurationError
from app.domain.data.providers.base import DataProvider


class AlpacaDataProvider(DataProvider):
    """Daily OHLCV provider backed by Alpaca historical bars."""

    provider_name = "alpaca"

    def __init__(self, api_key: str | None, api_secret: str | None, base_url: str) -> None:
        if not api_key or not api_secret:
            raise ProviderConfigurationError(
                "ALPACA_API_KEY and ALPACA_API_SECRET are required when DATA_PROVIDER=alpaca."
            )
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")

    @retry(wait=wait_exponential(multiplier=1, min=1, max=4), stop=stop_after_attempt(3), reraise=True)
    def fetch_daily_ohlcv(self, ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
        url = f"{self.base_url}/v2/stocks/{ticker.upper()}/bars"
        params = {
            "timeframe": "1Day",
            "start": start_date.isoformat(),
            "end": (end_date + timedelta(days=1)).isoformat(),
            "adjustment": "all",
            "feed": "iex",
        }
        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()

        bars = payload.get("bars", [])
        if not bars:
            return pd.DataFrame(columns=OHLCV_COLUMNS)

        frame = pd.DataFrame(bars)
        index = pd.DatetimeIndex(pd.to_datetime(frame["t"], utc=True).dt.tz_localize(None).dt.normalize())
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
