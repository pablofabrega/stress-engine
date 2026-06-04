from datetime import datetime, timezone

from sqlalchemy import text

from app.core.config import get_settings
from app.domain.data.cache import LocalParquetCache
from app.schemas.health import DataSourceHealth, DatabaseStatus, HealthResponse
from app.db.session import engine


def _check_database() -> DatabaseStatus:
    connected = False
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            connected = True
    except Exception:
        connected = False

    return DatabaseStatus(connected=connected, checked_at=datetime.now(timezone.utc))


def _source_health(source_name: str, namespace: str, cache: LocalParquetCache) -> DataSourceHealth:
    """Report a data source's freshness from its parquet cache.

    "Freshness" is the most recent successful fetch we cached for that source:
    ``not_fetched`` when the cache is empty, ``stale`` when the newest dataset is
    older than the configured staleness window, otherwise ``ok``.
    """

    last_fetched = cache.latest_fetch(namespace)
    if last_fetched is None:
        return DataSourceHealth(source_name=source_name, status="not_fetched")
    status = "stale" if cache.is_stale(last_fetched) else "ok"
    return DataSourceHealth(source_name=source_name, status=status, last_fetched=last_fetched)


def build_health_response() -> HealthResponse:
    settings = get_settings()
    database = _check_database()
    status = "ok" if database.connected else "degraded"

    cache = LocalParquetCache(settings.data_cache_dir, stale_after_hours=settings.data_stale_after_hours)
    sources = [
        _source_health(settings.data_provider, f"prices/{settings.data_provider}", cache),
        _source_health("fred", "macro/fred", cache),
    ]

    return HealthResponse(
        service=settings.app_name,
        status=status,
        database=database,
        data_sources=sources,
    )

