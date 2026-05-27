from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd


@dataclass(slots=True)
class FetchResult:
    """Normalized result wrapper for cached or live market data fetches."""

    data: pd.DataFrame
    source: str
    cache_hit: bool
    stale: bool = False
    fetched_at: datetime | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CachedDataset:
    """Represents a dataset loaded from local parquet storage."""

    data: pd.DataFrame
    fetched_at: datetime | None = None
    stale: bool = False

