from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
import re

import pandas as pd

from app.domain.data.models import CachedDataset


@dataclass(slots=True)
class CacheDescriptor:
    namespace: str
    identifier: str
    start_date: date
    end_date: date


class LocalParquetCache:
    """Local parquet cache keyed by namespace, identifier, and date range."""

    def __init__(self, root_dir: str | Path, stale_after_hours: int = 24) -> None:
        self.root_dir = Path(root_dir)
        self.stale_after_hours = stale_after_hours
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize(self, value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip().lower())

    def _path_for(self, descriptor: CacheDescriptor) -> Path:
        safe_identifier = self._sanitize(descriptor.identifier)
        filename = f"{descriptor.start_date.isoformat()}_{descriptor.end_date.isoformat()}.parquet"
        return self.root_dir / self._sanitize(descriptor.namespace) / safe_identifier / filename

    def exists(self, descriptor: CacheDescriptor) -> bool:
        return self._path_for(descriptor).exists()

    def read(self, descriptor: CacheDescriptor) -> CachedDataset | None:
        path = self._path_for(descriptor)
        if not path.exists():
            return None

        dataframe = pd.read_parquet(path)
        if "date" in dataframe.columns:
            dataframe["date"] = pd.to_datetime(dataframe["date"], utc=False)
            dataframe = dataframe.set_index("date")
            inferred_frequency = pd.infer_freq(dataframe.index)
            if inferred_frequency is not None:
                dataframe.index.freq = inferred_frequency

        metadata = {
            "fetched_at": path.stat().st_mtime,
        }
        fetched_at = datetime.fromtimestamp(metadata["fetched_at"], tz=timezone.utc)
        return CachedDataset(data=dataframe, fetched_at=fetched_at, stale=self._is_stale(fetched_at))

    def write(self, descriptor: CacheDescriptor, dataframe: pd.DataFrame) -> Path:
        path = self._path_for(descriptor)
        path.parent.mkdir(parents=True, exist_ok=True)

        to_store = dataframe.copy()
        if to_store.index.name != "date":
            to_store.index.name = "date"
        to_store.reset_index().to_parquet(path, index=False)
        return path

    def describe(self, descriptor: CacheDescriptor) -> dict[str, str]:
        return asdict(descriptor)

    def _is_stale(self, fetched_at: datetime | None) -> bool:
        if fetched_at is None:
            return False
        age_seconds = (datetime.now(timezone.utc) - fetched_at).total_seconds()
        return age_seconds > self.stale_after_hours * 3600
