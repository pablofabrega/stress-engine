from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd


class DataProvider(ABC):
    """Abstract interface for fetching normalized daily OHLCV market data."""

    provider_name: str

    @abstractmethod
    def fetch_daily_ohlcv(self, ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
        """Fetch daily OHLCV data inclusive of the provided date window."""

