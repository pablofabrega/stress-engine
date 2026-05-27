from __future__ import annotations

from datetime import date
from io import StringIO

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings


class FredClient:
    """Lightweight FRED CSV client for macroeconomic time series."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.fred_base_url.rstrip("/")

    @retry(wait=wait_exponential(multiplier=1, min=1, max=4), stop=stop_after_attempt(3), reraise=True)
    def fetch_series(self, series_id: str, start_date: date, end_date: date) -> pd.DataFrame:
        url = f"{self.base_url}/graph/fredgraph.csv"
        params = {"id": series_id, "cosd": start_date.isoformat(), "coed": end_date.isoformat()}

        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()

        dataframe = pd.read_csv(StringIO(response.text))
        if dataframe.empty:
            return pd.DataFrame(columns=["value"])

        dataframe.columns = [column.lower() for column in dataframe.columns]
        dataframe["date"] = pd.to_datetime(dataframe["date"])
        value_column = [column for column in dataframe.columns if column != "date"][0]
        dataframe[value_column] = pd.to_numeric(dataframe[value_column].replace(".", pd.NA), errors="coerce")
        normalized = dataframe.rename(columns={value_column: "value"}).set_index("date").sort_index()
        normalized.index.name = "date"
        return normalized

