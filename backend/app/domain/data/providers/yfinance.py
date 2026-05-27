from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from app.domain.data.constants import OHLCV_COLUMNS
from app.domain.data.providers.base import DataProvider


class YFinanceDataProvider(DataProvider):
    """Development-friendly OHLCV provider backed by yfinance."""

    provider_name = "yfinance"

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch_daily_ohlcv(self, ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
        history = yf.Ticker(ticker).history(
            start=start_date.isoformat(),
            end=(end_date + timedelta(days=1)).isoformat(),
            auto_adjust=False,
            actions=True,
            timeout=self.timeout_seconds,
        )
        if history.empty:
            return pd.DataFrame(columns=OHLCV_COLUMNS)

        renamed = history.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Adj Close": "adj_close",
                "Volume": "volume",
                "Dividends": "dividends",
                "Stock Splits": "stock_splits",
            }
        )
        normalized = renamed.reindex(columns=OHLCV_COLUMNS)
        normalized.index = pd.to_datetime(normalized.index).tz_localize(None).normalize()
        normalized.index.name = "date"
        return normalized.sort_index()

