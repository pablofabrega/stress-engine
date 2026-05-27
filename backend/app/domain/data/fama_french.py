from __future__ import annotations

from datetime import date
from io import BytesIO, StringIO
from zipfile import ZipFile

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.domain.data.cache import CacheDescriptor, LocalParquetCache


class FamaFrenchLoader:
    """Download, parse, cache, and align Fama-French daily 3-factor data."""

    DAILY_3_FACTOR_ZIP = (
        "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip"
    )

    def __init__(self, cache: LocalParquetCache | None = None) -> None:
        settings = get_settings()
        self.cache = cache or LocalParquetCache(settings.data_cache_dir, stale_after_hours=settings.data_stale_after_hours)

    def load(self, start_date: date | None = None, end_date: date | None = None, force_refresh: bool = False) -> pd.DataFrame:
        descriptor = CacheDescriptor(
            namespace="factors/fama_french",
            identifier="ff3_daily",
            start_date=date(1900, 1, 1),
            end_date=date(2100, 12, 31),
        )
        if not force_refresh:
            cached = self.cache.read(descriptor)
            if cached is not None:
                return self._slice(cached.data, start_date=start_date, end_date=end_date)

        factors = self._download_and_parse()
        self.cache.write(descriptor, factors)
        return self._slice(factors, start_date=start_date, end_date=end_date)

    @retry(wait=wait_exponential(multiplier=1, min=1, max=4), stop=stop_after_attempt(3), reraise=True)
    def _download_and_parse(self) -> pd.DataFrame:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(self.DAILY_3_FACTOR_ZIP)
            response.raise_for_status()

        with ZipFile(BytesIO(response.content)) as archive:
            file_name = archive.namelist()[0]
            raw_text = archive.read(file_name).decode("utf-8")

        factor_lines = []
        for line in raw_text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            first_cell = stripped.split(",")[0].strip()
            if first_cell.isdigit() and len(first_cell) == 8:
                factor_lines.append(stripped)

        frame = pd.read_csv(
            StringIO("\n".join(["date,Mkt-RF,SMB,HML,RF", *factor_lines])),
            parse_dates=["date"],
            date_format="%Y%m%d",
        )
        frame = frame.rename(columns={"Mkt-RF": "mkt_rf", "SMB": "smb", "HML": "hml", "RF": "rf"})
        for column in ["mkt_rf", "smb", "hml", "rf"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce") / 100.0

        normalized = frame.set_index("date").sort_index()
        normalized.index.name = "date"
        return normalized

    def _slice(self, factors: pd.DataFrame, start_date: date | None, end_date: date | None) -> pd.DataFrame:
        sliced = factors
        if start_date is not None:
            sliced = sliced.loc[sliced.index >= pd.Timestamp(start_date)]
        if end_date is not None:
            sliced = sliced.loc[sliced.index <= pd.Timestamp(end_date)]
        return sliced.copy()
